from datetime import date

import pandas as pd
from sqlalchemy import Select, delete, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import Session

from app.models import Asset, AssetFundamental, CandleDaily, CandleWeekly, IndicatorDaily, IndicatorWeekly, Signal


def candle_rows_to_dataframe(rows: list[CandleDaily] | list[CandleWeekly]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": row.date,
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
                "volume": row.volume,
            }
            for row in rows
        ]
    )


def get_asset_by_ticker(db: Session, ticker: str) -> Asset | None:
    return db.scalar(select(Asset).where(Asset.ticker == ticker.upper()))


def list_assets(db: Session) -> list[Asset]:
    return list(db.scalars(select(Asset).order_by(Asset.ticker)))


def ensure_asset(
    db: Session,
    ticker: str,
    name: str,
    sector: str | None = None,
    asset_type: str = "STOCK",
    is_bdr: bool = False,
    is_etf: bool = False,
    is_fii: bool = False,
    is_under_judicial_recovery: bool = False,
    has_special_trading_condition: bool = False,
) -> Asset:
    asset = get_asset_by_ticker(db, ticker)
    if asset:
        asset.name = name
        asset.sector = sector
        asset.asset_type = asset_type
        asset.is_bdr = is_bdr
        asset.is_etf = is_etf
        asset.is_fii = is_fii
        asset.is_under_judicial_recovery = is_under_judicial_recovery
        asset.has_special_trading_condition = has_special_trading_condition
        return asset
    asset = Asset(
        ticker=ticker.upper(),
        name=name,
        sector=sector,
        asset_type=asset_type,
        active=True,
        is_active=True,
        is_bdr=is_bdr,
        is_etf=is_etf,
        is_fii=is_fii,
        is_under_judicial_recovery=is_under_judicial_recovery,
        has_special_trading_condition=has_special_trading_condition,
    )
    db.add(asset)
    db.flush()
    return asset


def get_candles(db: Session, asset_id: int, timeframe: str = "1d") -> pd.DataFrame:
    model = CandleWeekly if timeframe == "1w" else CandleDaily
    rows = list(db.scalars(select(model).where(model.asset_id == asset_id).order_by(model.date)))
    return candle_rows_to_dataframe(rows)


def upsert_candles(db: Session, asset_id: int, df: pd.DataFrame, timeframe: str = "1d") -> None:
    model = CandleWeekly if timeframe == "1w" else CandleDaily
    rows = [
        {
            "asset_id": asset_id,
            "date": row.date,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
        }
        for row in df.itertuples(index=False)
    ]
    if not rows:
        return

    if db.bind and db.bind.dialect.name == "postgresql":
        _postgres_upsert_candles(db, model, rows)
        return

    for row in rows:
        candle = db.scalar(select(model).where(model.asset_id == asset_id, model.date == row["date"]))
        if candle is None:
            db.add(model(**row))
        else:
            candle.open = row["open"]
            candle.high = row["high"]
            candle.low = row["low"]
            candle.close = row["close"]
            candle.volume = row["volume"]


def replace_candles(db: Session, asset_id: int, df: pd.DataFrame, timeframe: str = "1d") -> None:
    model = CandleWeekly if timeframe == "1w" else CandleDaily
    db.execute(delete(model).where(model.asset_id == asset_id))
    rows = [
        model(
            asset_id=asset_id,
            date=row.date,
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
        )
        for row in df.itertuples(index=False)
    ]
    db.add_all(rows)


def _postgres_upsert_candles(
    db: Session,
    model: type[CandleDaily] | type[CandleWeekly],
    rows: list[dict],
) -> None:
    table = model.__table__
    stmt = postgres_insert(table).values(rows)
    update_columns = {col: getattr(stmt.excluded, col) for col in ["open", "high", "low", "close", "volume"]}
    db.execute(stmt.on_conflict_do_update(index_elements=["asset_id", "date"], set_=update_columns))


def replace_indicators(db: Session, asset_id: int, df: pd.DataFrame, timeframe: str = "1d") -> None:
    model = IndicatorWeekly if timeframe == "1w" else IndicatorDaily
    db.execute(delete(model).where(model.asset_id == asset_id))
    rows = []
    for row in df.itertuples(index=False):
        rows.append(
            model(
                asset_id=asset_id,
                date=row.date,
                sma20=_safe_float(row.sma20),
                sma50=_safe_float(row.sma50),
                sma200=_safe_float(row.sma200),
                atr14=_safe_float(row.atr14),
                rsi14=_safe_float(row.rsi14),
                volume_ratio=_safe_float(row.volume_ratio),
                breakout_20=bool(row.breakout_20),
                high_52w_distance=_safe_float(row.high_52w_distance),
                relative_strength=_safe_float(row.relative_strength),
                pullback_sma20=bool(row.pullback_sma20),
            )
        )
    db.add_all(rows)


def latest_signal_date(db: Session) -> date | None:
    return db.scalar(select(Signal.signal_date).order_by(Signal.signal_date.desc()).limit(1))


def signal_query() -> Select[tuple[Signal, str]]:
    return select(Signal, Asset.ticker).join(Asset, Signal.asset_id == Asset.id)


def upsert_signal(db: Session, asset_id: int, signal_data: dict) -> Signal:
    signal = db.scalar(
        select(Signal).where(
            Signal.asset_id == asset_id,
            Signal.signal_date == signal_data["signal_date"],
            Signal.setup_type == signal_data["setup_type"],
        )
    )
    if signal is None:
        signal = Signal(asset_id=asset_id, **signal_data)
        db.add(signal)
    else:
        for key, value in signal_data.items():
            setattr(signal, key, value)
    db.flush()
    return signal


def delete_signals_for_asset(db: Session, asset_id: int) -> None:
    db.execute(delete(Signal).where(Signal.asset_id == asset_id))


def get_latest_fundamentals(db: Session, asset_id: int) -> AssetFundamental | None:
    return db.scalar(
        select(AssetFundamental)
        .where(AssetFundamental.asset_id == asset_id)
        .order_by(AssetFundamental.period_date.desc(), AssetFundamental.created_at.desc())
        .limit(1)
    )


def upsert_fundamentals(db: Session, asset_id: int, data: dict) -> AssetFundamental:
    row = db.scalar(
        select(AssetFundamental).where(
            AssetFundamental.asset_id == asset_id,
            AssetFundamental.period_date == data["period_date"],
            AssetFundamental.source == data["source"],
        )
    )
    if row is None:
        row = AssetFundamental(asset_id=asset_id, **data)
        db.add(row)
    else:
        for key, value in data.items():
            setattr(row, key, value)
    db.flush()
    return row


def _safe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)
