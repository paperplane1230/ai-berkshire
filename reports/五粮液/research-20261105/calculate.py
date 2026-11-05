"""Reproducible, offline Decimal calculations; all amounts start in CNY yuan.

Run normally to rebuild calculations/cross-source checks from portable inputs.
--refresh-manifest additionally records the already-downloaded local evidence.
No network, no quote refresh, no changes to primary input transcription.
"""
import argparse
import contextlib
import hashlib
import io
import json
import re
import sys
from decimal import Decimal, getcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import financial_rigor as rigor

getcontext().prec = 40
D = rigor.exact
Y = D('100000000')

def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'), parse_float=Decimal)

def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')

def pv(flows, rate):
    return sum(value / (1 + rate) ** t for t, value in enumerate(flows, 1))

def irr(price, flows):
    """Unique IRR for positive year-end cash flows and one initial outflow."""
    if price <= 0 or any(value < 0 for value in flows):
        raise ValueError('This solver requires positive initial price and nonnegative receipts')
    lo, hi = D('-.99'), D('3')
    while pv(flows, hi) > price:
        hi = hi * 2 + 1
    for _ in range(180):
        mid = (lo + hi) / 2
        if pv(flows, mid) > price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

def scenario(eps0, growth, exit_pe, price, first_dividend, payout, discount, years=5):
    earnings = [eps0 * (1 + growth) ** t for t in range(1, years + 1)]
    dividends = [first_dividend] + [e * payout for e in earnings[1:]]
    terminal = earnings[-1] * exit_pe
    flows = dividends[:-1] + [dividends[-1] + terminal]
    rate = irr(price, flows)
    sensitivity_dividends = [e * payout for e in earnings]
    sensitivity_flows = sensitivity_dividends[:-1] + [sensitivity_dividends[-1] + terminal]
    return {
        'eps0_CNY': eps0, 'growth': growth, 'exit_PE': exit_pe,
        'annual_EPS_CNY': earnings, 'year5_EPS_CNY': earnings[-1],
        'dividends_CNY': dividends, 'dividend_sum_CNY': sum(dividends),
        'terminal_price_CNY': terminal, 'cashflows_CNY': [-price] + flows,
        'IRR_pct': rate * 100, 'PV10_CNY': pv(flows, discount),
        'NPV10_at_current_price_CNY': pv(flows, discount) - price,
        'IRR_residual_CNY': pv(flows, rate) - price,
        'all_years_70pct_sensitivity': {
            'dividends_CNY': sensitivity_dividends,
            'dividend_sum_CNY': sum(sensitivity_dividends),
            'cashflows_CNY': [-price] + sensitivity_flows,
            'IRR_pct': irr(price, sensitivity_flows) * 100,
            'PV10_CNY': pv(sensitivity_flows, discount),
        },
    }

def required_growth(eps0, exit_pe, price, first_dividend, payout, discount):
    lo, hi = D('-.95'), D('1')
    for _ in range(180):
        growth = (lo + hi) / 2
        earnings = [eps0 * (1 + growth) ** t for t in range(1, 6)]
        receipts = [first_dividend] + [e * payout for e in earnings[1:]]
        receipts[-1] += earnings[-1] * exit_pe
        if pv(receipts, discount) < price:
            lo = growth
        else:
            hi = growth
    return (lo + hi) / 2

def calculate():
    data = load('inputs.json')
    fin = {period: {key: D(value) for key, value in row.items()} for period, row in data['financial'].items()}
    for year in ('2025', '2026'):
        ytd, h1 = fin[year + 'YTD'], fin[year + 'H1']
        fin[year + 'Q3'] = {key: ytd[key] - h1[key] for key in sorted(ytd.keys() & h1.keys())}
    fin['2025Q4'] = {key: fin['2025'][key] - fin['2025YTD'][key] for key in sorted(fin['2025'].keys() & fin['2025YTD'].keys())}
    out = {'cutoff': data['cutoff'], 'units': 'Amounts in CNY 100 million unless a key says CNY, pct, days, shares or multiple; percentages are percent, not fractions.',
           'comparability': '2025 H1 and YTD are corrected comparatives from 2026 filings, not originally published figures.',
           'periods': {}, 'growth': {}}
    for period, row in fin.items():
        result = {key: value / Y for key, value in row.items()}
        result['parent_margin_pct'] = row['profit'] / row['revenue'] * 100
        result['core_margin_pct'] = row['core'] / row['revenue'] * 100
        result['cfo_parent_ratio_pct'] = row['cfo'] / row['profit'] * 100
        result['nonrecurring_profit_pct'] = (row['profit'] - row['core']) / row['profit'] * 100
        if 'cost' in row:
            result['gross_margin_pct'] = (1 - row['cost'] / row['revenue']) * 100
        for field in ('sales_expense', 'admin_expense', 'rd_expense', 'tax_surcharges', 'operating_profit', 'net_profit', 'sale_cash'):
            if field in row:
                result[field + '_revenue_pct'] = row[field] / row['revenue'] * 100
        if 'net_profit' in row:
            result['cfo_total_profit_ratio_pct'] = row['cfo'] / row['net_profit'] * 100
        if 'capex' in row:
            result['simple_fcf'] = (row['cfo'] - row['capex']) / Y
        out['periods'][period] = result
    for period in ('H1', 'YTD', 'Q3'):
        now, prev = fin['2026' + period], fin['2025' + period]
        out['growth'][period] = {key: (now[key] / prev[key] - 1) * 100 for key in sorted(now.keys() & prev.keys()) if prev[key] != 0}
        out['growth'][period]['cfo_absolute_change'] = (now['cfo'] - prev['cfo']) / Y
        out['growth'][period]['cfo_growth_caveat'] = 'Signed-denominator growth is not economically meaningful if the prior CFO is negative; use absolute change.'
        for margin in ('gross_margin_pct', 'parent_margin_pct', 'sales_expense_revenue_pct', 'tax_surcharges_revenue_pct'):
            out['growth'][period][margin + '_change_pp'] = out['periods']['2026' + period][margin] - out['periods']['2025' + period][margin]
    ttm = {key: fin['2025'][key] + fin['2026YTD'][key] - fin['2025YTD'][key] for key in sorted(fin['2025'].keys() & fin['2026YTD'].keys() & fin['2025YTD'].keys())}
    shares, price = D(data['shares']), D(data['quote']['price'])
    eps, eps0 = ttm['profit'] / shares, ttm['core'] / shares
    out['ttm'] = {key: value / Y for key, value in ttm.items()}
    out['ttm'].update(EPS_CNY=eps, core_EPS_CNY=eps0, simple_fcf=(ttm['cfo'] - ttm['capex']) / Y, cfo_parent_ratio_pct=ttm['cfo']/ttm['profit']*100)
    bal = {period: {key: D(value) for key, value in row.items()} for period, row in data['balance'].items()}
    now, old = bal['2026Q3'], bal['2025end']
    cap = price * shares
    terms = data['scenario_terms']
    planned_dividend = D(terms['first_model_year_distribution_CNY'])
    first_dividend = planned_dividend / shares
    out['valuation'] = {
        'price_CNY': price, 'registered_shares': shares, 'market_cap': cap/Y,
        'TTM_PE': cap/ttm['profit'], 'TTM_core_PE': cap/ttm['core'],
        'PB': cap/now['parent_equity'], 'BVPS_CNY': now['parent_equity']/shares,
        'first_model_year_assumed_dividend_CNY': first_dividend,
        'first_model_year_assumed_dividend_yield_pct': first_dividend/price*100,
        'plan_20bn_to_TTM_parent_profit_pct': planned_dividend/ttm['profit']*100,
        'plan_20bn_to_TTM_core_profit_pct': planned_dividend/ttm['core']*100,
        'plan_20bn_to_2025_parent_profit_pct': planned_dividend/fin['2025']['profit']*100,
        'registered_share_basis_note': 'Treasury shares are not cancelled; do not subtract them from legal registered market-cap shares. Actual dividend entitlement excludes treasury stock and may change.',
        'dividend_note': terms['note'],
    }
    named_debt = now['current_noncurrent_debt'] + now['lease_liability']
    out['balance'] = {period: {key: value / Y for key, value in row.items()} for period, row in bal.items()}
    out['balance_changes'] = {}
    for base_period in ('2025end', '2026H1'):
        base = bal[base_period]
        out['balance_changes'][base_period + '_to_2026Q3'] = {
            key: {'change': (now[key]-base[key])/Y, 'pct': (now[key]/base[key]-1)*100 if base[key] else None}
            for key in sorted(now.keys() & base.keys())
        }
    out['cash_and_quality'] = {
        'disclosed_current_maturity_and_lease_debt': named_debt/Y,
        'cash_less_disclosed_maturity_lease_debt': (now['cash']-named_debt)/Y,
        'cash_equivalents_less_disclosed_maturity_lease_debt': (now['cash_equivalents']-named_debt)/Y,
        'cash_to_plan_20bn_multiple': now['cash']/planned_dividend,
        'cash_equivalents_to_plan_20bn_multiple': now['cash_equivalents']/planned_dividend,
        'YTD_CFO_to_plan_20bn_pct': fin['2026YTD']['cfo']/planned_dividend*100,
        'TTM_CFO_to_plan_20bn_pct': ttm['cfo']/planned_dividend*100,
        'TTM_simple_FCF_to_plan_20bn_pct': (ttm['cfo']-ttm['capex'])/planned_dividend*100,
        'cash_less_other_current_contract_dividend_liabilities_and_named_debt':
            (now['cash']-now['other_current_liabilities']-now['contract_liabilities']-now['dividend_payable']-named_debt)/Y,
        'cash_caveat': 'Cash is consolidated cash, not all freely distributable parent cash. The adjusted cash subtotal is an illustrative non-GAAP subtraction, not legal distributable reserves. No cash value is added to PE scenarios.',
        'receivables_plus_bills': (now['receivables']+now['bills_financing'])/Y,
        'receivables_plus_bills_change': (now['receivables']+now['bills_financing']-old['receivables']-old['bills_financing'])/Y,
        'DSO_receivables_only_273_days': (now['receivables']+old['receivables'])/2/fin['2026YTD']['revenue']*273,
        'DIO_273_days': (now['inventory']+old['inventory'])/2/fin['2026YTD']['cost']*273,
        'turnover_caveat': 'Average opening/closing balances and 273 calendar days; liquor aging inventory is not equivalent to channel stock. Vendor day conventions can differ.',
        'goodwill_intangibles_assets_pct': (now['goodwill']+now['intangibles'])/now['assets']*100,
        'finance_company_deposit_H1_cash_pct': D(data['notes']['finance_company_deposit_2026H1'])/bal['2026H1']['cash']*100,
        'H1_restricted_cash': D(data['notes']['restricted_cash_2026H1'])/Y,
    }
    out['products_H1'] = {}
    for product, values in data['products_h1'].items():
        row = {key: D(value) for key, value in values.items()}
        result = {'revenue': row['revenue']/Y, 'cost': row['cost']/Y, 'gross_margin_pct': (1-row['cost']/row['revenue'])*100}
        if 'volume_tonnes' in row:
            result['revenue_per_tonne_CNY'] = row['revenue']/row['volume_tonnes']
            result['implied_revenue_per_tonne_yoy_pct'] = ((1+row['yoy_revenue_pct']/100)/(1+row['volume_yoy_pct']/100)-1)*100
            result['price_caveat'] = 'Mix-adjusted only by total tonnes, not a quoted retail/wholesale bottle price; source growth rates are rounded.'
        out['products_H1'][product] = result
    out['scenarios'] = []
    for assumption in data['scenarios']:
        result = scenario(eps0, D(assumption['growth']), D(assumption['exit_pe']), price, first_dividend, D(terms['payout_years_2_to_5']), D(terms['discount_rate']), terms['years'])
        result['name'] = assumption['name']
        out['scenarios'].append(result)
    growth = required_growth(eps0, D('20'), price, first_dividend, D('0.70'), D('0.10'))
    out['required_growth_for_10pct_IRR_at_20PE'] = {
        'growth_pct': growth*100,
        'verification': scenario(eps0, growth, D('20'), price, first_dividend, D('0.70'), D('0.10')),
        'assumptions': 'Same five year-end timing and first-year transition distribution as the main scenarios; not a forecast.',
    }
    return data, out

def cross_source(data):
    vendor = load('vendor-snapshot.json')
    rows = []
    primary = {'2023': 'S3 annual 2025 comparative history', '2024': 'S3 annual 2025 comparative history',
               '2025': 'S3 annual 2025', '2025H1': 'S2 H1 2026 corrected comparative',
               '2026H1': 'S2 H1 2026', '2025YTD': 'S1 Q3 2026 corrected comparative', '2026YTD': 'S1 Q3 2026'}
    for period, values in vendor['financial'].items():
        for metric in ('revenue', 'profit', 'core', 'cfo'):
            a, b = D(data['financial'][period][metric]), D(values[metric])
            deviation = abs(a-b)/abs(a)*100 if a else (D(0) if not b else None)
            check = rigor.cross_validate(period + ':' + metric, {'issuer_filing': a, 'Eastmoney': b}, unit='CNY yuan', tolerance_pct=1)
            passed = deviation is not None and deviation <= 1 and check['all_consistent']
            rows.append({'label': period + ':' + metric, 'period': period, 'metric': metric,
                         'primary': str(a), 'secondary': str(b), 'primary_source': primary[period],
                         'secondary_source': 'S5 Eastmoney snapshot, see vendor-snapshot.json field mapping',
                         'deviation_pct_primary_denominator': deviation, 'tolerance_pct': 1, 'passed': passed})
    return rows

def refresh_manifest():
    source_dir = ROOT/'local'/'五粮液-20261105'/'wuliangye'
    records = {}
    for meta in sorted(source_dir.glob('*.meta.json')):
        name = meta.name.removesuffix('.meta.json')
        record = json.loads(meta.read_text(encoding='utf-8'))
        record['response_sha256_as_recorded_at_capture'] = record.pop('sha256', None)
        record['cached_artifacts'] = []
        for extension in ('.pdf', '.html', '.txt', '.json'):
            artifact = source_dir/(name+extension)
            if artifact.exists():
                record['cached_artifacts'].append({'path': artifact.relative_to(ROOT).as_posix(),
                    'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(), 'bytes': artifact.stat().st_size})
        records[name] = record
    # These full PDF text extractions were separately retained by the IR review.
    # Their exact capture timestamps/raw PDF bytes were not persisted.
    for name, pages in (('ir-april', 18), ('ir-june', 5)):
        artifact = source_dir.parent/(name+'.txt')
        if artifact.exists():
            header = artifact.read_text(encoding='utf-8').splitlines()[0]
            if not header.startswith('URL: '):
                raise ValueError('Missing source URL in ' + str(artifact))
            records[name] = {
                'url': header.removeprefix('URL: ').strip(), 'retrieved_on': '2026-11-05',
                'retrieved_at': None, 'pages': pages,
                'capture_note': 'Full PDF text extracted through Tavily; raw PDF bytes and exact retrieval timestamp were not retained. Date is documented in ir-governance-notes.md.',
                'cached_artifacts': [{'path': artifact.relative_to(ROOT).as_posix(),
                    'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(), 'bytes': artifact.stat().st_size}],
            }
    manifest = {
        'cutoff': '2026-11-05',
        'source_id_map': {'S1': 'q3-pdf', 'S2': 'h1-pdf', 'S3': 'annual-pdf', 'S4': 'correction-pdf', 'S5': 'eastmoney', 'S6': ['qq', 'sina'],
                          'S7': ['ir-april', 'ir-june'], 'S8': 'dividend', 'S9': 'buyback', 'S10': 'chair'},
        'source_independence': 'Issuer filings and Eastmoney are separate publishing channels; Eastmoney ultimately transcribes issuer disclosures, so matching figures do not constitute an independent audit of the underlying accounts. Tencent and Sina independently publish the quote.',
        'hash_note': 'Capture response hashes describe downloaded bytes; cached JSON may be pretty-printed and has its own separately calculated artifact hash.',
        'scope_note': 'Primary PDFs/text are local cache artifacts and may be git-ignored; portable inputs and vendor snapshot suffice for offline arithmetic and 28 comparisons.',
        'gaps': ['No uniformly verified current wholesale bottle price; do not reuse old 745 CNY quote.', 'Q3 report is unaudited; no new quarterly full footnote audit.', 'The 20bn first-model-year payout is a plan-based scenario assumption, not a newly declared payment.'],
        'sources': records,
    }
    save('source-manifest.json', manifest)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh-manifest', action='store_true')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    data, out = calculate()
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        market_cap_passed = rigor.verify_market_cap(data['quote']['price'], data['shares'], data['quote']['reported_market_cap'], 'CNY')
        valuation_checks = rigor.verify_valuation(data['quote']['price'], out['ttm']['EPS_CNY'], out['valuation']['BVPS_CNY'],
            fcf_per_share=out['ttm']['simple_fcf']*Y/D(data['shares']), revenue_per_share=out['ttm']['revenue']*Y/D(data['shares']))
        rows = cross_source(data)
    clean = re.sub(r'\x1b\[[0-9;]*m', '', log.getvalue())
    out['financial_rigor'] = {'market_cap_passed': market_cap_passed, 'valuation_checks': valuation_checks,
                              'cross_source_count': len(rows), 'cross_source_all_passed': all(row['passed'] for row in rows),
                              'log': '\n'.join(line.rstrip() for line in clean.splitlines()) + '\n'}
    save('cross-source.json', rows)
    save('calculations.json', out)
    if args.refresh_manifest:
        refresh_manifest()
    print(json.dumps({'valuation': out['valuation'], 'ttm': out['ttm'], 'scenarios': out['scenarios'],
        'required_growth_pct': out['required_growth_for_10pct_IRR_at_20PE']['growth_pct'],
        'cross_source_count': len(rows), 'cross_source_all_passed': all(row['passed'] for row in rows)}, ensure_ascii=False, indent=2, default=str))
    if not market_cap_passed or len(rows) != 28 or not all(row['passed'] for row in rows):
        raise SystemExit('Verification failed')

if __name__ == '__main__':
    main()
