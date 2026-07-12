import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.rbac import User
from app.modules.auth.repository import UserRepository


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def login(self, email: str, password: str) -> str:
        user = self.users.get_by_email_any_org(email)
        if user is None or not user.is_active or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")
        return create_access_token(subject=str(user.id), extra_claims={"org": str(user.organization_id)})

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
