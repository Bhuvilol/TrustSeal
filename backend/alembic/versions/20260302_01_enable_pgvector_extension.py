"""enable pgvector extension

Revision ID: 20260302_01
Revises: 20260228_01
Create Date: 2026-03-02 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260302_01"
down_revision: Union[str, Sequence[str], None] = "20260228_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # Keep extension in place because other schemas may depend on it.
    pass
