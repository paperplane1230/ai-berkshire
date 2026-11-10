"""Offline Decimal calculations and source checks for the three-part series."""
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
PRICE,SHARES=D(DATA['quote']['price']),D(DATA['shares'])
def write(name,obj):
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
def clean_log(text):
    return '\n'.join(line.rstrip() for line in re.sub(r'\x1b\[[0-9;]*m','',text).splitlines()).rstrip()+'\n'
def pv(flows,r):
    return sum((c/(1+r)**t for t,c in enumerate(flows,1)),D(0))
def irr(price,flows):
    lo,hi=D('-.999'),D('3')
    assert price>0 and all(c>=0 for c in flows) and flows[-1]>0
    while pv(flows,hi)>price: hi=hi*2+1
    for _ in range(220):
        mid=(lo+hi)/2
        if pv(flows,mid)>price:lo=mid
        else:hi=mid
    return (lo+hi)/2
def extend(spec):
    profits=list(map(D,spec['first5_profit_yi']))
    while len(profits)<10:profits.append(profits[-1]*(1+D(spec['after5_growth'])))
    return profits
def main():
    fin={p:{k:D(v) for k,v in row.items()} for p,row in DATA['financial'].items()}
    for year in ('2025','2026'):
        a,b=fin[year+'YTD'],fin[year+'H1']
        fin[year+'Q3']={k:a[k]-b[k] for k in a.keys()&b.keys()}
    ttm={k:fin['2025'][k]+fin['2026YTD'][k]-fin['2025YTD'][k] for k in fin['2025'].keys()&fin['2026YTD'].keys()&fin['2025YTD'].keys()}
    bal={p:{k:D(v) for k,v in row.items()} for p,row in DATA['balance'].items()}
    b=bal['2026Q3']
    debt=sum(b[k] for k in ('short_debt','long_debt','current_noncurrent_debt','lease_liability'))
    market={'price':PRICE,'shares':SHARES,'market_cap_yi':PRICE*SHARES/Y,'eps_ttm':ttm['profit']/SHARES,'pe_ttm':PRICE*SHARES/ttm['profit'],'core_pe_ttm':PRICE*SHARES/ttm['core'],'bvps':b['parent_equity']/SHARES,'pb':PRICE*SHARES/b['parent_equity'],'historical_dividend_yield_pct':D('1.47')/PRICE*100,'ttm_profit_yi':ttm['profit']/Y,'ttm_cfo_yi':ttm['cfo']/Y,'ttm_simple_fcf_yi':(ttm['cfo']-ttm['capex'])/Y}
    liquidity={'named_debt_yi':debt/Y,'cash_equivalents_net_yi':(b['cash_equivalents']-debt)/Y,'cash_and_trading_net_yi':(b['cash_equivalents']+b['trading_financial_assets']-debt)/Y,'financial_pool_book_net_yi':(b['cash_equivalents']+b['trading_financial_assets']+b['noncurrent_financial_assets']+b['long_equity_investments']-debt)/Y,'not_distributable_cash':True}
    annual_derived={}
    for year,row in DATA['annual'].items():
        rev,cost,profit,cfo,capex=[D(row[k]) for k in ('revenue','cost','profit','cfo','capex')]
        annual_derived[year]={'revenue_yi':rev/Y,'profit_yi':profit/Y,'core_profit_yi':D(row['deducted_profit'])/Y,'cfo_yi':cfo/Y,'capex_yi':capex/Y,'simple_fcf_yi':(cfo-capex)/Y,'gross_profit_yi':(rev-cost)/Y,'gross_margin_pct':(rev-cost)/rev*100,'parent_margin_pct':profit/rev*100,'selling_expense_yi':D(row['selling_expense'])/Y,'selling_ratio_pct':D(row['selling_expense'])/rev*100,'admin_expense_yi':D(row['admin_expense'])/Y,'cash_conversion_pct':cfo/profit*100,'alcohol_share_pct':D(row['alcohol_revenue'])/rev*100,'online_share_pct':D(row['online_alcohol_revenue'])/D(row['alcohol_revenue'])*100}
    totals={key:sum(D(row[key]) for row in DATA['annual'].values())/Y for key in ('profit','cfo','capex')}
    totals['cfo_to_profit_pct']=totals['cfo']/totals['profit']*100
    totals['simple_fcf_to_profit_pct']=(totals['cfo']-totals['capex'])/totals['profit']*100
    notes=DATA['notes']
    auxiliary={'h1_rebates_share_pct':D(notes['unsettled_rebates_2026H1'])/(D(notes['unsettled_rebates_2026H1'])+D(notes['prepayment_2026H1']))*100,'h1_prepayment_ytd_change_pct':(D(notes['prepayment_2026H1'])/D(notes['prepayment_2025end'])-1)*100,'h1_finished_goods_change_pct':(D(notes['finished_goods_2026H1'])/D(notes['finished_goods_2025end'])-1)*100,'h1_semi_finished_inventory_pct':D(notes['semi_finished_2026H1'])/bal['2026H1']['inventory']*100}
    checks=[]
    vendors={r['REPORT_DATE'][:10]:r for r in DATA['vendor']}
    fields={'revenue':'TOTALOPERATEREVE','profit':'PARENTNETPROFIT','core':'KCFJCXSYJLR','cfo':'NETCASH_OPERATE_PK'}
    dates={'2023':'2023-12-31','2024':'2024-12-31','2025':'2025-12-31','2025H1':'2025-06-30','2026H1':'2026-06-30','2025YTD':'2025-09-30','2026YTD':'2026-09-30'}
    log=io.StringIO()
    with contextlib.redirect_stdout(log):
        assert rigor.verify_market_cap(PRICE,SHARES,D(DATA['quote']['reported_market_cap_yi'])*Y,'CNY')
        rigor.verify_valuation(PRICE,market['eps_ttm'],market['bvps'],dividend=D('1.47'))
        for period,date in dates.items():
            for key,field in fields.items():
                a,bv=fin[period][key],D(vendors[date][field])
                result=rigor.cross_validate(period+':'+key,{'issuer':a,'Eastmoney':bv},'CNY yuan',1.0)
                checks.append({'period':period,'metric':key,'primary':a,'secondary':bv,'exact':a==bv,'pass':result['all_consistent']})
        for year,row in DATA['annual'].items():
            for key,field in [('revenue','TOTALOPERATEREVE'),('profit','PARENTNETPROFIT'),('deducted_profit','KCFJCXSYJLR'),('cfo','NETCASH_OPERATE_PK')]:
                a,bv=D(row[key]),D(vendors[year+'-12-31'][field])
                documented=year=='2021' and key=='profit' and bv==D(row['profit_original'])
                assert a==bv or documented
                result=rigor.cross_validate(year+':'+key,{'restated_issuer':a,'Eastmoney':bv},'CNY yuan',1.0)
                checks.append({'period':year,'metric':key,'primary':a,'secondary':bv,'exact':a==bv,'documented_restatement_difference':documented,'pass':result['all_consistent']})
        balance_fields={'cash':'MONETARYFUNDS','trading_financial_assets':'TRADE_FINASSET_NOTFVTPL','noncurrent_financial_assets':'OTHER_NONCURRENT_FINASSET','long_equity_investments':'LONG_EQUITY_INVEST','inventory':'INVENTORY','contract_liabilities':'CONTRACT_LIAB','short_debt':'SHORT_LOAN','long_debt':'LONG_LOAN','current_noncurrent_debt':'NONCURRENT_LIAB_1YEAR','lease_liability':'LEASE_LIAB','parent_equity':'TOTAL_PARENT_EQUITY'}
        assert DATA['vendor_balance']['REPORT_DATE'].startswith('2026-09-30')
        for key,field in balance_fields.items():
            a,bv=bal['2026Q3'][key],D(DATA['vendor_balance'][field])
            result=rigor.cross_validate('2026Q3 balance:'+key,{'issuer':a,'Eastmoney_balance':bv},'CNY yuan',1.0)
            checks.append({'period':'2026Q3 balance','metric':key,'primary':a,'secondary':bv,'exact':a==bv,'pass':result['all_consistent']})
    audit=subprocess.run([sys.executable,str(ROOT/'tools/terminal_value.py'),'audit','--currency','CNY','--r','.08','--roic','.15','--g','0,.01,.02','--rf','.017','--beta','1','--discrete-risks','品牌失速:情景,资本配置损失:情景,重大监管变化:未建模'],capture_output=True,text=True,encoding='utf-8')
    (HERE/'terminal-audit.txt').write_text(clean_log(audit.stdout+audit.stderr),encoding='utf-8')
    assert audit.returncode==0
    whole={}
    for name,spec in DATA['whole_equity_scenarios'].items():
        profits=extend(spec)
        dividends=[p*Y/SHARES*(D(1) if i==0 else D('.8')) for i,p in enumerate(profits)]
        e3=profits[2]*Y/SHARES
        f3=dividends[:2]+[dividends[2]+e3*D(spec['pe3'])]
        curve=[]
        for r in map(D,('.06','.07','.08','.09','.10')):
            g,roic=D(spec['g']),D(spec['roic'])
            pe=(1-g/roic)/(r-g)
            exit_price=profits[-1]*Y/SHARES*(1+g)*pe
            flows=dividends[:-1]+[dividends[-1]+exit_price]
            actual=irr(PRICE,flows)
            assert abs(pv(flows,actual)-PRICE)<D('1e-25')
            curve.append({'r':r,'g':g,'spread':r-g,'valid_spread':r-g>=D('.05'),'in_CNY_band':r<=D('.09'),'pe_forward':pe,'exit_price':exit_price,'pv_per_share':pv(flows,r),'irr_pct':actual*100,'covers_r':actual>=r})
        pe10=(1-D(spec['g'])/D(spec['roic']))/(D('.10')-D(spec['g']))
        terminal10=profits[-1]*Y/SHARES*(1+D(spec['g']))*pe10
        approximate=(float(terminal10/PRICE)**.1-1)*100
        single={'roic':float(D(spec['roic'])),'g':(float(D(spec['g'])),)*3,'p':(1.,0.,0.),'irr10':(approximate,)*3,'k':0.}
        whole[name]={'profit_path_yi':profits,'dividends':dividends,'year3_exit_price':e3*D(spec['pe3']),'year3_irr_pct':irr(PRICE,f3)*100,'year3_pv8':pv(f3,D('.08')),'curve':curve,'conditional_terminal_only_flip':{str(delta):terminal.flip_analysis(single,.08,delta=delta,band=terminal.CURRENCY_BANDS['CNY']) for delta in (.02,.01)}}
        with contextlib.redirect_stdout(log):
            print('Endpoint check only: EPS input below is assumed year3 EPS, not current TTM.')
            rigor.three_scenario_valuation(PRICE,e3,SHARES/Y,D(0),D(0),D(0),D(spec['pe3']),D(spec['pe3']),D(spec['pe3']),3,'CNY')
    core={}
    for name,spec in DATA['core_dcf_scenarios'].items():
        profits=extend(spec)
        # A conversion ratio below 100% must not make a loss look safer.
        # Loss years assume the full loss is a cash outflow; no invented release.
        cash=[p if p<0 else p*D(spec['cash_conversion']) for p in profits]
        curve=[]
        for r in map(D,('.06','.07','.08','.09','.10')):
            g,roic=D(spec['g']),D(spec['roic'])
            pe=(1-g/roic)/(r-g)
            terminal_value=profits[-1]*(1+g)*pe
            operating_pv=pv(cash,r)+terminal_value/(1+r)**10
            a=D(spec['net_financial_asset_yi'])
            unchanged_terminal=profits[-1]*(1+g)*D(spec['cash_conversion'])/(r-g)
            unchanged_pv=pv(cash,r)+unchanged_terminal/(1+r)**10+a
            value=(operating_pv+a)*Y/SHARES
            curve.append({'r':r,'spread':r-g,'valid_spread':r-g>=D('.05'),'in_CNY_band':r<=D('.09'),'forward_terminal_pe':pe,'operating_pv_yi':operating_pv,'net_asset_value_A_yi':a,'total_equity_value_yi':operating_pv+a,'value_per_share':value,'value_gap_to_price_pct':(value/PRICE-1)*100,'margin_of_safety_pct':(value-PRICE)/value*100,'price_at_20pct_discount':value*D('.8'),'terminal_cash_conversion':1-g/roic,'terminal_conversion_unchanged_value_per_share':unchanged_pv*Y/SHARES,'terminal_share_of_operating_pv_pct':terminal_value/(1+r)**10/operating_pv*100})
        core[name]={'profit_path_yi':profits,'operating_cash_path_yi':cash,'cash_conversion':spec['cash_conversion'],'g':spec['g'],'incremental_roic':spec['roic'],'curve':curve}
    cap=market['market_cap_yi']
    reverse=[{'A_yi':a,'multiple':m,'required_pure_operating_profit_yi':(cap-a)/m} for a in map(D,('0','100','150','180')) for m in map(D,('12','16','20'))]
    base=next(x for x in core['recovery']['curve'] if x['r']==D('.08'))
    scale=(cap-D(150))/base['operating_pv_yi']
    asset_delay=[{'years':n,'present_value_yi':D(150)/D('1.08')**n,'per_share':D(150)/D('1.08')**n*Y/SHARES} for n in (0,5,10)]
    asset_grid=[{'A_yi':a,'profit_yi':p,'multiple':D(16),'price':(a+p*D(16))*Y/SHARES} for a in map(D,('100','150','180')) for p in map(D,('15','20','25','30'))]
    tests={'two_quote_prices':PRICE==D(DATA['quote']['sina_price']),'quote_total_shares':SHARES==D(vendors['2026-09-30']['TOTAL_SHARE']),'59_cross_checks':len(checks)==59 and all(x['pass'] for x in checks),'58_exact_one_documented':sum(x['exact'] for x in checks)==58,'cash_not_inventory':liquidity['cash_and_trading_net_yi']<liquidity['financial_pool_book_net_yi'],'core_model_has_negative_first_year':core['stress']['operating_cash_path_yi'][0]<0,'quarter_profit_check':fin['2026Q3']['profit']==D(DATA['primary_quarter_checks']['2026Q3']['profit']),'quarter_revenue_check':fin['2026Q3']['revenue']==D(DATA['primary_quarter_checks']['2026Q3']['revenue']),'ttm_not_annualized':ttm['profit']!=fin['2026YTD']['profit']*4/3}
    tests['sotp_adds_only_net_A']=all(abs(row['total_equity_value_yi']-row['operating_pv_yi']-row['net_asset_value_A_yi'])<D('1e-30') for case in core.values() for row in case['curve'])
    tests['whole_equity_exit_has_no_extra_asset']=all(abs(row['exit_price']-case['profit_path_yi'][-1]*Y/SHARES*(1+row['g'])*row['pe_forward'])<D('1e-30') for case in whole.values() for row in case['curve'])
    tests['asset_delay_reduces_PV']=asset_delay[0]['present_value_yi']>asset_delay[1]['present_value_yi']>asset_delay[2]['present_value_yi']
    tests['no_terminal_conversion_improvement_reduces_value']=all(row['terminal_conversion_unchanged_value_per_share']<=row['value_per_share'] for case in core.values() for row in case['curve'])
    assert all(tests.values())
    result={'cutoff':DATA['cutoff'],'market':market,'liquidity':liquidity,'annual_derived':annual_derived,'five_year_totals_yi':totals,'auxiliary':auxiliary,'ttm':{k:v/Y for k,v in ttm.items()},'quarter_yi':{p:{k:v/Y for k,v in row.items()} for p,row in fin.items() if p.endswith('Q3')},'whole_equity':whole,'core_dcf':core,'reverse_operating_profit':reverse,'static_A_E_grid':asset_grid,'asset_release_delay_no_extra_income':asset_delay,'reverse_core_base_scaling':{'scale':scale,'required_year1_yi':core['recovery']['profit_path_yi'][0]*scale,'required_year5_yi':core['recovery']['profit_path_yi'][4]*scale,'required_year10_yi':core['recovery']['profit_path_yi'][9]*scale},'tests':tests,'boundaries':DATA['model_boundaries']}
    write('results.json',result)
    write('cross-checks.json',checks)
    write('tests.json',tests)
    (HERE/'financial-rigor.txt').write_text(clean_log(log.getvalue()),encoding='utf-8')
    print(json.dumps({'market':market,'liquidity':liquidity,'core_at8':{n:next(x for x in case['curve'] if x['r']==D('.08')) for n,case in core.items()},'reverse_base':result['reverse_core_base_scaling'],'tests':tests},ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
