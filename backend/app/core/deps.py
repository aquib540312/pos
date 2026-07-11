
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.rbac import Permission, Role, RolePermission, User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
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
