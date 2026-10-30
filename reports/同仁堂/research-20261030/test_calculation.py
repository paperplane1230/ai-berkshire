import hashlib
import json
import unittest
from decimal import Decimal as D
from pathlib import Path
from calculate import calculate,irr
HERE=Path(__file__).resolve().parent
I,rows,R=calculate()
class ResearchTests(unittest.TestCase):
    def test_primary_q3_profit(self):self.assertEqual(rows['2026Q3']['profit'],D('139538314.73'))
    def test_primary_q3_revenue(self):self.assertEqual(rows['2026Q3']['revenue'],D('2679807105.22'))
    def test_q3_cash(self):self.assertEqual(rows['2026Q3']['ocf'],D('146899367.03'))
    def test_ttm_profit(self):self.assertEqual(rows['TTM']['profit'],D('877548511.93'))
    def test_current_shares(self):self.assertEqual(D(I['price'])*D(I['shares']),R['valuation']['market_cap_yi']*D('1e8'))
    def test_minority_loss_not_added_to_parent(self):
        self.assertLess(R['periods']['2026Q3']['minority_profit'],0)
        self.assertLess(rows['2026Q3']['group_profit'],rows['2026Q3']['profit'])
    def test_nested_stakes(self):
        self.assertEqual(R['business']['guoyao_lookthrough_stake'],D('51.446425'))
        self.assertNotEqual(R['business']['guoyao_lookthrough_stake'],D('71.67'))
    def test_industry_elimination(self):
        b=I['business']; total=sum(D(b[k]) for k in ('h1_industrial_revenue','h1_commercial_revenue','h1_other_revenue'))-D(b['h1_elimination'])
        self.assertEqual(total,D(b['h1_main_revenue']))
    def test_irr(self):self.assertAlmostEqual(float(irr(D(100),[D(5)]*5,D(100))),.05,places=12)
    def test_all_scenarios_independent_residual(self):
        for s in R['scenarios'].values():
            r=float(s['irr_pct'])/100
            pv=sum(float(x)/(1+r)**t for t,x in enumerate(s['dividends'],1))+float(s['exit_price'])/(1+r)**5
            self.assertAlmostEqual(pv,25.07,places=10)
    def test_rounding_differences_not_hidden(self):
        checks=json.loads((HERE/'cross-source.json').read_text(encoding='utf-8'))
        self.assertEqual(len(checks),28)
        self.assertTrue(any(D(x['primary'])!=D(x['secondary']) for x in checks))
        self.assertTrue(all(D(x['difference_pct'])<D('.01') for x in checks))
    def test_report_and_sample(self):
        report=(HERE.parent/'同仁堂研究报告-20261030.md').read_bytes()
        a=json.loads((HERE/'audit-summary.json').read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256(report).hexdigest(),a['report_sha256'])
        self.assertGreaterEqual(a['random_count']/a['effective_population'],.15)
        self.assertFalse(any(c<32 and c not in (9,10,13) for c in report))
        self.assertNotIn('\x1b',(HERE/'audit-verdict.txt').read_text(encoding='utf-8'))
if __name__=='__main__':unittest.main()
