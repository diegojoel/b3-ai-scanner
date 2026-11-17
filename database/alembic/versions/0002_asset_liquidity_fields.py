"""asset liquidity fields

Revision ID: 0002_asset_liquidity_fields
Revises: 0001_initial_schema
Create Date: 2026-05-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_asset_liquidity_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_columns = _asset_columns()
    _add_column_if_missing(existing_columns, sa.Column("asset_type", sa.String(length=24), nullable=False, server_default="STOCK"))
    _add_column_if_missing(existing_columns, sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    _add_column_if_missing(existing_columns, sa.Column("is_bdr", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column_if_missing(existing_columns, sa.Column("is_etf", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column_if_missing(existing_columns, sa.Column("is_fii", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_column_if_missing(
        existing_columns,
        sa.Column("is_under_judicial_recovery", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing(
        existing_columns,
        sa.Column("has_special_trading_condition", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing(existing_columns, sa.Column("liquidity_score", sa.Float(), nullable=True))
    _add_column_if_missing(existing_columns, sa.Column("average_daily_financial_volume_30d", sa.Float(), nullable=True))
    _add_column_if_missing(existing_columns, sa.Column("average_daily_traded_shares_30d", sa.Float(), nullable=True))
    _add_column_if_missing(existing_columns, sa.Column("trading_frequency_12m", sa.Float(), nullable=True))

    op.execute("UPDATE assets SET is_active = active WHERE is_active IS NULL")


def downgrade() -> None:
    existing_columns = _asset_columns()
    for column_name in (
        "trading_frequency_12m",
        "average_daily_traded_shares_30d",
        "average_daily_financial_volume_30d",
        "liquidity_score",
        "has_special_trading_condition",
        "is_under_judicial_recovery",
        "is_fii",
        "is_etf",
        "is_bdr",
        "is_active",
        "asset_type",
    ):
        if column_name in existing_columns:
            op.drop_column("assets", column_name)


def _asset_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("assets")}


def _add_column_if_missing(existing_columns: set[str], column: sa.Column) -> None:
    if column.name not in existing_columns:
        op.add_column("assets", column)
        existing_columns.add(column.name)
