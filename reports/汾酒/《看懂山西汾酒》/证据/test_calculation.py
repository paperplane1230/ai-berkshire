"""Independent unit/period checks on the fixed Fenjiu series packet."""
import io
import json
import sys
import unittest
from decimal import Decimal as D, getcontext
from pathlib import Path
getcontext().prec=40
HERE=Path(__file__).resolve().parent
data=json.loads((HERE/'source-data.json').read_text(encoding='utf-8'))
out=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
class Check(unittest.TestCase):
    def test_quote_units_and_shares(self):
        self.assertEqual(D(data['shares']),D('1219964222'))
        self.assertEqual(D(data['quote']['price']),D(data['quote']['sina_price']))
        self.assertEqual(D(out['market']['market_cap_yi']),D('1576.803756935'))
    def test_quote_day_is_last_trading_day(self):
        self.assertEqual(data['quote']['date'],'2026-11-13')
        self.assertEqual(data['cutoff'],'2026-11-14')
    def test_ttm_from_annual_and_cumulative(self):
        f=data['financial']
        expected=D(f['2025']['profit'])+D(f['2026YTD']['profit'])-D(f['2025YTD']['profit'])
        self.assertEqual(expected/D('1e8'),D(out['ttm']['profit']))
        self.assertNotEqual(expected,D(f['2026YTD']['profit'])*4/3)
    def test_ttm_quarter_sum(self):
        q=out['periods']
        self.assertEqual(sum(D(q[p]['profit']) for p in ('2025Q4','2026Q1','2026Q2','2026Q3')),D(out['ttm']['profit']))
    def test_restatement_explicit(self):
        checks=json.loads((HERE/'cross-checks.json').read_text(encoding='utf-8'))
        self.assertEqual(len(checks),57)
        differences=[x for x in checks if not x['exact']]
        self.assertEqual(len(differences),1)
        self.assertEqual(differences[0]['period'],'2021')
        self.assertTrue(differences[0]['documented_restatement_difference'])
    def test_quarter_province_difference(self):
        self.assertEqual((D('1053902.30')-D('793815.09'))/D(10000),D('26.008721'))
        self.assertEqual(D(out['operations']['省内']['q3']),D('26.008721'))
        self.assertGreater(D(out['operations']['省内']['q3_yoy_pct']),0)
        self.assertLess(D(out['operations']['省内']['ytd_yoy_pct']),0)
    def test_outside_difference(self):
        self.assertEqual(D(out['operations']['省外']['q3']),D('46.913585'))
        self.assertLess(D(out['operations']['省外']['q3_yoy_pct']),D('-29'))
    def test_alcohol_not_consolidated_revenue(self):
        liquor=D(out['operations']['省内']['q3'])+D(out['operations']['省外']['q3'])
        self.assertLess(liquor,D(out['periods']['2026Q3']['revenue']))
    def test_leases_not_ignored(self):
        self.assertEqual(D(out['cash']['named_lease_and_current_noncurrent']),D('22.3545072901'))
        self.assertEqual(D(out['cash']['narrow_cash_net']),D('46.3302690213'))
        self.assertIsNone(out['cash']['q3_excess_distributable_cash'])
    def test_dividend_fiscal_year_and_date(self):
        self.assertEqual(data['notes']['dividend_profit_year'],'2025')
        self.assertEqual(data['notes']['dividend_ex_and_payment_date'],'2026-07-31')
        self.assertEqual(D('6.56')*D(data['shares']),D(data['notes']['dividend_paid_2026_total']))
    def test_future_dividend_not_paid_history(self):
        for model in out['models'].values():
            expected=D(model['profit_path_yi'][0])*D('1e8')/D(data['shares'])*D('.65')
            self.assertLess(abs(expected-D(model['annual_dividends'][0])),D('1e-25'))
    def test_terminal_forward_year11(self):
        for model in out['models'].values():
            e10=D(model['profit_path_yi'][-1])*D('1e8')/D(data['shares'])
            for row in model['curves']:
                expected=e10*(1+D(row['g']))*D(row['terminal_capacity_forward_pe'])
                self.assertLess(abs(expected-D(row['capacity']['terminal_price'])),D('1e-25'))
    def test_terminal_policy_exact_gordon(self):
        for model in out['models'].values():
            e10=D(model['profit_path_yi'][-1])*D('1e8')/D(data['shares'])
            for row in model['curves']:
                expected=e10*(1+D(row['g']))*D('.65')/(D(row['r'])-D(row['g']))
                self.assertLess(abs(expected-D(row['policy65']['terminal_price'])),D('1e-25'))
    def test_irr_and_pv_independent_identity(self):
        for model in out['models'].values():
            div=list(map(D,model['annual_dividends']))
            for row in model['curves']:
                for mode in ('capacity','policy65'):
                    ir=D(row[mode]['irr_pct'])/100
                    value=sum(c/(1+ir)**t for t,c in enumerate(div,1))+D(row[mode]['terminal_price'])/(1+ir)**10
                    self.assertLess(abs(value-D(data['quote']['price'])),D('1e-25'))
    def test_policy_terminal_lower_and_different_decision(self):
        row=next(x for x in out['models']['strong']['curves'] if x['r']=='0.08')
        self.assertTrue(row['capacity']['covers_r'])
        self.assertFalse(row['policy65']['covers_r'])
        self.assertLess(D(row['policy65']['pv']),D(row['capacity']['pv']))
    def test_rate_validity(self):
        rows=out['models']['strong']['curves']
        self.assertFalse(next(x for x in rows if x['r']=='0.06')['valid_spread'])
        self.assertFalse(next(x for x in rows if x['r']=='0.10')['in_CNY_band'])
    def test_reverse_residual(self):
        self.assertTrue(all(abs(D(x['residual']))<D('1e-25') for x in out['reverse_growth']))
    def test_retained_capital_parameter_is_assumption(self):
        self.assertEqual(D(data['model']['incremental_retained_capital_return_proxy']),D('.20'))
        self.assertEqual(set(data['model']['cases']),{'stress','base','strong'})
if __name__=='__main__':
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Check))
    (HERE/'unit-tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    (HERE/'unit-tests.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)},indent=2)+'\n',encoding='utf-8')
    print(stream.getvalue())
    sys.exit(0 if result.wasSuccessful() else 1)
