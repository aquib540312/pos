import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, Perm
from app.core.security import create_access_token, hash_password, verify_password
from app.models.organization import Branch, Organization, Warehouse
from app.models.rbac import User
from app.models.subscriptions import PasswordResetToken
from app.modules.auth.repository import UserRepository
from app.modules.notifications.tasks import send_notification_task
from app.modules.rbac.repository import PermissionRepository
from app.modules.rbac.service import RoleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.service import SubscriptionService

_RESET_TOKEN_VALID_HOURS = 1


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def login(self, email: str, password: str) -> str:
        user = self.users.get_by_email_any_org(email)
        if user is None or not user.is_active or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")
        return create_access_token(subject=str(user.id), extra_claims={"org": str(user.organization_id)})

    def signup(
        self,
        legal_name: str,
        trade_name: str,
        default_state_code: str,
        gstin: str | None,
        branch_code: str,
        branch_name: str,
        admin_full_name: str,
        admin_email: str,
        admin_password: str,
        admin_phone: str | None,
        plan_code: str,
    ) -> tuple[User, str]:
        """Self-service tenant onboarding: one call creates the Organization,
        its first Branch/Warehouse, the standard role set, the admin User,
        and a trialing Subscription -- everything app/seed.py does for the
        demo org, minus the sample catalog, plus a trial subscription which
        the demo org (seeded before this feature existed) intentionally
        doesn't get. Returns (user, access_token) so the frontend can go
        straight to the dashboard without a second login round-trip."""
        # Email uniqueness must be checked globally, not per-org: a brand
        # new org has no users yet, so the per-org check in create_user
        # would never catch a collision with an existing user in a
        # *different* org -- and login resolves email globally (see
        # UserRepository.get_by_email_any_org), so an undetected collision
        # here would make one of the two accounts unable to log in later.
        if self.users.get_by_email_any_org(admin_email) is not None:
            raise ConflictError(f"A user with email {admin_email} already exists")

        organization = Organization(
            legal_name=legal_name, trade_name=trade_name, gstin=gstin, default_state_code=default_state_code,
        )
        self.db.add(organization)
        self.db.flush()

        branch = Branch(
            organization_id=organization.id, code=branch_code, name=branch_name, business_type="grocery",
            state_code=default_state_code, gstin=gstin,
        )
        self.db.add(branch)
        self.db.flush()

        self.db.add(Warehouse(branch_id=branch.id, code="WH1", name=f"{branch_name} Warehouse", is_default=True))
        self.db.flush()

        PermissionRepository(self.db).ensure_seeded(Perm.ALL_PERMISSIONS)
        role_service = RoleService(self.db)
        admin_role_id = None
        for role_name, perm_codes in DEFAULT_ROLE_PERMISSIONS.items():
            role = role_service.create_role(organization.id, role_name, f"{role_name} role", perm_codes)
            if role_name == "admin":
                admin_role_id = role.id

        admin_user = self.create_user(
            organization_id=organization.id,
            full_name=admin_full_name,
            email=admin_email,
            password=admin_password,
            phone=admin_phone,
            role_ids=[admin_role_id],
        )

        SubscriptionService(self.db).start_trial(organization.id, plan_code)

        token = create_access_token(subject=str(admin_user.id), extra_claims={"org": str(organization.id)})
        return admin_user, token

    def create_user(
        self,
        organization_id: uuid.UUID,
        full_name: str,
        email: str,
        password: str,
        phone: str | None = None,
        role_ids: list[uuid.UUID] | None = None,
    ) -> User:
        if self.users.get_by_email(organization_id, email) is not None:
            raise ConflictError(f"A user with email {email} already exists")
        self._enforce_user_limit(organization_id)
        user = User(
            organization_id=organization_id,
            full_name=full_name,
            email=email,
            phone=phone,
            hashed_password=hash_password(password),
        )
        self.users.add(user)
        for role_id in role_ids or []:
            self.users.assign_role(user.id, role_id)
        return user

    def _enforce_user_limit(self, organization_id: uuid.UUID) -> None:
        """No-op for orgs without a Subscription row (legacy/seeded/test
        orgs, grandfathered -- see core/deps.get_current_user's identical
        reasoning) or on the Enterprise plan (max_users is None = unlimited)."""
        subscription = SubscriptionRepository(self.db).get_by_org(organization_id)
        if subscription is None or subscription.plan.max_users is None:
            return
        current_count = len(self.users.list(organization_id))
        if current_count >= subscription.plan.max_users:
            raise ValidationError(
                f"Plan '{subscription.plan.name}' allows at most {subscription.plan.max_users} users; "
                "upgrade your plan to add more"
            )

    def get_user_or_404(self, user_id: uuid.UUID) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user

    def list_users(self, organization_id: uuid.UUID) -> list[User]:
        return self.users.list(organization_id)

    def set_active(self, actor_user_id: uuid.UUID, target_user_id: uuid.UUID, is_active: bool) -> User:
        if actor_user_id == target_user_id and not is_active:
            raise ValidationError("You cannot deactivate your own account")
        user = self.get_user_or_404(target_user_id)
        user.is_active = is_active
        self.db.flush()
        return user

    def update_roles(self, user_id: uuid.UUID, role_ids: list[uuid.UUID]) -> User:
        user = self.get_user_or_404(user_id)
        self.users.replace_roles(user_id, role_ids)
        self.db.flush()
        return user

    def request_password_reset(self, email: str) -> None:
        """Always succeeds from the caller's point of view, whether or not
        the email matches an account -- the API must not let an attacker
        use this endpoint to enumerate registered emails."""
        user = self.users.get_by_email_any_org(email)
        if user is None:
            return
        token = secrets.token_urlsafe(32)
        self.db.add(
            PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=_RESET_TOKEN_VALID_HOURS),
            )
        )
        self.db.flush()
        reset_link = f"{get_settings().frontend_base_url}/reset-password?token={token}"
        try:
            # Best-effort, same as the checkout receipt SMS in sales/api.py:
            # a delivery failure (no broker, SMTP down) must never turn a
            # "check your email" response into a 500.
            send_notification_task.delay(
                "email", user.email, f"Reset your password: {reset_link} (valid for {_RESET_TOKEN_VALID_HOURS}h)"
            )
        except Exception:  # noqa: BLE001 - notification dispatch must never break the request
            pass

    def reset_password(self, token: str, new_password: str) -> None:
        stmt = select(PasswordResetToken).where(PasswordResetToken.token == token)
        reset_token = self.db.execute(stmt).scalar_one_or_none()
        if reset_token is None or reset_token.used_at is not None:
            raise ValidationError("Invalid or already-used reset token")
        expires_at = reset_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            raise ValidationError("Reset token has expired")

        user = self.get_user_or_404(reset_token.user_id)
        user.hashed_password = hash_password(new_password)
        reset_token.used_at = datetime.now(timezone.utc)
        self.db.flush()

    def change_password(self, user_id: uuid.UUID, current_password: str, new_password: str) -> None:
        """Authenticated password change -- the user must prove they know
        their current password (unlike the token-based reset flow)."""
        user = self.get_user_or_404(user_id)
        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect")
        user.hashed_password = hash_password(new_password)
        self.db.flush()
