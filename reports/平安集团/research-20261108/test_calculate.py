"""Independent arithmetic/accounting tests with fixed source-anchored expectations."""
import io
import json
import sys
sys.dont_write_bytecode=True
import unittest
from decimal import Decimal as D
from pathlib import Path
from calculate import calculate, ROOT, OUT
sys.stdout.reconfigure(encoding="utf-8",errors="replace")

class ResearchChecks(unittest.TestCase):
    def setUp(self):
        self.data=calculate()
        self.m=self.data["market"]
    def test_share_partition(self):
        self.assertEqual(self.m["all_shares"],D("18107641995"))
        self.assertEqual(D("10660065083")+D("7447576912"),self.m["all_shares"])
    def test_both_quote_channels(self):
        base=ROOT/"local/三季报-20261108/pingan"
        qq=(base/"qq.txt").read_text(encoding="utf-8")
        sina=(base/"sina.txt").read_text(encoding="utf-8")
        self.assertIn("~601318~54.50~",qq)
        self.assertIn("~02318~53.150~",qq)
        self.assertIn(",54.500,",sina)
        self.assertIn(",53.150,",sina)
    def test_class_market_cap_currency(self):
        self.assertEqual(self.m["a_class_cap_cny_yi"],D("5809.735470235"))
        self.assertEqual(self.m["h_class_cap_hkd_yi"],D("3958.387128728"))
        self.assertEqual(self.m["actual_combined_cap_cny_yi"],D("9181.1005170307564376"))
        self.assertLess(self.m["actual_combined_cap_cny_yi"],self.m["a_reference_all_cap_cny_yi"])
    def test_ttm_not_nine_month_annualization(self):
        self.assertEqual(self.m["net_profit_ttm_yi"],D("985.67"))
        self.assertEqual(self.m["opat_ttm_yi"],D("1440.56"))
        self.assertNotEqual(self.m["net_profit_ttm_yi"],D("966.45")*4/3)
    def test_quarterly_difference(self):
        self.assertEqual(self.data["derivations"]["nbv_q3_2026"],D("61.40"))
        self.assertEqual(self.data["derivations"]["nbv_q3_2025"],D("133.89"))
        self.assertEqual(self.data["derivations"]["q3_net_profit"],D("40.60"))
    def test_opat_and_minority_bridge(self):
        self.assertEqual(sum(map(D,("824.92","46.96","227.13","194.23","-5.06","-29.13"))),D("1259.05"))
        self.assertEqual(D("1480.63")-D("339.57")+D("44.62")-D("219.22"),D("966.46"))
        # Original filing rounds million amounts independently; 0.01 yi = RMB1m.
        self.assertLessEqual(abs(D("966.46")-D("966.45")),D("0.01"))
    def test_ex_asset_management_growth(self):
        self.assertEqual(self.data["derivations"]["am_increment"],D("167.69"))
        self.assertLess(self.data["derivations"]["ex_am_opat_growth_pct"],D("-6.27"))
        self.assertGreater(self.data["derivations"]["ex_am_opat_growth_pct"],D("-6.28"))
    def test_csm_rollforward(self):
        self.assertEqual(D("725119")+D("29811")+D("10586")+D("5843")-D("33584"),D("737775"))
        self.assertLess(D("29811"),D("33584"))
    def test_ev_no_double_count(self):
        self.assertEqual(D("970839")+D("596961"),D("1567800"))
        self.assertEqual(self.m["h1_evps"].quantize(D("0.01")),D("86.58"))
    def test_parent_cash_scope(self):
        self.assertEqual(D("44024")-D("42758"),D("1266"))
        self.assertEqual(self.data["derivations"]["parent_invest_cash_less_div_interest"],D("12.66"))
    def test_immediate_scenarios(self):
        expected=(D("36.45"),D("61.85"),D("88.36"))
        self.assertEqual(tuple(x["immediate_value_cny"].quantize(D("0.01")) for x in self.data["immediate_scenarios"]),expected)
    def test_ddm_and_reverse_growth(self):
        self.assertEqual(D("2.73")*D("1.04")/D("0.06"),D("47.32"))
        g=self.m["a_reverse_div_growth_r10_pct"]/100
        implied=D("2.73")*(1+g)/(D("0.10")-g)
        self.assertLess(abs(implied-D("54.50")),D("0.000000000000000001"))
    def test_portal_filing_numbers(self):
        rows=json.loads((ROOT/"local/三季报-20261108/pingan/eastmoney.json").read_text(encoding="utf-8"))["result"]["data"]
        row=next(x for x in rows if x["REPORT_DATE"].startswith("2026-09-30"))
        self.assertEqual(row["PARENTNETPROFIT"],96645000000)
        self.assertEqual(row["NBV_LIFE"],30987000000)
        self.assertEqual(row["EARNED_PREMIUM"],422944000000)
        self.assertEqual(row["NETCASH_OPERATE_PK"],566872000000)

if __name__=="__main__":
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ResearchChecks))
    (OUT/"tests.txt").write_text(stream.getvalue(),encoding="utf-8")
    (OUT/"tests.json").write_text(json.dumps({"tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors)},indent=2)+"\n",encoding="utf-8")
    print(stream.getvalue())
    sys.exit(0 if result.wasSuccessful() else 1)
