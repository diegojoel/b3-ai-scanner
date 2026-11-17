"""asset open position field

Revision ID: 0003_asset_open_position
Revises: 0002_asset_liquidity_fields
Create Date: 2026-05-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_asset_open_position"
down_revision = "0002_asset_liquidity_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_columns = _asset_columns()
    if "has_open_position" not in existing_columns:
        op.add_column(
            "assets",
            sa.Column("has_open_position", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    existing_columns = _asset_columns()
    if "has_open_position" in existing_columns:
        op.drop_column("assets", "has_open_position")


def _asset_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("assets")}
