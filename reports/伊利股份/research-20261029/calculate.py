"""Reproducible Decimal calculations; no network, no financial data invented."""
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from decimal import Decimal as D

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from financial_rigor import exact, verify_market_cap, verify_valuation, cross_validate
sys.stdout.reconfigure(encoding='utf-8')
I = json.loads((HERE / 'inputs.json').read_text(encoding='utf-8'))
Y = D('100000000')
P = exact(I['price'])
N = exact(I['shares'])
rows = {k:{m:exact(v) for m,v in r.items()} for k,r in I['periods'].items()}
for year in ('2025','2026'):
    rows[year+'q3'] = {m: rows[year+'ytd'][m]-rows[year+'h1'][m] for m in rows[year+'ytd']}

def metrics(r):
    result = {k:v/Y for k,v in r.items()}
    result.update(fcf=(r['ocf']-r['capex'])/Y,
                  gross_margin=(1-r['cost']/r['revenue'])*100,
                  operating_margin=r['operating']/r['revenue']*100,
                  net_margin=r['profit']/r['revenue']*100,
                  cash_conversion=r['ocf']/r['profit']*100,
                  tax_rate=r['tax']/r['pbt']*100,
                  sales_ratio=r['sales']/r['revenue']*100)
    return result

R = {'periods':{k:metrics(r) for k,r in rows.items()}}
R['growth']={period:{m:(rows['2026'+period][m]/rows['2025'+period][m]-1)*100 for m in rows['2026'+period]} for period in ('ytd','q3')}
A={m:exact(v) for m,v in I['annual']['2025'].items()}
T={m:A[m]+rows['2026ytd'][m]-rows['2025ytd'][m] for m in A}
R['ttm']={m:v/Y for m,v in T.items()}
R['valuation']={'market_cap_yi':P*N/Y,'eps_ttm':T['profit']/N,'pe_ttm':P*N/T['profit'],
                'pe_deduct_ttm':P*N/T['deduct'],'pe_2025':P*N/A['profit'],
                'pb':P*N/exact(I['balance']['2026q3']['equity']),
                'historical_dividend_yield':exact(I['dividend_2025'])/P*100,
                'fcf_ttm':(T['ocf']-T['capex'])/Y,
                'fcf_ttm_yield':(T['ocf']-T['capex'])/(P*N)*100}
B={k:{m:exact(v) for m,v in r.items()} for k,r in I['balance'].items()}
R['working_capital']={}
for year,start,end in [('2026','2025end','2026q3'),('2025','2024end','2025q3')]:
    R['working_capital'][year]={'dso':(B[start]['ar']+B[end]['ar'])/2/rows[year+'ytd']['revenue']*273,
        'dio':(B[start]['inventory']+B[end]['inventory'])/2/rows[year+'ytd']['cost']*273}
R['balance_changes']={m:(B['2026q3'][m]/B['2025end'][m]-1)*100 for m in B['2025end']}
R['supplier_funding_increase']=(B['2026q3']['payables']+B['2026q3']['payable_notes']-B['2025end']['payables']-B['2025end']['payable_notes'])/Y
R['identified_interest_debt']=(B['2026q3']['short_debt']+B['2026q3']['long_debt']+B['2026q3']['current_long_debt']+B['2026q3']['lease'])/Y
R['goodwill_intangible_ratio']=(B['2026q3']['goodwill']+B['2026q3']['intangibles'])/B['2026q3']['assets']*100
R['segment_weights']={k:exact(v)/exact(I['segments_ytd']['total'])*100 for k,v in I['segments_ytd'].items() if k!='total'}

def irr(price, dividends, terminal):
    low, high = D('-0.9'), D('2')
    for _ in range(180):
        r = (low+high)/2
        pv=sum(d/(1+r)**t for t,d in enumerate(dividends,1))+terminal/(1+r)**5
        if pv > price: low=r
        else: high=r
    return (low+high)/2

def scenario(eps,g,pe,payout):
    future=[eps*(1+g)**t for t in range(1,6)]
    div=[x*payout for x in future]
    terminal=future[-1]*pe
    return {'eps5':future[-1], 'terminal_price':terminal, 'dividends':div,
            'dividend_sum':sum(div), 'irr_pct':irr(P,div,terminal)*100,
            'pv_at_10pct':sum(d/D('1.1')**t for t,d in enumerate(div,1))+terminal/D('1.1')**5}

R['scenarios']={s['name']:scenario(*[exact(s[k]) for k in ('eps0','growth','terminal_pe','payout')]) for s in I['scenarios']}
R['growth_for_return']={}
for hurdle in (D('.08'),D('.10')):
    lo,hi=D('-.1'),D('.3')
    for _ in range(180):
        g=(lo+hi)/2
        ss=scenario(D('1.75'),g,D('16'),D('.75'))
        pv=sum(d/(1+hurdle)**t for t,d in enumerate(ss['dividends'],1))+ss['terminal_price']/(1+hurdle)**5
        if pv<P: lo=g
        else: hi=g
    R['growth_for_return'][str(hurdle)]=(lo+hi)/2*100

log=io.StringIO()
with redirect_stdout(log):
    verify_market_cap(P,N,exact(I['reported_cap']),'CNY')
    verify_valuation(P,eps=T['profit']/N,bvps=B['2026q3']['equity']/N,dividend=exact(I['dividend_2025']))
    if (HERE/'cross_checks.json').exists():
        for check in json.loads((HERE/'cross_checks.json').read_text(encoding='utf-8')):
            cross_validate(check['field'],{'原始公告':check['primary'],'东方财富':check['secondary']},'元',tolerance_pct=1)
(HERE/'financial-rigor.txt').write_text(log.getvalue(),encoding='utf-8')
(HERE/'calculations.json').write_text(json.dumps(R,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
print(json.dumps(R,ensure_ascii=False,indent=2,default=lambda x:str(x.quantize(D('0.0001')))))
