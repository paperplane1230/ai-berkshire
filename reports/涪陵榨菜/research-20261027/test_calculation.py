"""Focused numerical invariants for the Fuling research artifacts."""
import json
import unittest
from decimal import Decimal as D
from pathlib import Path
import calculate

HERE = Path(__file__).resolve().parent
I = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
R = json.loads((HERE / "results.json").read_text(encoding="utf-8"))


class ResearchCalculationTests(unittest.TestCase):
    def test_market_cap(self):
        self.assertEqual(D(R["metrics"]["market_cap"]), D("12946971494.16"))
        self.assertEqual(D(I["price"])*D(I["shares"]), D(R["metrics"]["market_cap"]))

    def test_ttm_and_quarter(self):
        self.assertEqual(D(R["ttm"]["profit"]), D("708955706.70"))
        self.assertEqual(D(R["ttm"]["adjusted_profit"]), D("664722356.57"))
        self.assertEqual(D(R["q3_current"]["ocf"]), D("325207828.26"))
        self.assertLess(D(R["q3_comparison"]["ocf_growth_pct"]), 1)
        self.assertGreater(D(R["ytd_comparison"]["ocf_growth_pct"]), 54)

    def test_cash_bridge(self):
        bridge = sum(D(v) for v in R["cashflow_bridge"].values())
        self.assertEqual(bridge, D("244323238.03"))
        self.assertEqual(bridge, D(I["ytd_2026q3"]["ocf"])-D(I["ytd_2025q3"]["ocf"]))

    def test_no_cash_double_count(self):
        self.assertEqual(D(R["metrics"]["liquid_assets_reference"]),D("6392447505.51"))
        self.assertLess(D(I["ytd_2026q3"]["cash_equivalents"]),D(I["ytd_2026q3"]["cash"]))
        self.assertEqual(D(R["sotp_core_profit_proxy"]),D(R["ttm"]["adjusted_profit"])-D(R["ttm"]["interest_income"])*D(".85"))

    def test_seasonal_credit(self):
        self.assertGreater(D(R["metrics"]["contract_yoy_pct"]), 0)
        self.assertLess(D(R["metrics"]["contract_year_start_pct"]), 0)
        self.assertLess(D(R["metrics"]["ar_yoy_pct"]),D(R["metrics"]["ar_year_start_pct"]))

    def test_irr_cashflow_root(self):
        rate = calculate.irr([D("-100"),D("5"),D("105")])
        self.assertLess(abs(rate-D(".05")),D("1e-20"))
        eps = D(R["metrics"]["eps_adjusted_ttm"])
        s = R["three_year"][1]
        cfs = [-D(I["price"])] + [eps*D("1.03")**y*D(".65") for y in range(1,4)]
        cfs[-1] += D(s["price_year3"])
        self.assertLess(abs(calculate.irr(cfs)*100-D(s["cashflow_irr_pct"])),D("1e-20"))

    def test_terminal_timing_and_constraints(self):
        self.assertEqual(sum(D(s["probability"]) for s in R["ten_year"]),1)
        for s in R["ten_year"]:
            g=D(s["terminal_g"])
            self.assertEqual(D(s["profit_year11"]),D(s["profit_year10"])*(1+g))
            self.assertGreaterEqual(D(s["spread_pp"]),5)
            expected=(1-g/D(".15"))/(D(".08")-g)
            self.assertLess(abs(D(s["exit_pe"])-expected),D("1e-25"))
        self.assertFalse(R["sensitivity"][0]["all_spreads_valid"])
        self.assertFalse(R["sensitivity"][-1]["valid_currency_band"])

    def test_dividend_period_bridge(self):
        self.assertEqual(D("230783805.60")+D("253862186.16"),D("484645991.76"))
        self.assertEqual(D(I["historical_dividend_per_share"])*D(I["shares"]),D("484645991.76"))


if __name__ == "__main__":
    unittest.main()
