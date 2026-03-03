"""create documents table for agentic rag

Revision ID: 20260303_01
Revises: 20260302_01
Create Date: 2026-03-03 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260303_01"
down_revision: Union[str, Sequence[str], None] = "20260302_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata JSONB,
            embedding VECTOR(1536),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS documents_embedding_idx "
        "ON documents USING ivfflat (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS documents_tenant_device_idx "
        "ON documents (tenant_id, device_id)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS documents_tenant_device_idx")
    op.execute("DROP INDEX IF EXISTS documents_embedding_idx")
    op.execute("DROP TABLE IF EXISTS documents")
