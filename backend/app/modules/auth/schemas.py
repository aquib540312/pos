import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = None
    password: str = Field(min_length=8)
    role_ids: list[uuid.UUID] = Field(default_factory=list)


class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    phone: str | None
    is_active: bool
    role_ids: list[uuid.UUID] = Field(default_factory=list)
    role_names: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class UserActiveUpdateRequest(BaseModel):
    is_active: bool


class UserRolesUpdateRequest(BaseModel):
    role_ids: list[uuid.UUID] = Field(default_factory=list)


class SignupRequest(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    trade_name: str = Field(min_length=1, max_length=255)
    gstin: str | None = None
    default_state_code: str = Field(min_length=2, max_length=2)
    branch_name: str = Field(min_length=1, max_length=255)
    branch_code: str = Field(default="MAIN", min_length=1, max_length=20)
    admin_full_name: str = Field(min_length=1, max_length=255)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8)
    admin_phone: str | None = None
    plan_code: str = Field(default="starter", pattern="^(starter|growth|enterprise)$")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
