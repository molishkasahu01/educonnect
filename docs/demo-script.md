# EDXSO — Live Real-Data Operational Walkthrough

## Prerequisites
- Backend running (`uvicorn app.main:app --host 127.0.0.1 --port 8010`, DB migrated cleanly to `0003_remove_synthetic_data` and bootstrapped with `scripts/bootstrap_db.py`)
- Frontend built and running (`NEXT_PUBLIC_API_URL=http://127.0.0.1:8010`)
- Real authorized data sources prepared: permitted official school/consultancy URLs, conference speaker directory URLs, an authorized CSV/CRM export, or licensed API credentials (`LICENSED_DATA_API_URL`, `LICENSED_DATA_API_KEY`).

## Step-by-Step Walkthrough

1. **Authentication & Clean Real-Only Dashboard (1 min)**
   - Sign in on `/login` or register a new workspace analyst on `/register`.
   - Confirm `/dashboard` and `/analytics` display genuine SQL metrics from the database (`0` profiles / `0` jobs if no real candidates have been ingested yet).

2. **Connect Authorized Real Data Sources (2 min)**
   - Open **Data Sources** (`/datasets/sources`) to inspect live adapter status (`OrganizationWebsiteAdapter`, `PublicDirectoryAdapter`, `AuthorizedAPIAdapter`, `CSVAdapter`, `ManualProfileAdapter`) and ethical compliance boundaries (`linkedin.com` and `lnkd.in` blocked).
   - Open **Dataset Import** (`/datasets/import`) and either:
     - Fetch real profiles from permitted school/consultancy/conference URLs (`POST /api/candidates/fetch-url`), or
     - Upload an authorized CSV/CRM partner export with explicit consent confirmation (`POST /api/candidates/import`).

3. **Reference Profile Analysis (1.5 min)**
   - Navigate to **New Discovery** (`/discovery/new`).
   - Supply a genuine reference K-12 leader profile (designation, bio, career dates, skills) and click **ANALYZE REFERENCE PROFILE**.
   - Inspect extracted `OBSERVED FACT`, `AI-DERIVED CLASSIFICATION`, and `MISSING INFORMATION` badges alongside the 19 school ecosystem indicators.

4. **Discovery Mode Selection & Execution (2 min)**
   - Choose **Real External Sources** (`REAL_DATA`), **Authorized Uploads** (`USER_PROVIDED`), or **All Authorized Sources** (`ALL_AUTHORIZED`), optionally supplying additional permitted directory/school URLs (curated permitted public K-12 directories and consultancy pages run automatically when enabled).
   - Click **Start Discovery & Hybrid Ranking** and observe the asynchronous stage tracker (`/discovery/[jobId]`).
   - If zero real profiles exist when all live/uploaded sources are disabled or empty, the job completes cleanly with the honest empty-state notice (`"No verified or authorized professional profiles were found for this discovery. Connect an authorized source or import genuine professional records."`).

5. **Ranked Results, Provenance & Exports (2.5 min)**
   - Open **View Ranked Results** (`/discovery/[jobId]/results`).
   - Verify `VERIFIED REAL` vs `UNVERIFIED REAL` provenance badges, separate **Relevance Score** and calibrated **Evidence Confidence**, expandable **Score Breakdown**, role/location filters, sorting, and **Shortlist**.
   - Click **Inspect** on a candidate (`/candidates/[id]`) to verify attribute-level classification (`OBSERVED FACT`, `SOURCE-SUPPORTED FACT`, `AI-DERIVED CLASSIFICATION`, `UNVERIFIED INFORMATION`) and source URL/restrictions.
   - Export ranked results via **Export CSV**, **Export XLSX**, or **Export JSON**.
