"""Independent checks of financial bridges and cash-flow valuation."""
import json
import unittest
from decimal import Decimal as D
from pathlib import Path
HERE=Path(__file__).resolve().parent
I=json.loads((HERE/"inputs.json").read_text(encoding="utf-8"))
R=json.loads((HERE/"results.json").read_text(encoding="utf-8"))

class TestCalculation(unittest.TestCase):
    def test_market_cap_and_share_base(self):
        self.assertEqual(D(I["price"])*D(I["shares"]),D("11662598053.64"))
        self.assertEqual(357322814-2405040,int(I["shares"]))
    def test_ttm_not_annualized_q3(self):
        self.assertEqual(D(R["ttm"]["profit"]),D("802055067.08"))
        self.assertEqual(D(R["ttm"]["adjusted_profit"]),D("816767814.56"))
    def test_q3_direct_disclosure(self):
        for key,value in (("revenue","836741184.59"),("profit","274701563.62"),("adjusted_profit","284222460.41")):
            self.assertEqual(D(R["q3_current"][key]),D(value))
        self.assertEqual(D(R["q3_prior"]["profit"]),D("264080331.35"))
    def test_cashflow_bridge(self):
        self.assertEqual(sum(D(v) for v in R["cashflow_bridge"].values()),D("138015516.39"))
        self.assertEqual(D(R["q3_current"]["ocf"]),D("319089087.19"))
    def test_three_year_irr_independent_npv(self):
        eps=float(R["valuation"]["eps_adjusted_ttm"])
        for row in R["three_year"]:
            rate=float(row["cashflow_irr_pct"])/100
            cfs=[-float(I["price"])]+[eps*(1+float(row["growth"]))**y*float(row["payout"]) for y in range(1,4)]
            cfs[-1]+=float(row["target_price"])
            self.assertAlmostEqual(sum(cf/(1+rate)**y for y,cf in enumerate(cfs)),0,places=8)
    def test_ten_year_irr_and_forward_pe(self):
        for row in R["ten_year"]:
            rate=float(row["cashflow_irr_pct"])/100
            cfs=list(map(float,row["cfs"]))
            self.assertAlmostEqual(sum(cf/(1+rate)**y for y,cf in enumerate(cfs)),0,places=4)
            p10=float(row["profit10"]); g=float(row["terminal_g"]); pe=float(row["exit_pe"])
            self.assertAlmostEqual(float(row["profit11"]),p10*(1+g),places=5)
            self.assertAlmostEqual(cfs[-1],p10*float(row["payout"])+p10*(1+g)*pe,places=4)
            self.assertGreaterEqual(float(row["spread_pp"]),5)
    def test_no_perpetual_high_growth(self):
        for row in R["ten_year"]:
            self.assertLessEqual(D(row["terminal_g"]),D(".02"))
            self.assertLessEqual(D(row["growth_next7"]),D(".06"))
    def test_net_cash_no_duplicate_cash_equivalents(self):
        self.assertEqual(D(R["valuation"]["net_cash_after_leases"]),D("432241403.36"))
    def test_price_volume_math(self):
        self.assertAlmostEqual((1+float(R["valuation"]["price_cut_pct"])/100)*(1+float(R["valuation"]["required_volume_lift_pct"])/100),1,places=12)

if __name__=="__main__":
    unittest.main()
