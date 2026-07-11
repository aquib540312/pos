import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rbac import User, UserRole


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, organization_id: uuid.UUID, email: str) -> User | None:
        stmt = select(User).where(User.organization_id == organization_id, User.email == email)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_email_any_org(self, email: str) -> User | None:
        """Login is resolved without a pre-selected tenant: each deployment
        of this product is typically one business (one organization row
        represents "the business"), so email is looked up globally and the
        matching user's own organization_id becomes their session tenant.
        A true multi-org-per-login-page product would resolve the tenant
        first (subdomain/org picker) before this lookup."""
        stmt = select(User).where(User.email == email)
        return self.db.execute(stmt).scalar_one_or_none()

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def assign_role(self, user_id: uuid.UUID, role_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> UserRole:
        assignment = UserRole(user_id=user_id, role_id=role_id, branch_id=branch_id)
        self.db.add(assignment)
        self.db.flush()
        return assignment
