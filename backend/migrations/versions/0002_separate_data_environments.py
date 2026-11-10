"""Separate REAL_DATA, USER_PROVIDED, and SYNTHETIC_BENCHMARK data environments

Revision ID: 0002_separate_data_environments
Revises: 0001_initial_schema
Create Date: 2026-11-11 00:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.core.types import PortableJSON

revision: str = "0002_separate_data_environments"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    return {col["name"] for col in inspector.get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    candidate_cols = _column_names(bind, "candidate_profiles")
    if "dataset_type" not in candidate_cols:
        op.add_column(
            "candidate_profiles",
            sa.Column(
                "dataset_type",
                sa.String(length=32),
                nullable=False,
                server_default="USER_PROVIDED",
            ),
        )
    if "ix_candidate_profiles_dataset_type" not in _index_names(bind, "candidate_profiles"):
        op.create_index(
            "ix_candidate_profiles_dataset_type",
            "candidate_profiles",
            ["dataset_type"],
            unique=False,
        )

    # Backfill synthetic benchmark candidates accurately without deleting records
    op.execute(
        sa.text(
            "UPDATE candidate_profiles SET dataset_type = 'SYNTHETIC_BENCHMARK' "
            "WHERE verification_status = 'synthetic' OR visibility = 'shared_benchmark'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE candidate_profiles SET dataset_type = 'USER_PROVIDED' "
            "WHERE verification_status != 'synthetic' AND visibility != 'shared_benchmark' "
            "AND (dataset_type IS NULL OR dataset_type = '')"
        )
    )

    job_cols = _column_names(bind, "discovery_jobs")
    if "discovery_mode" not in job_cols:
        op.add_column(
            "discovery_jobs",
            sa.Column(
                "discovery_mode",
                sa.String(length=32),
                nullable=False,
                server_default="REAL_DATA",
            ),
        )
    if "selected_sources" not in job_cols:
        op.add_column(
            "discovery_jobs",
            sa.Column(
                "selected_sources",
                PortableJSON(),
                nullable=False,
                server_default="[]",
            ),
        )
    if "provider_diagnostics" not in job_cols:
        op.add_column(
            "discovery_jobs",
            sa.Column(
                "provider_diagnostics",
                PortableJSON(),
                nullable=False,
                server_default="{}",
            ),
        )
    if "ix_discovery_jobs_discovery_mode" not in _index_names(bind, "discovery_jobs"):
        op.create_index(
            "ix_discovery_jobs_discovery_mode",
            "discovery_jobs",
            ["discovery_mode"],
            unique=False,
        )

    # Tag historical discovery jobs that evaluated synthetic benchmark rows accurately
    op.execute(
        sa.text(
            "UPDATE discovery_jobs SET discovery_mode = 'SYNTHETIC_BENCHMARK' "
            "WHERE EXISTS ("
            "  SELECT 1 FROM discovery_results dr "
            "  JOIN candidate_profiles cp ON cp.id = dr.candidate_id "
            "  WHERE dr.discovery_job_id = discovery_jobs.id AND cp.dataset_type = 'SYNTHETIC_BENCHMARK'"
            ")"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "ix_discovery_jobs_discovery_mode" in _index_names(bind, "discovery_jobs"):
        op.drop_index("ix_discovery_jobs_discovery_mode", table_name="discovery_jobs")
    job_cols = _column_names(bind, "discovery_jobs")
    for col in ("provider_diagnostics", "selected_sources", "discovery_mode"):
        if col in job_cols:
            op.drop_column("discovery_jobs", col)

    if "ix_candidate_profiles_dataset_type" in _index_names(bind, "candidate_profiles"):
        op.drop_index("ix_candidate_profiles_dataset_type", table_name="candidate_profiles")
    candidate_cols = _column_names(bind, "candidate_profiles")
    if "dataset_type" in candidate_cols:
        op.drop_column("candidate_profiles", "dataset_type")
