"""asset fundamentals

Revision ID: 0004_asset_fundamentals
Revises: 0003_asset_open_position
Create Date: 2026-05-22 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_asset_fundamentals"
down_revision = "0003_asset_open_position"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if _table_exists("asset_fundamentals"):
        return

    op.create_table(
        "asset_fundamentals",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="manual"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="BRL"),
        sa.Column("net_debt_ebitda", sa.Float(), nullable=True),
        sa.Column("ebitda_margin", sa.Float(), nullable=True),
        sa.Column("current_ratio", sa.Float(), nullable=True),
        sa.Column("free_cash_flow_yield", sa.Float(), nullable=True),
        sa.Column("cash_burn_ratio", sa.Float(), nullable=True),
        sa.Column("roe", sa.Float(), nullable=True),
        sa.Column("revenue_growth_yoy", sa.Float(), nullable=True),
        sa.Column("ebitda_growth_yoy", sa.Float(), nullable=True),
        sa.Column("profit_quality_score", sa.Float(), nullable=True),
        sa.Column("default_or_restructuring_risk", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("going_concern_risk", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dilution_risk", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fiscal_benefit_dependency", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "period_date", "source", name="uq_asset_fundamentals_asset_period_source"),
    )
    op.create_index(op.f("ix_asset_fundamentals_asset_id"), "asset_fundamentals", ["asset_id"], unique=False)
    op.create_index(op.f("ix_asset_fundamentals_period_date"), "asset_fundamentals", ["period_date"], unique=False)


def downgrade() -> None:
    if _table_exists("asset_fundamentals"):
        op.drop_index(op.f("ix_asset_fundamentals_period_date"), table_name="asset_fundamentals")
        op.drop_index(op.f("ix_asset_fundamentals_asset_id"), table_name="asset_fundamentals")
        op.drop_table("asset_fundamentals")


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()
