import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import CreditLimitExceededError, NotFoundError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.audit.service import write_audit_log
from app.modules.party.schemas import (
    CreditPaymentRequest,
    CustomerCreateRequest,
    CustomerResponse,
    CustomerUpdateRequest,
    SupplierCreateRequest,
    SupplierPaymentRequest,
    SupplierPaymentResponse,
    SupplierResponse,
    SupplierUpdateRequest,
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


@router.patch("/customers/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PARTY_MANAGE)),
):
    service = PartyService(db)
    try:
        customer = service.update_customer(user.organization_id, customer_id, payload.model_dump())
        write_audit_log(db, user.organization_id, user.id, "party.customer_update", "customer", customer.id)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return customer


@router.patch("/customers/{customer_id}/deactivate", response_model=CustomerResponse)
def deactivate_customer(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PARTY_MANAGE)),
):
    service = PartyService(db)
    try:
        customer = service.update_customer(user.organization_id, customer_id, {"is_active": False})
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return customer


@router.post("/customers/{customer_id}/collect", response_model=CustomerResponse)
def collect_credit_payment(
    customer_id: uuid.UUID,
    payload: CreditPaymentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PARTY_MANAGE)),
):
    service = PartyService(db)
    try:
        customer, applied = service.collect_credit(
            user.organization_id, customer_id, payload.amount, payload.method, payload.reference
        )
        write_audit_log(
            db, user.organization_id, user.id, "party.credit_collection", "customer", customer.id,
            {"amount": applied, "method": payload.method},
        )
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return customer


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


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
def get_supplier(
    supplier_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.PARTY_MANAGE))
):
    try:
        return PartyService(db).get_supplier_or_404(supplier_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)
def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PARTY_MANAGE)),
):
    service = PartyService(db)
    try:
        supplier = service.update_supplier(user.organization_id, supplier_id, payload.model_dump())
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return supplier


@router.patch("/suppliers/{supplier_id}/deactivate", response_model=SupplierResponse)
def deactivate_supplier(
    supplier_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PARTY_MANAGE)),
):
    service = PartyService(db)
    try:
        supplier = service.update_supplier(user.organization_id, supplier_id, {"is_active": False})
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return supplier


@router.post("/suppliers/{supplier_id}/pay", response_model=SupplierPaymentResponse)
def pay_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierPaymentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PARTY_MANAGE)),
):
    service = PartyService(db)
    try:
        supplier, payment, applied = service.pay_supplier(
            user.organization_id, supplier_id, payload.amount, payload.method, payload.reference, payload.note
        )
        write_audit_log(
            db, user.organization_id, user.id, "party.supplier_payment", "supplier", supplier.id,
            {"amount": applied, "method": payload.method},
        )
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except CreditLimitExceededError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    payment.outstanding_payable = float(supplier.payable_balance)
    return payment


@router.get("/suppliers/{supplier_id}/payments", response_model=list[SupplierPaymentResponse])
def list_supplier_payments(
    supplier_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.PARTY_MANAGE))
):
    payments = PartyService(db).supplier_payments.list(user.organization_id, supplier_id)
    for p in payments:
        p.outstanding_payable = 0.0
    return payments
