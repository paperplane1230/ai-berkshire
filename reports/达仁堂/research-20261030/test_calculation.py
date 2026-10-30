import json
import unittest
from decimal import Decimal as D
from pathlib import Path
from calculate import calculate,irr
HERE=Path(__file__).resolve().parent
class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.I,cls.raw,cls.R=calculate()
    def test_share_classes(self):self.assertEqual(D(self.I['a_shares'])+D(self.I['s_shares']),D(self.I['shares']))
    def test_restricted_a_not_omitted(self):self.assertEqual(D(self.I['a_shares'])-D('567089356'),D('3005000'))
    def test_q3_direct_profit(self):self.assertEqual(self.raw['2026Q3']['profit'],D('272083559.02'))
    def test_q3_direct_core(self):self.assertEqual(self.raw['2026Q3']['core'],D('271312035.10'))
    def test_q3_direct_cash(self):self.assertEqual(self.raw['2026Q3']['cfo'],D('23935676.68'))
    def test_ttm_core(self):self.assertEqual(self.raw['TTM']['core'],D('889048378.03'))
    def test_current_cash_not_cumulative(self):self.assertLess(self.R['periods']['2026Q3']['fcf'],0);self.assertGreater(self.R['periods']['2026YTD']['fcf'],0)
    def test_core_vs_oneoff(self):self.assertLess(abs(self.raw['TTM']['profit']-self.raw['TTM']['core']),D('1e7'))
    def test_segments(self):self.assertEqual(sum(D(self.I['annual_segments'][x]) for x in ('industrial','trade')),self.raw['2025']['revenue'])
    def test_double_sources(self):
        v=json.loads((HERE/'vendor-snapshot.json').read_text(encoding='utf-8'))
        self.assertEqual(len(v['financial'])*4,28)
        for name,row in v['financial'].items():
            for key,value in row.items():self.assertEqual(D(value),self.raw[name][key])
    def test_irr_reference(self):self.assertLess(abs(irr(D(100),[D(5),D(5),D(105)])-D('.05')),D('1e-20'))
    def test_irr_independent_residual(self):
        for s in self.R['scenarios'].values():
            r=float(s['irr_pct'])/100
            pv=sum(float(d)/(1+r)**t for t,d in enumerate(s['dividends'],1))+float(s['terminal_price'])/(1+r)**5
            self.assertAlmostEqual(pv,float(self.I['price']),places=9)
    def test_report_hash(self):
        import hashlib
        a=json.loads((HERE/'audit-summary.json').read_text(encoding='utf-8'))
        self.assertEqual(a['report_sha256'],hashlib.sha256((HERE.parent/'达仁堂研究报告-20261030.md').read_bytes()).hexdigest())
        self.assertGreaterEqual(a['random_coverage_pct'],15)
    def test_logs_clean(self):
        for file in ('audit-verdict.txt','financial-rigor.txt'):
            t=(HERE/file).read_text(encoding='utf-8')
            self.assertNotIn(chr(27),t)
            self.assertTrue(all(x==x.rstrip() for x in t.splitlines()))
if __name__=='__main__':unittest.main()
