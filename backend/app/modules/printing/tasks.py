from app.celery_app import celery_app
from app.modules.printing.service import PrintService


@celery_app.task(name="printing.print_receipt")
def print_receipt_task(invoice_payload: dict) -> bool:
    """Runs off the request thread -- real printer I/O (network/USB) is
    slow and unreliable hardware, must never add latency to checkout."""
    return PrintService().print_invoice(invoice_payload)
