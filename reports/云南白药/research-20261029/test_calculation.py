import json
import unittest
from decimal import Decimal as D
from pathlib import Path
HERE=Path(__file__).parent
R=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
class FinancialChecks(unittest.TestCase):
    def test_q3_revenue(self):self.assertEqual(D(R['q3']['2026']['revenue']),D('103.7298734438'))
    def test_q3_profit(self):self.assertEqual(D(R['q3']['2026']['profit']),D('11.2118270053'))
    def test_q3_core(self):self.assertEqual(D(R['q3']['2026']['core']),D('11.1249133288'))
    def test_q3_cash(self):self.assertEqual(D(R['q3']['2026']['ocf']),D('7.6811082389'))
    def test_ttm_profit(self):self.assertEqual(D(R['ttm']['profit']),D('51.9872050064'))
    def test_ttm_core(self):self.assertEqual(D(R['ttm']['core']),D('49.4553599149'))
    def test_ttm_fcf(self):self.assertEqual(D(R['valuation']['fcf_ttm']),D('44.8405030372'))
    def test_market_cap(self):self.assertEqual(D(R['valuation']['market_cap_yi']),D('944.4101957679'))
    def test_irr(self):
        eps=D('4945535991.49')/D('1784262603')
        for scenario in R['scenarios'].values():
            growth=D(scenario['growth'])/100;payout=D(scenario['payout'])/100
            r=D(scenario['irr_pct'])/100
            cash=[eps*(1+growth)**t*payout for t in range(1,6)]
            cash[-1]+=eps*(1+growth)**5*D(scenario['exit_pe'])
            npv=sum(c/(1+r)**t for t,c in enumerate(cash,1))-D('52.93')
            self.assertLess(abs(npv),D('0.00000001'))
    def test_no_controls(self):
        report=(HERE.parent/'云南白药研究报告-20261029.md').read_text(encoding='utf-8')
        self.assertFalse(any(ord(ch)<32 and ch not in '\n\r\t' for ch in report))
if __name__=='__main__':unittest.main()
