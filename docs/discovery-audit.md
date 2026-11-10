# Discovery Pipeline Audit (`docs/discovery-audit.md`)

**Audit Date**: 2026-11-11  
**Issue Reported**: Clicking "View Results" on a normal discovery run displays synthetic benchmark profiles (`Meera Srinivasan-Demo`, `Arjun Rathore-Demo`, `Deccan Cedar Public Schools Trust (Synthetic)`) originating from `edxso_curated_synthetic_benchmark_v1` (110 synthetic profiles) instead of real professional discovery results.

---

## Verified Root Causes (Code Inspection)

### 1. Discovery Pipeline Unconditionally Queries `shared_benchmark` (`backend/app/discovery/pipeline.py:156-163`)
In `execute_discovery_pipeline`, Stage 5 (`CANDIDATE_RETRIEVAL`) executes:
```python
cand_query = db.query(CandidateProfile).filter(
    CandidateProfile.deleted_at.is_(None),
    CandidateProfile.is_duplicate_of.is_(None),
    or_(
        CandidateProfile.visibility == "shared_benchmark",
        CandidateProfile.owner_id == job.owner_id,
    ),
)
```
Because `scripts/seed_dataset.py` seeds all 110 records from `dataset/demo_profiles.csv` (`edxso_curated_synthetic_benchmark_v1`) with `visibility="shared_benchmark"` and `verification_status="synthetic"`, **every discovery job always includes all 110 synthetic benchmark profiles** in its retrieval pool, regardless of user intent.

### 2. Missing Data Environment Separation (`backend/app/models/profile.py` & `discovery.py`)
- `CandidateProfile` only tracks `visibility` (`shared_benchmark` | `private`) and `verification_status` (`verified` | `unverified` | `synthetic`). There is no `dataset_type` column distinguishing `REAL_DATA`, `USER_PROVIDED`, and `SYNTHETIC_BENCHMARK`.
- `DiscoveryJob` has no `discovery_mode` / `dataset_type` or `selected_sources` fields, so `POST /api/discovery` (`backend/app/api/discovery.py`) cannot restrict retrieval to real external providers, user-uploaded datasets, or synthetic benchmark mode.

### 3. Frontend Defaults to Undifferentiated Discovery (`frontend/app/(app)/discovery/new/page.tsx`)
- The New Discovery interface submits only `reference_profile_id` to `POST /api/discovery` (lines 148–153) with no **Discovery Mode** selector (`Real Professional Discovery`, `Uploaded Dataset`, `Synthetic Benchmark`) and no source/provider selection UI.
- Clicking "View Results" on `frontend/app/(app)/discovery/[jobId]/page.tsx` routes to `/discovery/[jobId]/results`, which queries `GET /api/discovery/{job_id}/results`—and since the persisted `DiscoveryResult` rows were generated from the `shared_benchmark` pool, synthetic `-Demo` records appear as normal results.

### 4. Real External Adapters Are Not Executed During Discovery (`backend/app/data_sources/` & `pipeline.py`)
- `AuthorizedAPIAdapter`, `PublicDirectoryAdapter`, `OrganizationWebsiteAdapter`, and `CRMAdapter` exist as ingestion classes in `backend/app/data_sources/`, but `execute_discovery_pipeline` never queries configured real providers before semantic retrieval.
- When no real profiles exist in the database, `pipeline.py:174` raises `ValueError("No eligible candidates found in database...")` (marking the job `FAILED`) rather than completing cleanly with an honest empty state in `REAL_DATA` / `USER_PROVIDED` modes.

### 5. Candidate Directory & Dashboard Analytics Mix Benchmark & User Data (`candidates.py`, `analytics.py`)
- `GET /api/candidates` (`backend/app/api/candidates.py:35-42`) and `GET /api/analytics/dashboard` (`backend/app/api/analytics.py:20-31`) both pull `visibility == "shared_benchmark"` together with private user records without filtering by `dataset_type`.

### 6. Real LinkedIn Profiles & Compliance Boundary
- Unauthorized LinkedIn scraping, session cookie reuse, or authentication bypass is strictly prohibited by policy and LinkedIn Terms of Service.
- Real LinkedIn-linked professional profiles can only enter `REAL_DATA` or `USER_PROVIDED` legitimately through:
  1. **Configured Licensed Professional Data APIs** (`LICENSED_DATA_API_URL` + `LICENSED_DATA_API_KEY`, e.g., authorized enrichment/B2B data APIs).
  2. **User-Authorized CSV / CRM Exports** uploaded via `/datasets/import` (where the user provides lawfully exported CSV/CRM data containing sourced `linkedin_url` values).
  3. **Permitted Public Education Directories & Official School Websites** explicitly configured by an administrator.

---

## Remediation Plan
1. Add `dataset_type` (`REAL_DATA`, `USER_PROVIDED`, `SYNTHETIC_BENCHMARK`) to `candidate_profiles`, `discovery_mode` & `selected_sources` & `provider_diagnostics` to `discovery_jobs`, and `relevance_score`/`evidence_confidence` inspection fields cleanly via Alembic migration `0002_separate_data_environments.py` (preserving all 110 benchmark profiles).
2. Wire `AuthorizedAPIAdapter`, `PublicDirectoryAdapter`, `OrganizationWebsiteAdapter`, `CRMAdapter`, `CSVAdapter`, and `ManualProfileAdapter` into a dedicated `backend/app/services/real_discovery.py` orchestrator invoked by `execute_discovery_pipeline` when `discovery_mode == "REAL_DATA"`.
3. Enforce strict mode isolation in `pipeline.py`, `candidates.py`, `analytics.py`, and `discovery.py`:
   - `REAL_DATA`: retrieves ONLY `dataset_type == "REAL_DATA"` (never `SYNTHETIC_BENCHMARK`), plus triggers live fetch from authorized external providers if configured. If 0 real candidates are found, job completes cleanly with `0` results and surfaces the honest empty state.
   - `USER_PROVIDED`: retrieves ONLY `dataset_type == "USER_PROVIDED"` owned by `job.owner_id` (or `REAL_DATA` if explicitly included via `selected_sources`), never `SYNTHETIC_BENCHMARK`.
   - `SYNTHETIC_BENCHMARK`: explicitly runs benchmark evaluation against `dataset_type == "SYNTHETIC_BENCHMARK"` (110 synthetic profiles) and displays a persistent synthetic warning.
5. Add `GET /api/discovery/providers`, `POST /api/candidates/fetch-url`, and real-data HTML/JSON extraction.

---

## Final Real-Data-Only Resolution (Applied)
Per the subsequent strict real-data-only directive:
- All synthetic datasets (`dataset/demo_profiles.csv`, `dataset/benchmark_labels.csv`), synthetic generators/seeders (`scripts/generate_benchmark_dataset.py`, `scripts/seed_dataset.py`), and `SYNTHETIC_BENCHMARK` modes/badges/endpoints were permanently **removed**.
- Alembic migration `0003_remove_synthetic_data.py` cleaned all synthetic candidates, organizations, labels, evaluation runs, discovery jobs, results, and seeded demo reference archetypes from the database while preserving genuine users, auth sessions, user-created reference profiles, real data sources, system config, and audit logs.
