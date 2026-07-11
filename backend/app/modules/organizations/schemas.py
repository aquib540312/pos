import uuid

from pydantic import BaseModel


class WarehouseResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    is_default: bool

    model_config = {"from_attributes": True}


class BranchResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    business_type: str
    state_code: str
    warehouses: list[WarehouseResponse]

    model_config = {"from_attributes": True}
