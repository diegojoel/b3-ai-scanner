import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.market_data import extend_daily_history, parse_cotahist_quote_line


BOVA11_LINE = (
    "012026110314BOVA11      010ISHARES BOVACI  ATZ      R$  "
    "00000000163000000000016389000000001617700000000162730000000016301"
    "00000000163000000000016302910750000000000081098440000001319"
)


class CotahistTests(unittest.TestCase):
    def test_parses_cash_market_bova11_session(self):
        row = parse_cotahist_quote_line(BOVA11_LINE, "BOVA11")
        self.assertEqual(
            row,
            {
                "date": date(2026, 11, 3),
                "open": 163.0,
                "high": 163.89,
                "low": 161.77,
                "close": 163.01,
                "volume": 8109844.0,
            },
        )

    def test_ignores_option_rows_and_other_tickers(self):
        option = BOVA11_LINE[:12] + "BOVA11T     " + BOVA11_LINE[24:]
        self.assertIsNone(parse_cotahist_quote_line(option, "BOVA11"))
        self.assertIsNone(parse_cotahist_quote_line(BOVA11_LINE, "PETR4"))

    def test_extends_stale_history_with_recent_sessions(self):
        stale = pd.DataFrame([{"date": date(2026, 5, 21), "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}])
        recent = pd.DataFrame([{"date": date(2026, 11, 3), "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2}])
        combined = extend_daily_history(stale, recent)
        self.assertEqual(list(combined["date"]), [date(2026, 5, 21), date(2026, 11, 3)])


if __name__ == "__main__":
    unittest.main()
