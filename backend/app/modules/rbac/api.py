from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import ConflictError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import Role, User
from app.modules.rbac.repository import PermissionRepository
from app.modules.rbac.schemas import PermissionResponse, RoleCreateRequest, RoleResponse
from app.modules.rbac.service import RoleService

router = APIRouter(prefix="/api/v1/rbac", tags=["rbac"])


def _to_role_response(role: Role) -> RoleResponse:
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permission_codes=[rp.permission.code for rp in role.permissions],
    )


@router.get("/permissions", response_model=list[PermissionResponse])
def list_permissions(db: Session = Depends(get_db), _: User = Depends(require_permission(Perm.ROLES_MANAGE))):
    return PermissionRepository(db).list_all()


@router.get("/roles", response_model=list[RoleResponse])
def list_roles(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.ROLES_MANAGE))):
    roles = RoleService(db).list_roles(user.organization_id)
    return [_to_role_response(r) for r in roles]


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.ROLES_MANAGE)),
):
    try:
        role = RoleService(db).create_role(
            user.organization_id, payload.name, payload.description, payload.permission_codes
        )
        db.commit()
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _to_role_response(role)
