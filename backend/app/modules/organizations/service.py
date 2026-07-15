import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.organization import Branch, Warehouse
from app.modules.subscriptions.repository import SubscriptionRepository


class OrganizationService:
    def __init__(self, db: Session):
        self.db = db

    def _enforce_branch_limit(self, organization_id: uuid.UUID) -> None:
        """No-op for orgs without a Subscription row (legacy/seeded/test
        orgs, grandfathered -- see core/deps.get_current_user) or on the
        Enterprise plan (max_branches is None = unlimited)."""
        subscription = SubscriptionRepository(self.db).get_by_org(organization_id)
        if subscription is None or subscription.plan.max_branches is None:
            return
        current_count = self.db.execute(
            select(func.count()).select_from(Branch).where(Branch.organization_id == organization_id)
        ).scalar_one()
        if current_count >= subscription.plan.max_branches:
            raise ValidationError(
                f"Plan '{subscription.plan.name}' allows at most {subscription.plan.max_branches} branches; "
                "upgrade your plan to add more"
            )

    def create_branch(
        self,
        organization_id: uuid.UUID,
        code: str,
        name: str,
        business_type: str,
        state_code: str,
        gstin: str | None,
        address: str | None,
    ) -> Branch:
        stmt = select(Branch).where(Branch.organization_id == organization_id, Branch.code == code)
        if self.db.execute(stmt).scalars().first() is not None:
            raise ConflictError(f"Branch code '{code}' already exists")
        self._enforce_branch_limit(organization_id)
        branch = Branch(
            organization_id=organization_id,
            code=code,
            name=name,
            business_type=business_type,
            state_code=state_code,
            gstin=gstin,
            address=address,
        )
        self.db.add(branch)
        self.db.flush()
        return branch

    def create_warehouse(
        self, organization_id: uuid.UUID, branch_id: uuid.UUID, code: str, name: str, is_default: bool
    ) -> Warehouse:
        branch = self.db.get(Branch, branch_id)
        if branch is None or branch.organization_id != organization_id:
            raise NotFoundError(f"Branch {branch_id} not found")
        stmt = select(Warehouse).where(Warehouse.branch_id == branch_id, Warehouse.code == code)
        if self.db.execute(stmt).scalars().first() is not None:
            raise ConflictError(f"Warehouse code '{code}' already exists for this branch")
        warehouse = Warehouse(branch_id=branch_id, code=code, name=name, is_default=is_default)
        self.db.add(warehouse)
        self.db.flush()
        return warehouse
