# Deployment Guide — EduConnect (School Influencer Intelligence)

## Architecture Targets
- **Backend API**: FastAPI + Uvicorn + `BAAI/bge-small-en-v1.5` on **Render** (`backend/Dockerfile`, configured in `render.yaml`)
- **Frontend UI**: Next.js 15 App Router on **Render** (`frontend/`, proxying `/api/*` at runtime via `frontend/app/api/[...path]/route.ts` using `BACKEND_URL`) or **Vercel**
- **Database**: Managed **PostgreSQL 16** with `pgvector` extension (`educonnect-db`)

---

## Option 1: Deploy Backend & Frontend on Render via 1-Click Blueprint (`render.yaml`)

1. Open the **Render Dashboard** (`https://dashboard.render.com`) -> **New +** -> **Blueprint**.
2. Connect GitHub account `molishkasahu01` and select repository **`educonnect`** (`main` branch).
3. Review the Blueprint resources defined in `render.yaml`:
   - **`educonnect-db`**: Render Managed PostgreSQL 16 (`plan: free`, `pgvector` supported automatically via `0001_initial_schema.py`).
   - **`educonnect-api`**: Docker Web Service (`rootDir: backend`, `plan: free`, `healthCheckPath: /api/health`, auto-generated `JWT_SECRET_KEY`, `TASK_QUEUE_MODE=local`, `DATABASE_URL` linked to `educonnect-db`).
   - **`educonnect-web`**: Node Web Service (`rootDir: frontend`, `plan: free`, `NEXT_PUBLIC_API_URL=same-origin`, `BACKEND_URL` automatically linked to `educonnect-api`).
4. Click **Apply** and wait for Docker build & migrations (`alembic upgrade head`) to finish. Default ranking weights and authorized data sources initialize automatically on startup.
5. Open `https://<your-educonnect-web>.onrender.com`, create your workspace account on `/register`, and verify `/api/health`.

> [!NOTE]
> **Memory / Plan Sizing Note for Render Backend (`educonnect-api`)**: `render.yaml` defaults to `plan: free` so you can deploy without billing blockers. However, `sentence-transformers` (`BAAI/bge-small-en-v1.5` + CPU PyTorch) uses ~450–650 MB RAM during active embedding computation; upgrade `educonnect-api` to **Standard (2 GB RAM)** in Render Dashboard if free-tier `512 MB` RAM hits OOM during embedding runs (and note Render Free Postgres databases expire after 30 days unless upgraded).

---

## Option 2: Manual Setup on Render (Without Blueprint)

### Step A: PostgreSQL Database
1. In Render -> **New +** -> **PostgreSQL** (`educonnect-db`, PostgreSQL 16).
2. Copy the **Internal Database URL** (starts with `postgres://...`; EduConnect automatically normalizes it to `postgresql+psycopg2://`).

### Step B: Backend Web Service (`educonnect-api`)
1. **New +** -> **Web Service** -> select `molishkasahu01/educonnect`.
2. **Root Directory**: `backend` · **Language**: `Docker` (Dockerfile Path: `./Dockerfile`).
3. **Health Check Path**: `/api/health`.
4. Add **Environment Variables**:
   - `DATABASE_URL` = *(Internal Database URL from Step A)*
   - `JWT_SECRET_KEY` = *(click Generate or `openssl rand -hex 32`)*
   - `TASK_QUEUE_MODE` = `local`
   - `EDXSO_ENABLE_DEFAULT_PUBLIC_WEB_SOURCES` = `true`
   - `CORS_ORIGINS` = `https://<your-frontend-service>.onrender.com`
5. Wait until `/api/health` returns `200 OK`, then copy your backend URL (`https://<your-api-service>.onrender.com`).

### Step C: Frontend Web Service (`educonnect-web`)
1. **New +** -> **Web Service** -> select `molishkasahu01/educonnect`.
2. **Root Directory**: `frontend` · **Language**: `Node`.
3. **Build Command**: `npm ci && npm run build`
4. **Start Command**: `npx next start -H 0.0.0.0 -p ${PORT:-3000}`
5. Add **Environment Variables**:
   - `NODE_ENV` = `production`
   - `NEXT_PUBLIC_API_URL` = `same-origin`
   - `BACKEND_URL` = `https://<your-api-service>.onrender.com`
6. Deploy and visit `https://<your-frontend-service>.onrender.com`.

---

## Option 3: Local Docker Compose Deployment
```bash
cp .env.example .env
# Edit JWT_SECRET_KEY in .env before starting
docker compose up --build -d
docker compose exec backend alembic upgrade head
```
