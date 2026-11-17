from types import SimpleNamespace
import unittest

from quant_engine.share_class_selector import (
    build_preferred_universe,
    extract_company_root,
    group_assets_by_company,
    select_preferred_share_class,
)


def make_asset(**overrides):
    values = {
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


class ShareClassSelectorTests(unittest.TestCase):
    def test_extract_company_root(self):
        self.assertEqual(extract_company_root("PETR4"), "PETR")
        self.assertEqual(extract_company_root("BBDC3.SA"), "BBDC")
        self.assertEqual(extract_company_root("BPAC11"), "BPAC")

    def test_group_assets_by_company(self):
        groups = group_assets_by_company([make_asset(ticker="PETR3"), make_asset(ticker="PETR4")])

        self.assertEqual(set(groups), {"PETR"})
        self.assertEqual(len(groups["PETR"]), 2)

    def test_petr4_selected_over_petr3_when_liquidity_is_similar(self):
        petr3 = make_asset(ticker="PETR3", liquidity_score=86, average_daily_financial_volume_30d=450_000_000)
        petr4 = make_asset(ticker="PETR4", liquidity_score=84, average_daily_financial_volume_30d=420_000_000)

        selected = select_preferred_share_class([petr3, petr4])

        self.assertEqual(selected.ticker, "PETR4")

    def test_bbdc4_selected_over_bbdc3_when_liquidity_is_similar(self):
        bbdc3 = make_asset(ticker="BBDC3", liquidity_score=83, average_daily_financial_volume_30d=120_000_000)
        bbdc4 = make_asset(ticker="BBDC4", liquidity_score=82, average_daily_financial_volume_30d=118_000_000)

        selected = select_preferred_share_class([bbdc3, bbdc4])

        self.assertEqual(selected.ticker, "BBDC4")

    def test_single_class_company_is_kept(self):
        vale3 = make_asset(ticker="VALE3", liquidity_score=95)

        preferred = build_preferred_universe([vale3])

        self.assertEqual([asset.ticker for asset in preferred], ["VALE3"])

    def test_illiquid_pn_is_rejected(self):
        petr3 = make_asset(ticker="PETR3", liquidity_score=88, average_daily_financial_volume_30d=300_000_000)
        petr4 = make_asset(ticker="PETR4", liquidity_score=35, average_daily_financial_volume_30d=20_000_000)

        selected = select_preferred_share_class([petr3, petr4])

        self.assertEqual(selected.ticker, "PETR3")

    def test_unit_selected_only_when_significantly_more_liquid(self):
        sanb3 = make_asset(ticker="SANB3", liquidity_score=80, average_daily_financial_volume_30d=60_000_000)
        sanb11 = make_asset(
            ticker="SANB11",
            asset_type="UNIT",
            liquidity_score=92,
            average_daily_financial_volume_30d=120_000_000,
        )

        selected = select_preferred_share_class([sanb3, sanb11])

        self.assertEqual(selected.ticker, "SANB11")

    def test_unit_not_selected_when_only_marginally_more_liquid(self):
        bpac3 = make_asset(ticker="BPAC3", liquidity_score=85, average_daily_financial_volume_30d=100_000_000)
        bpac11 = make_asset(
            ticker="BPAC11",
            asset_type="UNIT",
            liquidity_score=88,
            average_daily_financial_volume_30d=110_000_000,
        )

        selected = select_preferred_share_class([bpac3, bpac11])

        self.assertEqual(selected.ticker, "BPAC3")


if __name__ == "__main__":
    unittest.main()
