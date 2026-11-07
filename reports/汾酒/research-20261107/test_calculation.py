"""Portable regression checks for primary inputs, derived quarters and scenarios."""
import contextlib
import io
import json
import unittest
from decimal import Decimal
from pathlib import Path
import calculate as c


class FinancialEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.out = c.calculate()

    def test_primary_values_are_exact_strings(self):
        for group in ("financial", "balance", "primary_quarter_checks"):
            for row in self.data[group].values():
                for value in row.values():
                    self.assertIsInstance(value, str)
                    self.assertTrue(Decimal(value).is_finite())

    def test_quarter_reconciliation(self):
        self.assertTrue(all(row["passed"] for row in self.out["primary_quarter_reconciliation"]))
        self.assertEqual(self.out["periods"]["2026Q3"]["cfo"], Decimal("12.8275595705"))
        self.assertEqual(self.out["periods"]["2026Q2"]["cfo"], Decimal("-16.0206834804"))

    def test_exact_ttm(self):
        self.assertEqual(self.out["ttm"]["profit"], Decimal("91.7971031184"))
        self.assertEqual(self.out["ttm"]["revenue"], Decimal("341.7573992158"))
        self.assertEqual(self.out["ttm"]["cfo"], Decimal("79.6570999827"))
        self.assertEqual(self.out["ttm"]["simple_fcf"], Decimal("71.6237691461"))

    def test_registered_shares_not_derived_from_market_cap(self):
        self.assertEqual(self.data["shares"], "1219964222")
        self.assertEqual(self.out["valuation"]["market_cap"], Decimal("1610.35277304"))
        self.assertEqual(Decimal(self.data["notes"]["dividend_paid_2026_total"]),
                         Decimal(self.data["shares"])*Decimal(self.data["notes"]["dividend_paid_2026_per_share"]))

    def test_dividend_is_prior_earnings_and_not_forward_promise(self):
        self.assertEqual(self.data["notes"]["dividend_profit_year"], "2025")
        self.assertEqual(self.data["notes"]["dividend_ex_and_payment_date"], "2026-07-31")
        self.assertGreater(self.out["valuation"]["same_dividend_to_TTM_profit_pct"], Decimal("87"))
        self.assertLess(self.out["valuation"]["paid_dividend_to_FY2025_profit_pct"], Decimal("66"))

    def test_cash_excludes_unverified_other_current_assets_and_bills(self):
        quality = self.out["cash_and_quality"]
        self.assertIsNone(quality["Q3_freely_distributable_excess_cash"])
        self.assertEqual(quality["named_lease_and_current_noncurrent_debt"], Decimal("22.3545072901"))
        self.assertEqual(quality["cash_equivalents_less_named_debt"], Decimal("46.3302690213"))
        self.assertGreater(quality["other_current_assets_excluded_pending_breakdown"], Decimal("200"))

    def test_profit_bridge(self):
        self.assertTrue(self.out["Q3_parent_profit_bridge"]["sum_equals_profit_change"])
        self.assertGreater(self.out["Q3_parent_profit_bridge"]["tax_surcharges_effect"], 0)
        self.assertLess(self.out["growth"]["Q3"]["margin_changes_pp"]["gross_margin_pct"], Decimal("-4.5"))

    def test_28_cross_source_checks(self):
        with contextlib.redirect_stdout(io.StringIO()):
            rows = c.cross_source(self.data)
        self.assertEqual(len(rows), 28)
        self.assertTrue(all(row["passed"] for row in rows))
        self.assertEqual(len({(row["period"], row["metric"]) for row in rows}), 28)

    def test_scenario_no_cash_double_count(self):
        self.assertEqual(len(self.out["scenarios"]), 3)
        for row in self.out["scenarios"]:
            self.assertEqual(row["terminal_price_CNY"], row["annual_EPS_CNY"][-1]*row["exit_PE"])
            self.assertLess(abs(row["IRR_residual_CNY"]), Decimal("1e-25"))
            self.assertGreater(row["IRR_pct"], row["no_dividend_IRR_pct"])
            self.assertEqual(len(row["cashflows_CNY"]), 6)

    def test_scenario_core_base_and_parameters(self):
        for row, growth, multiple in zip(self.out["scenarios"], ("-5", "2", "6"), ("12", "16", "20")):
            self.assertEqual(row["initial_core_profit"], self.out["ttm"]["core"])
            self.assertEqual(row["annual_growth_pct"], Decimal(growth))
            self.assertEqual(row["exit_PE"], Decimal(multiple))
            self.assertEqual(row["annual_payouts"], [Decimal("0.65")]*5)
        self.assertAlmostEqual(self.out["scenarios"][1]["PV10_CNY"], Decimal("102.1346513306286096"), places=14)

    def test_reverse_growth(self):
        result = self.out["required_growth_for_10pct_IRR"]
        self.assertLess(abs(result["PV_residual_CNY"]), Decimal("1e-25"))
        self.assertAlmostEqual(result["annual_growth_pct"], Decimal("7.82827220048337"), places=12)
        self.assertGreater(result["annual_growth_pct"], Decimal("2"))

    def test_quote_sources_agree(self):
        quote = self.data["quote"]
        self.assertEqual(Decimal(quote["price"]), Decimal(quote["sina_price"]))
        self.assertEqual(Decimal(quote["price"]), Decimal(quote["tencent_price"]))
        self.assertEqual(quote["tencent_total_shares"], self.data["shares"])
        self.assertEqual(quote["sina_time"][:10], quote["date"])
        self.assertEqual(quote["tencent_time"][:8], quote["date"].replace("-", ""))

    def test_cashflow_discount_timing(self):
        self.assertEqual(c.pv([Decimal("110")], Decimal("0.10")), Decimal("100"))
        self.assertAlmostEqual(c.irr(Decimal("100"), [Decimal("110")]), Decimal("0.10"), places=28)
        with self.assertRaises(ValueError):
            c.irr(Decimal("100"), [Decimal("-1")])

    def test_clean_log(self):
        log = (Path(__file__).parent / "financial-rigor.txt").read_text(encoding="utf-8")
        self.assertNotIn("\x1b", log)
        self.assertTrue(all(line == line.rstrip() for line in log.splitlines()))


if __name__ == "__main__":
    unittest.main()
