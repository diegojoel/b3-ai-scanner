from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db.base import Base
from app import models  # noqa: F401


def create_local_schema(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        _ensure_sqlite_asset_columns(engine)
    elif engine.dialect.name == "postgresql":
        _ensure_postgres_asset_columns(engine)


def _ensure_sqlite_asset_columns(engine: Engine) -> None:
    existing = {column["name"] for column in inspect(engine).get_columns("assets")}
    columns = {
        "asset_type": "VARCHAR(24) DEFAULT 'STOCK' NOT NULL",
        "is_active": "BOOLEAN DEFAULT 1 NOT NULL",
        "is_bdr": "BOOLEAN DEFAULT 0 NOT NULL",
        "is_etf": "BOOLEAN DEFAULT 0 NOT NULL",
        "is_fii": "BOOLEAN DEFAULT 0 NOT NULL",
        "is_under_judicial_recovery": "BOOLEAN DEFAULT 0 NOT NULL",
        "has_special_trading_condition": "BOOLEAN DEFAULT 0 NOT NULL",
        "has_open_position": "BOOLEAN DEFAULT 0 NOT NULL",
        "liquidity_score": "FLOAT",
        "average_daily_financial_volume_30d": "FLOAT",
        "average_daily_traded_shares_30d": "FLOAT",
        "trading_frequency_12m": "FLOAT",
    }
    with engine.begin() as connection:
        for name, ddl in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE assets ADD COLUMN {name} {ddl}"))
        if "is_active" not in existing:
            connection.execute(text("UPDATE assets SET is_active = active"))


def _ensure_postgres_asset_columns(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS has_open_position BOOLEAN DEFAULT FALSE NOT NULL")
        )
