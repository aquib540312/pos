import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.models.rbac import Role
from app.modules.rbac.repository import PermissionRepository, RoleRepository


class RoleService:
    def __init__(self, db: Session):
        self.db = db
        self.roles = RoleRepository(db)
        self.permissions = PermissionRepository(db)

    def list_roles(self, organization_id: uuid.UUID) -> list[Role]:
        return self.roles.list(organization_id)

    def create_role(
        self, organization_id: uuid.UUID, name: str, description: str | None, permission_codes: list[str]
    ) -> Role:
        existing = [r for r in self.roles.list(organization_id) if r.name == name]
        if existing:
            raise ConflictError(f"Role '{name}' already exists")
        role = Role(organization_id=organization_id, name=name, description=description)
        self.roles.add(role)
        for perm in self.roles.get_permissions_by_codes(permission_codes):
            self.roles.grant_permission(role.id, perm.id)
        self.db.flush()
        return self.roles.get(role.id)  # reload with relationships
