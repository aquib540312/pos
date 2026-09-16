# Beef Wholesale + Retail POS - Local Setup Tutorial

Yeh tutorial batata hai kaise apne PC peh POS application ko setup karein.

---

## Prerequisites (Pehle install karo)

### 1. Python 3.11+
```bash
# Download karo: https://www.python.org/downloads/
# Install karte waqt "Add Python to PATH" check karo
python --version   # verify karo
```

### 2. Node.js 18+ (npm ke saath)
```bash
# Download karo: https://nodejs.org/
node --version     # verify karo
npm --version      # verify karo
```

### 3. PostgreSQL 16
```bash
# Download karo: https://www.postgresql.org/download/windows/
# Install karo, default port 5432 rakho
# Password yaad rakho (default: postgres)
```

### 4. Redis (Optional - Celery ke liye)
```bash
# Windows peh: https://github.com/microsoftarchive/redis/releases
# ya Docker use karo
```

### 5. Git
```bash
# Download karo: https://git-scm.com/download/win
git --version
```

---

## Step 1: Repository Clone Karo

```bash
git clone <repo-url> pos
cd pos
```

---

## Step 2: Backend Setup

### 2.1 Virtual Environment Banao

```bash
cd backend
python -m venv .venv
```

### 2.2 Virtual Environment Activate Karo

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
.venv\Scripts\activate.bat
```

**Mac/Linux:**
```bash
source .venv/bin/activate
```

### 2.3 Dependencies Install Karo

```bash
pip install -r requirements-dev.txt
```

### 2.4 Environment File Banao

```bash
# .env file banao backend folder mein
```

**backend/.env** mein yeh likho:
```env
# Database
POS_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/pos

# Secret Key (koi bhi random string)
POS_SECRET_KEY=my-super-secret-key-change-this

# Redis (optional)
POS_REDIS_URL=redis://localhost:6379/0

# Celery (local dev ke liye true rakho)
POS_CELERY_TASK_ALWAYS_EAGER=true

# Payment (test mode - change mat karo)
POS_RAZORPAY_KEY_ID=rzp_test_0000000000000
POS_RAZORPAY_KEY_SECRET=test_secret_change_me

# Printer (disabled by default)
POS_PRINTER_ENABLED=false

# GST/VAT (mock mode)
POS_GSP_PROVIDER=mock
```

### 2.5 Database Banao

PostgreSQL open karo aur `pos` database banao:

```sql
CREATE DATABASE pos;
```

Ya psql command use karo:
```bash
psql -U postgres -c "CREATE DATABASE pos;"
```

### 2.6 Migrations Run Karo

```bash
alembic upgrade head
```

### 2.7 Seed Data Load Karo (Demo Data)

```bash
python -m app.seed
```

Yeh demo organization, admin user, aur products create karega.

### 2.8 Backend Start Karo

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend ab http://localhost:8000 peh chal raha hai.

**API Docs dekhne ke liye:** http://localhost:8000/docs

---

## Step 3: Frontend Setup

### 3.1 Naya Terminal Kholein

```bash
cd frontend
```

### 3.2 Dependencies Install Karo

```bash
npm install
```

### 3.3 Frontend Start Karo

```bash
npm run dev
```

Frontend ab http://localhost:5173 peh chal raha hai.

---

## Step 4: Login Karo

Browser mein http://localhost:5173 kholein.

**Demo Login:**
- Email: `admin@demo.local`
- Password: `ChangeMe123!`

---

## Docker Se Setup (Alternative)

Agar Docker installed hai toh sab kuch ek command mein:

```bash
# Root folder mein
cp .env.example .env
# .env mein POS_SECRET_KEY change karo

docker compose up --build
```

Yeh automatically:
- PostgreSQL start karega
- Redis start karega
- Backend build & run karega
- Frontend build & serve karega

**Access:**
- Frontend: http://localhost
- API Docs: http://localhost:8000/docs

---

## Test Run Karo

```bash
cd backend

# Unit tests
python -m pytest tests/unit/ -v

# Integration tests
python -m pytest tests/integration/ -v

# Sab tests
python -m pytest -v
```

---

## Common Issues aur Solutions

### Issue 1: `psycopg2` install ho raha hai
```bash
# Windows peh Visual C++ Build Tools chahiye
# Download: https://visualstudio.microsoft.com/visual-cpp-build-tools/
```

### Issue 2: Port already in use
```bash
# Port 8000 busy hai toh
uvicorn app.main:app --reload --port 8001
```

### Issue 3: Database connection error
```bash
# PostgreSQL chalu hai check karo
# pgAdmin ya psql se verify karo
psql -U postgres -c "\l"
```

### Issue 4: Node modules install ho raha hai
```bash
# Cache clear karo
npm cache clean --force
rm -rf node_modules
npm install
```

### Issue 5: Alembic migration error
```bash
# Database mein alembic_version table delete karo
psql -U postgres -d pos -c "DROP TABLE IF EXISTS alembic_version;"
alembic upgrade head
```

---

## Project Structure

```
pos/
├── backend/
│   ├── app/
│   │   ├── models/          # Database models
│   │   ├── modules/         # Business logic (catalog, sales, inventory, etc.)
│   │   ├── core/            # Config, security, utils
│   │   └── main.py          # FastAPI app
│   ├── alembic/             # Database migrations
│   ├── tests/               # Unit & integration tests
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── pages/           # React pages
│   │   ├── components/      # React components
│   │   ├── api/             # API calls
│   │   └── App.tsx          # Main app
│   └── package.json         # Node dependencies
└── docker-compose.yml       # Docker setup
```

---

## API Endpoints (Kuch Important)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/login` | POST | Login |
| `/api/v1/catalog/products` | GET/POST | Products list/create |
| `/api/v1/sales` | POST | Create sale |
| `/api/v1/sales/returns` | POST | Create return |
| `/api/v1/purchasing/goods-receipts` | POST | Receive stock |
| `/api/v1/inventory/stock` | GET | Stock levels |
| `/api/v1/party/customers` | GET/POST | Customers |
| `/api/v1/party/suppliers` | GET/POST | Suppliers |
| `/api/v1/reports/profit-and-loss` | GET | P&L report |

---

## Beef POS Features

### Product Management
- Beef cuts (Tenderloin, Ribeye, Sirloin, etc.)
- Fresh/Frozen status
- Local/Imported
- Country of origin
- Variable weight sales (KG)

### Pricing
- Retail price
- Wholesale price
- Restaurant price
- VIP price
- Custom customer price

### Customer Types
- Walk-in
- Restaurant
- Hotel
- Catering
- Regular
- Wholesale

### Saudi VAT (15%)
- Automatic VAT calculation
- VAT invoice
- Input VAT credit

### Inventory
- Weight-based (KG)
- Batch tracking
- Expiry tracking
- Waste/spoilage tracking
- Butcher/cutting workflow

---

## Development Commands

```bash
# Backend
cd backend
uvicorn app.main:app --reload        # Start dev server
python -m pytest -v                   # Run tests
ruff check .                          # Lint code
alembic revision --autogenerate -m "description"  # New migration

# Frontend
cd frontend
npm run dev                           # Start dev server
npm run build                         # Production build
npm run lint                          # Lint code
```

---

## Support

Agar koi issue aaye toh:
1. README.md check karo
2. ARCHITECTURE.md padho
3. API docs http://localhost:8000/docs peh dekho
