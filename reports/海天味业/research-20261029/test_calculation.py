import unittest
from decimal import Decimal as D
from calculate import calculate, irr

class FinancialTests(unittest.TestCase):
    def setUp(self): self.data,self.out=calculate()
    def test_share_classes(self):
        s=self.data['shares']; self.assertEqual(D(s['A'])+D(s['H']),D(s['total']))
    def test_q3_direct_profit(self):
        self.assertEqual(self.out['2026Q3']['profit'],D('11.8967262633'))
    def test_cash_bridge(self):
        self.assertEqual(self.out['2026Q3']['fcf'],D('5.7724556860'))
    def test_ttm_profit(self):
        self.assertEqual(self.out['ttm']['profit'],D('71.0046944666'))
    def test_class_market_cap(self):
        v=self.out['valuation']; self.assertLess(v['combined_cap_CNY_yi'],v['A_equivalent_cap_yi'])
    def test_irr_cashflows(self):
        rate=irr(D(100),[D(5),D(5),D(105)])
        self.assertLess(abs(rate-D('.05')),D('1e-20'))
    def test_scenario_reconciliation(self):
        eps=self.out['ttm']['eps']; fx=D(self.data['quote']['HKDCNY'])
        for i,s in enumerate(self.data['scenarios']):
            r=self.out['scenarios'][i]; growth=D(s['growth']); payout=D(s['payout'])
            self.assertLessEqual(payout,D(1))
            for market,price in [('A',D(self.data['quote']['A_CNY'])),('H',D(self.data['quote']['H_HKD'])*fx)]:
                rate=r[market+'_IRR_pct']/100
                pv=sum(eps*(1+growth)**t*payout/(1+rate)**t for t in range(1,6))
                pv+=r['year5_eps']*D(s[market+'_exit_PE'])/(1+rate)**5
                self.assertLess(abs(pv-price),D('1e-20'))
    def test_historical_special_not_normalized(self):
        d=self.out['dividends'];self.assertEqual(d['including_special']-d['regular'],D('.30'))

if __name__=='__main__': unittest.main()
