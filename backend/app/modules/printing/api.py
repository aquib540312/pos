import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.catalog.service import CatalogService
from app.modules.printing.service import PrintService, invoice_to_print_payload
from app.modules.printing.tasks import print_receipt_task
from app.modules.sales.service import SalesService

router = APIRouter(prefix="/api/v1/printing", tags=["printing"])
logger = logging.getLogger("app.printing")


def _build_payload(db: Session, invoice_id: uuid.UUID) -> dict:
    invoice = SalesService(db).invoices.get(invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Invoice {invoice_id} not found")
    catalog = CatalogService(db)
    product_names = {}
    for item in invoice.items:
        if item.product_id not in product_names:
            product = catalog.products.get(item.product_id)
            product_names[item.product_id] = product.name if product else str(item.product_id)
    return invoice_to_print_payload(invoice, product_names)


@router.get("/receipt/{invoice_id}/escpos")
def preview_receipt_escpos(
    invoice_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.REPORTS_VIEW))
):
    """Returns the raw ESC/POS byte stream -- no hardware required. Useful
    for previewing the layout, or for setups that pipe raw ESC/POS bytes
    to a shared printer via the OS print spooler instead of talking to it
    over the network directly."""
    payload = _build_payload(db, invoice_id)
    raw_bytes = PrintService().render_to_bytes(payload)
    return Response(content=raw_bytes, media_type="application/octet-stream")


@router.post("/receipt/{invoice_id}/print", status_code=status.HTTP_202_ACCEPTED)
def print_receipt(
    invoice_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.SALES_CREATE))
) -> dict[str, str]:
    """Queues a print job on Celery against the configured Epson ESC/POS
    printer (POS_PRINTER_HOST/PORT). Requires POS_PRINTER_ENABLED=true and
    the Celery worker + Redis broker running (see docker-compose.yml) --
    fires-and-forgets by design so a jammed or offline printer can never
    block the till."""
    payload = _build_payload(db, invoice_id)
    try:
        print_receipt_task.delay(payload)
    except Exception:  # noqa: BLE001 - printing must never break the request
        logger.warning("Failed to queue print job for invoice %s", invoice_id, exc_info=True)
        return {"status": "queue_failed"}
    return {"status": "queued"}
