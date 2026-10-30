"""Finite five-year distribution and exit-PE model, with exact inputs."""
import io
import json
import re
import sys
from contextlib import redirect_stdout
from decimal import Decimal as D
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from financial_rigor import exact,verify_market_cap,verify_valuation,cross_validate
Y=D('100000000')

def irr(price,flows):
    lo,hi=D('-.95'),D('3')
    for _ in range(160):
        r=(lo+hi)/2
        pv=sum(cf/(1+r)**t for t,cf in enumerate(flows,1))
        if pv>price:lo=r
        else:hi=r
    return (lo+hi)/2

def calculate():
    I=json.loads((HERE/'inputs.json').read_text(encoding='utf-8'))
    P,N=exact(I['price']),exact(I['shares'])
    rows={k:{m:exact(v) for m,v in r.items()} for k,r in I['periods'].items()}
    for year in ('2025','2026'):
        rows[year+'Q3']={m:rows[year+'YTD'][m]-rows[year+'H1'][m] for m in rows[year+'YTD']}
    rows['TTM']={m:rows['2025'][m]+rows['2026YTD'][m]-rows['2025YTD'][m] for m in rows['2025']}
    R={'periods':{},'growth':{}}
    for name,row in rows.items():
        d={k:v/Y for k,v in row.items()}
        d['cash_conversion']=row['cfo']/row['profit']*100
        d['core_cash_conversion']=row['cfo']/row['core']*100
        d['net_margin']=row['profit']/row['revenue']*100
        if 'capex' in row:d['fcf']=(row['cfo']-row['capex'])/Y
        if 'cost' in row:d['gross_margin']=(1-row['cost']/row['revenue'])*100;d['gross_profit']=(row['revenue']-row['cost'])/Y
        if 'sales' in row:d['sales_ratio']=row['sales']/row['revenue']*100
        if 'operating' in row:d['operating_margin']=row['operating']/row['revenue']*100
        R['periods'][name]=d
    for period in ('YTD','H1','Q3'):
        R['growth'][period]={k:(rows['2026'+period][k]/rows['2025'+period][k]-1)*100 for k in rows['2026'+period]}
    B={k:exact(v) for k,v in I['balance'].items()}
    eps=rows['TTM']['core']/N
    R['valuation']={'a_equivalent_cap_yi':P*N/Y,'a_class_cap_yi':P*exact(I['a_shares'])/Y,'gaap_pe':P*N/rows['TTM']['profit'],'core_pe':P/eps,'core_eps':eps,'gaap_eps':rows['TTM']['profit']/N,'pb':P*N/B['equity'],'historical_2025_dividend_yield':D('4.79')/P*100,'final_dividend_yield':D('2.34')/P*100,'fcf_yield':(rows['TTM']['cfo']-rows['TTM']['capex'])/(P*N)*100,'mechanical_core_payout75_yield':eps*D('.75')/P*100}
    R['balance']={k:v/Y for k,v in B.items()}
    R['balance']['named_debt_yi']=(B['short_loan']+B['current_noncurrent_debt']+B['lease'])/Y
    R['balance']['cash_less_scoped_burden_yi']=(B['cash_equivalents']-B['short_loan']-B['current_noncurrent_debt']-B['lease']-B['long_payables'])/Y
    R['balance']['dso_273']=(B['receivables']+B['receivables_previous'])/2/rows['2026YTD']['revenue']*273
    R['balance']['dio_273']=(B['inventory']+B['inventory_previous'])/2/rows['2026YTD']['cost']*273
    R['balance']['intangible_goodwill_pct']=(B['intangibles']+B['goodwill'])/B['assets']*100
    R['annual_weights']={k:exact(v)/rows['2025']['revenue']*100 for k,v in I['annual_segments'].items()}
    R['dividend_total_2025']=D('4.79')*N/Y
    R['dividend_payout_2025']=D('4.79')*N/rows['2025']['profit']*100
    R['q3_gross_profit_change']=R['periods']['2026Q3']['gross_profit']-R['periods']['2025Q3']['gross_profit']
    R['q3_sales_saving']=(rows['2025Q3']['sales']-rows['2026Q3']['sales'])/Y
    R['scenarios']={}
    for s in I['scenarios']:
        g,payout,pe=[D(s[x]) for x in ('growth','payout','exit_pe')]
        earnings=[eps*(1+g)**t for t in range(1,6)]
        dividends=[e*payout for e in earnings]
        terminal=earnings[-1]*pe
        flows=dividends.copy();flows[-1]+=terminal
        R['scenarios'][s['name']]={'eps5':earnings[-1],'terminal_price':terminal,'dividends':dividends,'dividend_sum':sum(dividends),'irr_pct':irr(P,flows)*100,'pv_at_10pct':sum(cf/D('1.10')**t for t,cf in enumerate(flows,1))}
    lo,hi=D('-.2'),D('.5')
    for _ in range(160):
        g=(lo+hi)/2
        flows=[eps*(1+g)**t*D('.75') for t in range(1,6)]
        flows[-1]+=eps*(1+g)**5*28
        if sum(cf/D('1.1')**t for t,cf in enumerate(flows,1))<P:lo=g
        else:hi=g
    R['growth_for_10pct_return']=(lo+hi)/2*100
    return I,rows,R

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    I,rows,R=calculate()
    log=io.StringIO()
    with redirect_stdout(log):
        verify_market_cap(I['price'],I['shares'],I['vendor_a_equivalent_cap'],'CNY A-price equivalent, NOT combined trading cap')
        verify_valuation(I['price'],eps=rows['TTM']['profit']/exact(I['shares']),bvps=exact(I['balance']['equity'])/exact(I['shares']))
        if (HERE/'vendor-snapshot.json').exists():
            V=json.loads((HERE/'vendor-snapshot.json').read_text(encoding='utf-8'))
            for name,rec in V['financial'].items():
                for key in ('revenue','profit','core','cfo'):
                    cross_validate(name+'/'+key,{'issuer filing':I['periods'][name][key],'Eastmoney':rec[key]},'元',tolerance_pct=1)
    clean=re.sub(r'\x1b\[[0-9;]*m','',log.getvalue())
    (HERE/'financial-rigor.txt').write_text('\n'.join(x.rstrip() for x in clean.splitlines())+'\n',encoding='utf-8')
    (HERE/'calculations.json').write_text(json.dumps(R,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    print(json.dumps(R,ensure_ascii=False,indent=2,default=lambda v:str(v.quantize(D('.0001')))))
