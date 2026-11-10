"""Remove all synthetic, benchmark, and seeded demo-archetype data while preserving genuine user records

Revision ID: 0003_remove_synthetic_data
Revises: 0002_separate_data_environments
Create Date: 2026-11-11 00:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003_remove_synthetic_data"
down_revision: Union[str, None] = "0002_separate_data_environments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SYN_CAND_PRED = (
    "verification_status = 'synthetic' "
    "OR dataset_type = 'SYNTHETIC_BENCHMARK' "
    "OR visibility = 'shared_benchmark' "
    "OR primary_source = 'edxso_curated_synthetic_benchmark_v1'"
)

_SYN_REF_PRED = (
    "full_name IN ("
    "  'Dr. Kavita Narayanan (Demo Reference Archetype)',"
    "  'Dr. Kavita Narayanan (Benchmark Reference)',"
    "  'Dr. Kavita Narayanan (Audit Ref)'"
    ")"
)


def upgrade() -> None:
    # 1. Remove ranking artifacts & discovery results linked to synthetic candidates or synthetic jobs
    op.execute(
        sa.text(
            "DELETE FROM ranking_scores WHERE discovery_result_id IN ("
            "  SELECT id FROM discovery_results WHERE candidate_id IN "
            f"  (SELECT id FROM candidate_profiles WHERE {_SYN_CAND_PRED}) "
            "  OR discovery_job_id IN "
            "  (SELECT id FROM discovery_jobs WHERE discovery_mode = 'SYNTHETIC_BENCHMARK')"
            ")"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM ranking_explanations WHERE discovery_result_id IN ("
            "  SELECT id FROM discovery_results WHERE candidate_id IN "
            f"  (SELECT id FROM candidate_profiles WHERE {_SYN_CAND_PRED}) "
            "  OR discovery_job_id IN "
            "  (SELECT id FROM discovery_jobs WHERE discovery_mode = 'SYNTHETIC_BENCHMARK')"
            ")"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM discovery_results WHERE candidate_id IN "
            f"(SELECT id FROM candidate_profiles WHERE {_SYN_CAND_PRED}) "
            "OR discovery_job_id IN "
            "(SELECT id FROM discovery_jobs WHERE discovery_mode = 'SYNTHETIC_BENCHMARK')"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM saved_list_profiles WHERE candidate_id IN "
            f"(SELECT id FROM candidate_profiles WHERE {_SYN_CAND_PRED})"
        )
    )

    # 2. Remove synthetic evaluation runs & labels
    op.execute(
        sa.text(
            "DELETE FROM benchmark_labels WHERE candidate_source_record_id LIKE 'syn-%' "
            f"OR candidate_id IN (SELECT id FROM candidate_profiles WHERE {_SYN_CAND_PRED})"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM evaluation_runs WHERE benchmark_name = 'k12_senior_consultant_benchmark_v1' "
            "OR LOWER(dataset_disclaimer) LIKE '%synthetic%'"
        )
    )

    # 3. Remove child evidence/embedding/source records of synthetic candidates
    for child_tbl in ("profile_embeddings", "profile_indicators", "profile_sources", "profile_experiences"):
        op.execute(
            sa.text(
                f"DELETE FROM {child_tbl} WHERE candidate_id IN "
                f"(SELECT id FROM candidate_profiles WHERE {_SYN_CAND_PRED})"
            )
        )

    # 4. Remove synthetic candidates & synthetic discovery jobs
    op.execute(sa.text(f"DELETE FROM candidate_profiles WHERE {_SYN_CAND_PRED}"))
    op.execute(sa.text("DELETE FROM discovery_jobs WHERE discovery_mode = 'SYNTHETIC_BENCHMARK'"))

    # 5. Remove seeded demo archetype reference profiles & their dependent rows (preserve genuine user refs)
    op.execute(
        sa.text(
            "DELETE FROM ranking_scores WHERE discovery_result_id IN ("
            "  SELECT id FROM discovery_results WHERE discovery_job_id IN ("
            f"    SELECT id FROM discovery_jobs WHERE reference_profile_id IN (SELECT id FROM reference_profiles WHERE {_SYN_REF_PRED})"
            "  )"
            ")"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM ranking_explanations WHERE discovery_result_id IN ("
            "  SELECT id FROM discovery_results WHERE discovery_job_id IN ("
            f"    SELECT id FROM discovery_jobs WHERE reference_profile_id IN (SELECT id FROM reference_profiles WHERE {_SYN_REF_PRED})"
            "  )"
            ")"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM discovery_results WHERE discovery_job_id IN ("
            f"  SELECT id FROM discovery_jobs WHERE reference_profile_id IN (SELECT id FROM reference_profiles WHERE {_SYN_REF_PRED})"
            ")"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM discovery_jobs WHERE reference_profile_id IN ("
            f"  SELECT id FROM reference_profiles WHERE {_SYN_REF_PRED}"
            ")"
        )
    )
    for child_tbl in ("profile_embeddings", "profile_indicators", "profile_experiences"):
        op.execute(
            sa.text(
                f"DELETE FROM {child_tbl} WHERE reference_profile_id IN "
                f"(SELECT id FROM reference_profiles WHERE {_SYN_REF_PRED})"
            )
        )
    op.execute(sa.text(f"DELETE FROM reference_profiles WHERE {_SYN_REF_PRED}"))

    # 6. Remove synthetic organizations and synthetic benchmark data source entry
    op.execute(sa.text("DELETE FROM organizations WHERE is_synthetic = :val").bindparams(val=True))
    op.execute(sa.text("DELETE FROM data_sources WHERE name = 'edxso_curated_synthetic_benchmark_v1'"))


def downgrade() -> None:
    # Irreversible data cleanup: synthetic records must not be restored automatically.
    pass
