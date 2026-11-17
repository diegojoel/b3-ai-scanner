from datetime import date
from hashlib import sha256

import numpy as np
import pandas as pd


DEMO_ASSETS = [
    ("PETR4", "Petrobras PN", "Energia"),
    ("VALE3", "Vale ON", "Materiais básicos"),
    ("ITUB4", "Itaú Unibanco PN", "Financeiro"),
    ("WEGE3", "WEG ON", "Bens industriais"),
    ("BOVA11", "iShares Ibovespa Fundo de Índice", "Benchmark"),
]

DEMO_PRICE_ANCHORS = {
    "PETR4": 45.99,
    "VALE3": 58.0,
    "ITUB4": 39.0,
    "WEGE3": 43.0,
    "BOVA11": 145.0,
}


def generate_demo_ohlcv(ticker: str, years: int = 10, end: date | None = None) -> pd.DataFrame:
    end_ts = pd.Timestamp(end or date.today())
    dates = pd.bdate_range(end=end_ts, periods=252 * years)
    seed = int(sha256(ticker.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    drift = 0.0002 if ticker in {"BOVA11", "IBOV"} else 0.00045 + (seed % 9) / 100000
    volatility = 0.018 + (seed % 7) / 1000
    returns = rng.normal(drift, volatility, len(dates))
    base = 18 + (seed % 80)
    close = base * np.exp(np.cumsum(returns))
    open_ = close * (1 + rng.normal(0, 0.004, len(dates)))
    high = np.maximum(open_, close) * (1 + rng.uniform(0.001, 0.025, len(dates)))
    low = np.minimum(open_, close) * (1 - rng.uniform(0.001, 0.025, len(dates)))
    volume = rng.integers(1_000_000, 25_000_000, len(dates)).astype(float)

    if ticker not in {"BOVA11", "IBOV"}:
        close[-45:] = np.linspace(close[-46], close[-46] * 1.24, 45)
        previous_breakout_level = max(close[-22:-1] * 1.01)
        close[-1] = previous_breakout_level * 1.012
        open_[-45:] = close[-45:] * (1 + rng.normal(-0.002, 0.003, 45))
        high[-45:] = np.maximum(open_[-45:], close[-45:]) * 1.01
        low[-45:] = np.minimum(open_[-45:], close[-45:]) * 0.99
        volume[-1] = np.mean(volume[-21:-1]) * 2.2

    if ticker in DEMO_PRICE_ANCHORS:
        price_scale = DEMO_PRICE_ANCHORS[ticker] / close[-1]
        open_ *= price_scale
        high *= price_scale
        low *= price_scale
        close *= price_scale

    return pd.DataFrame(
        {
            "date": dates.date,
            "open": open_.round(2),
            "high": high.round(2),
            "low": low.round(2),
            "close": close.round(2),
            "volume": volume,
        }
    )
