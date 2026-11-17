import unittest

from quant_engine.fundamentals import analyze_fundamental_risk


class FundamentalRiskTests(unittest.TestCase):
    def test_distressed_profile_should_be_extreme_risk(self):
        analysis = analyze_fundamental_risk(
            {
                "net_debt_ebitda": 16.8,
                "ebitda_margin": 0.03,
                "free_cash_flow_yield": -0.12,
                "cash_burn_ratio": 1.4,
                "default_or_restructuring_risk": True,
                "dilution_risk": True,
                "fiscal_benefit_dependency": True,
            }
        )

        self.assertEqual(analysis.risk_level, "EXTREME")
        self.assertGreaterEqual(analysis.risk_score or 0, 75)
        self.assertTrue(any("Alavancagem" in warning for warning in analysis.warnings))

    def test_healthy_profile_should_be_low_risk(self):
        analysis = analyze_fundamental_risk(
            {
                "net_debt_ebitda": 0.8,
                "ebitda_margin": 0.22,
                "current_ratio": 1.8,
                "free_cash_flow_yield": 0.06,
                "roe": 0.16,
                "revenue_growth_yoy": 0.11,
                "ebitda_growth_yoy": 0.14,
                "profit_quality_score": 80,
            }
        )

        self.assertEqual(analysis.risk_level, "LOW")
        self.assertEqual(analysis.risk_score, 0)
        self.assertGreaterEqual(len(analysis.strengths), 4)

    def test_missing_profile_should_be_unknown(self):
        analysis = analyze_fundamental_risk({})

        self.assertIsNone(analysis.risk_score)
        self.assertEqual(analysis.risk_level, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
