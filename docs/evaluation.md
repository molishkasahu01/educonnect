# Evaluation Framework Methodology

## Real-Data Evaluation Policy
EDXSO evaluates ranking quality **only against genuine human-labeled non-synthetic candidate records** (`dataset_type IN ('REAL_DATA', 'USER_PROVIDED')`, `verification_status IN ('verified', 'unverified')`). All synthetic datasets, synthetic candidate profiles, and synthetic labels have been permanently removed from the codebase and database.

## Metrics & Relevance Label Treatment
When an administrator executes evaluation (`POST /api/admin/evaluation/run` or `scripts/run_evaluation.py`) against a genuine labeled dataset stored in `benchmark_labels` and an existing `ReferenceProfile`:
- **Models Compared**: Keyword-only baseline vs. Semantic similarity baseline vs. 6-factor Hybrid Ranking Model.
- **Binary Metrics** (`Precision@10`, `Precision@20`, `Recall@20`, `MRR`): `RELEVANT = 1`, `PARTIALLY_RELEVANT = 0`, `IRRELEVANT = 0`.
- **Graded Metric** (`NDCG@10`): `RELEVANT = 2`, `PARTIALLY_RELEVANT = 1`, `IRRELEVANT = 0`.

## Honest Missing-Evaluation Disclosure
If no genuine human-labeled evaluation dataset is present in the database, `POST /api/admin/evaluation/run` returns HTTP `404` (`"No genuine labeled evaluation dataset found. Import real candidate profiles and genuine evaluation labels before running evaluation."`) and `scripts/run_evaluation.py` exits with a `"skipped"` notice. EDXSO never fabricates evaluation scores or hardcodes a benchmark reference persona.
