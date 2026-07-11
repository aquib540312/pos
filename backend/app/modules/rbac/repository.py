from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.rbac import Permission, Role, RolePermission


class RoleRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, organization_id: uuid.UUID) -> list[Role]:
        stmt = (
            select(Role)
            .where(Role.organization_id == organization_id)
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
        )
        return list(self.db.execute(stmt).scalars().all())

    def get(self, role_id: uuid.UUID) -> Role | None:
        return self.db.get(Role, role_id)

    def add(self, role: Role) -> Role:
        self.db.add(role)
        self.db.flush()
        return role

    def get_permissions_by_codes(self, codes: list[str]) -> list[Permission]:
        if not codes:
            return []
        stmt = select(Permission).where(Permission.code.in_(codes))
        return list(self.db.execute(stmt).scalars().all())

    def grant_permission(self, role_id: uuid.UUID, permission_id: uuid.UUID) -> None:
        self.db.add(RolePermission(role_id=role_id, permission_id=permission_id))


class PermissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> list[Permission]:
        return list(self.db.execute(select(Permission)).scalars().all())

    def ensure_seeded(self, codes: list[str]) -> None:
        existing = {p.code for p in self.list_all()}
        for code in codes:
            if code not in existing:
                self.db.add(Permission(code=code))
        self.db.flush()
