# Data Compliance & Ethical Access Policy

## Guiding Principles
1. **Strictly Real-Data-Only Platform**: EDXSO stores, indexes, and ranks exclusively real, verified, or user-authorized professional records (`dataset_type IN ('REAL_DATA', 'USER_PROVIDED')`, `verification_status IN ('verified', 'unverified')`). All synthetic, fictional, simulated, and mock data paths have been permanently removed.
2. **Zero Unauthorized Scraping & Anti-Bot Compliance**:
   - EDXSO never scrapes LinkedIn (`linkedin.com`, `lnkd.in`), circumvents authentication walls, solves or bypasses CAPTCHAs/Turnstile gates, or harvests session cookies.
   - All live URL fetches (`fetch_permitted_public_url`) check `robots.txt` before retrieval and abort cleanly with explicit permission errors on `401`/`403`, `Disallow` directives, or anti-bot challenges.
3. **LinkedIn URL Policy**:
   - Reference profiles treat LinkedIn URLs solely as reference identifiers; if supplied without structured bio/role context, analysis halts with `NEEDS_MORE_INFO`.
   - Real candidate LinkedIn links enter EDXSO legitimately only where published on permitted official school/consultancy websites or public directories, via user-authorized CSV/CRM partner exports (`USER_PROVIDED`), or through properly licensed B2B data APIs (`REAL_DATA`).
4. **Honest Empty-State & Unpadded Results**:
   - When 0 real/authorized profiles match a discovery query, jobs complete cleanly with 0 results and surface: `"No verified or authorized professional profiles were found for this discovery. Connect an authorized source or import genuine professional records."`
   - When fewer than 20 real profiles exist, only the real discovered records are returned (never padded with fabricated profiles).
5. **Verified vs. Unverified Provenance Distinction**:
   - Every candidate stores `source_name`, `source_url`, `source_record_id`, `collection_timestamp`, `verification_status` (`verified` vs `unverified`), `dataset_type` (`REAL_DATA` vs `USER_PROVIDED`), `data_confidence`, `data_freshness_days`, `usage_restrictions`, and `upload_authorization_note`.
6. **Privacy Controls**: Users can inspect, export (`GET /api/auth/me/export`), configure retention windows, or soft-delete (`DELETE /api/auth/me`) their account and private uploads at any time.
