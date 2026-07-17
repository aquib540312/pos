# POS Desktop (Electron)

A native shell around the web frontend for a physical shop counter:
kiosk-mode window, no browser chrome, and a File > Backend Settings screen
so one installer can be pointed at any shop's backend at runtime (there's
no reverse proxy in front of it the way `nginx` provides for the
Docker/web deployment, so the URL can't be baked in at build time).

## Offline sales (embedded sync_agent)

On startup, this shell spawns `backend/sync_agent/local_server.py` as a
child process and points the frontend at it instead of the real backend
directly. That local server:

- **Proxies every request to your real backend when it's reachable** —
  online behavior is unchanged, byte-identical to the frontend talking to
  the backend directly.
- **Falls back to sync_agent's own synced SQLite cache** when the backend
  isn't reachable: product/customer search and barcode lookup keep
  working, and `POST /sales` queues the sale into the offline sales queue
  instead of failing. That queue syncs automatically once connectivity
  returns (`sync_agent`'s existing background worker — see
  `ARCHITECTURE.md` §5).
- Offline sales come back as a **provisional receipt**, not a tax
  invoice — there's no cached GST rate to compute CGST/SGST/IGST from
  offline, so it prints subtotal/total only, clearly marked, until the
  real invoice posts server-side after sync.
- Gift cards and UPI QR payments need a live connection (no local cache
  for those) — offline checkout only supports cash/card/credit.

If the local server can't start at all (no Python, or `sync_agent`'s
dependencies aren't installed) or doesn't come up within a few seconds,
this shell **falls back to the old online-only behavior**: the frontend
talks to your configured backend directly, same as before this feature
existed. A till without Python still works, it just can't take sales
while offline.

### One-time setup per till (for offline sales to actually work)

The local cache starts empty — it only has data to fall back on after at
least one successful online sync, which needs a registered terminal:

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r sync_agent/requirements.txt
python -m sync_agent.cli register   # prompts for a manager/admin JWT, prints a terminal API key
```

Paste that key into this shell's Settings screen (Terminal API key) along
with a local database passphrase, then launch normally — the till needs
to be online at least once after this so sync_agent can pull products/
customers/stock into its local cache before it can serve them offline.

### Prerequisites

`POS_DESKTOP_PYTHON` overrides which interpreter this shell spawns
(defaults to `python` on `PATH`); it needs `sync_agent/requirements.txt`
installed. **Not yet done**: freezing that Python process into the
packaged installer (e.g. via PyInstaller) so end users don't need Python
themselves — for now, a packaged build still expects a Python environment
on the till (see `build.extraResources` in `package.json`, which bundles
`backend/sync_agent/` itself into the installer, but not an interpreter).

## Cash drawer control

The POS billing screen's "Open Drawer" button calls the backend's
`POST /api/v1/printing/drawer/kick`, which pulses the drawer wired into
the same ESC/POS receipt printer already configured for thermal printing
(`POS_PRINTER_HOST/PORT/ENABLED`). Works the same in a browser or this
shell — no hardware talking happens in Electron itself. Offline, this
call proxies/falls through like anything else not in sync_agent's scope
(product/customer/sales) — it needs connectivity, since the backend is
what actually talks to the printer.

## Run in dev

```bash
cd frontend && npm install && npm run build   # produces frontend/dist
cd ../desktop && npm install
npm start
```

First launch shows the backend settings screen; enter your backend's
**origin only** (e.g. `http://localhost:8000`, no `/api/v1` suffix — that
part is added automatically). Settings are stored in Electron's per-user
config dir and only need setting once (change them later via File >
Backend Settings; changing them relaunches the app).

## Build an installer

```bash
npm run dist
```

Builds `frontend/dist` fresh, then packages a Windows/Mac/Linux installer
into `desktop/release/` via `electron-builder` (target OS is whichever
you run this on, unless you configure cross-building — see
electron-builder's docs for that).
