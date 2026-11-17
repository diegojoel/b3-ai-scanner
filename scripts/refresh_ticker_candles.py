from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal
from app.services.market_data import fetch_daily_ohlcv
from app.services.repository import get_asset_by_ticker, replace_candles


def main(tickers: list[str]) -> None:
    db = SessionLocal()
    try:
        updated: list[tuple[str, str]] = []
        for ticker in tickers:
            asset = get_asset_by_ticker(db, ticker)
            if asset is None:
                continue
            daily = fetch_daily_ohlcv(ticker)
            if daily.empty:
                continue
            replace_candles(db, asset.id, daily, "1d")
            updated.append((ticker, str(daily.iloc[-1]["date"])))
        db.commit()
        for ticker, latest_date in updated:
            print(f"{ticker} {latest_date}")
    finally:
        db.close()


if __name__ == "__main__":
    main([ticker.upper() for ticker in sys.argv[1:]])
