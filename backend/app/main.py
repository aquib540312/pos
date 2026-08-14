import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.accounting.api import router as accounting_router
from app.modules.audit.api import router as audit_router
from app.modules.auth.api import router as auth_router
from app.modules.billing.api import router as billing_router
from app.modules.catalog.api import router as catalog_router
from app.modules.gst_filing.api import router as gst_filing_router
from app.modules.inventory.api import router as inventory_router
from app.modules.loyalty.api import router as loyalty_router
from app.modules.notifications.api import router as notifications_router
from app.modules.organizations.api import router as organizations_router
from app.modules.party.api import router as party_router
from app.modules.payments.api import router as payments_router
from app.modules.printing.api import router as printing_router
from app.modules.purchasing.api import router as purchasing_router
from app.modules.rbac.api import router as rbac_router
from app.modules.reports.api import router as reports_router
from app.modules.sales.api import router as sales_router
from app.modules.subscriptions.api import router as subscriptions_router
from app.modules.sync.api import router as sync_router

# Without this, the root logger's default level (WARNING) silently drops
# every INFO-level log in the app -- including the ones that are the only
# visible trace that a background task ran at all now that
# celery_task_always_eager makes them execute in-process instead of on a
# separately-observable worker (see notifications/adapters.py's
# LoggingAdapter, printing/service.py).
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth_router,
    rbac_router,
    organizations_router,
    catalog_router,
    inventory_router,
    party_router,
    purchasing_router,
    sales_router,
    billing_router,
    reports_router,
    loyalty_router,
    notifications_router,
    payments_router,
    printing_router,
    gst_filing_router,
    audit_router,
    sync_router,
    subscriptions_router,
    accounting_router,
):
    app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
