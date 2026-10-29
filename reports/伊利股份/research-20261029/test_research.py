import json
import unittest
from decimal import Decimal as D
from pathlib import Path
HERE=Path(__file__).resolve().parent
I=json.loads((HERE/'inputs.json').read_text(encoding='utf-8'))
C=json.loads((HERE/'calculations.json').read_text(encoding='utf-8'))

class ResearchTests(unittest.TestCase):
    def test_primary_q3_profit(self):
        self.assertEqual(D(C['periods']['2026q3']['profit'])*D('1e8'),D('3045142053.73'))
    def test_primary_q3_revenue(self):
        self.assertEqual(D(C['periods']['2026q3']['revenue'])*D('1e8'),D('29250582318.09'))
    def test_ttm_not_annualised_ytd(self):
        self.assertEqual(D(C['ttm']['profit'])*D('1e8'),D('9942834032.29'))
    def test_current_shares_market_cap(self):
        self.assertEqual(D(C['valuation']['market_cap_yi'])*D('1e8'),D('29.45')*D('6325360667'))
    def test_quarter_cashflow_decline(self):
        self.assertLess(D(C['growth']['q3']['ocf']),0)
        self.assertGreater(D(C['growth']['ytd']['ocf']),0)
    def test_not_mother_company_cashflow(self):
        self.assertEqual(D(I['periods']['2026ytd']['ocf']),D('15441464454.51'))
        self.assertNotEqual(D(I['periods']['2026ytd']['ocf']),D('39649098007.27'))
    def test_segment_weights(self):
        self.assertAlmostEqual(sum(D(C['segment_weights'][k]) for k in ('liquid','powder','icecream','other')),D('100'),places=20)
    def test_irr_independent_float_residual(self):
        for s in C['scenarios'].values():
            r=float(s['irr_pct'])/100
            pv=sum(float(x)/(1+r)**t for t,x in enumerate(s['dividends'],1))+float(s['terminal_price'])/(1+r)**5
            self.assertAlmostEqual(pv,29.45,places=9)
    def test_scenario_model(self):
        self.assertAlmostEqual(float(C['scenarios']['base']['terminal_price']),1.75*1.04**5*16,places=10)
    def test_exact_cross_sources(self):
        checks=json.loads((HERE/'cross_checks.json').read_text(encoding='utf-8'))
        self.assertEqual(len(checks),69)
        self.assertTrue(all(D(x['primary'])==D(x['secondary']) for x in checks))
    def test_single_source_not_fake_double(self):
        gaps=json.loads((HERE/'source-gaps.json').read_text(encoding='utf-8'))
        self.assertEqual(len(gaps),2)
        self.assertTrue(all('NOT counted' in x['note'] for x in gaps))
    def test_report_and_audit(self):
        import hashlib
        report=(HERE.parent/'伊利股份研究报告-20261029.md').read_bytes()
        self.assertFalse(any(c<32 and c not in (9,10,13) for c in report))
        audit=json.loads((HERE/'audit-summary.json').read_text(encoding='utf-8'))
        self.assertEqual(audit['sha256'],hashlib.sha256(report).hexdigest())
        self.assertEqual(audit['verdict']['verdict'],'PASS')
        self.assertGreaterEqual(audit['random_sample']/audit['effective'],.15)

if __name__=='__main__': unittest.main()
