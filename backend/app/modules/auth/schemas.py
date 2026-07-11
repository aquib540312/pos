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

    model_config = {"from_attributes": True}
