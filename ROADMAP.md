# Roadmap

## Phase 1 — Foundation (this session)
Status: in progress / see commit history for exact state.

- [x] Architecture decisions documented (`ARCHITECTURE.md`)
- [x] Normalized DB schema: orgs/branches/warehouses, RBAC, catalog
      (products, categories, HSN/SAC, UOM, tax rates, batches, serials),
      parties (customers with credit, suppliers), inventory + stock ledger,
      purchasing (PO → GRN), sales (quotations, invoices, returns), billing
      (shifts, cash drawer sessions, payments incl. multi-tender), basic
      accounting ledger, loyalty points, coupons, gift cards, audit log
- [x] Backend: auth/JWT, RBAC enforcement, catalog CRUD, inventory,
      purchasing (PO → GRN with stock posting), sales/billing (GST-correct
      invoice creation, returns), shift open/close & cash reconciliation,
      basic reports (sales summary, stock summary, GSTR-1 line-level export)
- [x] Unit tests (GST split, discounts, credit limit, loyalty accrual) +
      integration tests (auth flow, full sale-to-ledger flow)
- [x] Frontend: login, product management, POS billing screen (cart,
      discounts, GST breakdown, multi-payment, receipt view), customers list
- [x] Docker Compose (Postgres, Redis, backend, Celery worker, frontend,
      Nginx), GitHub Actions CI (lint + test)

## Phase 2 — Depth on the built modules (needs product prioritization)
- [x] Stock transfer between branches/warehouses: draft -> dispatched ->
      received lifecycle, FEFO batch allocation on dispatch, stock genuinely
      in-transit (unsellable at either end) between the two steps.
- [x] Full accounting: journal entries now post on goods receipt (Inventory
      vs Accounts Payable) and sales returns (reversing revenue/GST vs
      cash/bank/receivable) in addition to sales; P&L and Balance Sheet
      report endpoints (`/reports/profit-and-loss`, `/reports/balance-sheet`)
      built on top of the ledger. Known simplification: purchase-side input
      GST credit isn't posted yet because PO/GRN line items don't carry
      HSN/tax-rate data — only ex-tax cost is booked to Inventory.
- [x] Barcode/QR product labels: `/catalog/products/{id}/barcode.png`
      (Code128) and `/qr.png` (SKU+name+MRP payload), plus a printable
      `/label-sheet.png` grid (N copies, configurable columns) sized for
      standard adhesive label sheets on any regular printer. A "Print
      labels" action on the Products page opens the sheet in a new tab and
      triggers the browser print dialog. Direct thermal label-printer
      (ZPL) output is still Phase 3 — needs your target hardware model.
- [x] Combo/bundle products: a combo bills as one line at its own price/HSN
      (like any product), but selling or returning it moves stock on its
      *components* instead — scaled by each component's quantity — since
      the combo SKU itself never carries stock. Nesting a combo inside
      another combo is rejected. Design decision made without further
      input, since it directly implements "Combo Products" from the
      original brief the same way Indian retail already prices bundles
      (one MRP on the pack). A full promo rule DSL ("buy 2 get 1", tiered
      slabs, auto-detected combos at checkout) is a separate, larger
      feature — this covers pre-defined combo SKUs only.
- [x] Coupons and gift cards, previously standalone endpoints only, are now
      wired into the actual checkout: `POST /sales` accepts `coupon_code`
      (validated against min order value/date range/redemption limit,
      applied as a post-tax discount, redemption count incremented) and
      `gift_card_number`/`gift_card_amount` (balance/expiry checked,
      recorded as an implicit `gift_card` payment). The invoice now stores
      which coupon was used and its discount amount (new migration). POS
      billing screen has real Coupon and Gift Card fields, verified
      end-to-end in a browser.
- GSTR-1/3B **filing** integration — requires a GSP (GST Suvidha Provider)
  API account and credentials from you; today we generate the correct
  line-level data, not the government-format JSON/upload.
- Employee management beyond RBAC (attendance, payroll is out of scope for
  a POS unless you want it).

## Phase 3 — Channel expansion

- [x] **Payments (Razorpay UPI QR)**: real, documented QR Code API
      integration (`app/modules/payments/`) — create/close a dynamic UPI
      QR tied to a sale amount, webhook confirms payment with real
      HMAC-SHA256 signature verification via the official SDK. Ships with
      Razorpay *test-mode* keys as safe defaults; swap
      `POS_RAZORPAY_KEY_ID/SECRET/WEBHOOK_SECRET` for live values from
      the dashboard and it works unchanged. Fully wired into the POS
      billing screen: a feature-flagged "UPI QR" payment mode generates
      the QR, polls status live, auto-finalizes the sale and prints the
      receipt the moment payment is confirmed, and handles expiry,
      cashier cancellation, and connection loss during polling.
- [x] **SMS (MSG91)**: real Flow API integration
      (`app/modules/notifications/adapters.py`), wired to an actual
      trigger — every completed sale with a customer phone on file
      queues a receipt SMS via Celery, best-effort (never blocks
      checkout). Needs `POS_MSG91_AUTH_KEY` + a DLT-registered template
      (`POS_MSG91_FLOW_ID`) from your MSG91 dashboard; falls back to a
      safe logging adapter until configured.
- [x] **Thermal printing (Epson ESC/POS)**: real ESC/POS command
      generation (`app/modules/printing/`, via `python-escpos`) for a
      full receipt layout, sendable to any Epson TM-series or ESC/POS-
      compatible printer over the network (raw port 9100) or previewable
      as raw bytes with no hardware at all
      (`GET /printing/receipt/{id}/escpos`). Set `POS_PRINTER_HOST/PORT`
      and `POS_PRINTER_ENABLED=true` to print for real; every failure is
      caught and logged, never breaks a sale.
- [x] **GST e-filing (GSP)**: `app/modules/gst_filing/` renders our GST
      report data into the actual GSTN GSTR-1 JSON schema (HSN summary +
      B2C-small) and runs a full generate → submit → status workflow
      against a `MockGSPAdapter` (deterministic fake acknowledgements) by
      default. `HttpGSPAdapter` implements the generic submit/poll shape
      most GSPs share; set `POS_GSP_PROVIDER=http` plus your real GSP's
      base URL/API key once you have a contract (ClearTax, Cygnet,
      MasterGST, etc.) — the two endpoint paths are the part you'll
      adjust to that provider's specific docs. B2B (GSTIN-wise) invoice
      reporting isn't built yet, only B2C-small — see
      `gst_filing/schema_builder.py`.
- [x] **Offline-first + sync**: full bidirectional sync engine. Design in
  `ARCHITECTURE.md` §5; server half in `app/modules/sync/` (change-log
  capture, idempotent push, cursor-based pull, conflict dashboard), client
  half in `sync_agent/` (encrypted-at-rest SQLite via SQLCipher, offline
  sales queue, background worker with exponential backoff + reconnect
  detection + crash recovery, CLI). Oversell policy: stock can never go
  negative — an offline sale that can't be safely applied becomes an open
  conflict for a manager to retry or cancel, never forced through.
  153 backend tests passing (40 of them sync-specific, including a real
  loopback-socket integration test against the actual API).
- **Electron desktop shell**: thin wrapper over the web frontend + cash
  drawer kick (serial/USB), now that `sync_agent` provides the offline
  cache/queue engine itself. The ESC/POS printing piece is also already
  built and reusable from Electron (it's just talking to the same printer
  over the network) — what's left here is specifically embedding
  `sync_agent` as the desktop shell's local data layer and the
  drawer-kick integration.
- **React Native mobile**: for supervisor dashboards / handheld barcode
  scanning — confirm this is actually wanted before building it; POS
  billing on a phone is unusual for a retail counter.
- Restaurant module (tables, KOT, kitchen display) — explicitly marked
  optional in the brief; build after core retail flows are validated
  with real usage.
- Plugin architecture (third-party extensibility) — design after 2-3
  real modules exist to extract a genuine extension point from, rather
  than guessing one upfront.

## Explicitly deferred, needs your decision before scheduling
1. Which business type to pilot first (grocery/supermarket vs medical vs
   electronics vs garment) — the generic catalog/batch/serial model covers
   all four reasonably, but medical stores often need drug-schedule
   (H/H1/X) compliance fields; confirm if that's needed.
2. Real Razorpay/MSG91/GSP credentials, and which specific GSP to
   contract with, once you're ready to go live.
3. Target thermal printer hardware model to validate against for real
   (architecture assumes standard Epson ESC/POS over network, port 9100).
