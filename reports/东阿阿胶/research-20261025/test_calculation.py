import json
from decimal import Decimal as D
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
I = json.loads((HERE/"inputs.json").read_text(encoding="utf-8"))
R = json.loads((HERE/"results.json").read_text(encoding="utf-8"))


class ReportCalculationTest(unittest.TestCase):
    def test_market_cap_units(self):
        self.assertEqual(D(R["metrics"]["market_cap"]), D(I["price"])*D(I["shares"]))
        self.assertTrue(D("3e10") < D(R["metrics"]["market_cap"]) < D("3.1e10"))

    def test_ttm_periods(self):
        for key in ("revenue","profit","adjusted_profit","ocf","capex"):
            expected = D(I["annual_original"]["2025"][key])+D(I["ytd_2026q3"][key])-D(I["ytd_2025q3"][key])
            self.assertEqual(D(R["ttm"][key]), expected)

    def test_cashflow_bridge(self):
        self.assertEqual(sum(D(v) for v in R["cashflow_bridge"].values()),
                         D(I["ytd_2026q3"]["ocf"])-D(I["ytd_2025q3"]["ocf"]))

    def test_year11_terminal_alignment(self):
        r = D(I["ten_year_assumptions"]["r"])
        roic = D(I["ten_year_assumptions"]["roic"])
        for s in R["ten_year"]:
            g = D(s["terminal_g"])
            self.assertEqual(D(s["profit_year11"]),D(s["profit_year10"])*(1+g))
            self.assertEqual(D(s["exit_pe"]),(1-g/roic)/(r-g))

    def test_true_irr_zeroes_npv(self):
        initial = D(R["metrics"]["market_cap"])
        profit = D(R["ttm"]["adjusted_profit"])
        payout = D(I["ten_year_assumptions"]["payout_ratio"])
        for s in R["ten_year"]:
            rate, growth = D(s["cashflow_irr_pct"])/100,D(s["growth"])
            npv = -initial + sum(profit*(1+growth)**year*payout/(1+rate)**year for year in range(1,11))
            npv += D(s["profit_year11"])*D(s["exit_pe"])/(1+rate)**10
            self.assertLess(abs(npv),D("0.01"))

    def test_no_private_portfolio_in_report(self):
        text = (HERE.parent/"东阿阿胶研究报告-20261025.md").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"用户现金\s*[:：]\s*[\d,.]+")
        self.assertNotIn("stocks.json",text)


if __name__ == "__main__":
    unittest.main()
