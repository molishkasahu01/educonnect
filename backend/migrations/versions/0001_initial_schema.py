"""Initial schema with all 19 EDXSO intelligence tables and pgvector extension

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-10 22:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.core.database import Base
import app.models  # noqa: F401

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    if is_pg:
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=bind)

    if is_pg:
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_profile_embeddings_vector "
                "ON profile_embeddings USING hnsw (embedding vector_cosine_ops)"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP INDEX IF EXISTS ix_profile_embeddings_vector"))
    Base.metadata.drop_all(bind=bind)
