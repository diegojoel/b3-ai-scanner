from datetime import date
from types import SimpleNamespace
import unittest

import pandas as pd

from quant_engine.liquidity import calculate_liquidity_score, is_liquid_asset


def make_asset(**overrides):
    values = {
        "ticker": "TEST3",
        "asset_type": "STOCK",
        "is_bdr": False,
        "is_etf": False,
        "is_fii": False,
        "is_under_judicial_recovery": False,
        "has_special_trading_condition": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_candles(close=60.0, volume=2_000_000, sessions=760):
    dates = pd.bdate_range(end=date(2026, 5, 20), periods=sessions)
    return pd.DataFrame(
        {
            "date": dates.date,
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": volume,
        }
    )


class LiquidityTests(unittest.TestCase):
    def test_highly_liquid_asset_should_pass(self):
        asset = make_asset()
        candles = make_candles(close=60, volume=2_000_000)

        self.assertTrue(is_liquid_asset(asset, candles))

    def test_low_volume_asset_should_fail(self):
        asset = make_asset()
        candles = make_candles(close=20, volume=100_000)

        self.assertFalse(is_liquid_asset(asset, candles))

    def test_penny_stock_should_fail(self):
        asset = make_asset()
        candles = make_candles(close=4, volume=5_000_000)

        self.assertFalse(is_liquid_asset(asset, candles))

    def test_low_trading_frequency_should_fail(self):
        asset = make_asset()
        candles = make_candles(close=60, volume=2_000_000)
        recent_index = candles.tail(252).index
        candles.loc[recent_index[::2], "volume"] = 0

        self.assertFalse(is_liquid_asset(asset, candles))

    def test_bdr_fii_etf_should_fail(self):
        candles = make_candles(close=60, volume=2_000_000)

        for asset in (
            make_asset(asset_type="BDR", is_bdr=True),
            make_asset(asset_type="FII", is_fii=True),
            make_asset(asset_type="ETF", is_etf=True),
        ):
            with self.subTest(asset_type=asset.asset_type):
                self.assertFalse(is_liquid_asset(asset, candles))

    def test_asset_with_liquidity_score_under_40_should_fail(self):
        asset = make_asset()
        candles = make_candles(close=5, volume=100_000)

        metrics = calculate_liquidity_score(asset, candles)

        self.assertLess(metrics.liquidity_score, 40)
        self.assertFalse(is_liquid_asset(asset, candles))


if __name__ == "__main__":
    unittest.main()
