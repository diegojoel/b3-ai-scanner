from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services import scanner


def make_asset(**overrides):
    values = {
        "id": 1,
        "ticker": "TEST3",
        "asset_type": "STOCK",
        "is_bdr": False,
        "is_etf": False,
        "is_fii": False,
        "is_under_judicial_recovery": False,
        "has_special_trading_condition": False,
        "liquidity_score": 80,
        "average_daily_financial_volume_30d": 80_000_000,
        "average_daily_traded_shares_30d": 2_000_000,
        "trading_frequency_12m": 1.0,
        "estimated_spread_pct": 0.25,
        "close_price": 20.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_daily(ticker: str):
    daily = pd.DataFrame({"close": [10.0], "volume": [1_000_000]})
    daily.attrs["ticker"] = ticker
    return daily


class ScannerCompanySignalSelectionTests(unittest.TestCase):
    def test_selects_non_preferred_share_class_when_it_has_the_only_signal(self):
        usim3 = make_asset(id=1, ticker="USIM3", liquidity_score=50, average_daily_financial_volume_30d=5_000_000)
        usim5 = make_asset(id=2, ticker="USIM5", liquidity_score=95, average_daily_financial_volume_30d=150_000_000)
        signal = {
            "setup_type": "velez_vbs",
            "score": 81,
            "metrics": {"daily_setup_rank": 87},
        }
        daily_by_ticker = {"USIM3": make_daily("USIM3"), "USIM5": make_daily("USIM5")}

        def fake_build_recent_signal(daily, benchmark_daily, recent_days):
            return signal if daily.attrs["ticker"] == "USIM3" else None

        with patch("app.services.scanner.build_recent_signal", side_effect=fake_build_recent_signal):
            selected_asset, selected_signal = scanner._select_company_signal(
                [usim3, usim5],
                daily_by_ticker,
                benchmark_daily=None,
                recent_days=30,
            )

        self.assertEqual(selected_asset.ticker, "USIM3")
        self.assertEqual(selected_signal["setup_type"], "velez_vbs")


if __name__ == "__main__":
    unittest.main()
