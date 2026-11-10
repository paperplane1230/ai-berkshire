"""Independent checks of frozen source values, units and model identities."""
import json
import io
import sys
import unittest
from decimal import Decimal as D, getcontext
from pathlib import Path
getcontext().prec=40
HERE=Path(__file__).resolve().parent
data=json.loads((HERE/'source-data.json').read_text(encoding='utf-8'))
result=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
shares=D(data['shares'])
class Checks(unittest.TestCase):
    def test_share_and_market_units(self):
        self.assertEqual(shares,D('1506445074'))
        self.assertEqual(D('37.24')*shares/D('1e8'),D(result['market']['market_cap_yi']))
        self.assertEqual(D(result['market']['market_cap_yi']),D('561.0001455576'))
    def test_two_quote_prices_and_day(self):
        self.assertEqual(D(data['quote']['price']),D(data['quote']['sina_price']))
        self.assertEqual(data['quote']['date'],'2026-11-10')
        self.assertTrue(data['quote']['tencent_timestamp'].startswith('20261110'))
    def test_ttm_not_profit_growth_base(self):
        value=D('2206058926.68')+D('1830804016.17')-D('3975002897.08')
        self.assertEqual(value/D('1e8'),D('0.6186004577'))
        self.assertEqual(value/D('1e8'),D(result['market']['ttm_profit_yi']))
    def test_q3_difference(self):
        self.assertEqual(D('1830804016.17')-D('2601710694.52'),D('-770906678.35'))
        self.assertEqual(D('11821851942.02')-D('10540431576.04'),D('1281420365.98'))
    def test_contract_liability_split(self):
        self.assertEqual(D('775673065.92')+D('3528164914.53'),D('4303837980.45'))
        self.assertGreater(D('3528164914.53')/D('4303837980.45'),D('.8'))
    def test_inventory_transcription(self):
        self.assertEqual(D(data['annual']['2025']['inventory']),D('20375489436.78'))
        self.assertEqual(data['annual']['2025']['inventory'],data['balance']['2025end']['inventory'])
    def test_restatement_preserved(self):
        row=data['annual']['2021']
        self.assertEqual(D(row['profit'])-D(row['profit_original']),D('58801.63'))
        checks=json.loads((HERE/'cross-checks.json').read_text(encoding='utf-8'))
        self.assertEqual(sum(not x['exact'] for x in checks),1)
    def test_financial_asset_tiers(self):
        liq=result['liquidity']
        self.assertEqual(D(liq['cash_and_trading_net_yi'])-D(liq['cash_equivalents_net_yi']),D('86.6304130053'))
        self.assertEqual(D(liq['financial_pool_book_net_yi']),D('228.9177082125'))
    def test_discounted_core_cash_and_year11(self):
        case=result['core_dcf']['recovery']
        profits=list(map(D,case['profit_path_yi']))
        cash=list(map(D,case['operating_cash_path_yi']))
        r,g,roic=D('.08'),D('.01'),D('.15')
        value=sum(c/(1+r)**t for t,c in enumerate(cash,1))
        value+=profits[-1]*(1+g)*(1-g/roic)/(r-g)/(1+r)**10
        row=next(x for x in case['curve'] if x['r']=='0.08')
        self.assertLess(abs(value-D(row['operating_pv_yi'])),D('1e-30'))
        self.assertLess(abs((value+D(150))*D('1e8')/shares-D(row['value_per_share'])),D('1e-30'))
    def test_narrow_spread_and_out_of_band(self):
        rows=result['core_dcf']['strong']['curve']
        self.assertFalse(next(x for x in rows if x['r']=='0.06')['valid_spread'])
        self.assertFalse(next(x for x in rows if x['r']=='0.10')['in_CNY_band'])
    def test_terminal_cash_conversion_sensitivity(self):
        for case in result['core_dcf'].values():
            for row in case['curve']:
                self.assertLessEqual(D(row['terminal_conversion_unchanged_value_per_share']),D(row['value_per_share']))
    def test_loss_year_not_softened_by_conversion_ratio(self):
        case=result['core_dcf']['stress']
        self.assertEqual(D(case['operating_cash_path_yi'][0]),D('-3'))
        self.assertEqual(D(case['profit_path_yi'][0]),D('-3'))
    def test_whole_equity_irr_residual(self):
        price=D(data['quote']['price'])
        for case in result['whole_equity'].values():
            dividends=list(map(D,case['dividends']))
            for row in case['curve']:
                rate=D(row['irr_pct'])/100
                receipts=sum(c/(1+rate)**t for t,c in enumerate(dividends,1))
                receipts+=D(row['exit_price'])/(1+rate)**10
                self.assertLess(abs(receipts-price),D('1e-25'))
    def test_asset_not_added_twice(self):
        for case in result['core_dcf'].values():
            for row in case['curve']:
                self.assertLess(abs(D(row['total_equity_value_yi'])-D(row['operating_pv_yi'])-D(row['net_asset_value_A_yi'])),D('1e-30'))
    def test_reverse_model_matches_price(self):
        reverse=result['reverse_core_base_scaling']
        base=next(x for x in result['core_dcf']['recovery']['curve'] if x['r']=='0.08')
        mcap=D(base['operating_pv_yi'])*D(reverse['scale'])+D(150)
        self.assertLess(abs(mcap-D(result['market']['market_cap_yi'])),D('1e-30'))
    def test_delayed_assets_no_free_interest(self):
        for row in result['asset_release_delay_no_extra_income']:
            self.assertEqual(D(row['present_value_yi']),D(150)/D('1.08')**row['years'])
if __name__=='__main__':
    stream=io.StringIO()
    tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    (HERE/'unit-tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    (HERE/'unit-tests.json').write_text(json.dumps({'tests':tests.testsRun,'failures':len(tests.failures),'errors':len(tests.errors)},indent=2)+'\n',encoding='utf-8')
    print(stream.getvalue())
    sys.exit(0 if tests.wasSuccessful() else 1)
