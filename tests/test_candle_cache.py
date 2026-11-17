from datetime import date, timedelta
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import _is_daily_candle_cache_stale
from app.services.scanner import (
    _activate_existing_assets_with_recent_data,
    _benchmark_covers,
    _build_refresh_batch,
    _can_reuse_existing_data,
)


class CandleCacheTests(unittest.TestCase):
    def test_missing_candle_cache_is_stale(self):
        self.assertTrue(_is_daily_candle_cache_stale(None, today=date(2026, 5, 28)))

    def test_today_candle_cache_is_fresh(self):
        self.assertFalse(_is_daily_candle_cache_stale(date(2026, 5, 28), today=date(2026, 5, 28)))

    def test_yesterday_candle_cache_is_stale(self):
        self.assertTrue(_is_daily_candle_cache_stale(date(2026, 5, 27), today=date(2026, 5, 28)))

    def test_two_day_old_candle_cache_is_stale(self):
        self.assertTrue(_is_daily_candle_cache_stale(date(2026, 5, 26), today=date(2026, 5, 28)))

    def test_older_candle_cache_is_stale(self):
        self.assertTrue(_is_daily_candle_cache_stale(date(2026, 5, 20), today=date(2026, 5, 28)))

    def test_scanner_reuses_data_inside_recent_window(self):
        daily = pd.DataFrame([{"date": date(2026, 5, 28)}])
        self.assertTrue(_can_reuse_existing_data(daily, recent_days=7, today=date(2026, 5, 28)))

    def test_scanner_reuses_yesterday_candle_inside_recent_window(self):
        daily = pd.DataFrame([{"date": date(2026, 5, 27)}])
        self.assertTrue(_can_reuse_existing_data(daily, recent_days=7, today=date(2026, 5, 28)))

    def test_scanner_refreshes_when_recent_window_is_missing(self):
        daily = pd.DataFrame([{"date": date(2026, 5, 20)}])
        self.assertFalse(_can_reuse_existing_data(daily, recent_days=7, today=date(2026, 5, 28)))

    def test_scanner_reactivates_existing_assets_with_recent_candles(self):
        today = date.today()
        recent_asset = SimpleNamespace(id=1, ticker="TEST3", active=False, is_active=False)
        stale_asset = SimpleNamespace(id=2, ticker="OLD3", active=False, is_active=False)
        daily_by_asset = {
            1: pd.DataFrame([{"date": today - timedelta(days=1), "volume": 1000}]),
            2: pd.DataFrame([{"date": today - timedelta(days=45), "volume": 1000}]),
        }
        db = SimpleNamespace(scalars=lambda query: [recent_asset, stale_asset])

        with patch("app.services.scanner.get_candles", side_effect=lambda db, asset_id, timeframe: daily_by_asset[asset_id]):
            _activate_existing_assets_with_recent_data(db, recent_days=30)

        self.assertTrue(recent_asset.active)
        self.assertTrue(recent_asset.is_active)
        self.assertFalse(stale_asset.active)
        self.assertFalse(stale_asset.is_active)

    def test_refresh_batch_keeps_benchmark_and_prefers_stale_liquid_names(self):
        def item(ticker, score, empty):
            asset = SimpleNamespace(ticker=ticker, liquidity_score=score)
            daily = pd.DataFrame() if empty else pd.DataFrame([{"date": date(2026, 5, 1)}])
            return (asset, None, daily)

        queue = [
            item("NEW1", None, True),
            item("NEW2", None, True),
            item("LOW3", 10, False),
            item("PETR4", 90, False),
            item("BOVA11", None, False),
        ]
        batch = _build_refresh_batch(queue, 2)
        self.assertEqual([row[0].ticker for row in batch], ["BOVA11", "PETR4", "LOW3"])

    def test_benchmark_must_cover_the_asset_last_session(self):
        asset = pd.DataFrame([{"date": date(2026, 11, 3)}])
        stale_benchmark = pd.DataFrame([{"date": date(2026, 5, 21)}])
        current_benchmark = pd.DataFrame([{"date": date(2026, 11, 3)}])
        self.assertFalse(_benchmark_covers(stale_benchmark, asset))
        self.assertTrue(_benchmark_covers(current_benchmark, asset))
        self.assertFalse(_benchmark_covers(pd.DataFrame(), asset))


if __name__ == "__main__":
    unittest.main()
