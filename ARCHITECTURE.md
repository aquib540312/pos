# Architecture & Design Decisions

This document explains the *why* behind the structure of this codebase. Read it
before adding a module — new code should follow these patterns, not invent new ones.

## 1. Modular Monolith, not Microservices (yet)

We start as a **single deployable FastAPI service, internally partitioned into
modules with hard boundaries**. Each module owns its own tables, repository,
service layer, and API router; modules talk to each other only through service
interfaces (never by importing another module's repository or ORM model
directly across the boundary), except for shared reference data (org, party,
catalog) which is explicitly a shared kernel.

Why not microservices now:
- A retail POS backend for a single business (even a chain with branches) has
  low enough scale that network-hop overhead between "services" would only add
  latency and operational cost (service discovery, distributed transactions,
  saga orchestration for what is fundamentally one ACID transaction: "sell an
  item, decrement stock, post a ledger entry, record payment").
- A sale is inherently a single transaction spanning catalog, inventory,
  accounting, and payments. Splitting these into separate services on day one
  would force distributed transactions (2PC or sagas) for the most common,
  highest-throughput operation in the system. That is solved *after* we know
  real bottlenecks, not before.
- Module boundaries are enforced at the code level (import-linter style
  boundaries, one router/service/repository per module) specifically so that
  extraction to a separate service later is a mechanical, low-risk move: cut
  along the module seam, put a network call where a Python call used to be.

## 2. Clean Architecture / DDD layering

Every module follows the same four layers, dependencies point inward:

```
api/          FastAPI routers + Pydantic request/response schemas (I/O only)
service/      Application/domain logic, orchestrates repositories, enforces
              business rules (e.g. GST split logic, credit limit checks,
              stock availability, discount rule evaluation)
repository/   SQLAlchemy queries only. No business logic. Returns ORM
              entities or DTOs. Swappable (e.g. for testing, or to move a
              module to its own DB later).
models/       SQLAlchemy ORM models (persistence) - shared per bounded
              context, defined centrally in app/models for now since the
              schema is highly relational (FKs across modules).
```

`service/` never imports SQLAlchemy directly; it depends on repository
interfaces (Python Protocols) so unit tests can inject fakes instead of
hitting a database. Integration tests exercise the real repository against a
throwaway SQLite/Postgres DB.

## 3. Database: normalized, constraint-heavy, index-conscious

PostgreSQL is the system of record. Design principles:

- **3NF by default.** Denormalization (e.g. storing `line_total` on invoice
  lines instead of recomputing from qty*rate every read) is only done for
  values that are legally/audit-frozen at transaction time (an invoice must
  never recompute differently after a tax rate changes later).
- **Every money-bearing table** row for a completed transaction is
  **immutable after posting** (sales invoices, purchase invoices, journal
  entries) — corrections happen via reversing entries (credit notes, debit
  notes, returns), never UPDATE/DELETE. This is a legal requirement for GST
  audit trails, not a style preference.
- **Multi-tenancy via `organization_id` + `branch_id` on every scoped table**,
  enforced via a repository-level base filter, not left to individual query
  authors to remember.
- **Batch/serial tracking is modeled as its own entity** (`product_batches`,
  `product_serials`) with FK from stock and invoice lines, so expiry (medical,
  grocery) and serial warranty (electronics) share one mechanism instead of
  two.
- **GST fields live on `tax_rates` + `hsn_codes`**, not hardcoded — CGST/SGST
  vs IGST is a *derived* decision made at invoice-post time by comparing the
  seller branch's state code to the buyer's state code (or place of supply),
  never stored as a static "this product is CGST" flag.
- Indexes: FK columns, `(organization_id, branch_id)` composite on
  transactional tables, unique constraints on business keys (SKU/barcode per
  org, invoice number per branch+financial year, GSTIN format).

See `backend/alembic/versions/0001_initial_schema.py` for the full DDL and
`docs/erd.md` for the entity relationship narrative.

## 4. GST correctness

GST is not a flat "tax %" — it's computed per line as:
1. Resolve the applicable `tax_rate` for the product's `hsn_code` (rate can
   vary by date — `tax_rates` is versioned with `effective_from`/`effective_to`).
2. Determine **intra-state vs inter-state**: compare `branch.state_code`
   (place of supply is normally the selling branch for POS) to
   `customer.state_code` if the customer is registered/has a shipping state;
   default to intra-state for walk-in/unregistered customers.
3. Intra-state → split total rate into CGST + SGST (each rate/2).
   Inter-state → apply full rate as IGST.
4. Round per-line per GST rules (round the tax amount, not the rate), and
   store CGST/SGST/IGST amounts as separate columns on the invoice line for
   GSTR-1/3B reporting — never recompute the split for reports, only read
   the stored values, since rates change over time and reports are historical.

## 5. Offline-first (Phase 2 design note, not yet implemented)

The POS terminal is the least reliable network node in this system (retail
counters, patchy connectivity). The plan (not yet built — see ROADMAP.md):
- Each terminal keeps a local SQLite (via the Electron shell) mirroring the
  subset of catalog/customer/tax data it needs, and queues sales as an
  **append-only outbox** of domain events (`SaleCompleted`, `PaymentTaken`)
  with a client-generated UUID as idempotency key.
- Sync worker (Celery) drains the outbox against the server API; conflicts on
  stock are resolved server-side (server is the source of truth for
  quantities; overselling offline is allowed and reconciled, then flagged for
  manual review — this matches how real Indian retail counters already work
  with manual bill books during outages).
- This requires the sync protocol and conflict-resolution rules to be
  designed with you (business tolerance for oversell, whether offline sales
  need manager approval) before implementation — flagged in ROADMAP.md.

## 6. RBAC

`roles`, `permissions`, `role_permissions` (many-to-many), `user_roles`
(many-to-many, scoped per branch — a user can be a cashier at Branch A and
manager at Branch B). Permissions are coarse resource:action strings
(`sales:create`, `reports:view`, `inventory:adjust`) checked via a FastAPI
dependency (`require_permission("sales:create")`), not scattered `if role ==`
checks.

## 7. Why FastAPI + SQLAlchemy 2.0 + Alembic + Celery + Redis

- FastAPI: async-capable, Pydantic-native validation matches the strict-schema
  needs of GST-compliant documents, OpenAPI generation doubles as API docs
  for the future mobile/desktop clients.
- SQLAlchemy 2.0 (typed, `Mapped[...]`) for the ORM; Alembic for versioned,
  reviewable migrations (never `create_all` in production).
- Redis: cache for hot reference data (tax rates, product lookup by
  barcode) and Celery broker.
- Celery: async jobs that must not block a checkout request — receipt
  PDF/thermal rendering, SMS/email/WhatsApp notification dispatch, nightly
  GSTR export generation, backup jobs.

## 8. Testing strategy

- **Unit tests** (`backend/tests/unit`): pure service-layer logic against
  fake repositories — GST split calculation, discount/combo rule evaluation,
  credit-limit enforcement, loyalty point accrual. No DB, no I/O, run in
  milliseconds.
- **Integration tests** (`backend/tests/integration`): FastAPI `TestClient`
  against a real (SQLite in CI for speed / Postgres locally via
  docker-compose) database, exercising full request→DB round trips: the
  create-invoice endpoint actually decrements stock and posts ledger rows.
- CI runs both on every push (see `.github/workflows/ci.yml`).

## 9. External integrations: adapter pattern

Every third-party integration (payment gateway, SMS, thermal printing,
GST e-filing) follows the same shape, so swapping a provider or moving
from sandbox to production credentials is a config change, never a
rewrite of calling code:

```
NotificationAdapter / PaymentGatewayAdapter / GSPAdapter  (Protocol)
        ├── LoggingAdapter / MockGSPAdapter                (safe default)
        └── MSG91Adapter / RazorpayAdapter / HttpGSPAdapter (real, config-driven)
```

A factory function (`_resolve_adapter`, `get_gsp_adapter`, or the
service constructor's `adapter or RealAdapter(settings)` default)
picks the real implementation only when its credentials are actually
configured; every module also accepts an injected adapter so tests
exercise the calling code against a fake without any network access.
Concretely, in this codebase:

- **Payments (Razorpay UPI QR)** — `app/modules/payments/adapters.py`.
  `RazorpayAdapter` implements the real, documented QR Code API
  (create/close a dynamic UPI QR, HMAC-SHA256 webhook signature
  verification via the official SDK). A `PaymentGatewayTransaction` row
  tracks a QR from creation through the `qr_code.credited`/
  `payment.captured` webhook that marks it paid — deliberately separate
  from `SalesInvoice`/`Payment`, since in a physical POS the money
  arrives *before* the cashier finalizes the sale record; once paid, its
  gateway reference is passed as an ordinary `reference` on the normal
  `POST /sales` call, so the core checkout flow needed zero changes to
  support it. Swap `POS_RAZORPAY_KEY_ID/SECRET/WEBHOOK_SECRET` for live
  values from the Razorpay dashboard; nothing else changes.
- **SMS (MSG91)** — `app/modules/notifications/adapters.py`.
  `MSG91Adapter` implements the real Flow API (template-based, since
  Indian transactional SMS is DLT-regulated and can't send free text).
  Falls back to `LoggingAdapter` until `POS_MSG91_AUTH_KEY` and
  `POS_MSG91_FLOW_ID` are set. Wired to a real trigger: a receipt SMS
  fires (via Celery, best-effort, never blocking checkout) after every
  completed sale with a customer phone on file.
- **Thermal printing (Epson ESC/POS)** — `app/modules/printing/`.
  `receipt_builder.py` is a pure function writing real ESC/POS commands
  (via `python-escpos`) onto any printer-shaped object — `Dummy()` for
  tests/preview (captures bytes, no hardware), `Network(host, port)` for
  a real Epson TM-series or any ESC/POS-compatible network printer
  (raw TCP port 9100 by convention). Set `POS_PRINTER_HOST`/`_PORT` and
  `POS_PRINTER_ENABLED=true`; printing is always dispatched through
  Celery and every failure is caught and logged, never raised, since a
  jammed or offline printer must not be able to block a sale.
- **GST e-filing (GSP)** — `app/modules/gst_filing/`.
  `schema_builder.py` renders our existing GST report data into the
  actual published GSTN GSTR-1 JSON schema (HSN summary + B2C-small
  sections). `MockGSPAdapter` (the default) fully exercises
  generate→submit→status with deterministic fake acknowledgements;
  `HttpGSPAdapter` implements the generic submit-JSON/poll-status shape
  most GSPs (ClearTax, Cygnet, MasterGST, ...) share. Set
  `POS_GSP_PROVIDER=http` plus `POS_GSP_BASE_URL`/`POS_GSP_API_KEY` once
  you have a real GSP contract — the two endpoint paths in
  `HttpGSPAdapter` are the part you'll adjust to match that specific
  provider's API docs.

None of these were tested against a live provider (no real credentials
exist yet) — what's verified is the code we own: real cryptographic/
signature logic (webhook verification), real byte-level protocol output
(ESC/POS commands), real JSON schema shape (GSTR-1), and the full
request/response flow through each service with the network boundary
mocked at the adapter's edge. That boundary is intentionally the
*only* thing a real credential swap touches.

## 10. Folder structure

```
pos/
  ARCHITECTURE.md, ROADMAP.md, README.md
  docker-compose.yml
  .github/workflows/ci.yml
  backend/
    app/
      core/            # config, security, deps, permissions, exceptions
      db/               # session/engine setup, declarative base
      models/           # SQLAlchemy ORM models, one file per bounded context
      schemas/           # Pydantic I/O schemas, mirrors models/
      modules/
        auth/  organizations/  rbac/  catalog/  inventory/
        purchasing/  sales/  billing/  gst/  accounting/  loyalty/  reports/  audit/
        notifications/  payments/  printing/  gst_filing/   # external integrations, see §9
        <module>/repository.py service.py api.py
      main.py
    alembic/
    tests/{unit,integration}
    requirements.txt / requirements-dev.txt
  frontend/            # React + TS + Tailwind (Vite)
  docs/erd.md
```
