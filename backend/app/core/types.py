import uuid
from typing import Any, Optional
from pgvector.sqlalchemy import Vector
from sqlalchemy import CHAR, JSON, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID


class GUID(TypeDecorator):
    """Platform-independent GUID type: PostgreSQL UUID, SQLite CHAR(36)."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value: Any, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value: Any, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class PortableJSON(TypeDecorator):
    """PostgreSQL JSONB, SQLite JSON."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB(astext_type=None))
        return dialect.type_descriptor(JSON())


class EmbeddingVector(TypeDecorator):
    """PostgreSQL pgvector Vector(dim), SQLite JSON float array."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: Optional[int] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect):
        if value is None:
            return None
        return [float(x) for x in value]

    def process_result_value(self, value: Any, dialect):
        if value is None:
            return None
        return [float(x) for x in value]
