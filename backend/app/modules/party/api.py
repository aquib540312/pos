import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import NotFoundError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.party.schemas import (
    CustomerCreateRequest,
    CustomerResponse,
    SupplierCreateRequest,
    SupplierResponse,
)
from app.modules.party.service import PartyService

router = APIRouter(prefix="/api/v1/party", tags=["party"])


@router.get("/customers", response_model=list[CustomerResponse])
def list_customers(
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PARTY_MANAGE)),
):
    return PartyService(db).customers.list(user.organization_id, search)


@router.post("/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PARTY_MANAGE)),
):
    customer = PartyService(db).create_customer(user.organization_id, **payload.model_dump())
    db.commit()
    return customer


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.PARTY_MANAGE))
):
    try:
        return PartyService(db).get_customer_or_404(customer_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/suppliers", response_model=list[SupplierResponse])
def list_suppliers(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.PARTY_MANAGE))):
    return PartyService(db).suppliers.list(user.organization_id)


@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PARTY_MANAGE)),
):
    supplier = PartyService(db).create_supplier(user.organization_id, **payload.model_dump())
    db.commit()
    return supplier
