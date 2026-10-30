"""Offline exact financial reconstruction; issuer input and vendor snapshot separate."""
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
sys.stdout.reconfigure(encoding='utf-8')
Y=D('100000000')

def irr(price,dividends,terminal):
    lo,hi=D('-.95'),D('2')
    for _ in range(160):
        r=(lo+hi)/2
        pv=sum(x/(1+r)**t for t,x in enumerate(dividends,1))+terminal/(1+r)**len(dividends)
        if pv>price:lo=r
        else:hi=r
    return (lo+hi)/2

def calculate():
    I=json.loads((HERE/'inputs.json').read_text(encoding='utf-8'))
    rows={k:{m:exact(v) for m,v in r.items()} for k,r in I['periods'].items()}
    for year in ('2025','2026'):
        rows[year+'Q3']={m:rows[year+'YTD'][m]-rows[year+'H1'][m] for m in rows[year+'H1']}
    T={m:rows['2025'][m]+rows['2026YTD'][m]-rows['2025YTD'][m] for m in rows['2025']}
    rows['TTM']=T
    R={'periods':{},'growth':{}}
    for name,row in rows.items():
        r={m:v/Y for m,v in row.items()}
        r['parent_margin']=row['profit']/row['revenue']*100
        r['cfo_parent_ratio']=row['ocf']/row['profit']*100
        if 'group_profit' in row:
            r['minority_profit']=(row['group_profit']-row['profit'])/Y
            r['cfo_group_ratio']=row['ocf']/row['group_profit']*100
        if 'cost' in row:r['gross_margin']=(1-row['cost']/row['revenue'])*100
        if 'operating' in row:r['operating_margin']=row['operating']/row['revenue']*100
        if 'sales' in row:r['sales_ratio']=row['sales']/row['revenue']*100
        if 'admin' in row:r['admin_ratio']=row['admin']/row['revenue']*100
        if 'capex' in row:r['fcf']=(row['ocf']-row['capex'])/Y
        R['periods'][name]=r
    for period in ('YTD','H1','Q3'):
        R['growth'][period]={m:(rows['2026'+period][m]/rows['2025'+period][m]-1)*100 for m in rows['2026'+period] if rows['2025'+period][m]}
    price,shares=exact(I['price']),exact(I['shares'])
    B={p:{k:exact(v) for k,v in row.items()} for p,row in I['balance'].items()}
    R['valuation']={'market_cap_yi':price*shares/Y,'pe':price*shares/T['profit'],'core_pe':price*shares/T['core'],
        'pb':price*shares/B['current']['equity'],'eps':T['profit']/shares,'core_eps':T['core']/shares,
        'historical_dividend_yield':exact(I['dividend_2025'])/price*100,
        'fcf_yield':(T['ocf']-T['capex'])/(price*shares)*100}
    R['balance']={}
    for period,b in B.items():
        debt=sum(b[k] for k in ('short_debt','long_debt','current_noncurrent','lease'))
        R['balance'][period]={'cash_plus_trading':(b['cash']+b['trading'])/Y,'specified_debt':debt/Y,
            'liquid_minus_debt':(b['cce']+b['trading']-debt)/Y}
    R['balance']['ar_growth']=(B['current']['ar']/B['opening']['ar']-1)*100
    R['balance']['inventory_growth']=(B['current']['inventory']/B['opening']['inventory']-1)*100
    R['balance']['ar_days_270']=(B['current']['ar']+B['opening']['ar'])/2/rows['2026YTD']['revenue']*270
    R['balance']['inventory_days_270']=(B['current']['inventory']+B['opening']['inventory'])/2/rows['2026YTD']['cost']*270
    R['balance']['minority_equity_share']=B['current']['minority_equity']/(B['current']['equity']+B['current']['minority_equity'])*100
    R['balance']['intangibles_goodwill_share']=(B['current']['intangibles']+B['current']['goodwill'])/B['current']['assets']*100
    biz={k:exact(v) for k,v in I['business'].items()}
    R['business']={'guoyao_lookthrough_stake':biz['guoyao_direct']+biz['technology_stake']*biz['guoyao_technology']/100,
        'commercial_h1_margin':biz['commercial_h1_profit']/biz['commercial_h1_revenue']*100}
    eps=T['core']/shares
    R['scenarios']={}
    for s in I['scenarios']:
        g,payout,pe=map(exact,(s['growth'],s['payout'],s['exit_pe']))
        earnings=[eps*(1+g)**t for t in range(1,6)]
        div=[x*payout for x in earnings]
        terminal=earnings[-1]*pe
        R['scenarios'][s['name']]={'growth':g*100,'payout':payout*100,'exit_pe':pe,'eps5':earnings[-1],
            'exit_price':terminal,'dividends':div,'dividend_sum':sum(div),'irr_pct':irr(price,div,terminal)*100,
            'pv_10pct':sum(x/D('1.10')**t for t,x in enumerate(div,1))+terminal/D('1.10')**5}
    lo,hi=D('-.1'),D('.5')
    for _ in range(160):
        g=(lo+hi)/2
        value=sum(eps*(1+g)**t*D('.6')/D('1.1')**t for t in range(1,6))+eps*(1+g)**5*24/D('1.1')**5
        if value<price:lo=g
        else:hi=g
    R['reverse_growth_10pct']=(lo+hi)/2*100
    return I,rows,R

def run():
    I,rows,R=calculate()
    (HERE/'results.json').write_text(json.dumps(R,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    log=io.StringIO(); checks=[]
    with redirect_stdout(log):
        verify_market_cap(I['price'],I['shares'],exact(I['reported_cap_yi'])*Y,'CNY')
        verify_valuation(I['price'],R['valuation']['eps'],exact(I['balance']['current']['equity'])/exact(I['shares']),dividend=I['dividend_2025'])
        if (HERE/'vendor-snapshot.json').exists():
            snapshot=json.loads((HERE/'vendor-snapshot.json').read_text(encoding='utf-8'))['periods']
            for period,vendor in snapshot.items():
                for field in ('revenue','profit','core','ocf'):
                    primary=rows[period][field]; secondary=exact(vendor[field])
                    deviation=abs(primary-secondary)/abs(primary)*100
                    cross_validate(period+'/'+field,{'issuer':primary,'Eastmoney':secondary},'CNY',tolerance_pct=1)
                    assert deviation <= D('.01'), (period,field,deviation)
                    checks.append({'period':period,'metric':field,'primary':str(primary),'secondary':str(secondary),
                        'difference_pct':str(deviation),'note':'CNY100 precision in some issuer summary rows; no exact-match claim'})
    clean='\n'.join(x.rstrip() for x in re.sub(r'\x1b\[[0-9;]*m','',log.getvalue()).splitlines())+'\n'
    (HERE/'financial-rigor.txt').write_text(clean,encoding='utf-8')
    (HERE/'cross-source.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(R,ensure_ascii=False,indent=2,default=lambda x:str(x.quantize(D('.0001')))))
    print('Cross-source checks:',len(checks))

if __name__=='__main__':run()
