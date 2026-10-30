"""Offline Decimal arithmetic for the 2026Q3 research report.

Financial inputs are primary-filing transcriptions. Scenario inputs are
explicit assumptions, not facts. No network access or hidden data dependency.
"""
import contextlib
import io
import json
import re
import sys
from decimal import Decimal as D
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import financial_rigor as rigor
Y = D('100000000')

def irr(price, flows):
    lo, hi = D('-.99'), D('3')
    for _ in range(180):
        mid = (lo + hi) / 2
        pv = sum(x / (1 + mid) ** t for t, x in enumerate(flows, 1))
        if pv > price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

def calculate():
    data = json.loads((HERE / 'inputs.json').read_text(encoding='utf-8'))
    fin = {p: {k: D(v) for k, v in row.items()} for p, row in data['financial'].items()}
    for year in ('2025', '2026'):
        ytd, h1 = fin[year+'YTD'], fin[year+'H1']
        fin[year+'Q3'] = {k: ytd[k]-h1[k] for k in sorted(ytd.keys() & h1.keys())}
    out = {'periods': {}, 'growth': {}}
    for period, row in fin.items():
        result = {k: v / Y for k, v in row.items()}
        result['parent_margin_pct'] = row['profit'] / row['revenue'] * 100
        result['cfo_parent_ratio_pct'] = row['cfo'] / row['profit'] * 100
        if 'cost' in row:
            result['gross_margin_pct'] = (1 - row['cost'] / row['revenue']) * 100
        if 'operating_profit' in row:
            result['operating_margin_pct'] = row['operating_profit'] / row['revenue'] * 100
        if 'net_profit' in row:
            result['minority_share_pct'] = (1 - row['profit'] / row['net_profit']) * 100
            result['cfo_total_profit_ratio_pct'] = row['cfo'] / row['net_profit'] * 100
        if 'capex' in row:
            result['simple_fcf'] = (row['cfo'] - row['capex']) / Y
        if 'lease_cash' in row and 'capex' in row:
            result['fcf_after_lease_cash'] = (row['cfo']-row['capex']-row['lease_cash'])/Y
        out['periods'][period] = result
    for period in ('YTD', 'Q3'):
        now, prev = fin['2026'+period], fin['2025'+period]
        out['growth'][period] = {k: (now[k] / prev[k]-1) * 100 for k in ('revenue', 'profit', 'adjusted', 'cfo') if prev[k]}
        out['growth'][period]['net_profit'] = (now['net_profit']/prev['net_profit']-1)*100
        out['growth'][period]['operating_profit'] = (now['operating_profit']/prev['operating_profit']-1)*100
        out['growth'][period]['minority_bridge_yi'] = ((prev['net_profit']-prev['profit'])-(now['net_profit']-now['profit']))/Y
        out['growth'][period]['minority_bridge_share_pct'] = ((prev['net_profit']-prev['profit'])-(now['net_profit']-now['profit']))/(now['profit']-prev['profit'])*100
    ttm = {k: fin['2025'][k]+fin['2026YTD'][k]-fin['2025YTD'][k]
           for k in sorted(fin['2025'].keys() & fin['2026YTD'].keys() & fin['2025YTD'].keys())}
    q, shares = data['quote'], {k: D(v) for k, v in data['shares'].items()}
    a, h, fx = D(q['A_CNY']), D(q['H_HKD']), D(q['HKDCNY'])
    hc, n = h*fx, shares['total']
    eps, core = ttm['profit']/n, ttm['adjusted']/n
    out['ttm'] = {k: v/Y for k, v in ttm.items()}
    out['ttm'].update(eps=eps, adjusted_eps=core, simple_fcf=(ttm['cfo']-ttm['capex'])/Y)
    bal = {k: D(v) for k, v in data['balance'].items()}
    cap_a, cap_h_hkd = a*shares['A'], h*shares['H']
    out['valuation'] = {
        'A_PE': a/eps, 'H_PE': hc/eps, 'A_adjusted_PE': a/core, 'H_adjusted_PE': hc/core,
        'A_PB': a*n/bal['parent_equity'], 'H_PB': hc*n/bal['parent_equity'],
        'A_cap_yi': cap_a/Y, 'H_cap_HKD_yi': cap_h_hkd/Y,
        'combined_cap_CNY_yi': (cap_a+cap_h_hkd*fx)/Y,
        'A_equivalent_cap_yi': a*n/Y, 'H_price_CNY': hc,
        'H_discount_pct': (1-hc/a)*100,
        'A_historical_dividend_yield_pct': D(data['dividend'])/a*100,
        'H_historical_dividend_yield_pct': D(data['dividend'])/hc*100,
    }
    out['balance'] = {
        'named_debt_yi': sum(bal[k] for k in ('short_loans', 'long_loans', 'current_noncurrent_debt', 'lease_liability'))/Y,
        'cash_minus_named_debt_yi': (bal['cash']-sum(bal[k] for k in ('short_loans', 'long_loans', 'current_noncurrent_debt', 'lease_liability')))/Y,
        'receivables_change_pct': (bal['receivables']/bal['receivables_yearend']-1)*100,
        'inventory_change_pct': (bal['inventory']/bal['inventory_yearend']-1)*100,
        'DSO_273': (bal['receivables']+bal['receivables_yearend'])/2/fin['2026YTD']['revenue']*273,
        'DIO_273': (bal['inventory']+bal['inventory_yearend'])/2/fin['2026YTD']['cost']*273,
        'intangibles_goodwill_assets_pct': (bal['goodwill']+bal['intangibles'])/bal['assets']*100,
    }
    out['scenarios'] = []
    out['products']={}
    for product,values in data['products'].items():
        r={k:D(v) for k,v in values.items()}
        out['products'][product]={'annual_revenue_yi':r['2025_revenue']/Y,'annual_margin_pct':(1-r['2025_cost']/r['2025_revenue'])*100,'h1_revenue_yi':r['H1_revenue']/Y,'h1_margin_pct':(1-r['H1_cost']/r['H1_revenue'])*100}
    out['operating_assets']={name:{**{k:D(v)/Y for k,v in row.items()},'net_margin_pct':D(row['profit'])/D(row['revenue'])*100} for name,row in data['assets_operating'].items()}
    for s in data['scenarios']:
        g, payout = D(s['growth']), D(s['payout'])
        start = D(s.get('eps0', str(core)))
        profits = [start*(1+g)**t for t in range(1, 6)]
        dividends = [p*payout for p in profits]
        result = {'name': s['name'], 'eps0': start, 'year5_eps': profits[-1], 'dividends': dividends, 'dividend_sum_CNY': sum(dividends)}
        for market, price in (('A', a), ('H', hc)):
            terminal = profits[-1]*D(s[market+'_exit_PE'])
            flows = dividends[:-1]+[dividends[-1]+terminal]
            result[market+'_exit_CNY'] = terminal
            result[market+'_exit_HKD'] = terminal/fx
            result[market+'_IRR_pct'] = irr(price, flows)*100
            result[market+'_PV10_CNY'] = sum(x/D('1.1')**t for t, x in enumerate(flows, 1))
        out['scenarios'].append(result)
    return data, out

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    data, out = calculate()
    (HERE/'calculations.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        rigor.verify_market_cap(data['quote']['A_CNY'], data['shares']['total'], data['quote']['A_equivalent_reported_cap'], 'CNY-equivalent, not A/H combined')
        rigor.verify_valuation(data['quote']['A_CNY'], out['ttm']['eps'], D(data['balance']['parent_equity'])/D(data['shares']['total']), dividend=data['dividend'])
        snapshot=json.loads((HERE/'cross-source.json').read_text(encoding='utf-8'))
        for row in snapshot:
            rigor.cross_validate(row['label'], {'issuer':row['primary'], 'Eastmoney':row['secondary']}, tolerance_pct=1)
    clean=re.sub(r'\x1b\[[0-9;]*m', '', log.getvalue())
    (HERE/'financial-rigor.txt').write_text('\n'.join(x.rstrip() for x in clean.splitlines())+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
