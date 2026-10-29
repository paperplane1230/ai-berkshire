"""Exact arithmetic and independently reproducible five-year cashflow IRRs."""
import contextlib
import io
import json
import sys
from decimal import Decimal as D
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import financial_rigor as rigor

def irr(price, flows):
    lo, hi = D('-0.99'), D('2')
    for _ in range(160):
        mid=(lo+hi)/2
        npv=sum(c/(1+mid)**i for i,c in enumerate(flows,1))-price
        if npv>0: lo=mid
        else: hi=mid
    return (lo+hi)/2

def calculate():
    data=json.loads((HERE/'inputs.json').read_text(encoding='utf-8'))
    fin={p:{k:D(v) for k,v in row.items()} for p,row in data['financial'].items()}
    q=data['quote']; shares=D(data['shares']['total']); fx=D(q['HKDCNY'])
    out={}
    for year in ['2025','2026']:
        fin[year+'Q3']={k:fin[year+'YTD'][k]-fin[year+'H1'][k] for k in ['revenue','profit','adjusted','cfo','cost','capex']}
    for period,row in fin.items():
        out[period]={k:v/D('1e8') for k,v in row.items()}
        if 'cost' in row: out[period]['gross_margin_pct']=(row['revenue']-row['cost'])/row['revenue']*100
        out[period]['cfo_to_profit_pct']=row['cfo']/row['profit']*100
        if 'capex' in row: out[period]['fcf']= (row['cfo']-row['capex'])/D('1e8')
    for period in ['YTD','Q3']:
        out['growth_'+period]={k:(fin['2026'+period][k]/fin['2025'+period][k]-1)*100 for k in ['revenue','profit','adjusted','cfo']}
    ttm={k:fin['2025'][k]+fin['2026YTD'][k]-fin['2025YTD'][k] for k in ['revenue','profit','adjusted','cfo','capex']}
    eps=ttm['profit']/shares
    out['ttm']={k:v/D('1e8') for k,v in ttm.items()}
    out['ttm'].update(eps=eps,adjusted_eps=ttm['adjusted']/shares,fcf=(ttm['cfo']-ttm['capex'])/D('1e8'))
    a=D(q['A_CNY']); h=D(q['H_HKD']); hc=h*fx
    cap_a=a*D(data['shares']['A']); cap_h=hc*D(data['shares']['H'])
    out['valuation']={'A_PE':a/eps,'H_PE':hc/eps,'A_deducted_PE':a/(ttm['adjusted']/shares),'H_deducted_PE':hc/(ttm['adjusted']/shares),'A_cap_yi':cap_a/D('1e8'),'H_cap_HKD_yi':h*D(data['shares']['H'])/D('1e8'),'combined_cap_CNY_yi':(cap_a+cap_h)/D('1e8'),'A_equivalent_cap_yi':a*shares/D('1e8'),'H_price_CNY':hc,'H_discount_pct':(1-hc/a)*100,'A_PB':a/(D(data['balance']['parent_equity'])/shares),'H_PB':hc/(D(data['balance']['parent_equity'])/shares)}
    regular=D('1.06'); special=D('1.36')
    out['dividends']={'regular':regular,'including_special':special,'A_regular_yield_pct':regular/a*100,'H_regular_yield_pct':regular/hc*100,'A_special_included_yield_pct':special/a*100,'H_special_included_yield_pct':special/hc*100,'A_policy_ttm_yield_pct':eps*D('0.8')/a*100,'H_policy_ttm_yield_pct':eps*D('0.8')/hc*100}
    bal={k:D(v) for k,v in data['balance'].items()}
    out['balance']={'cash_plus_trading_yi':(bal['cash']+bal['trading_assets'])/D('1e8'),'named_debt_yi':sum(bal[k] for k in ['short_loans','long_loans','current_noncurrent_debt','leases'])/D('1e8'),'receivables_change_pct':(bal['receivables']/bal['receivables_yearend']-1)*100,'inventory_change_pct':(bal['inventory']/bal['inventory_yearend']-1)*100,'intangibles_goodwill_assets_pct':(bal['intangibles']+bal['goodwill'])/bal['assets']*100,'DSO_270':(bal['receivables']+bal['receivables_yearend'])/2/fin['2026YTD']['revenue']*270,'DIO_270':(bal['inventory']+bal['inventory_yearend'])/2/fin['2026YTD']['cost']*270}
    out['products']={}
    for product,values in data['products'].items():
        y,prior,h,priorh=map(D,values)
        out['products'][product]={'YTD_yi':y/D('1e8'),'YTD_growth_pct':(y/prior-1)*100,'Q3_yi':(y-h)/D('1e8'),'Q3_growth_pct':((y-h)/(prior-priorh)-1)*100}
    out['scenarios']=[]
    for s in data['scenarios']:
        g=D(s['growth']); payout=D(s['payout'])
        earnings=[eps*(1+g)**i for i in range(1,6)]
        divs=[e*payout for e in earnings]
        exits={m:earnings[-1]*D(s[m+'_exit_PE']) for m in ['A','H']}
        out['scenarios'].append({'name':s['name'],'year5_eps':earnings[-1],'dividend_sum_CNY':sum(divs),'A_exit_CNY':exits['A'],'H_exit_HKD':exits['H']/fx,'A_IRR_pct':irr(a,divs[:-1]+[divs[-1]+exits['A']])*100,'H_IRR_pct':irr(hc,divs[:-1]+[divs[-1]+exits['H']])*100})
    return data,out

if __name__=='__main__':
    data,out=calculate()
    (HERE/'results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
    log=io.StringIO()
    with contextlib.redirect_stdout(log):
        rigor.verify_market_cap(data['quote']['A_CNY'],data['shares']['A'],'191981000000','CNY')
        rigor.verify_market_cap(data['quote']['H_HKD'],data['shares']['H'],'7245900000','HKD')
        rigor.verify_valuation(data['quote']['A_CNY'],out['ttm']['eps'],D(data['balance']['parent_equity'])/D(data['shares']['total']),out['ttm']['fcf']*D('1e8')/D(data['shares']['total']),D('1.06'))
        snapshot=HERE/'eastmoney-snapshot.json'
        if snapshot.exists():
            second=json.loads(snapshot.read_text(encoding='utf-8'))
            for period,row in second['data'].items():
                for metric,value in row.items():
                    rigor.cross_validate(period+' '+metric,{'issuer filing':data['financial'][period][metric],'Eastmoney':value},unit='CNY',tolerance_pct=1)
    (HERE/'financial-rigor.txt').write_text(log.getvalue(),encoding='utf-8')
