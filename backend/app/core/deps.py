
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.rbac import Permission, Role, RolePermission, User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# A locked-out org must still be able to log in, see its own subscription,
# pay to reactivate, and sign the very first user up -- exempting these
# prefixes from the gate below avoids a deadlock where the only way out
# of "past_due" is itself blocked by being "past_due".
_SUBSCRIPTION_GATE_EXEMPT_PREFIXES = ("/api/v1/auth", "/api/v1/subscriptions")


def get_current_user(
    request: Request, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    if not request.url.path.startswith(_SUBSCRIPTION_GATE_EXEMPT_PREFIXES):
        from app.modules.subscriptions.service import SubscriptionService

        if SubscriptionService(db).is_locked_out(user.organization_id):
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED, "Subscription inactive -- update billing to continue"
            )
    return user


def _user_permission_codes(db: Session, user: User) -> set[str]:
    """All permission codes granted to a user via any of their role
    assignments, across all branches.

    Simplification for Phase 1: permissions are not yet branch-scoped at
    the enforcement layer (a user with a role at Branch A can call
    permission-gated endpoints even when acting on Branch B's data) --
    branch-scoped enforcement should be added alongside true multi-branch
    UI switching in Phase 2.
    """
    if user.is_superuser:
        from app.core.permissions import Perm

        return set(Perm.ALL_PERMISSIONS)

    rows = db.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id)
    ).scalars()
    return set(rows)


def require_permission(permission_code: str):
    def _checker(
        db: Session = Depends(get_db), user: User = Depends(get_current_user)
    ) -> User:
        if permission_code not in _user_permission_codes(db, user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {permission_code}")
        return user

    return _checker
