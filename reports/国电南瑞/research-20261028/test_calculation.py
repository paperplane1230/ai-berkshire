"""Numerical invariants, not a financial audit or a test of future assumptions."""
import json
import unittest
from decimal import Decimal as D
from pathlib import Path
import calculate

HERE=Path(__file__).resolve().parent
I=json.loads((HERE/"inputs.json").read_text(encoding="utf-8"))
R=json.loads((HERE/"results.json").read_text(encoding="utf-8"))

class NariCalculationTests(unittest.TestCase):
    def test_market_cap_not_treasury_adjusted(self):
        self.assertEqual(D(I["price"])*D(I["shares"]),D(R["metrics"]["market_cap"]))
        self.assertEqual(D(I["shares"]),D("8031756156"))

    def test_ttm_identity(self):
        for key in ["revenue","profit","adjusted_profit","ocf","capex"]:
            expected=D(I["annual"]["2025"][key])+D(I["ytd_2026q3"][key])-D(I["ytd_2025q3"][key])
            self.assertEqual(expected,D(R["ttm"][key]))

    def test_quarter_is_not_ytd(self):
        for key in ["revenue","profit","adjusted_profit","ocf"]:
            self.assertEqual(D(R["q3_current"][key]),D(I["ytd_2026q3"][key])-D(I["h1_2026"][key]))
        self.assertLess(D(R["q3_current"]["ocf"]),0)
        self.assertLess(D(R["growth_q3_pct"]["profit"]),0)

    def test_cash_bridge(self):
        self.assertEqual(sum(D(v) for v in R["cashflow_bridge"].values()),D(I["ytd_2026q3"]["ocf"])-D(I["ytd_2025q3"]["ocf"]))

    def test_cash_not_added_twice(self):
        n=I["ytd_2026q3"]
        self.assertEqual(D(R["metrics"]["cash_plus_trading"]),D(n["cash"])+D(n["trading_assets"]))
        self.assertGreaterEqual(D(n["cash"]),D(n["cash_equivalents"]))
        for row in R["three_year"]:
            eps=D(R["metrics"]["eps_adjusted_ttm"])*(1+D(row["growth"]))**3
            self.assertAlmostEqual(D(row["price_year3"]),eps*D(row["pe"]),places=23)

    def test_dividend_arithmetic_and_period(self):
        self.assertEqual(D(".147")+D(".475"),D(I["dividend_2025_per_share"]))
        self.assertEqual(D(".475")+D(".153"),D(".628"))

    def test_terminal_timing_and_constraints(self):
        self.assertEqual(sum(D(s["probability"]) for s in R["ten_year"]),1)
        for s in R["ten_year"]:
            self.assertAlmostEqual(D(s["profit_year11"]),D(s["profit_year10"])*(1+D(s["terminal_g"])),places=19)
            self.assertAlmostEqual(D(s["terminal_market_cap"]),D(s["profit_year11"])*D(s["exit_forward_pe"]),places=19)
            self.assertGreaterEqual(D(s["spread_pp"]),5)
        self.assertFalse(R["sensitivity"][0]["all_spreads_valid"])
        self.assertFalse(R["sensitivity"][-1]["currency_band_valid"])

    def test_cashflow_irr(self):
        self.assertLess(abs(calculate.irr([D("-100"),D("5"),D("105")])-D(".05")),D("1e-25"))
        s=R["ten_year"][1]
        rate=D(s["cashflow_irr_pct"])/100
        profit=D(R["ttm"]["adjusted_profit"])
        flows=[-D(R["metrics"]["market_cap"])]+[profit*(1+D(s["growth"]))**y*D(I["ten_year_assumptions"]["payout"]) for y in range(1,11)]
        flows[-1]+=D(s["terminal_market_cap"])
        self.assertLess(abs(sum(v/(1+rate)**t for t,v in enumerate(flows))),D("1e-15"))

if __name__=="__main__":
    unittest.main()
