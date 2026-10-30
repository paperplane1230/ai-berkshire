import json
import unittest
from decimal import Decimal as D
from pathlib import Path
from calculate import calculate, irr

HERE=Path(__file__).resolve().parent

class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.i,cls.o=calculate()
    def test_share_classes(self):
        s=self.i['shares'];self.assertEqual(D(s['A'])+D(s['H']),D(s['total']))
        self.assertEqual(D(s['total'])-D(s['prior_total']),D('8937600'))
    def test_primary_q3_profit(self):
        self.assertEqual(self.o['periods']['2026Q3']['profit']*D('1e8'),D('563621244.51'))
    def test_primary_q3_revenue(self):
        self.assertEqual(self.o['periods']['2026Q3']['revenue']*D('1e8'),D('11165972544.63'))
    def test_not_annualised_ytd(self):
        self.assertEqual(self.o['ttm']['profit'],D('42.0427061262'))
    def test_minorities_bridge(self):
        self.assertEqual(self.o['growth']['YTD']['minority_bridge_yi'],D('4.7288732802'))
        self.assertLess(self.o['growth']['YTD']['net_profit'],self.o['growth']['YTD']['profit'])
    def test_q3_cash_turns_negative(self):
        self.assertEqual(self.o['periods']['2026Q3']['cfo'],D('-4.1225055223'))
    def test_lease_cash_not_double_counted(self):
        self.assertEqual(self.o['periods']['2026H1']['fcf_after_lease_cash'],D('13.8173701203'))
        self.assertNotIn('fcf_after_lease_cash',self.o['periods']['2026YTD'])
    def test_market_cap_not_all_A(self):
        v=self.o['valuation'];self.assertLess(v['combined_cap_CNY_yi'],v['A_equivalent_cap_yi'])
        self.assertEqual(v['A_cap_yi'],D('50.30')*D('1952475544')/D('1e8'))
    def test_historical_dividend_share_dates(self):
        actual=D('.25')*D('2068859044')+D('.45')*D('2077796644')
        self.assertEqual(actual,D('1452223250.80'))
        self.assertNotEqual(actual,D('.70')*D(self.i['shares']['total']))
    def test_irr_known_coupon(self):
        self.assertLess(abs(irr(D(100),[D(5),D(5),D(105)])-D('.05')),D('1e-20'))
    def test_scenario_independent_float_residual(self):
        fx=float(self.i['quote']['HKDCNY'])
        for s in self.o['scenarios']:
            for m,price in [('A',50.30),('H',42.44*fx)]:
                r=float(s[m+'_IRR_pct'])/100
                pv=sum(float(x)/(1+r)**t for t,x in enumerate(s['dividends'],1))
                pv+=float(s[m+'_exit_CNY'])/(1+r)**5
                self.assertAlmostEqual(pv,price,places=9)
    def test_cross_source_primary_facts(self):
        rows=json.loads((HERE/'cross-source.json').read_text(encoding='utf-8'))
        self.assertEqual(len(rows),28)
        self.assertTrue(all(D(x['primary'])==D(x['secondary']) for x in rows))

if __name__=='__main__':unittest.main()
