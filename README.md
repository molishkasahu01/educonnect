# EduConnect — School Influencer Intelligence

An enterprise full-stack AI/ML discovery and explainable hybrid ranking platform for identifying real, traceable leaders, former principals, school owners, managing trustees, multi-campus directors, and K-12 education consultants across authorized data sources.

EduConnect operates **exclusively on real, verified, or user-authorized professional records**. There is zero synthetic, fictional, simulated, or mocked discovery data anywhere in the platform.

---

## Features
- **Reference Profile Analysis (`POST /api/reference-profiles/{id}/analyze`)**: Structured extraction across Professional Identity, 19 K-12 School Ecosystem Indicators, Professional Influence, and date-grounded Career Context, categorizing every attribute as `OBSERVED_FACT`, `SOURCE_SUPPORTED`, `AI_DERIVED_CLASSIFICATION`, `UNVERIFIED`, or `MISSING_INFORMATION`.
- **Real-Data-Only Discovery & Ethical Access**: Supports modular authorized adapters across official school websites & school-group leadership pages (`OrganizationWebsiteAdapter`), permitted education & conference speaker directories (`PublicDirectoryAdapter`), authorized CSV/CRM exports (`CSVAdapter`, `CRMAdapter`), manually entered profiles (`ManualProfileAdapter`), and licensed professional data APIs (`AuthorizedAPIAdapter`). Enforces `robots.txt` compliance and blocks `linkedin.com` / `lnkd.in` scraping.
- **Honest Empty-State & Unpadded Ranking**: If zero verified or authorized real profiles exist in configured sources, discovery completes cleanly with `0` results (`"No verified or authorized professional profiles were found for this discovery. Connect an authorized source or import genuine professional records."`). If fewer than 20 real profiles exist, only the discovered real profiles are returned — never padded with fabricated records.
- **Semantic Similarity & Vector Retrieval**: Normalized professional context documents encoded with Sentence Transformers (`BAAI/bge-small-en-v1.5` default for low-RAM CPU execution; configurable to `BAAI/bge-m3`), stored in PostgreSQL `pgvector` (`HNSW vector_cosine_ops`) or portable SQLite cosine retrieval, with optional configurable Cross-Encoder reranking.
- **Explainable Hybrid Ranking**:
  $$\text{Relevance} = 0.30 \cdot \text{Semantic} + 0.25 \cdot \text{SchoolEcosystem} + 0.15 \cdot \text{Role} + 0.10 \cdot \text{Experience} + 0.10 \cdot \text{OrgNetwork} + 0.10 \cdot \text{Influence}$$
  with missing-evidence-aware normalization, an independent calibrated **Evidence Confidence** score, minimum-evidence guardrails, and evidence-linked explanations.
- **Real Database Analytics & Exports**: Every dashboard chart and KPI queries real database rows (`0` when empty). Full shortlisting and provenance-annotated CSV, XLSX, and JSON exports.

---

## Architecture & Technology Stack
- **Frontend**: Next.js 15 App Router, TypeScript, Tailwind CSS, Recharts, React Hook Form, Zod, Lucide Icons.
- **Backend**: Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Celery, bcrypt, PyJWT, openpyxl, structlog.
- **Database & Queue**: PostgreSQL 16 + `pgvector`, Redis 7 (with portable SQLite + ThreadPool worker fallback for standalone local runs).
- **AI/ML**: Sentence Transformers (`BAAI/bge-small-en-v1.5` / `BAAI/bge-m3`), optional `CrossEncoder` reranking, Scikit-learn/NumPy cosine evaluation.

---

## Local Setup & Execution

### Option A: Docker Compose
```bash
cd edxso-ai
cp .env.example .env
# Edit JWT_SECRET_KEY and optionally LICENSED_DATA_API_URL / LICENSED_DATA_API_KEY
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python /app/../scripts/bootstrap_db.py
```
- Frontend: `http://localhost:3000`
- Backend API / Swagger Docs: `http://localhost:8000/api/docs`

### Option B: Standalone Local Development (Python 3.11 + Node.js)
1. **Backend & Database**:
   ```bash
   cd edxso-ai/backend
   export DATABASE_URL=sqlite:///./edxso_local.db
   export TASK_QUEUE_MODE=local
   .venv/bin/alembic upgrade head
   .venv/bin/python ../scripts/bootstrap_db.py
   .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
   ```
2. **Frontend**:
   ```bash
   cd edxso-ai/frontend
   npm install
   NEXT_PUBLIC_API_URL=http://127.0.0.1:8010 npm run build
   NEXT_PUBLIC_API_URL=http://127.0.0.1:8010 npx next start -H 127.0.0.1 -p 3010
   ```

---

## Ingesting & Discovering Genuine Data Sources
1. Register/sign in via `/register` or `/login`.
2. Out-of-the-box **Real External Sources** (`REAL_DATA`, controlled via `EDXSO_ENABLE_DEFAULT_PUBLIC_WEB_SOURCES=true`) automatically queries permitted public K-12 association directories, conference speaker rosters, and official consultancy/school-group leadership websites (e.g., Association of Indian Principals, EGN Connect X, The Schools of India Summit, LIFE Educare, Global Schools Group, and Pratham Education Foundation) respecting `robots.txt` and source terms.
3. Supply additional permitted URLs directly on `/discovery/new`, or ingest additional records via **Dataset Import** (`/datasets/import`):
   - **Permitted Websites & Directories**: Provide official school leadership URLs, school group pages, education consultancy team pages, or conference/association speaker directories (`POST /api/candidates/fetch-url`).
   - **Authorized CSV / CRM Exports**: Upload `.csv` exports with explicit authorization confirmation (`POST /api/candidates/import`).
   - **Licensed Data API**: Configure `LICENSED_DATA_API_URL` and `LICENSED_DATA_API_KEY` in environment variables before launching discovery in `REAL_DATA` mode.

---

## Running Automated Verification
- **Backend pytest suite**:
  ```bash
  cd edxso-ai/backend && .venv/bin/pytest -v
  ```
- **Frontend unit tests**:
  ```bash
  cd edxso-ai/frontend && npm test -- --run
  ```
- **Playwright E2E tests** (against clean ephemeral DB):
  ```bash
  cd edxso-ai/frontend && npx playwright test --reporter=list
  ```

---

## Documentation Index
- [System Architecture](docs/architecture.md)
- [Technical Note](docs/technical-note.md)
- [Data Compliance & Ethical Access](docs/data-compliance.md)
- [Evaluation Methodology](docs/evaluation.md)
- [Live Operational Walkthrough](docs/demo-script.md)
- [Deployment Guide](docs/deployment.md)
- [Discovery Root-Cause Audit](docs/discovery-audit.md)
- [Requirements Traceability Matrix](REQUIREMENTS_TRACEABILITY.md)

---

## Known Limitations & Credential Requirements
1. External licensed B2B data API retrieval requires valid operator credentials (`LICENSED_DATA_API_URL`, `LICENSED_DATA_API_KEY`). Without them, `licensed_api` reports `Credentials Required`, while `organization_website` and `public_directory` retrieve live profiles from permitted public K-12 school/consultancy websites and directories (when `EDXSO_ENABLE_DEFAULT_PUBLIC_WEB_SOURCES=true`, or whenever custom permitted URLs are supplied).
2. Automated access to LinkedIn (`linkedin.com`, `lnkd.in`), auth-walled pages, or CAPTCHA-protected sites is strictly prohibited and blocked. Real LinkedIn profile links enter only where published on permitted official websites/directories, via user-authorized CRM/CSV uploads, or through licensed data APIs.
3. Optional LLM enrichment (`OPENAI_API_KEY` / `GEMINI_API_KEY`) enhances reference parsing when configured; deterministic local NLP extraction runs without external keys.
