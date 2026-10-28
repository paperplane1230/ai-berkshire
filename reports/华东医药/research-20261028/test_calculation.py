"""Numerical invariants, not validation of future clinical or business outcomes."""
import json
import hashlib
import math
import unittest
from decimal import Decimal as D
from pathlib import Path
import calculate

HERE=Path(__file__).resolve().parent
I=json.loads((HERE/"inputs.json").read_text(encoding="utf-8"))
R=json.loads((HERE/"results.json").read_text(encoding="utf-8"))

class ResearchCalculationTests(unittest.TestCase):
    def test_market_cap_share_units(self):
        self.assertEqual(D(I["price"])*D(I["shares"]),D(R["metrics"]["market_cap"]))
        self.assertEqual(D(R["metrics"]["market_cap"]),D("45825143838.24"))
        self.assertEqual(D(I["shares"]),D("1753736848"))

    def test_ttm_not_nine_month_annualization(self):
        self.assertEqual(D(R["ttm"]["profit"]),D("3438295994.53"))
        self.assertEqual(D(R["ttm"]["adjusted_profit"]),D("3407531153.47"))
        self.assertEqual(D(R["ttm"]["revenue"]),D("43966972364.65"))
        self.assertEqual(D(R["ttm"]["fcf"]),D("2257142029.66"))

    def test_quarter_is_cumulative_less_h1(self):
        self.assertEqual(D(R["q3_current"]["profit"]),D("911119424.81"))
        self.assertEqual(D(R["q3_current"]["adjusted_profit"]),D("932051389.97"))
        self.assertEqual(D(R["q3_current"]["ocf"]),D("-638637273.00"))
        self.assertEqual(D(R["q3_prior"]["ocf"]),D("154003434.08"))
        self.assertEqual(D(R["q3_current"]["capex"]),D("30888828.04"))

    def test_annual_quarter_reconciliation(self):
        self.assertEqual(sum(map(D,["897337982.42","864396273.56","931780891.87"])),D(I["ytd_2025q3"]["adjusted_profit"]))
        self.assertEqual(sum(map(D,["914708484.70","900118376.16","933089158.25","666419307.30"])),D(I["annual"]["2025"]["profit"]))

    def test_full_ocf_bridge(self):
        self.assertEqual(sum(D(v) for v in R["cashflow_bridge"].values()),D("-750069686.55"))
        self.assertEqual(sum(D(v) for v in R["cashflow_bridge"].values()),D(I["ytd_2026q3"]["ocf"])-D(I["ytd_2025q3"]["ocf"]))

    def test_cash_no_double_count(self):
        self.assertEqual(D(R["metrics"]["debt_reference"]),D("2074475682.97"))
        self.assertEqual(D(R["metrics"]["net_cash_reference"]),D("2040182903.17"))
        self.assertLess(D(I["ytd_2026q3"]["cash_equivalents"]),D(I["ytd_2026q3"]["cash"]))

    def test_rd_and_goodwill(self):
        self.assertGreater(D(R["extra"]["h1_capitalization_ratio_2026_pct"]),D(R["extra"]["h1_capitalization_ratio_2025_pct"]))
        self.assertGreater(D(R["extra"]["h1_capitalization_change_after_15pct_tax"]),D(R["extra"]["h1_reported_profit_change"]))
        self.assertEqual(D(R["extra"]["sinclair_headroom"]),D("58559588.35"))
        self.assertLess(D(R["extra"]["sinclair_headroom_pct"]),D("2.2"))

    def test_segment_elimination(self):
        self.assertEqual(D("29449035991.19")+D("15846613196.31")-D("1683639296.48"),D(I["annual"]["2025"]["revenue"]))
        self.assertEqual(D("14099335279.67")+D("8679896494.76")-D("712585588.74"),D(I["h1_2026"]["revenue"]))

    def test_irr_cashflow_root(self):
        self.assertLess(abs(calculate.irr(list(map(D,["-100","5","105"])))-D(".05")),D("1e-25"))
        eps=D(R["metrics"]["eps_adjusted_ttm"])
        for s in R["three_year"]:
            growth,payout=D(s["growth"]),D(s["payout"])
            cfs=[-D(I["price"])]+[eps*(1+growth)**y*payout for y in range(1,4)]
            cfs[-1]+=D(s["price_year3"])
            self.assertLess(abs(calculate.irr(cfs)*100-D(s["cashflow_irr_pct"])),D("1e-24"))

    def test_terminal_timing_and_constraints(self):
        self.assertEqual(sum(D(s["probability"]) for s in R["ten_year"]),1)
        for s in R["ten_year"]:
            self.assertEqual(D(s["profit_year11"]),D(s["profit_year10"])*(1+D(s["terminal_g"])))
            self.assertGreaterEqual(D(s["spread_pp"]),5)
            self.assertLess(abs(D(s["exit_pe"])-(1-D(s["terminal_g"])/D(".12"))/(D(".08")-D(s["terminal_g"]))),D("1e-28"))
        self.assertFalse(R["sensitivity"][0]["all_spreads_valid"])
        self.assertFalse(R["sensitivity"][-1]["valid_currency_band"])

    def test_historical_ocf_not_always_above_profit(self):
        self.assertLess(D(I["older_core"]["2022"]["ocf"]),D(I["older_core"]["2022"]["profit"]))

    def test_audit_effective_population_coverage(self):
        audit=json.loads((HERE/"audit-results.json").read_text(encoding="utf-8"))
        count=audit["eligible_count"]
        self.assertEqual(audit["extracted_count"],count+len(audit["excluded_non_financial"]))
        self.assertEqual(audit["random_sample_count"],math.ceil(count*.15))
        self.assertEqual(len(audit["random_sample"]),audit["random_sample_count"])
        self.assertGreaterEqual(audit["actual_sample_ratio"],.15)
        excluded={p["id"] for p in audit["excluded_non_financial"]}
        self.assertTrue(all(p["id"] not in excluded for p in audit["random_sample"]))
        report=HERE.parent/"华东医药研究报告-20261028.md"
        self.assertEqual(audit["report_sha256"],hashlib.sha256(report.read_bytes()).hexdigest())
        self.assertEqual(audit["outcome"]["verdict"],"PASS")

if __name__ == "__main__":
    unittest.main()
