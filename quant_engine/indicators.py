import numpy as np
import pandas as pd


def resample_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return daily.copy()
    df = daily.copy()
    df["date"] = pd.to_datetime(df["date"])
    weekly = (
        df.set_index("date")
        .resample("W-FRI")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
        .reset_index()
    )
    weekly["date"] = weekly["date"].dt.date
    return weekly


def calculate_indicators(candles: pd.DataFrame, benchmark: pd.DataFrame | None = None) -> pd.DataFrame:
    df = candles.copy().sort_values("date").reset_index(drop=True)
    if df.empty:
        return df

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    df["sma20"] = close.rolling(20).mean()
    df["sma50"] = close.rolling(50).mean()
    df["sma200"] = close.rolling(200).mean()
    df["atr14"] = _atr(high, low, close, 14)
    df["rsi14"] = _rsi(close, 14)
    df["volume_ratio"] = volume / volume.rolling(20).mean()
    previous_20_high = high.shift(1).rolling(20).max()
    df["breakout_20"] = close > previous_20_high
    high_52w = high.rolling(252, min_periods=60).max()
    df["high_52w_distance"] = (close / high_52w) - 1
    df["pullback_sma20"] = _pullback_near_sma20(df)
    df["relative_strength"] = _relative_strength(df, benchmark)
    return df.replace({np.inf: np.nan, -np.inf: np.nan})


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(period).mean()


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _pullback_near_sma20(df: pd.DataFrame) -> pd.Series:
    previous_high = df["high"].shift(1)
    near_sma20 = (df["low"] <= df["sma20"] * 1.015) & (df["close"] >= df["sma20"] * 0.985)
    recovered = df["close"] > previous_high
    trend_ok = df["close"] > df["sma50"]
    return near_sma20 & recovered & trend_ok


def _relative_strength(df: pd.DataFrame, benchmark: pd.DataFrame | None) -> pd.Series:
    if benchmark is None or benchmark.empty:
        return pd.Series(np.nan, index=df.index)

    stock = df[["date", "close"]].copy()
    stock["date"] = pd.to_datetime(stock["date"])
    bench = benchmark[["date", "close"]].copy()
    bench["date"] = pd.to_datetime(bench["date"])
    merged = stock.merge(bench, on="date", suffixes=("_stock", "_benchmark"), how="left")
    stock_return = merged["close_stock"].pct_change(20, fill_method=None)
    benchmark_return = merged["close_benchmark"].pct_change(20, fill_method=None)
    return (stock_return - benchmark_return).reindex(df.index)
