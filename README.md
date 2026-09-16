# Beef Wholesale + Retail POS

A modular-monolith POS platform customized for **Beef Wholesale + Retail business in Saudi Arabia**, built with FastAPI + PostgreSQL + React.

Features include:
- Variable-weight sales (KG) with decimal quantities
- Multiple price levels (Retail, Wholesale, Restaurant, VIP, Custom)
- Saudi VAT (15%) with proper invoicing
- Arabic + English support
- Beef-specific product management (cuts, fresh/frozen, local/imported)
- Customer types (Walk-in, Restaurant, Hotel, Catering, Wholesale)
- Credit sales with payment terms
- Weight-based inventory with batch/expiry tracking
- Waste/spoilage tracking
- Butcher/cutting workflow
- Purchase management (PO → GRN)
- Returns/exchange
- Shifts & cash reconciliation
- Loyalty points, coupons, gift cards
- Basic accounting/VAT reporting

Read **[ARCHITECTURE.md](ARCHITECTURE.md)** for the design decisions and **[SETUP_TUTORIAL.md](SETUP_TUTORIAL.md)** for local setup instructions.

## Quick start (Docker)

```bash
cp .env.example .env   # set POS_SECRET_KEY
docker compose up --build
```

- Frontend: http://localhost
- Backend API docs: http://localhost:8000/docs
- Demo login: `admin@demo.local` / `ChangeMe123!`

## Local development

See **[SETUP_TUTORIAL.md](SETUP_TUTORIAL.md)** for detailed instructions.

**Backend**

```bash
cd backend
python -m venv .venv && .venv/bin/Scripts/activate
pip install -r requirements-dev.txt
# Create PostgreSQL database 'pos'
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

**Frontend**

```bash
cd frontend
npm install
npm run dev            # proxies /api to http://localhost:8000
```

## Repository layout

```
backend/    FastAPI app (Clean Architecture: api / service / repository per module)
frontend/   React + TypeScript + Tailwind (Vite)
desktop/    Electron shell for a physical till (see desktop/README.md)
docs/       Entity-relationship notes
```
