import uuid

from pydantic import BaseModel, Field


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = None
    permission_codes: list[str] = Field(default_factory=list)


class RoleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    permission_codes: list[str]

    model_config = {"from_attributes": True}


class PermissionResponse(BaseModel):
    code: str
    description: str | None

    model_config = {"from_attributes": True}
