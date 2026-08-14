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
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    SignupRequest,
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


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Public -- no auth required, this is how a brand new tenant comes
    into existence. See AuthService.signup for exactly what gets created."""
    try:
        _, token = AuthService(db).signup(
            legal_name=payload.legal_name,
            trade_name=payload.trade_name,
            default_state_code=payload.default_state_code,
            gstin=payload.gstin,
            branch_code=payload.branch_code,
            branch_name=payload.branch_name,
            admin_full_name=payload.admin_full_name,
            admin_email=payload.admin_email,
            admin_password=payload.admin_password,
            admin_phone=payload.admin_phone,
            plan_code=payload.plan_code,
        )
        db.commit()
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except (NotFoundError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return TokenResponse(access_token=token)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    """Public. Always returns the same generic response regardless of
    whether the email matches an account -- see AuthService.request_password_reset."""
    AuthService(db).request_password_reset(payload.email)
    db.commit()
    return {"status": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    """Public -- the token itself, not a session, is the authorization here."""
    try:
        AuthService(db).reset_password(payload.token, payload.new_password)
        db.commit()
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return {"status": "Password updated. You can now log in."}


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return _to_user_response(user)


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    try:
        AuthService(db).change_password(user.id, payload.current_password, payload.new_password)
        write_audit_log(db, user.organization_id, user.id, "auth.change_password", "user", user.id)
        db.commit()
    except (AuthenticationError, NotFoundError) as exc:
        db.rollback()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return {"status": "Password updated."}


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
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
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
