from dataclasses import dataclass
from typing import Any

import pandas as pd


MIN_AVERAGE_FINANCIAL_VOLUME_30D = 10_000_000
MIN_AVERAGE_TRADED_SHARES_30D = 500_000
MIN_TRADING_FREQUENCY_12M = 0.95
MIN_CLOSE_PRICE = 5.0
MIN_DAILY_HISTORY_SESSIONS = 252 * 3
MAX_ESTIMATED_SPREAD_PCT = 1.0
ELIGIBLE_ASSET_TYPES = {"STOCK", "UNIT"}
EXCLUDED_ASSET_TYPES = {"BDR", "ETF", "FII", "OPTION", "FUTURE", "INDEX"}
MIN_LIQUIDITY_SCORE = 40


@dataclass(frozen=True)
class LiquidityMetrics:
    liquidity_score: int
    average_daily_financial_volume_30d: float
    average_daily_traded_shares_30d: float
    trading_frequency_12m: float
    close_price: float | None
    estimated_spread_pct: float | None


def calculate_average_financial_volume(candles: pd.DataFrame, window: int = 30) -> float:
    if candles.empty or not {"close", "volume"}.issubset(candles.columns):
        return 0.0
    recent = _sorted_recent(candles, window)
    financial_volume = recent["close"].astype(float) * recent["volume"].astype(float)
    return float(financial_volume.mean()) if not financial_volume.empty else 0.0


def calculate_average_traded_shares(candles: pd.DataFrame, window: int = 30) -> float:
    if candles.empty or "volume" not in candles.columns:
        return 0.0
    recent = _sorted_recent(candles, window)
    return float(recent["volume"].astype(float).mean()) if not recent.empty else 0.0


def calculate_trading_frequency(candles: pd.DataFrame, lookback_sessions: int = 252) -> float:
    if candles.empty or "volume" not in candles.columns:
        return 0.0
    recent = _sorted_recent(candles, lookback_sessions)
    if recent.empty:
        return 0.0
    traded_sessions = (recent["volume"].astype(float) > 0).sum()
    return float(traded_sessions / len(recent))


def calculate_liquidity_score(asset: Any, candles: pd.DataFrame, spread_data: Any = None) -> LiquidityMetrics:
    average_financial_volume = calculate_average_financial_volume(candles)
    average_traded_shares = calculate_average_traded_shares(candles)
    trading_frequency = calculate_trading_frequency(candles)
    close_price = _latest_close(candles)
    estimated_spread_pct = _estimated_spread_pct(spread_data)

    financial_volume_points = min(40.0, (average_financial_volume / 50_000_000) * 40)
    trading_frequency_points = min(25.0, trading_frequency * 25)
    traded_shares_points = min(15.0, (average_traded_shares / 2_000_000) * 15)
    spread_points = 10.0 if estimated_spread_pct is None else max(0.0, (1 - estimated_spread_pct / 1.0) * 10)
    price_points = 0.0 if close_price is None else min(10.0, (close_price / 20.0) * 10)

    score = int(
        round(
            financial_volume_points
            + trading_frequency_points
            + traded_shares_points
            + spread_points
            + price_points
        )
    )

    return LiquidityMetrics(
        liquidity_score=max(0, min(100, score)),
        average_daily_financial_volume_30d=average_financial_volume,
        average_daily_traded_shares_30d=average_traded_shares,
        trading_frequency_12m=trading_frequency,
        close_price=close_price,
        estimated_spread_pct=estimated_spread_pct,
    )


def is_liquid_asset(asset: Any, candles: pd.DataFrame, spread_data: Any = None) -> bool:
    metrics = calculate_liquidity_score(asset, candles, spread_data)
    asset_type = _asset_type(asset)
    estimated_spread_pct = metrics.estimated_spread_pct

    return (
        metrics.average_daily_financial_volume_30d >= MIN_AVERAGE_FINANCIAL_VOLUME_30D
        and metrics.average_daily_traded_shares_30d >= MIN_AVERAGE_TRADED_SHARES_30D
        and metrics.trading_frequency_12m >= MIN_TRADING_FREQUENCY_12M
        and metrics.close_price is not None
        and metrics.close_price >= MIN_CLOSE_PRICE
        and len(candles) >= MIN_DAILY_HISTORY_SESSIONS
        and (estimated_spread_pct is None or estimated_spread_pct <= MAX_ESTIMATED_SPREAD_PCT)
        and asset_type in ELIGIBLE_ASSET_TYPES
        and asset_type not in EXCLUDED_ASSET_TYPES
        and not bool(_asset_value(asset, "is_bdr", False))
        and not bool(_asset_value(asset, "is_etf", False))
        and not bool(_asset_value(asset, "is_fii", False))
        and not bool(_asset_value(asset, "is_under_judicial_recovery", False))
        and not bool(_asset_value(asset, "has_special_trading_condition", False))
        and metrics.liquidity_score >= MIN_LIQUIDITY_SCORE
    )


def filter_liquid_assets(
    assets: list[Any],
    candles_by_ticker: dict[str, pd.DataFrame],
    spread_data_by_ticker: dict[str, Any] | None = None,
) -> list[Any]:
    spread_data_by_ticker = spread_data_by_ticker or {}
    liquid_assets = []
    for asset in assets:
        ticker = str(_asset_value(asset, "ticker", "")).upper()
        candles = candles_by_ticker.get(ticker)
        if candles is not None and is_liquid_asset(asset, candles, spread_data_by_ticker.get(ticker)):
            liquid_assets.append(asset)
    return sorted(
        liquid_assets,
        key=lambda item: calculate_liquidity_score(
            item,
            candles_by_ticker[str(_asset_value(item, "ticker", "")).upper()],
            spread_data_by_ticker.get(str(_asset_value(item, "ticker", "")).upper()),
        ).liquidity_score,
        reverse=True,
    )


def _sorted_recent(candles: pd.DataFrame, window: int) -> pd.DataFrame:
    df = candles.copy()
    if "date" in df.columns:
        df = df.sort_values("date")
    return df.tail(window)


def _latest_close(candles: pd.DataFrame) -> float | None:
    if candles.empty or "close" not in candles.columns:
        return None
    df = candles.sort_values("date") if "date" in candles.columns else candles
    close = df.iloc[-1]["close"]
    if pd.isna(close):
        return None
    return float(close)


def _asset_type(asset: Any) -> str:
    value = str(_asset_value(asset, "asset_type", "STOCK") or "STOCK").upper()
    return value


def _estimated_spread_pct(spread_data: Any) -> float | None:
    if spread_data is None:
        return None
    value = _asset_value(spread_data, "estimated_spread_pct", spread_data)
    if value is None or pd.isna(value):
        return None
    return float(value)


def _asset_value(source: Any, field: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(field, default)
    return getattr(source, field, default)
