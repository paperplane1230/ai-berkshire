"""Portable offline calculations using financial_rigor.exact and Decimal.

Run normally to rebuild derived JSON. --refresh-manifest inventories existing
local sources only. No network, quote refresh or primary-input modification.
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
METRICS = ('revenue', 'profit', 'core', 'cfo')


def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'), parse_float=Decimal)


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


def pv(flows, rate):
    return sum((value / (1 + rate) ** year for year, value in enumerate(flows, 1)), D(0))


def irr(price, flows):
    if price <= 0 or any(value < 0 for value in flows) or not any(flows):
        raise ValueError('IRR requires positive initial price and nonnegative receipts')
    lo, hi = D('-.9999'), D('3')
    while pv(flows, hi) > price:
        hi = hi * 2 + 1
    for _ in range(180):
        mid = (lo + hi) / 2
        if pv(flows, mid) > price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def scenario(assumption, terms, shares, price):
    profits = [D(value) for value in assumption['annual_profit_CNY']]
    if len(profits) != terms['years'] or any(value < 0 for value in profits):
        raise ValueError('Scenario needs one nonnegative profit for each year')
    eps = [value / shares for value in profits]
    payouts = [D(terms['payout_first_year'])] + [D(terms['payout_later_years'])] * (len(profits)-1)
    dividends = [value * payout for value, payout in zip(eps, payouts)]
    terminal = eps[-1] * D(assumption['exit_pe'])
    flows = dividends[:-1] + [dividends[-1] + terminal]
    rate = irr(price, flows)
    return {'name': assumption['name'], 'annual_profit': [value/Y for value in profits],
            'annual_EPS_CNY': eps, 'payouts': payouts, 'exit_PE': D(assumption['exit_pe']),
            'annual_dividend_CNY': dividends, 'dividend_sum_CNY': sum(dividends),
            'terminal_price_CNY': terminal, 'cashflows_CNY': [-price] + flows,
            'IRR_pct': rate*100, 'PV10_CNY': pv(flows, D(terms['discount_rate'])),
            'NPV10_CNY': pv(flows, D(terms['discount_rate']))-price,
            'IRR_residual_CNY': pv(flows, rate)-price,
            'no_dividend_sensitivity_IRR_pct': irr(price, [D(0)]*(len(flows)-1)+[terminal])*100}


def calculate():
    data = load('inputs.json')
    fin = {period: {key: D(value) for key, value in row.items()} for period, row in data['financial'].items()}
    for year in ('2025', '2026'):
        ytd, h1 = fin[year+'YTD'], fin[year+'H1']
        fin[year+'Q3'] = {key: ytd[key]-h1[key] for key in sorted(ytd.keys() & h1.keys())}
    fin['2025Q4'] = {key: fin['2025'][key]-fin['2025YTD'][key] for key in sorted(fin['2025'].keys() & fin['2025YTD'].keys())}
    if '2026Q1' in data.get('primary_quarter_checks', {}):
        fin['2026Q1'] = {key: D(value) for key, value in data['primary_quarter_checks']['2026Q1'].items()}
        fin['2026Q2'] = {key: fin['2026H1'][key]-fin['2026Q1'][key] for key in sorted(fin['2026H1'].keys() & fin['2026Q1'].keys())}
    out = {'cutoff': data['cutoff'], 'units': 'Amounts CNY 100 million unless key says CNY, pct, days, shares or multiple. Pct is percent, not fraction.',
           'source_header': data['source_header'],
           'comparability': 'Issuer says no restatement required. 2025YTD core equals sum of 2025 annual quarterly table Q1+Q2+Q3.',
           'periods': {}, 'growth': {}}
    for period, row in fin.items():
        result = {key: value/Y for key, value in row.items()}
        result.update(parent_margin_pct=row['profit']/row['revenue']*100, core_margin_pct=row['core']/row['revenue']*100)
        if 'cfo' in row:
            result['cfo_parent_ratio_pct'] = row['cfo']/row['profit']*100 if row['profit']>0 else None
            if row['profit']<=0:
                result['cash_conversion_caveat'] = 'No cash-conversion percentage shown for a loss-making period; two negatives do not imply healthy cash conversion.'
        result['nonrecurring_profit'] = (row['profit']-row['core'])/Y
        if 'cost' in row:
            result['gross_margin_pct'] = (1-row['cost']/row['revenue'])*100
        for field in ('sales_expense', 'admin_expense', 'rd_expense', 'tax_surcharges', 'sale_cash'):
            if field in row:
                result[field+'_revenue_pct'] = row[field]/row['revenue']*100
        if 'capex' in row and 'cfo' in row:
            result['simple_fcf'] = (row['cfo']-row['capex'])/Y
        out['periods'][period] = result
    for suffix in ('H1', 'YTD', 'Q3'):
        now, old = fin['2026'+suffix], fin['2025'+suffix]
        out['growth'][suffix] = {key: {'absolute_change': (now[key]-old[key])/Y,
            'pct_vs_absolute_base': (now[key]-old[key])/abs(old[key])*100 if old[key] else None}
            for key in sorted(now.keys() & old.keys())}
        out['growth'][suffix]['note'] = 'Uses absolute denominator for negative prior profit/CFO. A negative change from loss means worsening, not positive growth.'
    ttm = {key: fin['2025'][key]+fin['2026YTD'][key]-fin['2025YTD'][key]
           for key in sorted(fin['2025'].keys() & fin['2026YTD'].keys() & fin['2025YTD'].keys())}
    shares, price = D(data['shares']), D(data['quote']['price'])
    cap = price*shares
    out['ttm'] = {key: value/Y for key, value in ttm.items()}
    out['ttm'].update(EPS_CNY=ttm['profit']/shares, core_EPS_CNY=ttm['core']/shares, simple_fcf=(ttm['cfo']-ttm['capex'])/Y)
    bal = {period: {key: D(value) for key, value in row.items()} for period, row in data['balance'].items()}
    now, old = bal['2026Q3'], bal['2025end']
    out['balance'] = {period: {key: value/Y for key, value in row.items()} for period, row in bal.items()}
    out['balance_changes'] = {period+'_to_2026Q3': {key: {'change': (now[key]-base[key])/Y,
        'pct': (now[key]/base[key]-1)*100 if base[key] else None} for key in sorted(now.keys() & base.keys())}
        for period, base in bal.items() if period != '2026Q3'}
    out['valuation'] = {'price_CNY': price, 'registered_shares': shares, 'market_cap': cap/Y,
        'TTM_PE': cap/ttm['profit'] if ttm['profit']>0 else None,
        'TTM_core_PE': cap/ttm['core'] if ttm['core']>0 else None,
        'PB': cap/now['parent_equity'], 'BVPS_CNY': now['parent_equity']/shares,
        'trailing_paid_dividend_CNY': D(data['notes']['dividend_paid_2026_per_share']),
        'trailing_paid_dividend_yield_pct': D(data['notes']['dividend_paid_2026_per_share'])/price*100,
        'TTM_100pct_payout_yield_pct': ttm['profit']/cap*100,
        'caveat': 'TTM earnings are near zero due partly to 2025Q4 losses; PE is arithmetic only. Trailing dividend yield is not a promised prospective yield. Negative FCF is not a positive cash earnings yield.'}
    debt = sum(now[key] for key in ('short_debt', 'long_debt', 'current_noncurrent_debt', 'lease_liability'))
    cash_net = now['cash_equivalents']-debt
    liquid_net = cash_net+now['trading_financial_assets']
    out['cash_and_quality'] = {
        'named_interest_and_lease_debt': debt/Y,
        'cash_equivalents_less_named_debt': cash_net/Y,
        'cash_plus_trading_assets_less_named_debt': liquid_net/Y,
        'excluded_noncurrent_financial_assets': now['noncurrent_financial_assets']/Y,
        'excluded_long_equity_investments': now['long_equity_investments']/Y,
        'cash_liquid_sensitivity_less_contract_liabilities': (liquid_net-now['contract_liabilities'])/Y,
        'cash_caveat': 'Cash-equivalent subtotal is not legal distributable parent cash. Trading assets involve redemption/valuation risk, not cash equivalents. Other noncurrent financial assets and long-term equity stakes excluded from liquid cash. Subtracting all contract liabilities is an illustrative conservative adjustment, not a liquidation valuation.',
        'receivables_notes_financing': (now['receivables']+now['notes_receivable']+now['bills_financing'])/Y,
        'DSO_receivables_only_273_days': (now['receivables']+old['receivables'])/2/fin['2026YTD']['revenue']*273,
        'DIO_273_days': (now['inventory']+old['inventory'])/2/fin['2026YTD']['cost']*273,
        'turnover_caveat': 'Average year-opening and current balance, 273 days. Long aging raw liquor is not dealer inventory. DIO is an accounting ratio, not a channel-clearance countdown.',
        'goodwill_intangibles_assets_pct': (now['goodwill']+now['intangibles'])/now['assets']*100,
        'asset_impairment_YTD': fin['2026YTD']['asset_impairment']/Y,
        'asset_impairment_note': 'Large percentage increase is from a tiny base; all YTD asset impairment is only CNY3.61 million and cannot explain the CNY771 million Q3 loss.',
        'investment_net_cash_outflow_YTD': (fin['2026YTD']['investment_paid']-fin['2026YTD']['investment_recovered'])/Y}
    notes = data['notes']
    out['contract_split'] = {}
    for period in ('2025end', '2026H1'):
        if 'prepayment_'+period in notes:
            advance, rebate = D(notes['prepayment_'+period]), D(notes['unsettled_rebates_'+period])
            out['contract_split'][period] = {'prepayments': advance/Y, 'unsettled_rebates': rebate/Y,
                'total': (advance+rebate)/Y, 'rebates_pct': rebate/(advance+rebate)*100}
    out['scenarios'] = [scenario(item, data['scenario_terms'], shares, price) for item in data['scenarios']]
    out['products_H1'] = {}
    for name, raw in data.get('products_h1', {}).items():
        row = {key:D(value) for key, value in raw.items()}
        result = {'revenue':row['revenue']/Y}
        if 'cost' in row:
            result.update(cost=row['cost']/Y, gross_margin_pct=(1-row['cost']/row['revenue'])*100)
        if 'prior_revenue' in row:
            result['revenue_yoy_pct'] = (row['revenue']/row['prior_revenue']-1)*100
        out['products_H1'][name] = result
    out['inventory_split_H1'] = {
        'finished_goods':D(notes['finished_goods_2026H1'])/Y,
        'semi_finished':D(notes['semi_finished_2026H1'])/Y,
        'finished_goods_change_pct':(D(notes['finished_goods_2026H1'])/D(notes['finished_goods_2025end'])-1)*100,
        'semi_finished_change_pct':(D(notes['semi_finished_2026H1'])/D(notes['semi_finished_2025end'])-1)*100,
        'semi_finished_inventory_pct':D(notes['semi_finished_2026H1'])/bal['2026H1']['inventory']*100}
    out['H1_prepayment_change_pct'] = (D(notes['prepayment_2026H1'])/D(notes['prepayment_2025end'])-1)*100
    out['scenario_terms'] = data['scenario_terms']
    asset_terms = data['asset_reverse_terms']
    out['asset_reverse_sensitivity'] = {
        'market_cap_CNY':cap, 'market_cap':cap/Y,
        'formula':'required sustainable core after-tax operating profit = (market cap - separable financial asset scenario value A) / multiple M',
        'note':asset_terms['note'],
        'precision':'Decimal, 40 significant digits. Each cell retains the exact numerator and denominator as well as the decimal quotient; no binary float arithmetic.',
        'rows':[]}
    for asset in asset_terms['separable_financial_asset_values_CNY']:
        for multiple in asset_terms['core_after_tax_profit_multiples']:
            a, m = D(asset), D(multiple)
            residual_equity = cap-a
            out['asset_reverse_sensitivity']['rows'].append({
                'separable_financial_asset_value_A':a/Y, 'core_after_tax_multiple_M':m,
                'exact_numerator_CNY':residual_equity, 'exact_denominator_multiple':m,
                'required_core_after_tax_profit_CNY':residual_equity/m,
                'required_core_after_tax_profit':residual_equity/m/Y})
    out['flat_profit_requirement'] = {}
    payouts = [D(data['scenario_terms']['payout_first_year'])]+[D(data['scenario_terms']['payout_later_years'])]*4
    for pe in ('12', '16', '20'):
        flows = payouts[:-1]+[payouts[-1]+D(pe)]
        required_eps = price/pv(flows, D('0.10'))
        out['flat_profit_requirement'][pe] = {'annual_profit_for_10pct_return': required_eps*shares/Y,
            'note': 'Same profit every model year, same payout/timing; not the actual recovery path.'}
    out['primary_quarter_reconciliation'] = [
        {'period': period, 'metric': key, 'calculated_CNY': fin[period][key], 'issuer_CNY': D(value),
         'passed': fin[period][key] == D(value)}
        for period, checks in data['primary_quarter_checks'].items() for key, value in checks.items() if period in fin]
    return data, out


def cross_source(data):
    vendor = load('vendor-snapshot.json')
    primary = {'2023':'S3 p8', '2024':'S3 p8', '2025':'S3 p8', '2025H1':'S2 comparative',
               '2026H1':'S2 current', '2025YTD':'S1 comparative; core S3 p9 sum Q1-Q3', '2026YTD':'S1 p2/p7-10'}
    checks = []
    for period, values in vendor['financial'].items():
        for metric in METRICS:
            a, b = D(data['financial'][period][metric]), D(values[metric])
            deviation = abs(a-b)/abs(a)*100 if a else (D(0) if b==0 else None)
            result = rigor.cross_validate(period+':'+metric, {'issuer_filing':a, 'Eastmoney':b}, unit='CNY yuan', tolerance_pct=1)
            checks.append({'label':period+':'+metric, 'period':period, 'metric':metric, 'primary':a, 'secondary':b,
                'primary_source':primary[period], 'secondary_source':'S5 vendor-snapshot.json',
                'deviation_pct_primary_denominator':deviation, 'tolerance_pct':1,
                'passed': deviation is not None and deviation<=1 and result['all_consistent']})
    return checks


def refresh_manifest():
    records = {}
    source_dir = ROOT/'local'/'洋河股份-20261106'/'yanghe'
    for meta in sorted(source_dir.glob('*.meta.json')):
        name = meta.name.removesuffix('.meta.json')
        record = json.loads(meta.read_text(encoding='utf-8'))
        record['response_sha256_as_recorded_at_capture'] = record.pop('sha256', None)
        record['cached_artifacts'] = []
        for extension in ('.pdf', '.html', '.txt', '.json'):
            path = source_dir/(name+extension)
            if path.exists():
                record['cached_artifacts'].append({'path':path.relative_to(ROOT).as_posix(),
                    'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes':path.stat().st_size})
        records[name] = record
    # Both full filings were independently read via Tavily before disk downloads.
    # Do not invent a download hash/timestamp when local bytes are not yet present.
    inputs = load('inputs.json')
    for name, source_id in (('q3-pdf', 'S1'), ('h1', 'S2')):
        if name not in records and not (name=='h1' and any(item in records for item in ('h1-pdf', 'h1-full'))):
            records[name] = {'url':inputs['sources'][source_id], 'retrieved_on':'2026-11-06',
                'retrieved_at':None, 'cached_artifacts':[],
                'capture_note':'Full filing read with Tavily extract in this research session; raw response bytes and exact extraction timestamp were not persisted. Refresh manifest after local download to replace this provenance record.'}
    save('source-manifest.json', {'cutoff':'2026-11-06',
        'source_header':inputs['source_header'],
        'source_id_map':{'S1':'q3-pdf', 'S2':[name for name in ('h1','h1-pdf','h1-full') if name in records], 'S3':'annual-pdf', 'S4':'eastmoney', 'S5':['plan-new-pdf','plan-old-pdf'], 'S6':['dividend','progress'], 'S7':['ir','ir-may'], 'S9':['related-investment'], 'S10':['qq','sina']},
        'visual_review':{'reviewed_on':'2026-11-06', 'q3_pdf_pages':[2,7,8,10], 'annual_pdf_pages':[9],
            'result':'Rendered primary data table, income statement, cash-flow statement and annual quarterly comparison; numeric columns, negative signs and CNY units visually agree with inputs.',
            'artifacts':[path.relative_to(ROOT).as_posix() for path in sorted(source_dir.glob('*-check.png'))]},
        'source_independence':'Issuer filings and Eastmoney are distinct publishing channels, not independent audits of accounts. Tencent/Sina separately publish quotes.',
        'hash_note':'Response-byte hashes are distinct from normalized/pretty-printed cached-artifact hashes.',
        'portable_scope':'Inputs and vendor snapshot support offline arithmetic and 28 checks without local caches.',
        'gaps':['Q3 unaudited and lacks full footnotes.', 'Q3 contract-liability split and current dealer inventories not disclosed in Q3 accounts.',
                'Future payout/valuation multiples are assumptions; no CNY7bn guaranteed annual dividend.', 'No exact free cash available for parent shareholder distribution established.'],
        'sources':records})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh-manifest', action='store_true')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    data, out = calculate()
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        market_ok = rigor.verify_market_cap(data['quote']['price'], data['shares'], data['quote']['reported_market_cap'], 'CNY')
        valuation = rigor.verify_valuation(data['quote']['price'], out['ttm']['EPS_CNY'], out['valuation']['BVPS_CNY'],
            fcf_per_share=out['ttm']['simple_fcf']*Y/D(data['shares']), dividend=data['notes']['dividend_paid_2026_per_share'])
        rows = cross_source(data)
    clean = re.sub(r'\x1b\[[0-9;]*m', '', log.getvalue())
    out['financial_rigor'] = {'market_cap_passed':market_ok, 'valuation_checks':valuation,
        'cross_source_count':len(rows), 'cross_source_all_passed':all(row['passed'] for row in rows),
        'log':'\n'.join(line.rstrip() for line in clean.splitlines())+'\n'}
    (HERE/'financial-rigor.txt').write_text(out['financial_rigor']['log'], encoding='utf-8')
    save('calculations.json', out)
    save('cross-source.json', rows)
    if args.refresh_manifest:
        refresh_manifest()
    print(json.dumps({'valuation':out['valuation'], 'ttm':out['ttm'], 'scenarios':out['scenarios'],
        'cross_source_count':len(rows), 'cross_source_all_passed':all(row['passed'] for row in rows)}, ensure_ascii=False, indent=2, default=str))
    if not market_ok or len(rows)!=28 or not all(row['passed'] for row in rows) or not all(row['passed'] for row in out['primary_quarter_reconciliation']):
        raise SystemExit('Verification failed')


if __name__ == '__main__':
    main()
