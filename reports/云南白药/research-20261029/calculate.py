"""Exact arithmetic; inputs are transcribed from the cited primary filings."""
import json
import sys
import io
from contextlib import redirect_stdout
from decimal import Decimal as D
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from financial_rigor import exact, verify_market_cap, verify_valuation, cross_validate
HERE=Path(__file__).parent
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
I=json.loads((HERE/'inputs.json').read_text(encoding='utf-8'))
Y=D('100000000')
data={k:{m:exact(v) for m,v in row.items()} for k,row in I.items() if isinstance(row,dict)}
q={str(y):{m:data[f'{y}ytd'][m]-data[f'{y}h1'][m] for m in data[f'{y}h1']} for y in (2025,2026)}
ttm={m:data['2025'][m]+data['2026ytd'][m]-data['2025ytd'][m] for m in data['2025']}
results={'periods':{},'q3':{},'ttm':{k:str(v/Y) for k,v in ttm.items()}}
for name,row in data.items():
    if 'profit' not in row:continue
    r={m:str(v/Y) for m,v in row.items()}
    r['net_margin']=str(row['profit']/row['revenue']*100)
    r['cash_conversion']=str(row['ocf']/row['profit']*100)
    if 'cost' in row:r['gross_margin']=str((1-row['cost']/row['revenue'])*100)
    if 'capex' in row:r['fcf']=str((row['ocf']-row['capex'])/Y)
    results['periods'][name]=r
for year,row in q.items():
    r={m:str(v/Y) for m,v in row.items()}
    r['gross_margin']=str((1-row['cost']/row['revenue'])*100)
    r['operating_margin']=str(row['operating']/row['revenue']*100)
    r['fcf']=str((row['ocf']-row['capex'])/Y)
    r['cash_conversion']=str(row['ocf']/row['profit']*100)
    results['q3'][year]=r
results['q3_yoy']={m:str((q['2026'][m]/q['2025'][m]-1)*100) for m in q['2026']}
p=exact(I['price']);s=exact(I['shares']);cap=p*s
results['valuation']={'market_cap_yi':str(cap/Y),'pe':str(cap/ttm['profit']),'core_pe':str(cap/ttm['core']),'pb':str(cap/data['balance']['equity']),'eps_ttm':str(ttm['profit']/s),'core_eps_ttm':str(ttm['core']/s),'fcf_ttm':str((ttm['ocf']-ttm['capex'])/Y),'fcf_yield':str((ttm['ocf']-ttm['capex'])/cap*100)}
for name,div in [('2025_year',D('2.602')),('2026_cash',D('2.621'))]:
    results['valuation'][name+'_dividend_yield']=str(div/p*100)
b=data['balance']
results['balance']={
 'receivables_growth':str((b['receivables']/b['receivables_open']-1)*100),
 'inventory_growth':str((b['inventory']/b['inventory_open']-1)*100),
 'ar_days_273':str((b['receivables']+b['receivables_open'])/2/data['2026ytd']['revenue']*273),
 'inventory_days_273':str((b['inventory']+b['inventory_open'])/2/data['2026ytd']['cost']*273),
 'gross_liquid_yi':str((b['cash']+b['trading_assets'])/Y),
 'conservative_net_liquid_yi':str((b['cash_equivalents']+b['trading_assets']-sum(b[x] for x in ('short_debt','current_noncurrent_debt','long_debt','lease_debt','long_payables')))/Y),
 'goodwill_intangible_pct':str((b['goodwill']+b['intangibles'])/b['assets']*100)
}
def irr(cfs):
    lo,hi=D('-.9'),D('1')
    for _ in range(160):
        mid=(lo+hi)/2
        npv=sum(cf/(1+mid)**t for t,cf in enumerate(cfs))
        if npv>0:lo=mid
        else:hi=mid
    return (lo+hi)/2
results['scenarios']={}
eps=ttm['core']/s
for name,g,pe,payout in [('bear','-.02','14','.8'),('base','.03','18','.85'),('bull','.06','22','.85')]:
    g=D(g);pe=D(pe);payout=D(payout)
    earnings=[eps*(1+g)**t for t in range(1,6)]
    dividends=[e*payout for e in earnings]
    exit_price=earnings[-1]*pe
    cfs=[-p]+dividends[:-1]+[dividends[-1]+exit_price]
    results['scenarios'][name]={'growth':str(g*100),'exit_pe':str(pe),'payout':str(payout*100),'year5_eps':str(earnings[-1]),'exit_price':str(exit_price),'dividends_total':str(sum(dividends)),'irr_pct':str(irr(cfs)*100)}
results['price_bands']={str(pe):str(eps*D(pe)) for pe in (15,16,18,19,21,22)}
(HERE/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))
log=io.StringIO()
with redirect_stdout(log):
    verify_market_cap(p,s,exact(I['quote_market_cap_yi'])*Y,'CNY')
    verify_valuation(p,ttm['profit']/s,b['equity']/s,(ttm['ocf']-ttm['capex'])/s,D('2.602'))
    em=json.loads((ROOT/'local/云南白药-20261029/eastmoney-main.json').read_text(encoding='utf-8'))['result']['data']
    mapping={'2023':'2023-12-31','2024':'2024-12-31','2025':'2025-12-31','2025ytd':'2025-09-30','2026ytd':'2026-09-30','2025h1':'2025-06-30','2026h1':'2026-06-30'}
    checks=[]
    for period,date in mapping.items():
        source=next(row for row in em if row['REPORT_DATE'].startswith(date))
        for field,key in {'revenue':'TOTALOPERATEREVE','profit':'PARENTNETPROFIT','core':'KCFJCXSYJLR','ocf':'NETCASH_OPERATE_PK'}.items():
            a=data[period][field];bval=D(str(source[key]))
            cross_validate(period+' '+field,{'CNINFO':a,'Eastmoney':bval},'CNY',tolerance_pct=1.0)
            assert abs(a-bval)/abs(a)<=D('.01')
            checks.append({'period':period,'field':field,'primary':str(a),'secondary':str(bval),'secondary_key':key,'date':date})
    (HERE/'cross-source.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
(HERE/'financial-rigor.txt').write_text(log.getvalue(),encoding='utf-8')
print('Cross-source checks:',len(checks),'PASS')
