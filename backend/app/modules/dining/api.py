import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.dining import TableOrder
from app.models.rbac import User
from app.modules.audit.service import write_audit_log
from app.modules.catalog.repository import ProductRepository
from app.modules.dining.schemas import (
    CancelItemRequest,
    MergeOrdersRequest,
    OrderAddItemsRequest,
    OrderEstimateResponse,
    OrderItemUpdateRequest,
    OrderOpenRequest,
    OrderSettleRequest,
    ServeItemsRequest,
    SplitOrderRequest,
    TableCreateRequest,
    TableOrderResponse,
    TableResponse,
    TableUpdateRequest,
    TransferOrderRequest,
)
from app.modules.dining.service import DiningService
from app.modules.sales.schemas import SaleInvoiceResponse

router = APIRouter(prefix="/api/v1/dining", tags=["dining"])

_ERROR_STATUS = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
}


def _handle(exc: DomainError, db: Session) -> None:
    db.rollback()
    for exc_type, code in _ERROR_STATUS.items():
        if isinstance(exc, exc_type):
            raise HTTPException(code, str(exc)) from exc
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


def _serialize_order(order: TableOrder, product_names: dict[uuid.UUID, str]) -> dict:
    bilable = [i for i in order.items if i.status != "cancelled"]
    subtotal = sum(float(i.quantity) * float(i.unit_price) for i in bilable)
    discount = sum(float(i.discount_amount) for i in bilable)
    return {
        "id": order.id,
        "table_id": order.table_id,
        "table_number": order.table.table_number if order.table else "",
        "table_name": order.table.name if order.table else None,
        "customer_id": order.customer_id,
        "customer_name": order.customer.name if order.customer else None,
        "status": order.status,
        "opened_at": order.opened_at,
        "closed_at": order.closed_at,
        "kot_counter": order.kot_counter,
        "sales_invoice_id": order.sales_invoice_id,
        "note": order.note,
        "subtotal": round(subtotal, 2),
        "discount_total": round(discount, 2),
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": product_names.get(item.product_id, str(item.product_id)),
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "discount_amount": item.discount_amount,
                "line_total": item.line_total,
                "status": item.status,
                "kot_number": item.kot_number,
                "note": item.note,
            }
            for item in order.items
        ],
    }


def _serialize_orders(orders: list[TableOrder], db: Session) -> list[dict]:
    product_ids = {i.product_id for o in orders for i in o.items}
    product_names = {p.id: p.name for p in ProductRepository(db).list_by_ids(list(product_ids))}
    return [_serialize_order(o, product_names) for o in orders]


# ---------------- tables ----------------

@router.get("/tables", response_model=list[TableResponse])
def list_tables(
    branch_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_VIEW)),
):
    service = DiningService(db)
    return [
        TableResponse(
            id=t.id,
            table_number=t.table_number,
            name=t.name,
            capacity=t.capacity,
            status=t.status,
            is_active=t.is_active,
            active_order_id=active_order_id,
        )
        for t, active_order_id in service.list_tables(user.organization_id, branch_id)
    ]


@router.post("/tables", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
def create_table(
    branch_id: uuid.UUID,
    payload: TableCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_MANAGE)),
):
    service = DiningService(db)
    try:
        table = service.create_table(
            user.organization_id, branch_id, payload.table_number, payload.name, payload.capacity
        )
        write_audit_log(
            db, user.organization_id, user.id, "dining.table_create", "dining_table", table.id,
            {"table_number": payload.table_number, "capacity": payload.capacity},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return TableResponse(
        id=table.id, table_number=table.table_number, name=table.name, capacity=table.capacity,
        status=table.status, is_active=table.is_active, active_order_id=None,
    )


@router.patch("/tables/{table_id}", response_model=TableResponse)
def update_table(
    table_id: uuid.UUID,
    payload: TableUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_MANAGE)),
):
    service = DiningService(db)
    try:
        table = service.update_table(
            user.organization_id, table_id, payload.table_number, payload.name, payload.capacity, payload.status
        )
        write_audit_log(
            db, user.organization_id, user.id, "dining.table_update", "dining_table", table.id,
            payload.model_dump(exclude_unset=True) or None,
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return TableResponse(
        id=table.id, table_number=table.table_number, name=table.name, capacity=table.capacity,
        status=table.status, is_active=table.is_active,
        active_order_id=service._active_order_id(table.id),
    )


@router.post("/tables/{table_id}/deactivate", response_model=TableResponse)
def deactivate_table(
    table_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_MANAGE)),
):
    service = DiningService(db)
    try:
        table = service.deactivate_table(user.organization_id, table_id)
        write_audit_log(
            db, user.organization_id, user.id, "dining.table_deactivate", "dining_table", table.id,
            {"table_number": table.table_number},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return TableResponse(
        id=table.id, table_number=table.table_number, name=table.name, capacity=table.capacity,
        status=table.status, is_active=table.is_active, active_order_id=None,
    )


# ---------------- orders ----------------

@router.get("/orders", response_model=list[TableOrderResponse])
def list_orders(
    branch_id: uuid.UUID,
    status: str | None = Query(default=None, pattern="^(open|paid|cancelled)$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_VIEW)),
):
    orders = DiningService(db).list_orders(user.organization_id, branch_id, status)
    return _serialize_orders(orders, db)


@router.get("/orders/{order_id}", response_model=TableOrderResponse)
def get_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_VIEW)),
):
    service = DiningService(db)
    try:
        order = service.get_order_or_404(user.organization_id, order_id)
    except DomainError as exc:
        _handle(exc, db)
    return _serialize_orders([order], db)[0]


@router.post("/orders", response_model=TableOrderResponse, status_code=status.HTTP_201_CREATED)
def open_order(
    payload: OrderOpenRequest,
    branch_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_ORDER)),
):
    service = DiningService(db)
    try:
        order = service.open_order(
            user.organization_id, branch_id, payload.table_id, payload.customer_id, payload.shift_id, payload.note
        )
        write_audit_log(
            db, user.organization_id, user.id, "dining.order_open", "table_order", order.id,
            {"table_id": str(payload.table_id), "shift_id": str(payload.shift_id) if payload.shift_id else None},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return _serialize_orders([order], db)[0]


@router.post("/orders/{order_id}/items", response_model=TableOrderResponse)
def add_items(
    order_id: uuid.UUID,
    payload: OrderAddItemsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_ORDER)),
):
    service = DiningService(db)
    try:
        order = service.add_items(user.organization_id, order_id, [i.model_dump() for i in payload.items])
        write_audit_log(
            db, user.organization_id, user.id, "dining.items_added", "table_order", order.id,
            {"item_count": len(payload.items), "product_ids": [str(i.product_id) for i in payload.items]},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return _serialize_orders([order], db)[0]


@router.post("/orders/{order_id}/items/{item_id}/cancel", response_model=TableOrderResponse)
def cancel_item(
    order_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: CancelItemRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_ORDER)),
):
    """Void a single ordered line (even one already sent to the kitchen) with
    a server-side audit trail -- the sanctioned way to undo a KOT'd item."""
    service = DiningService(db)
    try:
        order = service.cancel_item(user.organization_id, order_id, item_id, payload.note)
        write_audit_log(
            db, user.organization_id, user.id, "dining.item_cancelled", "table_order_item", item_id,
            {"order_id": str(order.id), "note": payload.note},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return _serialize_orders([order], db)[0]


@router.patch("/orders/{order_id}/items/{item_id}", response_model=TableOrderResponse)
def update_item(
    order_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: OrderItemUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_ORDER)),
):
    service = DiningService(db)
    try:
        order = service.update_item(
            user.organization_id, order_id, item_id, payload.quantity, payload.discount_amount, payload.note
        )
        write_audit_log(
            db, user.organization_id, user.id, "dining.item_updated", "table_order_item", item_id,
            payload.model_dump(exclude_unset=True) or None,
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return _serialize_orders([order], db)[0]


@router.delete("/orders/{order_id}/items/{item_id}", response_model=TableOrderResponse)
def remove_item(
    order_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_ORDER)),
):
    service = DiningService(db)
    try:
        order = service.remove_item(user.organization_id, order_id, item_id)
        write_audit_log(
            db, user.organization_id, user.id, "dining.item_removed", "table_order_item", item_id,
            {"order_id": str(order.id)},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return _serialize_orders([order], db)[0]


@router.post("/orders/{order_id}/kitchen", response_model=TableOrderResponse)
def send_to_kitchen(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_ORDER)),
):
    service = DiningService(db)
    try:
        order = service.send_to_kitchen(user.organization_id, order_id)
        write_audit_log(
            db, user.organization_id, user.id, "dining.kitchen_sent", "table_order", order.id,
            {"kot_number": order.kot_counter},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return _serialize_orders([order], db)[0]


@router.post("/orders/{order_id}/ready", response_model=TableOrderResponse)
def mark_ready(
    order_id: uuid.UUID,
    payload: ServeItemsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_ORDER)),
):
    """Kitchen signals the selected dishes are plated and ready to serve."""
    service = DiningService(db)
    try:
        order = service.mark_ready(user.organization_id, order_id, payload.item_ids)
        write_audit_log(
            db, user.organization_id, user.id, "dining.items_ready", "table_order", order.id,
            {"item_ids": [str(i) for i in payload.item_ids]},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return _serialize_orders([order], db)[0]


@router.post("/orders/{order_id}/serve", response_model=TableOrderResponse)
def mark_served(
    order_id: uuid.UUID,
    payload: ServeItemsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_ORDER)),
):
    service = DiningService(db)
    try:
        order = service.mark_served(user.organization_id, order_id, payload.item_ids)
        write_audit_log(
            db, user.organization_id, user.id, "dining.items_served", "table_order", order.id,
            {"item_ids": [str(i) for i in payload.item_ids]},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return _serialize_orders([order], db)[0]


@router.post("/orders/{order_id}/cancel", response_model=TableOrderResponse)
def cancel_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_ORDER)),
):
    service = DiningService(db)
    try:
        order = service.cancel_order(user.organization_id, order_id)
        write_audit_log(
            db, user.organization_id, user.id, "dining.order_cancelled", "table_order", order.id,
            {"table_id": str(order.table_id)},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return _serialize_orders([order], db)[0]


@router.post("/orders/{order_id}/transfer", response_model=TableOrderResponse)
def transfer_order(
    order_id: uuid.UUID,
    payload: TransferOrderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_ORDER)),
):
    service = DiningService(db)
    try:
        source = service.get_order_or_404(user.organization_id, order_id)
        source_table_id = source.table_id
        order = service.transfer_order(user.organization_id, order_id, payload.target_table_id)
        write_audit_log(
            db, user.organization_id, user.id, "dining.order_transferred", "table_order", order.id,
            {"from_table_id": str(source_table_id), "to_table_id": str(payload.target_table_id)},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return _serialize_orders([order], db)[0]


@router.post("/orders/{order_id}/merge", response_model=TableOrderResponse)
def merge_orders(
    order_id: uuid.UUID,
    payload: MergeOrdersRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_ORDER)),
):
    """Join another open order into this one; the other order closes and its
    table is freed. `order_id` is the survivor."""
    service = DiningService(db)
    try:
        order = service.merge_orders(user.organization_id, payload.target_order_id, order_id)
        write_audit_log(
            db, user.organization_id, user.id, "dining.orders_merged", "table_order", order.id,
            {"into_order_id": str(order.id), "from_order_id": str(payload.target_order_id)},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return _serialize_orders([order], db)[0]


@router.post("/orders/{order_id}/split", response_model=TableOrderResponse)
def split_order(
    order_id: uuid.UUID,
    payload: SplitOrderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_ORDER)),
):
    """Move selected pending items onto a fresh order opened on another table."""
    service = DiningService(db)
    try:
        order = service.split_order(user.organization_id, order_id, payload.target_table_id, payload.item_ids)
        write_audit_log(
            db, user.organization_id, user.id, "dining.order_split", "table_order", order.id,
            {"from_order_id": str(order_id), "target_table_id": str(payload.target_table_id),
             "item_ids": [str(i) for i in payload.item_ids]},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return _serialize_orders([order], db)[0]


@router.post("/orders/{order_id}/estimate", response_model=OrderEstimateResponse)
def estimate_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_VIEW)),
):
    service = DiningService(db)
    try:
        _, estimate = service.estimate(user.organization_id, order_id)
    except DomainError as exc:
        _handle(exc, db)
    return estimate


@router.post("/orders/{order_id}/settle", response_model=SaleInvoiceResponse, status_code=status.HTTP_201_CREATED)
def settle_order(
    order_id: uuid.UUID,
    payload: OrderSettleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.DINING_SETTLE)),
):
    service = DiningService(db)
    try:
        order, invoice = service.settle_order(
            user.organization_id,
            order_id,
            payload.warehouse_id,
            payload.shift_id,
            [p.model_dump() for p in payload.payments],
            payload.is_credit_sale,
        )
        write_audit_log(
            db, user.organization_id, user.id, "dining.order_settled", "table_order", order.id,
            {"invoice_id": str(invoice.id), "grand_total": float(getattr(invoice, "grand_total", 0))},
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return invoice
