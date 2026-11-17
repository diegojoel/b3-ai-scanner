"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sector", sa.String(length=120), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assets_ticker"), "assets", ["ticker"], unique=True)

    for table_name in ("candles_daily", "candles_weekly"):
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("open", sa.Float(), nullable=False),
            sa.Column("high", sa.Float(), nullable=False),
            sa.Column("low", sa.Float(), nullable=False),
            sa.Column("close", sa.Float(), nullable=False),
            sa.Column("volume", sa.Float(), nullable=False),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", "date"),
            sa.UniqueConstraint("asset_id", "date", name=f"uq_{table_name}_asset_date"),
        )
        op.create_index(op.f(f"ix_{table_name}_asset_id"), table_name, ["asset_id"], unique=False)
        op.create_index(op.f(f"ix_{table_name}_date"), table_name, ["date"], unique=False)
        op.execute(
            f"SELECT create_hypertable('{table_name}', 'date', if_not_exists => TRUE, migrate_data => TRUE)"
        )

    for table_name in ("indicators_daily", "indicators_weekly"):
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("sma20", sa.Float(), nullable=True),
            sa.Column("sma50", sa.Float(), nullable=True),
            sa.Column("sma200", sa.Float(), nullable=True),
            sa.Column("atr14", sa.Float(), nullable=True),
            sa.Column("rsi14", sa.Float(), nullable=True),
            sa.Column("volume_ratio", sa.Float(), nullable=True),
            sa.Column("breakout_20", sa.Boolean(), nullable=False),
            sa.Column("high_52w_distance", sa.Float(), nullable=True),
            sa.Column("relative_strength", sa.Float(), nullable=True),
            sa.Column("pullback_sma20", sa.Boolean(), nullable=False),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id", "date"),
            sa.UniqueConstraint("asset_id", "date", name=f"uq_{table_name}_asset_date"),
        )
        op.create_index(op.f(f"ix_{table_name}_asset_id"), table_name, ["asset_id"], unique=False)
        op.create_index(op.f(f"ix_{table_name}_date"), table_name, ["date"], unique=False)
        op.execute(
            f"SELECT create_hypertable('{table_name}', 'date', if_not_exists => TRUE, migrate_data => TRUE)"
        )

    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("signal_date", sa.Date(), nullable=False),
        sa.Column("setup_type", sa.String(length=40), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_loss", sa.Float(), nullable=False),
        sa.Column("target_1", sa.Float(), nullable=False),
        sa.Column("target_2", sa.Float(), nullable=False),
        sa.Column("risk_reward", sa.Float(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "signal_date", "setup_type", name="uq_signal_asset_date_setup"),
    )
    op.create_index(op.f("ix_signals_asset_id"), "signals", ["asset_id"], unique=False)
    op.create_index(op.f("ix_signals_signal_date"), "signals", ["signal_date"], unique=False)

    op.create_table(
        "backtest_results",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("strategy_name", sa.String(length=80), nullable=False),
        sa.Column("started_at", sa.Date(), nullable=False),
        sa.Column("ended_at", sa.Date(), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("average_r", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_backtest_results_asset_id"), "backtest_results", ["asset_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_backtest_results_asset_id"), table_name="backtest_results")
    op.drop_table("backtest_results")
    op.drop_index(op.f("ix_signals_signal_date"), table_name="signals")
    op.drop_index(op.f("ix_signals_asset_id"), table_name="signals")
    op.drop_table("signals")
    for table_name in ("indicators_weekly", "indicators_daily", "candles_weekly", "candles_daily"):
        op.drop_index(op.f(f"ix_{table_name}_date"), table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_asset_id"), table_name=table_name)
        op.drop_table(table_name)
    op.drop_index(op.f("ix_assets_ticker"), table_name="assets")
    op.drop_table("assets")
