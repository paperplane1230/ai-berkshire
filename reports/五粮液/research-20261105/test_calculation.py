"""Independent residual, unit, source and accounting-bridge regression checks."""
import hashlib
import json
import unittest
from decimal import Decimal as D
from pathlib import Path
from calculate import calculate, irr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i, cls.o = calculate()

    def test_registered_shares_not_treasury_adjusted(self):
        self.assertEqual(D(self.i['shares']), D('3881608005'))
        self.assertEqual(self.o['valuation']['registered_shares'], D('3881608005'))
        self.assertNotEqual(self.o['valuation']['registered_shares'], D('3881608005')-D('16127753'))

    def test_quote_two_sources_and_timestamp(self):
        vendor = json.loads((HERE/'vendor-snapshot.json').read_text(encoding='utf-8'))
        self.assertEqual(D(vendor['quotes']['Tencent']['price']), D('75.82'))
        self.assertEqual(D(vendor['quotes']['Sina']['price']), D('75.82'))
        self.assertEqual(vendor['quotes']['Tencent']['time'], '20261105161454')
        self.assertTrue(vendor['quotes']['Sina']['time'].startswith('2026-11-05'))

    def test_market_cap_independent_integer_cents(self):
        expected_cents = 7582 * 3881608005
        self.assertEqual(self.o['valuation']['market_cap']*D('1e10'), D(expected_cents))

    def test_direct_primary_q3_revenue(self):
        self.assertEqual(self.o['periods']['2026Q3']['revenue']*D('1e8'), D('4441799422.57'))

    def test_direct_primary_q3_profit(self):
        self.assertEqual(self.o['periods']['2026Q3']['profit']*D('1e8'), D('957704479.72'))

    def test_direct_primary_q3_core(self):
        self.assertEqual(self.o['periods']['2026Q3']['core']*D('1e8'), D('957398695.72'))

    def test_cfo_unit_guard_ytd_is_less_than_one_yi(self):
        self.assertEqual(self.o['periods']['2026YTD']['cfo'], D('0.4668411579'))
        self.assertLess(self.o['periods']['2026YTD']['cfo'], D('1'))

    def test_q3_cfo_difference_from_negative_h1(self):
        self.assertEqual(self.o['periods']['2026H1']['cfo'], D('-21.5356879232'))
        self.assertEqual(self.o['periods']['2026Q3']['cfo'], D('22.0025290811'))

    def test_restatement_comparative_not_original_revenue(self):
        self.assertEqual(D(self.i['financial']['2025YTD']['revenue']), D('30637727654.97'))
        self.assertEqual(D(self.i['financial']['2025H1']['revenue']), D('23509972048.65'))
        self.assertLess(abs(self.o['growth']['Q3']['revenue']-D('-37.683056660479')), D('1e-10'))

    def test_all_quarter_differences_recombine(self):
        for year in ('2025', '2026'):
            for key in ('revenue', 'profit', 'core', 'cfo', 'capex', 'sales_expense', 'cost'):
                self.assertEqual(self.o['periods'][year+'H1'][key]+self.o['periods'][year+'Q3'][key], self.o['periods'][year+'YTD'][key])

    def test_ttm_direct_and_not_ytd_annualisation(self):
        self.assertEqual(self.o['ttm']['profit'], D('121.9035288136'))
        self.assertEqual(self.o['ttm']['core'], D('117.9808621753'))
        self.assertEqual(self.o['ttm']['revenue'], D('427.4925607960'))
        self.assertNotEqual(self.o['ttm']['profit'], self.o['periods']['2026YTD']['profit']*4/3)

    def test_ttm_equals_four_quarters_via_h1(self):
        for key in ('revenue', 'profit', 'core', 'cfo', 'capex'):
            rebuilt = self.o['periods']['2025Q4'][key] + self.o['periods']['2026H1'][key] + self.o['periods']['2026Q3'][key]
            self.assertEqual(rebuilt, self.o['ttm'][key])

    def test_simple_fcf_is_cash_less_capex(self):
        self.assertEqual(self.o['ttm']['simple_fcf'], D('3.6833058555'))
        self.assertEqual(self.o['periods']['2026Q3']['simple_fcf'], D('19.7298295609'))
        self.assertEqual(self.o['periods']['2026YTD']['simple_fcf'], D('-6.1156242130'))

    def test_q3_margin_independent_float(self):
        q = self.o['periods']['2026Q3']
        self.assertAlmostEqual(float(q['gross_margin_pct']), (1-1007338398.19/4441799422.57)*100, places=10)
        self.assertAlmostEqual(float(q['parent_margin_pct']), 957704479.72/4441799422.57*100, places=10)
        self.assertAlmostEqual(float(q['sales_expense_revenue_pct']), 1475844212.38/4441799422.57*100, places=10)

    def test_cash_balance_bridge(self):
        change = self.o['balance_changes']['2025end_to_2026Q3']['cash']['change']
        self.assertEqual(change, D('-152.8463305730'))
        self.assertEqual(self.o['balance']['2025end']['cash']+change, self.o['balance']['2026Q3']['cash'])

    def test_bills_and_inventory_changes(self):
        change = self.o['balance_changes']
        self.assertEqual(change['2026H1_to_2026Q3']['bills_financing']['change'], D('-65.2211786077'))
        self.assertEqual(change['2025end_to_2026Q3']['inventory']['change'], D('41.3211656269'))
        self.assertEqual(change['2025end_to_2026Q3']['contract_liabilities']['change'], D('-45.3261725753'))

    def test_cash_cover_not_profit_cover(self):
        c = self.o['cash_and_quality']
        self.assertEqual(c['YTD_CFO_to_plan_20bn_pct'], D('0.2334205789500'))
        self.assertEqual(c['TTM_CFO_to_plan_20bn_pct'], D('7.5272780899'))
        self.assertGreater(self.o['valuation']['plan_20bn_to_TTM_parent_profit_pct'], D(100))

    def test_irr_known_coupon_independent_anchor(self):
        self.assertLess(abs(irr(D(100), [D(5), D(5), D(105)])-D('.05')), D('1e-30'))

    def test_scenario_economic_formulas_independent_float(self):
        eps0 = 11798086217.53 / 3881608005
        first = 20000000000 / 3881608005
        for s in self.o['scenarios']:
            g, pe = float(s['growth']), float(s['exit_PE'])
            expected_eps5 = eps0*(1+g)**5
            expected_dividends = [first] + [eps0*(1+g)**t*.7 for t in range(2, 6)]
            self.assertAlmostEqual(float(s['year5_EPS_CNY']), expected_eps5, places=12)
            self.assertAlmostEqual(float(s['terminal_price_CNY']), expected_eps5*pe, places=10)
            self.assertAlmostEqual(float(s['dividend_sum_CNY']), sum(expected_dividends), places=11)
            self.assertEqual(len(s['cashflows_CNY']), 6)
            self.assertEqual(s['cashflows_CNY'][0], D('-75.82'))
            self.assertEqual(s['cashflows_CNY'][-1], s['dividends_CNY'][-1]+s['terminal_price_CNY'])

    def test_scenario_independent_float_irr_residual(self):
        for s in self.o['scenarios']:
            for result in (s, s['all_years_70pct_sensitivity']):
                rate = float(result['IRR_pct'])/100
                net_pv = sum(float(value)/(1+rate)**t for t, value in enumerate(result['cashflows_CNY']))
                self.assertAlmostEqual(net_pv, 0, places=10)
                value10 = sum(float(value)/(1.1)**t for t, value in enumerate(result['cashflows_CNY']) if t)
                self.assertAlmostEqual(value10, float(result['PV10_CNY']), places=10)

    def test_sensitivity_only_changes_first_dividend(self):
        for s in self.o['scenarios']:
            sensitivity = s['all_years_70pct_sensitivity']
            self.assertEqual(s['cashflows_CNY'][2:], sensitivity['cashflows_CNY'][2:])
            self.assertEqual(sensitivity['dividends_CNY'][0], s['annual_EPS_CNY'][0]*D('.7'))
            self.assertGreater(s['IRR_pct'], sensitivity['IRR_pct'])

    def test_required_growth_independent_residual(self):
        g = float(self.o['required_growth_for_10pct_IRR_at_20PE']['growth_pct'])/100
        eps0 = 11798086217.53/3881608005
        receipts = [20000000000/3881608005]+[eps0*(1+g)**t*.7 for t in range(2, 6)]
        receipts[-1] += eps0*(1+g)**5*20
        value = sum(cash/1.1**t for t, cash in enumerate(receipts, 1))
        self.assertAlmostEqual(value, 75.82, places=10)
        self.assertLess(abs(self.o['required_growth_for_10pct_IRR_at_20PE']['verification']['IRR_pct']-10), D('1e-30'))

    def test_cross_source_28_independent_primary_denominators(self):
        rows = json.loads((HERE/'cross-source.json').read_text(encoding='utf-8'))
        self.assertEqual(len(rows), 28)
        self.assertEqual(len({(r['period'], r['metric']) for r in rows}), 28)
        for row in rows:
            a, b = D(row['primary']), D(row['secondary'])
            self.assertEqual(a, b)
            self.assertLessEqual(abs(a-b)/abs(a)*100, D(1))
            self.assertTrue(row['passed'])
            self.assertEqual(row['tolerance_pct'], 1)

    def test_generated_rigor_pass_and_clean_log(self):
        result = json.loads((HERE/'calculations.json').read_text(encoding='utf-8'))['financial_rigor']
        self.assertTrue(result['market_cap_passed'])
        self.assertTrue(result['cross_source_all_passed'])
        self.assertEqual(result['cross_source_count'], 28)
        self.assertNotIn('\x1b', result['log'])
        self.assertTrue(all(line == line.rstrip() for line in result['log'].splitlines()))

    def test_vendor_snapshot_matches_raw_cache_when_available(self):
        path = ROOT/'local/五粮液-20261105/wuliangye/eastmoney.json'
        if not path.exists():
            self.skipTest('Optional raw evidence cache not present; portable snapshot checks remain active')
        raw = json.loads(path.read_text(encoding='utf-8'), parse_float=D)
        rows = {r['REPORT_DATE'][:10]: r for r in raw['result']['data']}
        snapshot = json.loads((HERE/'vendor-snapshot.json').read_text(encoding='utf-8'))
        for period, values in snapshot['financial'].items():
            source = rows[snapshot['report_dates'][period]]
            for key, value in values.items():
                self.assertEqual(D(str(source[snapshot['field_mapping'][key]])), D(value))

    def test_available_source_artifact_hashes(self):
        manifest = json.loads((HERE/'source-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['cutoff'], '2026-11-05')
        checked = 0
        for record in manifest['sources'].values():
            for artifact in record['cached_artifacts']:
                path = ROOT/artifact['path']
                if path.exists():
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact['sha256'])
                    checked += 1
        if not checked:
            self.skipTest('Optional source cache absent')

if __name__ == '__main__':
    unittest.main()
