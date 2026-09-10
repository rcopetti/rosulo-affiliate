# Rosulo Affiliate

Multi-tenant affiliate tracking and payout platform. Built to power the allbum.me affiliate program and, later, to be sold as a standalone SaaS product to third-party merchants.

This repository contains both the FastAPI backend and the React frontend in a single branch.

- **Backend:** `backend/` — FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, SQS, PayPal.
- **Frontend:** `frontend/` — Vite, React, TypeScript, Tailwind CSS, TanStack Query, Zustand.

---

## Repository Structure

```
.
├── backend/          # FastAPI application
│   ├── app/
│   ├── tests/
│   ├── alembic/
│   ├── pyproject.toml
│   ├── docker-compose.yml
│   └── .env.example
├── frontend/         # React SPA
│   ├── src/
│   ├── playwright/
│   ├── package.json
│   ├── vite.config.ts
│   └── .env.example
├── docs/
│   ├── specs/        # Service definition
│   └── superpowers/plans/  # Implementation plans
└── README.md
```

---

## Prerequisites

- `uv` (Python package manager and runtime)
- Node.js 20+ and npm
- Docker and Docker Compose (for the local PostgreSQL container)
- PayPal Payouts API sandbox or live credentials (for payout execution)

---

## Quick Start

### 1. Start PostgreSQL

```bash
cd backend
docker compose up -d postgres
```

This starts a Postgres container on port `15432` with the credentials used in `backend/.env`.

### 2. Set up the backend

`uv` manages the Python version and the virtual environment. The project targets Python 3.12.

```bash
cd backend
uv python install 3.12
uv venv --python 3.12
uv pip install -e ".[dev]"
cp .env.example .env
```

Edit `.env` if you need to change the database URL, PayPal credentials, or JWT secret.

Apply the Alembic migrations:

```bash
uv run alembic upgrade head
```

Run the backend:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

The API will be available at `http://localhost:8001`. The OpenAPI docs are at `http://localhost:8001/docs`.

### 3. Set up the frontend

```bash
cd frontend
npm install
cp .env.example .env
```

Edit `.env` if the backend URL is different from the default.

Run the frontend:

```bash
npm run dev
```

The application will be available at `http://localhost:5173`.

### 4. Create a tenant and admin user (first run)

The backend does not ship with a default tenant or admin. Use the admin script or a one-off command to create them:

```bash
cd backend
uv run python - <<'PY'
import asyncio
from app.db.session import async_session
from app.db.models import Tenant, TenantUser
from app.core.security import hash_api_key, hash_password

async def seed():
    async with async_session() as db:
        tenant = Tenant(name='allbum', api_key_hash=hash_api_key('test-api-key'))
        db.add(tenant)
        await db.flush()
        db.add(TenantUser(
            tenant_id=tenant.id,
            email='admin@allbum.me',
            password_hash=hash_password('admin123'),
            name='Admin',
        ))
        await db.commit()
        print('Tenant:', tenant.id)

asyncio.run(seed())
PY
```

- Admin login: `admin@allbum.me` / `admin123` at `http://localhost:5173/admin/login`.
- Affiliate accounts are created by accepting a tenant invitation. From the admin dashboard, create an invite, then open the registration link (e.g. `http://localhost:5173/register?token=...&email=...`).
- Server-to-server event ingestion uses the tenant API key (`X-API-Key` header).

---

## Running Tests

### Backend

```bash
cd backend
uv run pytest tests/ -v
```

### Frontend

```bash
cd frontend
npm run test
```

For end-to-end tests (requires a running backend):

```bash
npx playwright test
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT and token signing key |
| `PAYPAL_CLIENT_ID` | PayPal Payouts API client ID |
| `PAYPAL_CLIENT_SECRET` | PayPal Payouts API secret |
| `SQS_QUEUE_URL` | Amazon SQS queue URL for background jobs |

### Frontend (`frontend/.env`)

| Variable | Purpose |
|----------|---------|
| `VITE_API_BASE_URL` | Backend API base URL (default `/api/v1`, proxied by Vite dev server to `/v1` on the backend) |

---

## Deployment

### Backend — AWS App Runner

The backend is packaged with a `Dockerfile` and an `apprunner.yaml` for AWS App Runner. Build and deploy from the `backend/` directory.

### Frontend

Run `npm run build` to produce a `dist/` directory. Serve the `dist/` directory with any static host or CDN.

---

## Branching

Active development is on `feature/version-mvp`. Do not commit directly to `master`.

---

## Documentation

- Service definition: `docs/specs/2026-09-09-rosulo-affiliate-service-definition.md`
- Backend implementation plan: `docs/superpowers/plans/2026-09-09-rosulo-affiliate-v1.md`
- Frontend implementation plan: `docs/superpowers/plans/2026-09-09-rosulo-affiliate-frontend-v1.md`
