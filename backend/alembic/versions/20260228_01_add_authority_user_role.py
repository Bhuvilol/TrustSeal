"""add authority value to user role enum

Revision ID: 20260228_01
Revises: 20260216_01
Create Date: 2026-02-28 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260228_01"
down_revision: Union[str, Sequence[str], None] = "20260226_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_enum
                        WHERE enumlabel = 'authority'
                          AND enumtypid = 'userrole'::regtype
                    ) THEN
                        ALTER TYPE userrole ADD VALUE 'authority';
                    END IF;
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely without type recreation.
    pass
