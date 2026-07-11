# Indian Retail POS

A modular-monolith POS platform for Indian retail (grocery, supermarket,
medical, electronics, garment) built with FastAPI + PostgreSQL + React.
GST-correct billing (CGST/SGST/IGST), batch/expiry and serial tracking,
credit customers, purchasing (PO → GRN), returns/exchange, shifts & cash
reconciliation, loyalty points, coupons, gift cards, and basic
accounting/GST reporting.

Read **[ARCHITECTURE.md](ARCHITECTURE.md)** for the design decisions and
**[ROADMAP.md](ROADMAP.md)** for what's built vs. what's planned next.

## Quick start (Docker)

```bash
cp .env.example .env   # set POS_SECRET_KEY
docker compose up --build
docker compose exec backend python -m app.seed   # creates a demo org + admin login
```

- Frontend: http://localhost
- Backend API docs: http://localhost:8000/docs
- Demo login (after seeding): `admin@demo.local` / `ChangeMe123!`

## Local development

**Backend**

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
# point POS_DATABASE_URL at a local Postgres, then:
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
pytest                 # unit + integration tests
ruff check .           # lint
```

**Frontend**

```bash
cd frontend
npm install
npm run dev            # proxies /api to http://localhost:8000
npm run build           # typecheck + production build
```

## Repository layout

```
backend/    FastAPI app (Clean Architecture: api / service / repository per module)
frontend/   React + TypeScript + Tailwind (Vite)
docs/       Entity-relationship notes
```
