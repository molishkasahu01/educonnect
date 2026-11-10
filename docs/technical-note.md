# Technical Note — EDXSO School Influencer Intelligence

## 1. System Architecture
EDXSO separates UI presentation (Next.js App Router + TypeScript + Tailwind), REST API orchestration (FastAPI + Pydantic), asynchronous job execution (Celery + Redis, with a database-backed ThreadPool fallback), and relational + vector persistence (PostgreSQL 16 + `pgvector` or SQLite local runtime). All synthetic and mock datasets have been removed; EDXSO processes strictly real, verified, or user-authorized professional records.

## 2. Compliant Real-Data Retrieval & Profile Normalization
Six authorized ingestion adapters normalize real records into `NormalizedCandidateRecord`:
- `OrganizationWebsiteAdapter`: Fetches permitted official school websites, school-group leadership pages, and education consultancy pages respecting `robots.txt` (RFC-9309 check + redirect safety check blocking `linkedin.com`/`lnkd.in` on redirect targets) via JSON, `schema.org/Person` JSON-LD, and a DOM-tree single-person card extractor supporting multi-heading Elementor, list-item, and team-card layouts plus canonical `/in/` link extraction when explicitly published inside a card.
- `PublicDirectoryAdapter`: Indexes permitted public education association directories and conference speaker directories with explicit `source_url` provenance and deterministic per-URL record IDs.
- `AuthorizedAPIAdapter`: Integrates external licensed B2B professional data APIs (`LICENSED_DATA_API_URL` + `LICENSED_DATA_API_KEY`).
- `CSVAdapter`, `CRMAdapter`, and `ManualProfileAdapter`: Ingest user-authorized CSV/CRM partner exports and manual records after explicit compliance confirmation. Any record marked `synthetic` is rejected (`400 Bad Request` / skipped).

In standard runtime (`EDXSO_ENABLE_DEFAULT_PUBLIC_WEB_SOURCES=true`), `real_discovery.py` concurrently retrieves from 7 curated `robots.txt`-compliant K-12 education directories and leadership websites (`indianprincipals.com`, `egnconnectx.com`, `theschoolsofindia.org`, `lifeeducare.com`, `globalindianschool.org`, and `pratham.org`), deduplicating across sources (merging initial spacing variants like `S. K.` vs `SK` and shared organization tokens) and populating factual `school_indicators` directly from observed profile text. Canonical professional text is built via `build_normalized_professional_document` across role, organization, location, bio, career history, education segments, school indicators, organizations, skills, and influence indicators.

## 3. Embedding Generation & Semantic Retrieval
- Normalized documents are encoded via `SentenceTransformer` (`BAAI/bge-small-en-v1.5`, 384 dimensions by default; configurable to `BAAI/bge-m3` 1024 dimensions).
- Vectors are persisted alongside SHA-256 `document_hash` in `profile_embeddings` and queried with `pgvector` cosine distance on PostgreSQL (`HNSW vector_cosine_ops`) or exact NumPy cosine on SQLite.

## 4. Hybrid Ranking & Calibrated Evidence Confidence
Candidates are scored on six 0–100 normalized dimensions:
$$\text{Score} = \frac{\sum_{i \in \text{available}} w_i \cdot s_i}{\sum_{i \in \text{available}} w_i}$$
Default weights: Semantic `0.30`, School Ecosystem `0.25`, Role `0.15`, Experience `0.10`, Organization Network `0.10`, Influence `0.10`.
- **Missing-Evidence Awareness**: Omitted attributes are excluded from the denominator rather than penalized as zero overlap.
- **Independent Calibrated Evidence Confidence**: Computed separately from relevance score using core completeness (`0.26`), attribute depth (`0.24`), matched attribute density (`0.15`), source data confidence (`0.15`), verification status & source URL presence (`0.12`), and record freshness (`0.08`).
- **Minimum-Evidence Guardrail**: Sparse profiles lacking 3 available components or 2 core fields are damped (`×0.65`) and confidence-capped at `42%`.
- **Zero Fabricated Padding**: If 0 real candidates match, discovery completes honestly with 0 results (`"No verified or authorized professional profiles were found for this discovery. Connect an authorized source or import genuine professional records."`). If fewer than 20 candidates exist, only those genuine candidates are returned.

## 5. Limitations
1. Pages behind login gates, `robots.txt` `Disallow` directives, or Cloudflare/CAPTCHA challenges are skipped without bypass and reported in `provider_diagnostics.errors`.
2. Automated LinkedIn scraping is disabled across all layers (`linkedin.com`, `lnkd.in`).
3. Admin IR evaluation (`/api/admin/evaluation/run`) requires human-labeled genuine evaluation pairs stored in `benchmark_labels`; EDXSO never reports fabricated evaluation metrics.
