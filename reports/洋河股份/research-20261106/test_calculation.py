"""Offline regressions for signs, quarter reconciliation, cash scope and IRR."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch

import calculate as calc


class CalculationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.out = calc.calculate()

    def test_ttm_bridge_exact(self):
        self.assertEqual(self.out['ttm']['profit'], calc.D('0.6186004577'))
        self.assertEqual(self.out['ttm']['core'], calc.D('1.7543622546'))
        self.assertEqual(self.out['ttm']['cfo'], calc.D('-16.1367815375'))
        self.assertEqual(self.out['ttm']['simple_fcf'], calc.D('-21.131166451'))

    def test_quarter_reconciliation(self):
        self.assertGreaterEqual(len(self.out['primary_quarter_reconciliation']), 11)
        self.assertTrue(all(row['passed'] for row in self.out['primary_quarter_reconciliation']))
        self.assertEqual(self.out['periods']['2026Q3']['cfo'], calc.D('-2.1919312475'))
        self.assertEqual(self.out['periods']['2025Q4']['profit'], calc.D('-17.6894397040'))

    def test_negative_prior_sign_not_misleading(self):
        change = self.out['growth']['Q3']['profit']
        self.assertLess(change['pct_vs_absolute_base'], 0)
        self.assertLess(change['absolute_change'], 0)
        self.assertIsNone(self.out['periods']['2026Q3']['cfo_parent_ratio_pct'])

    def test_market_cap_and_two_quotes(self):
        self.assertEqual(self.out['valuation']['market_cap'], calc.D('570.3401050164'))
        self.assertEqual(calc.D(self.data['quote']['price']), calc.D(self.data['quote']['sina_price']))
        self.assertGreater(self.out['valuation']['TTM_PE'], 900)

    def test_cash_excludes_long_term_investments(self):
        quality = self.out['cash_and_quality']
        self.assertEqual(quality['named_interest_and_lease_debt'], calc.D('2.0165958472'))
        self.assertEqual(quality['cash_plus_trading_assets_less_named_debt'], calc.D('182.4884207496'))
        self.assertEqual(quality['excluded_noncurrent_financial_assets'], calc.D('33.3360436859'))
        self.assertEqual(quality['excluded_long_equity_investments'], calc.D('13.093243777'))

    def test_contract_liabilities_not_all_advances(self):
        row = self.out['contract_split']['2025end']
        self.assertEqual(row['prepayments']+row['unsettled_rebates'], row['total'])
        self.assertGreater(row['rebates_pct'], 50)

    def test_28_independent_publication_checks(self):
        with contextlib.redirect_stdout(io.StringIO()):
            checks = calc.cross_source(self.data)
        self.assertEqual(len(checks), 28)
        self.assertTrue(all(row['passed'] for row in checks))
        self.assertTrue(all(row['deviation_pct_primary_denominator']==0 for row in checks))

    def test_negative_cfo_cross_source_uses_absolute_denominator(self):
        vendor = calc.load('vendor-snapshot.json')
        vendor['financial']['2025']['cfo'] = '-900000000'
        with patch.object(calc, 'load', return_value=vendor), contextlib.redirect_stdout(io.StringIO()):
            checks = calc.cross_source(self.data)
        row = next(item for item in checks if item['label']=='2025:cfo')
        self.assertFalse(row['passed'])
        self.assertGreater(row['deviation_pct_primary_denominator'], 1)

    def test_h1_contract_and_inventory_scope(self):
        row = self.out['contract_split']['2026H1']
        self.assertEqual(row['prepayments'], calc.D('7.7567306592'))
        self.assertGreater(row['rebates_pct'], 80)
        self.assertGreater(self.out['inventory_split_H1']['semi_finished_inventory_pct'], 90)
        self.assertLess(self.out['inventory_split_H1']['finished_goods_change_pct'], -60)

    def test_scenarios_dividend_policy_not_fixed_cash_floor(self):
        for row in self.out['scenarios']:
            self.assertEqual(row['payouts'], [calc.D('1')]+[calc.D('.8')]*4)
            for dividend, eps, payout in zip(row['annual_dividend_CNY'], row['annual_EPS_CNY'], row['payouts']):
                self.assertEqual(dividend, eps*payout)
            self.assertEqual(row['terminal_price_CNY'], row['annual_EPS_CNY'][-1]*row['exit_PE'])

    def test_scenario_npv_and_unique_irr(self):
        rates = []
        for row in self.out['scenarios']:
            residual = calc.pv(row['cashflows_CNY'][1:], row['IRR_pct']/100) + row['cashflows_CNY'][0]
            self.assertLess(abs(residual), calc.D('1e-30'))
            self.assertLess(abs(row['IRR_residual_CNY']), calc.D('1e-30'))
            self.assertLess(row['NPV10_CNY'], 0)
            rates.append(row['IRR_pct'])
        self.assertEqual(rates, sorted(rates))
        self.assertLess(rates[-1], 10)

    def test_asset_reverse_sensitivity_is_separate_exact_bridge(self):
        result = self.out['asset_reverse_sensitivity']
        self.assertEqual(len(result['rows']), 12)
        for row in result['rows']:
            asset = row['separable_financial_asset_value_A']*calc.Y
            self.assertEqual(row['exact_numerator_CNY'], result['market_cap_CNY']-asset)
            residual = row['required_core_after_tax_profit_CNY']*row['core_after_tax_multiple_M']+asset-result['market_cap_CNY']
            self.assertLess(abs(residual), calc.D('1e-27'))
        cell = next(row for row in result['rows'] if row['separable_financial_asset_value_A']==180 and row['core_after_tax_multiple_M']==16)
        self.assertEqual(cell['required_core_after_tax_profit'], calc.D('24.396256563525'))
        self.assertEqual(self.out['scenarios'][1]['exit_PE'], calc.D(16))
        self.assertEqual(self.out['scenarios'][1]['annual_profit'], [calc.D(x) for x in ('10','13','16','18','20')])

    def test_no_ansi_or_trailing_space_in_generated_log(self):
        saved = calc.load('calculations.json')
        log = saved['financial_rigor']['log']
        self.assertNotIn('\x1b', log)
        self.assertTrue(all(line==line.rstrip() for line in log.splitlines()))

    def test_all_input_financial_values_are_strings(self):
        for rows in (self.data['financial'], self.data['balance']):
            self.assertTrue(all(isinstance(value, str) for row in rows.values() for value in row.values()))


if __name__ == '__main__':
    unittest.main()
