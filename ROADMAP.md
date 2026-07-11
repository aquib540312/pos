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
- Combo product rule engine (currently: basic percentage/flat discounts and
  manual combo price only; a full rule DSL — "buy 2 get 1", tiered slabs —
  needs your priority ranking of which promo types matter first).
- GSTR-1/3B **filing** integration — requires a GSP (GST Suvidha Provider)
  API account and credentials from you; today we generate the correct
  line-level data, not the government-format JSON/upload.
- Employee management beyond RBAC (attendance, payroll is out of scope for
  a POS unless you want it).

## Phase 3 — Channel expansion (needs infrastructure decisions from you)
- **Offline-first + sync**: design in `ARCHITECTURE.md` §5. Needs your
  answer on oversell tolerance and conflict-resolution policy before
  implementation.
- **Electron desktop shell**: thin wrapper over the web frontend +
  local SQLite cache + thermal printer driver (ESC/POS) + cash drawer
  kick (serial/USB) integration — needs to know your target printer
  models (most speak ESC/POS over USB/serial, but confirm before we pick
  a driver library).
- **React Native mobile**: for supervisor dashboards / handheld barcode
  scanning; POS billing on a phone is unusual for retail counters — confirm
  this is actually wanted before building it.
- **UPI QR integration**: needs a payment aggregator (Razorpay/PhonePe/
  BharatPe/PayU) merchant account and API keys — we can generate static
  UPI intent QR codes (upi://pay?...) without a gateway for basic cases,
  or dynamic reconciled QR via an aggregator if you want auto-reconciliation.
- **SMS/Email/WhatsApp**: needs provider accounts (e.g. MSG91/Twilio for
  SMS, WhatsApp Business API via Meta or a BSP like Gupshup/Interakt).
  Notification module is stubbed with an adapter interface so swapping in
  real credentials is a config change, not a rewrite.
- Restaurant module (tables, KOT, kitchen display) — explicitly marked
  optional in the brief; build after core retail flows are validated with
  real usage.
- Plugin architecture (third-party extensibility) — design after 2-3 real
  modules exist to extract a genuine extension point from, rather than
  guessing one upfront.

## Explicitly deferred, needs your decision before scheduling
1. Which business type to pilot first (grocery/supermarket vs medical vs
   electronics vs garment) — the generic catalog/batch/serial model covers
   all four reasonably, but medical stores often need drug-schedule
   (H/H1/X) compliance fields; confirm if that's needed.
2. Payment gateway / UPI aggregator choice.
3. SMS/WhatsApp provider choice.
4. Whether GSTR filing needs to be automated (GSP integration) or if
   exporting correct data for manual filing is sufficient.
5. Target thermal printer hardware models (for the Electron ESC/POS driver).
