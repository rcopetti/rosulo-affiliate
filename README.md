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

### 4. First run

1. Open the landing page at `http://localhost:5173/`.
2. Choose **Merchants → Sign up** to create a tenant and admin user.
3. Save the generated API key — it is shown only once and is required for server-to-server event ingestion (`X-API-Key` header).
4. Log in as a merchant at `http://localhost:5173/admin/login`.
5. Affiliate accounts are created by accepting a tenant invitation. From the admin dashboard, create an invite, then open the registration link (e.g. `http://localhost:5173/register?token=...&email=...`).

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
| `TEST_DATABASE_URL` | Optional test DB used by pytest; defaults to `<DATABASE_URL database>_test` |
| `SECRET_KEY` | JWT and token signing key |
| `PAYPAL_CLIENT_ID` | PayPal Payouts API client ID |
| `PAYPAL_CLIENT_SECRET` | PayPal Payouts API secret |
| `SQS_QUEUE_URL` | Amazon SQS queue URL for background jobs |
| `EMAIL_BACKEND` | `console` (logs) or `ses` (AWS SES) |
| `EMAIL_FROM` | Sender address (must be verified in SES) |
| `SES_REGION` | AWS SES region (default `us-east-1`) |
| `FRONTEND_URL` | Base URL used in email links (e.g. `http://localhost:5173`) |

### Frontend (`frontend/.env`)

| Variable | Purpose |
|----------|---------|
| `VITE_API_BASE_URL` | Backend API base URL (default `/api/v1`; the Vite dev server proxies `/api/*` to the backend unchanged) |

---

## Deployment

### Backend — AWS App Runner

The production image is defined in `backend/docker/Dockerfile`. Build it with the build script, which tags it `<major.minor>-<git short hash>` (from `pyproject.toml`) plus `latest`, and targets `linux/amd64` for App Runner:

```bash
cd backend
./build-docker.sh     # refuses on a dirty working tree; --force bypasses
./auth-docker.sh      # ECR login (once per session)
docker push <image>   # push the tags printed by the build script
./run-migration.sh <tag>      # one-shot Fargate task: alembic upgrade head
./deploy-apprunner.sh <tag>   # roll out to the Rosulo-Affiliates App Runner service
```

To run the full stack locally in Docker (Postgres + one-shot migration + API):

```bash
cd backend
docker compose -f docker/docker-compose.yml up --build
```

### Frontend

Build the static bundle with the build script, which loads env vars from `frontend/.env.prod` (create it from `.env.example`) and outputs a minified production bundle to `frontend/dist/`:

```bash
cd frontend
./build-web.sh                  # production build (loads .env.prod)
./build-web.sh --env .env       # local/sandbox build
./build-web.sh --dev            # non-minified, for staging inspection
./build-web.sh --clean          # clear the Vite cache before building
./build-web.sh --api-url URL    # talk directly to a backend URL (needs CORS)
```

Serve the `dist/` directory with any static host or CDN. The app calls the API via same-origin relative paths (`/api/v1`), so the CDN should proxy `/api/*` to the backend (App Runner) and fall back to `/index.html` for SPA routing.

---

## Branching

Active development is on `feature/version-mvp`. Do not commit directly to `master`.

---

## Documentation

- Service definition: `docs/specs/2026-09-09-rosulo-affiliate-service-definition.md`
- Backend implementation plan: `docs/superpowers/plans/2026-09-09-rosulo-affiliate-v1.md`
- Frontend implementation plan: `docs/superpowers/plans/2026-09-09-rosulo-affiliate-frontend-v1.md`
