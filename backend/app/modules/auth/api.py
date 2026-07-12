import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.audit.service import write_audit_log
from app.modules.auth.schemas import (
    TokenResponse,
    UserActiveUpdateRequest,
    UserCreateRequest,
    UserResponse,
    UserRolesUpdateRequest,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        is_active=user.is_active,
        role_ids=[ra.role_id for ra in user.role_assignments],
        role_names=[ra.role.name for ra in user.role_assignments],
    )


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenResponse:
    try:
        token = AuthService(db).login(form_data.username, form_data.password)
    except AuthenticationError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    db.commit()
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return _to_user_response(user)


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Perm.USERS_MANAGE)),
) -> list[UserResponse]:
    users = AuthService(db).list_users(current_user.organization_id)
    return [_to_user_response(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Perm.USERS_MANAGE)),
) -> UserResponse:
    try:
        user = AuthService(db).create_user(
            organization_id=current_user.organization_id,
            full_name=payload.full_name,
            email=payload.email,
            password=payload.password,
            phone=payload.phone,
            role_ids=payload.role_ids,
        )
        write_audit_log(db, current_user.organization_id, current_user.id, "user.create", "user", user.id)
        db.commit()
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _to_user_response(user)


@router.patch("/users/{user_id}/active", response_model=UserResponse)
def set_user_active(
    user_id: uuid.UUID,
    payload: UserActiveUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Perm.USERS_MANAGE)),
) -> UserResponse:
    try:
        user = AuthService(db).set_active(current_user.id, user_id, payload.is_active)
        action = "user.activate" if payload.is_active else "user.deactivate"
        write_audit_log(db, current_user.organization_id, current_user.id, action, "user", user.id)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return _to_user_response(user)


@router.patch("/users/{user_id}/roles", response_model=UserResponse)
def update_user_roles(
    user_id: uuid.UUID,
    payload: UserRolesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Perm.USERS_MANAGE)),
) -> UserResponse:
    try:
        user = AuthService(db).update_roles(user_id, payload.role_ids)
        write_audit_log(db, current_user.organization_id, current_user.id, "user.roles_update", "user", user.id)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return _to_user_response(user)
