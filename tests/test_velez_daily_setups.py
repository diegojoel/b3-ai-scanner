from datetime import date, timedelta
import unittest
from unittest.mock import patch

import pandas as pd

from quant_engine.signals import build_latest_signal, build_recent_signal, build_watchlist_signal


def _fake_signal(signal_date: date, entry: float, stop: float, target_1: float) -> dict:
    return {
        "signal_date": signal_date,
        "setup_type": "velez_elephant_bar",
        "entry_price": entry,
        "stop_loss": stop,
        "target_1": target_1,
        "score": 90,
        "metrics": {"daily_setup_rank": 94},
    }


def _daily_frame(rows: int = 230) -> pd.DataFrame:
    start = date(2025, 1, 1)
    data = []
    for index in range(rows):
        base = 100 + (index * 0.03)
        data.append(
            {
                "date": start + timedelta(days=index),
                "open": base,
                "high": base + 0.6,
                "low": base - 0.4,
                "close": base + 0.2,
                "volume": 1000,
                "sma20": base - 0.8,
                "sma50": base - 1.5,
                "sma200": base - 5,
                "atr14": 1.0,
                "rsi14": 60,
                "volume_ratio": 1.0,
                "breakout_20": False,
                "high_52w_distance": -0.04,
                "pullback_sma20": False,
                "relative_strength": 0.12,
            }
        )
    return pd.DataFrame(data)


def _weekly_frame(rows: int = 60) -> pd.DataFrame:
    start = date(2024, 1, 5)
    data = []
    for index in range(rows):
        data.append(
            {
                "date": start + timedelta(days=index * 7),
                "open": 100 + index,
                "high": 102 + index,
                "low": 99 + index,
                "close": 120 + index,
                "volume": 1000,
                "sma20": 105 + index,
                "sma50": 95 + index,
                "sma200": 80 + index,
                "atr14": 2.0,
                "rsi14": 62,
                "volume_ratio": 1.1,
                "breakout_20": False,
                "high_52w_distance": -0.02,
                "pullback_sma20": False,
                "relative_strength": None,
            }
        )
    return pd.DataFrame(data)


class VelezDailySetupTests(unittest.TestCase):
    def test_elephant_bar_generates_velez_signal(self):
        daily = _daily_frame()
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "atr14", "volume_ratio"]] = [
            100.2,
            105.0,
            99.0,
            104.8,
            100.0,
            3.0,
            1.5,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "velez_elephant_bar")
        self.assertIn("velez_elephant_bar", signal["metrics"]["daily_setups"])

    def test_three_bar_play_is_prioritized_over_elephant_ignition(self):
        daily = _daily_frame()
        daily.loc[daily.index[-3], ["open", "high", "low", "close", "sma20", "atr14", "volume_ratio"]] = [
            100.0,
            104.0,
            99.0,
            103.8,
            100.0,
            3.0,
            1.2,
        ]
        daily.loc[daily.index[-2], ["open", "high", "low", "close", "sma20", "atr14", "volume_ratio"]] = [
            103.5,
            104.0,
            102.5,
            103.0,
            100.8,
            2.0,
            0.9,
        ]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "atr14", "volume_ratio"]] = [
            103.1,
            105.0,
            102.8,
            104.5,
            101.0,
            2.0,
            1.0,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "velez_3_bar_play")

    def test_key_buy_setup_generates_velez_signal(self):
        daily = _daily_frame()
        daily.loc[daily.index[-4], ["open", "high", "low", "close", "sma20", "sma50", "atr14"]] = [
            104.0,
            105.0,
            101.0,
            102.0,
            101.0,
            98.0,
            5.0,
        ]
        daily.loc[daily.index[-3], ["open", "high", "low", "close", "sma20", "sma50", "atr14"]] = [
            103.0,
            104.0,
            100.0,
            101.0,
            101.0,
            98.0,
            5.0,
        ]
        daily.loc[daily.index[-2], ["open", "high", "low", "close", "sma20", "sma50", "atr14"]] = [
            102.0,
            103.0,
            99.0,
            100.0,
            101.0,
            98.0,
            5.0,
        ]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50", "atr14"]] = [
            100.2,
            104.0,
            99.8,
            103.5,
            101.0,
            98.0,
            5.0,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "velez_key_buy_setup")

    def test_vbs_generates_velez_signal(self):
        daily = _daily_frame()
        pullback = daily.index[-5:-1]
        daily.loc[pullback, ["open", "high", "low", "close", "sma20", "sma50", "atr14"]] = [
            105.0,
            106.0,
            101.0,
            103.0,
            102.0,
            99.0,
            4.0,
        ]
        daily.loc[daily.index[-6], "sma20"] = 100.0
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50", "atr14", "rsi14"]] = [
            103.4,
            107.0,
            103.2,
            106.5,
            102.5,
            99.0,
            4.0,
            58.0,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "velez_vbs")

    def test_rbi_generates_velez_signal(self):
        daily = _daily_frame()
        daily.loc[daily.index[-56:-2], "high"] = 110.0
        daily.loc[daily.index[-2], ["open", "high", "low", "close", "sma20", "sma50", "atr14"]] = [
            106.0,
            107.0,
            104.0,
            105.0,
            102.0,
            99.0,
            4.0,
        ]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50", "atr14", "volume_ratio", "rsi14"]] = [
            105.4,
            108.0,
            105.2,
            107.5,
            102.5,
            99.0,
            4.0,
            1.0,
            57.0,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "velez_rbi")

    def test_bull_180_generates_velez_signal(self):
        daily = _daily_frame()
        daily.loc[daily.index[-56:-2], "high"] = 110.0
        daily.loc[daily.index[-2], ["open", "high", "low", "close", "sma20", "sma50", "atr14"]] = [
            106.0,
            107.0,
            101.0,
            102.0,
            101.0,
            98.0,
            6.0,
        ]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50", "atr14", "rsi14"]] = [
            101.5,
            108.0,
            101.0,
            107.5,
            101.5,
            98.0,
            6.0,
            55.0,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "velez_bull_180")

    def test_recent_signal_selects_stronger_velez_candidate(self):
        daily = _daily_frame()

        def fake_latest_signal(daily_indicators, weekly_indicators):
            signal_date = daily_indicators.iloc[-1].date
            if not isinstance(signal_date, date):
                signal_date = pd.Timestamp(signal_date).date()
            if signal_date == daily.iloc[-1].date:
                return {
                    "signal_date": signal_date,
                    "setup_type": "pullback_sma20",
                    "entry_price": 107.8,
                    "stop_loss": 95.0,
                    "target_1": 140.0,
                    "score": 71,
                    "metrics": {"daily_setup_rank": 78},
                }
            if signal_date == daily.iloc[-2].date:
                return {
                    "signal_date": signal_date,
                    "setup_type": "velez_elephant_bar",
                    "entry_price": 107.8,
                    "stop_loss": 95.0,
                    "target_1": 140.0,
                    "score": 90,
                    "metrics": {"daily_setup_rank": 94},
                }
            return None

        with patch("quant_engine.signals.build_latest_signal", side_effect=fake_latest_signal):
            signal = build_recent_signal(daily, recent_days=7)

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "velez_elephant_bar")

    def test_recent_signal_removes_setup_after_stop_is_touched(self):
        daily = _daily_frame()
        signal_day = daily.iloc[-3].date
        daily.loc[daily.index[-2], "low"] = 94.0

        def fake_latest_signal(daily_indicators, weekly_indicators):
            signal_date = daily_indicators.iloc[-1].date
            if not isinstance(signal_date, date):
                signal_date = pd.Timestamp(signal_date).date()
            if signal_date == signal_day:
                return _fake_signal(signal_date, entry=110.0, stop=95.0, target_1=140.0)
            return None

        with patch("quant_engine.signals.build_latest_signal", side_effect=fake_latest_signal):
            signal = build_recent_signal(daily, recent_days=7)

        self.assertIsNone(signal)

    def test_recent_signal_keeps_pending_entry_inside_the_window(self):
        daily = _daily_frame()
        signal_day = daily.iloc[-5].date

        def fake_latest_signal(daily_indicators, weekly_indicators):
            signal_date = daily_indicators.iloc[-1].date
            if not isinstance(signal_date, date):
                signal_date = pd.Timestamp(signal_date).date()
            if signal_date == signal_day:
                return _fake_signal(signal_date, entry=108.0, stop=95.0, target_1=140.0)
            return None

        with patch("quant_engine.signals.build_latest_signal", side_effect=fake_latest_signal):
            signal = build_recent_signal(daily, recent_days=7)

        self.assertIsNotNone(signal)
        self.assertEqual(signal["metrics"]["actionability"], "pending_entry")

    def test_recent_signal_keeps_triggered_entry_inside_the_window(self):
        daily = _daily_frame()
        signal_day = daily.iloc[-6].date
        daily.loc[daily.index[-5], "high"] = 112.0

        def fake_latest_signal(daily_indicators, weekly_indicators):
            signal_date = daily_indicators.iloc[-1].date
            if not isinstance(signal_date, date):
                signal_date = pd.Timestamp(signal_date).date()
            if signal_date == signal_day:
                return _fake_signal(signal_date, entry=110.0, stop=95.0, target_1=140.0)
            return None

        with patch("quant_engine.signals.build_latest_signal", side_effect=fake_latest_signal):
            signal = build_recent_signal(daily, recent_days=10)

        self.assertIsNotNone(signal)
        self.assertEqual(signal["metrics"]["actionability"], "entry_triggered")

    def test_recent_signal_keeps_pending_entry_for_first_three_candles(self):
        daily = _daily_frame()
        signal_day = daily.iloc[-4].date

        def fake_latest_signal(daily_indicators, weekly_indicators):
            signal_date = daily_indicators.iloc[-1].date
            if not isinstance(signal_date, date):
                signal_date = pd.Timestamp(signal_date).date()
            if signal_date == signal_day:
                return _fake_signal(signal_date, entry=108.0, stop=95.0, target_1=140.0)
            return None

        with patch("quant_engine.signals.build_latest_signal", side_effect=fake_latest_signal):
            signal = build_recent_signal(daily, recent_days=7)

        self.assertIsNotNone(signal)
        self.assertEqual(signal["metrics"]["actionability"], "pending_entry")

    def test_recent_signal_removes_setup_after_bear_180_counter_signal(self):
        daily = _daily_frame()
        signal_day = daily.iloc[-3].date
        daily.loc[daily.index[-2], ["open", "high", "low", "close"]] = [104.0, 106.0, 103.0, 105.0]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50"]] = [105.2, 105.5, 100.0, 102.5, 101.0, 98.0]

        def fake_latest_signal(daily_indicators, weekly_indicators):
            signal_date = daily_indicators.iloc[-1].date
            if not isinstance(signal_date, date):
                signal_date = pd.Timestamp(signal_date).date()
            if signal_date == signal_day:
                return _fake_signal(signal_date, entry=108.0, stop=95.0, target_1=140.0)
            return None

        with patch("quant_engine.signals.build_latest_signal", side_effect=fake_latest_signal):
            signal = build_recent_signal(daily, recent_days=7)

        self.assertIsNone(signal)

    def test_minervini_vcp_generates_signal(self):
        daily = _daily_frame(400)
        first = daily.index[-46:-31]
        second = daily.index[-31:-16]
        third = daily.index[-16:-1]
        daily.loc[first, ["high", "low", "open", "close", "volume"]] = [120.0, 100.0, 106.0, 108.0, 2000.0]
        daily.loc[second, ["high", "low", "open", "close", "volume"]] = [116.0, 103.0, 108.0, 109.0, 1500.0]
        daily.loc[third, ["high", "low", "open", "close", "volume"]] = [112.0, 104.0, 109.0, 110.0, 900.0]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma50", "sma200", "volume_ratio", "rsi14"]] = [
            116.2,
            118.0,
            115.8,
            117.0,
            108.0,
            100.0,
            1.3,
            64.0,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "minervini_vcp")

    def test_oneil_base_breakout_generates_signal(self):
        daily = _daily_frame(260)
        base = daily.index[-66:-16]
        handle = daily.index[-16:-1]
        daily.loc[daily.index[-120:-66], ["high", "low", "open", "close"]] = [98.0, 90.0, 93.0, 95.0]
        daily.loc[base, ["high", "low", "open", "close", "volume"]] = [120.0, 95.0, 108.0, 110.0, 1200.0]
        daily.loc[handle, ["high", "low", "open", "close", "volume"]] = [119.0, 108.0, 112.0, 113.0, 1300.0]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma50", "sma200", "volume_ratio", "rsi14"]] = [
            119.5,
            122.0,
            119.0,
            121.0,
            111.0,
            100.0,
            1.25,
            66.0,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "oneil_base_breakout")

    def test_weinstein_stage2_breakout_generates_signal(self):
        daily = _daily_frame(260)
        daily.loc[daily.index[-61:-1], "high"] = 108.0
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma50", "sma200", "volume_ratio"]] = [
            108.5,
            110.0,
            108.2,
            109.5,
            101.0,
            95.0,
            0.8,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "weinstein_stage2_breakout")

    def test_darvas_box_breakout_generates_signal(self):
        daily = _daily_frame(260)
        box = daily.index[-41:-1]
        daily.loc[box, ["high", "low", "open", "close"]] = [100.0, 88.0, 94.0, 96.0]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma50", "sma200", "volume_ratio"]] = [
            100.5,
            103.0,
            100.0,
            102.0,
            96.0,
            100.0,
            1.06,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "darvas_box_breakout")

    def test_donchian_55_breakout_generates_signal(self):
        daily = _daily_frame(260)
        daily.loc[daily.index[-56:-1], ["high", "low", "open", "close"]] = [100.0, 70.0, 86.0, 88.0]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma50", "sma200", "volume_ratio"]] = [
            101.0,
            103.0,
            100.5,
            102.0,
            90.0,
            95.0,
            1.0,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "donchian_55_breakout")

    def test_pocket_pivot_generates_signal(self):
        daily = _daily_frame(260)
        recent = daily.index[-11:-1]
        daily.loc[recent, ["open", "high", "low", "close", "volume"]] = [105.0, 106.0, 103.0, 104.0, 1000.0]
        daily.loc[daily.index[-2], ["open", "high", "low", "close", "volume"]] = [104.0, 106.0, 103.0, 104.5, 900.0]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50", "sma200", "volume", "volume_ratio", "rsi14"]] = [
            105.0,
            108.0,
            104.8,
            107.5,
            103.0,
            101.0,
            99.0,
            1400.0,
            1.0,
            58.0,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "pocket_pivot")

    def test_bollinger_squeeze_breakout_generates_signal(self):
        daily = _daily_frame(260)
        wide = daily.index[-120:-30]
        tight = daily.index[-30:-1]
        daily.loc[wide, ["open", "high", "low", "close"]] = [100.0, 112.0, 88.0, 100.0]
        daily.loc[tight, ["open", "high", "low", "close"]] = [100.0, 101.0, 99.0, 100.0]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma50", "sma200", "volume_ratio", "rsi14"]] = [
            101.0,
            104.0,
            100.8,
            103.5,
            99.0,
            95.0,
            1.1,
            62.0,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "bollinger_squeeze_breakout")

    def test_nr7_inside_breakout_generates_signal(self):
        daily = _daily_frame(260)
        daily.loc[daily.index[-8:-2], ["high", "low", "open", "close"]] = [108.0, 100.0, 103.0, 104.0]
        daily.loc[daily.index[-3], ["high", "low", "open", "close"]] = [107.0, 100.0, 103.0, 104.0]
        daily.loc[daily.index[-2], ["high", "low", "open", "close"]] = [105.0, 103.0, 104.0, 104.5]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50", "sma200", "volume_ratio", "rsi14"]] = [
            105.2,
            107.0,
            105.0,
            106.5,
            102.0,
            100.0,
            98.0,
            0.95,
            57.0,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "nr7_inside_breakout")

    def test_larry_oops_buy_generates_signal(self):
        daily = _daily_frame(260)
        daily.loc[daily.index[-56:-2], "high"] = 120.0
        daily.loc[daily.index[-2], ["open", "high", "low", "close", "sma20", "sma50"]] = [
            110.0,
            112.0,
            108.0,
            111.0,
            104.0,
            101.0,
        ]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50", "sma200", "rsi14", "volume_ratio"]] = [
            107.5,
            110.5,
            107.0,
            109.8,
            104.5,
            101.0,
            98.0,
            52.0,
            0.9,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "larry_oops_buy")
        self.assertIn("larry_oops_buy", signal["metrics"]["daily_setups"])

    def test_larry_setups_do_not_override_existing_setups(self):
        daily = _daily_frame(260)
        daily.loc[daily.index[-56:-2], "high"] = 120.0
        daily.loc[daily.index[-2], ["open", "high", "low", "close", "sma20", "sma50"]] = [
            110.0,
            112.0,
            108.0,
            111.0,
            104.0,
            101.0,
        ]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50", "sma200", "rsi14", "volume_ratio", "pullback_sma20"]] = [
            107.5,
            110.5,
            107.0,
            109.8,
            104.5,
            101.0,
            98.0,
            52.0,
            0.9,
            True,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "pullback_sma20")
        self.assertNotIn("larry_oops_buy", signal["metrics"]["daily_setups"])

    def test_larry_williams_r_reversal_generates_signal(self):
        daily = _daily_frame(260)
        daily.loc[daily.index[-56:-15], "high"] = 120.0
        daily.loc[daily.index[-15:-1], ["high", "low", "open", "close"]] = [110.0, 100.0, 103.0, 102.0]
        daily.loc[daily.index[-3], ["high", "low", "open", "close"]] = [104.0, 101.0, 103.0, 102.5]
        daily.loc[daily.index[-2], ["open", "high", "low", "close", "sma20", "sma50"]] = [
            103.0,
            105.0,
            100.0,
            101.5,
            104.0,
            100.0,
        ]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50", "sma200", "rsi14", "volume_ratio"]] = [
            102.0,
            106.5,
            101.8,
            106.0,
            104.0,
            100.0,
            98.0,
            45.0,
            0.9,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "larry_williams_r_reversal")
        self.assertIn("larry_williams_r_reversal", signal["metrics"]["daily_setups"])

    def test_larry_smash_day_buy_generates_signal(self):
        daily = _daily_frame(260)
        daily.loc[daily.index[-56:-15], "high"] = 120.0
        daily.loc[daily.index[-15:-3], ["open", "high", "low", "close"]] = [104.0, 108.0, 100.0, 104.0]
        daily.loc[daily.index[-3], ["open", "high", "low", "close"]] = [104.0, 106.0, 103.0, 105.5]
        daily.loc[daily.index[-2], ["open", "high", "low", "close", "sma20", "sma50"]] = [
            105.0,
            108.0,
            100.0,
            101.8,
            103.0,
            99.0,
        ]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50", "sma200", "rsi14", "volume_ratio"]] = [
            102.0,
            109.5,
            101.8,
            109.0,
            103.0,
            99.0,
            97.0,
            55.0,
            0.9,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "larry_smash_day_buy")
        self.assertIn("larry_smash_day_buy", signal["metrics"]["daily_setups"])

    def test_watchlist_signal_when_weekly_trend_has_no_daily_trigger(self):
        daily = _daily_frame(400)
        benchmark = daily.copy()
        benchmark["close"] = 100.0

        signal = build_watchlist_signal(daily, benchmark)

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "weekly_trend_watchlist")
        self.assertEqual(signal["status"], "watchlist")

    def test_sma50_reclaim_fallback_generates_signal(self):
        daily = _daily_frame(260)
        daily.loc[daily.index[-56:-2], "high"] = 120.0
        daily.loc[daily.index[-6], "sma20"] = 100.0
        daily.loc[daily.index[-2], ["open", "high", "low", "close", "sma20", "sma50", "rsi14"]] = [
            102.0,
            105.0,
            101.0,
            102.5,
            103.0,
            103.0,
            47.0,
        ]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50", "sma200", "rsi14", "volume_ratio"]] = [
            102.8,
            105.2,
            102.4,
            104.5,
            103.2,
            103.6,
            98.0,
            53.0,
            0.9,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "sma50_reclaim")

    def test_higher_low_reversal_fallback_generates_signal(self):
        daily = _daily_frame(260)
        daily.loc[daily.index[-56:-2], "high"] = 120.0
        daily.loc[daily.index[-12:-6], ["open", "high", "low", "close"]] = [104.0, 107.0, 98.0, 104.5]
        daily.loc[daily.index[-6:-1], ["open", "high", "low", "close"]] = [104.0, 107.0, 101.0, 104.5]
        daily.loc[daily.index[-2], ["open", "high", "low", "close", "sma20", "sma50", "rsi14"]] = [
            104.0,
            106.0,
            101.0,
            104.5,
            103.0,
            100.0,
            52.0,
        ]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50", "sma200", "rsi14", "volume_ratio"]] = [
            104.8,
            107.2,
            104.5,
            106.8,
            103.0,
            100.0,
            98.0,
            55.0,
            0.8,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "higher_low_reversal")

    def test_rsi50_momentum_reclaim_fallback_generates_signal(self):
        daily = _daily_frame(260)
        daily.loc[daily.index[-56:-2], "high"] = 120.0
        daily.loc[daily.index[-12:-6], "low"] = 101.0
        daily.loc[daily.index[-6:-1], "low"] = 99.0
        daily.loc[daily.index[-6], "sma20"] = 100.0
        daily.loc[daily.index[-2], ["open", "high", "low", "close", "sma20", "sma50", "rsi14"]] = [
            103.0,
            106.0,
            99.0,
            104.0,
            103.0,
            100.0,
            49.0,
        ]
        daily.loc[daily.index[-1], ["open", "high", "low", "close", "sma20", "sma50", "sma200", "rsi14", "volume_ratio"]] = [
            104.1,
            105.5,
            103.8,
            105.0,
            103.2,
            100.0,
            98.0,
            52.0,
            0.8,
        ]

        signal = build_latest_signal(daily, _weekly_frame())

        self.assertIsNotNone(signal)
        self.assertEqual(signal["setup_type"], "rsi50_momentum_reclaim")


if __name__ == "__main__":
    unittest.main()
