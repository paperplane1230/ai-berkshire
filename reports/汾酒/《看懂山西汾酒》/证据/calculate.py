"""Offline exact calculations for the approved Fenjiu series."""
import contextlib
import io
import json
import re
import subprocess
import sys
from decimal import Decimal, getcontext
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'tools'))
import financial_rigor as rigor
import terminal_value as terminal
getcontext().prec=40
D=rigor.exact
Y=D('100000000')
DATA=json.loads((HERE/'source-data.json').read_text(encoding='utf-8'))
P,S=D(DATA['quote']['price']),D(DATA['shares'])
def dump(name,obj):
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str,sort_keys=True)+'\n',encoding='utf-8')
def clean(text):
    return '\n'.join(line.rstrip() for line in re.sub(r'\x1b\[[0-9;]*m','',text).splitlines()).rstrip()+'\n'
def pv(flows,rate):return sum((cf/(1+rate)**t for t,cf in enumerate(flows,1)),D(0))
def irr(price,flows):
    assert price>0 and all(x>=0 for x in flows) and flows[-1]>0
    lo,hi=D('-.9999'),D(3)
    while pv(flows,hi)>price:hi=2*hi+1
    for _ in range(220):
        mid=(lo+hi)/2
        if pv(flows,mid)>price:lo=mid
        else:hi=mid
    return (lo+hi)/2
def main():
    fin={period:{k:D(v) for k,v in row.items()} for period,row in DATA['financial'].items()}
    for year in ('2025','2026'):
        a,b=fin[year+'YTD'],fin[year+'H1']
        fin[year+'Q3']={k:a[k]-b[k] for k in a.keys()&b.keys()}
    fin['2025Q4']={k:fin['2025'][k]-fin['2025YTD'][k] for k in fin['2025'].keys()&fin['2025YTD'].keys()}
    fin['2026Q1']={k:D(v) for k,v in DATA['primary_quarter_checks']['2026Q1'].items()}
    fin['2026Q2']={k:fin['2026H1'][k]-fin['2026Q1'][k] for k in fin['2026H1'].keys()&fin['2026Q1'].keys()}
    ttm={k:fin['2025'][k]+fin['2026YTD'][k]-fin['2025YTD'][k] for k in fin['2025'].keys()&fin['2026YTD'].keys()&fin['2025YTD'].keys()}
    periods={}
    for name,row in fin.items():
        item={k:v/Y for k,v in row.items()}
        item['parent_margin_pct']=row['profit']/row['revenue']*100
        item['cash_parent_ratio_pct']=row['cfo']/row['profit']*100
        if 'cost' in row:item.update(gross_profit=(row['revenue']-row['cost'])/Y,gross_margin_pct=(1-row['cost']/row['revenue'])*100)
        if 'capex' in row:item['simple_fcf']=(row['cfo']-row['capex'])/Y
        for field in ('sales_expense','admin_expense','sale_cash'):
            if field in row:item[field+'_revenue_pct']=row[field]/row['revenue']*100
        periods[name]=item
    annual={}
    for year,row in DATA['annual'].items():
        revenue,profit,cfo,capex,cost=[D(row[k]) for k in ('revenue','profit','cfo','capex','cost')]
        annual[year]={'revenue':revenue/Y,'profit':profit/Y,'core':D(row['core'])/Y,'cfo':cfo/Y,'capex':capex/Y,'simple_fcf':(cfo-capex)/Y,'gross_margin_pct':(1-cost/revenue)*100,'selling_ratio_pct':D(row['selling_expense'])/revenue*100,'net_margin_pct':profit/revenue*100,'cash_parent_ratio_pct':cfo/profit*100,'outside_share_pct':D(row['outside_revenue'])/D(row['alcohol_revenue'])*100,'inventory':D(row['inventory'])/Y}
    total={k:sum(D(row[k]) for row in DATA['annual'].values())/Y for k in ('revenue','profit','cfo','capex')}
    total['simple_fcf']=total['cfo']-total['capex']
    total['cash_parent_ratio_pct']=total['cfo']/total['profit']*100
    total['simple_fcf_parent_ratio_pct']=total['simple_fcf']/total['profit']*100
    bal={p:{k:D(v) for k,v in row.items()} for p,row in DATA['balance'].items()}
    b=bal['2026Q3']
    debt=b['lease_liability']+b['current_noncurrent_debt']
    market={'price':P,'shares':S,'market_cap_yi':P*S/Y,'pe':P*S/ttm['profit'],'core_pe':P*S/ttm['core'],'pb':P*S/b['parent_equity'],'eps_ttm':ttm['profit']/S,'core_eps_ttm':ttm['core']/S,'bvps':b['parent_equity']/S,'historical_dividend_yield_pct':D('6.56')/P*100,'ttm65_dividend_per_share':ttm['profit']*D('.65')/S,'ttm65_dividend_yield_pct':ttm['profit']*D('.65')/(P*S)*100,'ttm_simple_fcf_yield_pct':(ttm['cfo']-ttm['capex'])/(P*S)*100}
    cash={'cash_equivalents':b['cash_equivalents']/Y,'named_lease_and_current_noncurrent':debt/Y,'narrow_cash_net':(b['cash_equivalents']-debt)/Y,'other_current_assets_not_all_cash':b['other_current_assets']/Y,'bills_financing_not_cash':b['bills_financing']/Y,'q3_excess_distributable_cash':None,'ytd_fcf_to_prior_fiscal_paid_dividend_pct':periods['2026YTD']['simple_fcf']/(D(DATA['notes']['dividend_paid_2026_total'])/Y)*100,'ttm_simple_fcf':(ttm['cfo']-ttm['capex'])/Y}
    operations={}
    for name,row in DATA['operating']['rows'].items():
        h,ph,y,py=[D(row[k]) for k in ('h1_current_wan','h1_prior_wan','ytd_current_wan','ytd_prior_wan')]
        operations[name]={'h1':h/D(10000),'h1_prior':ph/D(10000),'ytd':y/D(10000),'ytd_prior':py/D(10000),'q3':(y-h)/D(10000),'q3_prior':(py-ph)/D(10000),'q3_yoy_pct':((y-h)/(py-ph)-1)*100,'ytd_yoy_pct':(y/py-1)*100}
    log=io.StringIO();checks=[]
    em={r['REPORT_DATE'][:10]:r for r in DATA['vendors']}
    dates={'2023':'2023-12-31','2024':'2024-12-31','2025':'2025-12-31','2025H1':'2025-06-30','2026H1':'2026-06-30','2025YTD':'2025-09-30','2026YTD':'2026-09-30'}
    with contextlib.redirect_stdout(log):
        assert rigor.verify_market_cap(P,S,DATA['quote']['reported_market_cap'],'CNY')
        rigor.verify_valuation(P,market['eps_ttm'],market['bvps'],dividend=D('6.56'))
        for period,day in dates.items():
            for field,column in {'revenue':'TOTALOPERATEREVE','profit':'PARENTNETPROFIT','core':'KCFJCXSYJLR','cfo':'NETCASH_OPERATE_PK'}.items():
                a,z=fin[period][field],D(em[day][column]);r=rigor.cross_validate(period+field,{'issuer':a,'Eastmoney':z},'CNY',1)
                checks.append({'period':period,'field':field,'primary':a,'secondary':z,'exact':a==z,'passed':r['all_consistent']})
        for year,row in DATA['annual'].items():
            for field,column in {'revenue':'TOTALOPERATEREVE','profit':'PARENTNETPROFIT','core':'KCFJCXSYJLR','cfo':'NETCASH_OPERATE_PK'}.items():
                a,z=D(row[field]),D(em[year+'-12-31'][column]);documented=year=='2021' and field=='profit' and z==D(row['profit_original'])
                assert a==z or documented
                r=rigor.cross_validate(year+field,{'restated_issuer':a,'Eastmoney':z},'CNY',1)
                checks.append({'period':year,'field':field,'primary':a,'secondary':z,'exact':a==z,'documented_restatement_difference':documented,'passed':r['all_consistent']})
        for field,column in {'cash':'MONETARYFUNDS','other_current_assets':'OTHER_CURRENT_ASSET','inventory':'INVENTORY','contract_liabilities':'CONTRACT_LIAB','lease_liability':'LEASE_LIAB','current_noncurrent_debt':'NONCURRENT_LIAB_1YEAR','right_of_use':'USERIGHT_ASSET','construction':'CIP','parent_equity':'TOTAL_PARENT_EQUITY'}.items():
            a,z=b[field],D(DATA['vendor_balance'][column]);r=rigor.cross_validate('Q3 '+field,{'issuer':a,'Eastmoney':z},'CNY',1)
            checks.append({'period':'2026Q3 balance','field':field,'primary':a,'secondary':z,'exact':a==z,'passed':r['all_consistent']})
    audit=subprocess.run([sys.executable,str(ROOT/'tools/terminal_value.py'),'audit','--currency','CNY','--r','.08','--roic','.20','--g','0,.01,.02','--rf','.017','--beta','1','--discrete-risks','需求与结构恶化:情景,资本回报不足:情景,重大监管与品牌冲击:未建模'],capture_output=True,text=True,encoding='utf-8')
    (HERE/'terminal-audit.txt').write_text(clean(audit.stdout+audit.stderr),encoding='utf-8')
    assert audit.returncode==0
    initial=ttm['core'];pay=D(DATA['model']['payout']);R=D(DATA['model']['incremental_retained_capital_return_proxy'])
    models={}
    for name,spec in DATA['model']['cases'].items():
        growth,g=D(spec['growth']),D(spec['g_terminal'])
        profits=[initial*(1+growth)**t for t in range(1,11)]
        dividends=[v/S*pay for v in profits]
        exit3=profits[2]/S*D(spec['pe3']);flow3=dividends[:2]+[dividends[2]+exit3]
        curves=[]
        for rate in map(D,('.06','.07','.08','.09','.10')):
            capacity_fraction=1-g/R
            pe=capacity_fraction/(rate-g)
            price_capacity=profits[-1]/S*(1+g)*pe
            price_policy=profits[-1]/S*(1+g)*pay/(rate-g)
            row={'r':rate,'g':g,'spread':rate-g,'in_CNY_band':rate<=D('.09'),'valid_spread':rate-g>=D('.05'),'terminal_capacity_fraction':capacity_fraction,'terminal_capacity_forward_pe':pe,'terminal_policy_forward_pe':pay/(rate-g)}
            for mode,exitprice in [('capacity',price_capacity),('policy65',price_policy)]:
                flows=dividends[:-1]+[dividends[-1]+exitprice];rate_irr=irr(P,flows)
                assert abs(pv(flows,rate_irr)-P)<D('1e-25')
                value=pv(flows,rate)
                row[mode]={'terminal_price':exitprice,'irr_pct':rate_irr*100,'pv':value,'covers_r':rate_irr>=rate,'terminal_pv_weight_pct':exitprice/(1+rate)**10/value*100,'price_at20pct_discount':value*D('.8')}
            curves.append(row)
        end10=profits[-1]/S*(1+g)*(1-g/R)/(D('.10')-g)
        capital_only=(float(end10/P)**.1-1)*100
        single={'roic':float(R),'g':(float(g),)*3,'p':(1.,0.,0.),'irr10':(capital_only,)*3,'k':0.}
        models[name]={'growth':growth,'g_terminal':g,'profit_path_yi':[v/Y for v in profits],'annual_dividends':dividends,'three_year_exit_pe':D(spec['pe3']),'three_year_exit_price':exit3,'three_year_irr_pct':irr(P,flow3)*100,'three_year_pv8':pv(flow3,D('.08')),'curves':curves,'terminal_only_conditional_flip':{str(d):terminal.flip_analysis(single,.08,delta=d,band=terminal.CURRENCY_BANDS['CNY']) for d in (.02,.01)},'actual_cashflow_flips':{mode:len({row[mode]['covers_r'] for row in curves if row['valid_spread'] and row['in_CNY_band']})>1 for mode in ('capacity','policy65')}}
        with contextlib.redirect_stdout(log):rigor.three_scenario_valuation(P,initial/S,S/Y,growth,growth,growth,D(spec['pe3']),D(spec['pe3']),D(spec['pe3']),3,'CNY')
    def price_for_growth(growth,years,mode):
        profits=[initial/S*(1+growth)**t for t in range(1,years+1)]
        dividends=[v*pay for v in profits]
        multiple=D(16) if years==3 else ((1-D('.01')/R) if mode=='capacity' else pay)/(D('.08')-D('.01'))
        end=profits[-1]*multiple*(1+D('.01') if years==10 else D(1))
        return pv(dividends[:-1]+[dividends[-1]+end],D('.08'))
    reverse=[]
    for years,mode in ((3,'capacity'),(10,'capacity'),(10,'policy65')):
        lo,hi=D('-.5'),D('.5')
        for _ in range(200):
            mid=(lo+hi)/2
            if price_for_growth(mid,years,mode)<P:lo=mid
            else:hi=mid
        growth=(lo+hi)/2
        reverse.append({'years':years,'terminal_mode':'fixed_PE16' if years==3 else mode,'terminal_g':None if years==3 else D('.01'),'annual_payout':pay,'target_irr':D('.08'),'required_growth_pct':growth*100,'residual':price_for_growth(growth,years,mode)-P})
    tests={'two_prices_match':P==D(DATA['quote']['sina_price']),'correct_quote_day':DATA['quote']['date']=='2026-11-13','shares_match_portal':S==D(em['2026-09-30']['TOTAL_SHARE']),'57_comparisons_pass':len(checks)==57 and all(c['passed'] for c in checks),'one_restatement_difference':sum(not c['exact'] for c in checks)==1,'regional_q3_sum':operations['省内']['q3']+operations['省外']['q3']==operations['代理']['q3']+operations['直销电商']['q3'],'province_positive_outside_negative':operations['省内']['q3_yoy_pct']>0 and operations['省外']['q3_yoy_pct']<0,'debt_includes_lease':debt>b['lease_liability'],'policy_value_not_above_capacity':all(row['policy65']['pv']<=row['capacity']['pv'] for m in models.values() for row in m['curves']),'reverse_residual':all(abs(x['residual'])<D('1e-25') for x in reverse)}
    assert all(tests.values())
    result={'cutoff':DATA['cutoff'],'market':market,'ttm':{k:v/Y for k,v in ttm.items()},'periods':periods,'annual':annual,'five_year_totals':total,'cash':cash,'operations':operations,'models':models,'reverse_growth':reverse,'tests':tests,'boundaries':DATA['boundaries']}
    dump('results.json',result);dump('cross-checks.json',checks);dump('tests.json',tests)
    (HERE/'financial-rigor.txt').write_text(clean(log.getvalue()),encoding='utf-8')
    print(json.dumps({'market':market,'model_at8':{n:next(c for c in m['curves'] if c['r']==D('.08')) for n,m in models.items()},'reverse':reverse,'tests':tests},ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
