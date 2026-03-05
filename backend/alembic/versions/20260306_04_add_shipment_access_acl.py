"""add shipment access acl table

Revision ID: 20260306_04
Revises: 20260306_03
Create Date: 2026-03-06 23:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260306_04"
down_revision: Union[str, Sequence[str], None] = "20260306_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type(bind) -> sa.types.TypeEngine:
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def upgrade() -> None:
    bind = op.get_bind()
    uuid_type = _uuid_type(bind)

    op.create_table(
        "shipment_access",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("shipment_id", uuid_type, nullable=False),
        sa.Column("user_id", uuid_type, nullable=False),
        sa.Column("access_role", sa.String(), nullable=False, server_default="viewer"),
        sa.Column("granted_by", uuid_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shipment_id", "user_id", name="uq_shipment_access_shipment_user"),
    )
    op.create_index("ix_shipment_access_shipment_id", "shipment_access", ["shipment_id"], unique=False)
    op.create_index("ix_shipment_access_user_id", "shipment_access", ["user_id"], unique=False)
    op.create_index("ix_shipment_access_access_role", "shipment_access", ["access_role"], unique=False)
    op.create_index("ix_shipment_access_granted_by", "shipment_access", ["granted_by"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_shipment_access_granted_by", table_name="shipment_access")
    op.drop_index("ix_shipment_access_access_role", table_name="shipment_access")
    op.drop_index("ix_shipment_access_user_id", table_name="shipment_access")
    op.drop_index("ix_shipment_access_shipment_id", table_name="shipment_access")
    op.drop_table("shipment_access")

