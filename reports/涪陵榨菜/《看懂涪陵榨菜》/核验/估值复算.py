"""Offline, CNY and fiscal-year cash-flow conventions are explained in 核验/README.md."""
import contextlib, io, json, os, re, subprocess, sys
from decimal import Decimal as D
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[3];sys.path.insert(0,str(ROOT/'tools'))
import financial_rigor as F
import terminal_value as T
def read(name):return json.loads((HERE/name).read_text(encoding='utf8'))
def save(name,data):(HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf8')
def clean(s):return '\n'.join(l.rstrip() for l in re.sub(r'\x1b\[[0-9;]*m','',s).strip().splitlines())+'\n'
I=read('输入.json'); K=I['assumptions']; H=D('1e8'); sh=D(I['market']['shares']); p=D(I['market']['price_qq']);cap=p*sh
A=I['annual']['2025']; Y=I['ytd_2026q3']; O=I['ytd_2025q3'];B=I['h1_2026'];OB=I['h1_2025'];r=D(K['r']);roic=D(K['terminal_incremental_return']); payout=D(K['payout']); div=D(I['interim']); shares_yi=sh/H
def ttm(k):return D(A[k])+D(Y[k])-D(O[k])
eps=ttm('adjusted_profit')/sh; fin=(D(Y['cash'])+D(Y['trading_assets'])-D(Y['bank_debt'])-D(Y['lease_current'])-D(Y['lease_noncurrent']))/H; core=(ttm('adjusted_profit')-ttm('interest_income')*(1-D(K['interest_tax'])))/H
def pv(cf,r):return sum(f/(1+r)**n for n,f in enumerate(cf,1))
def root(f,target,a,b,up=True):
    assert min(f(a),f(b))<target<max(f(a),f(b))
    for _ in range(120):
        mid=(a+b)/2
        if (f(mid)<target)==up:a=mid
        else:b=mid
    assert abs(f(mid)-target)<D('1e-8');return mid
def irr(cf):return 100*root(lambda k:pv(cf,k),p,D('-.6'),D('.8'),False)
def path(h,eg,g,disc,fixed=None,keep=False):
    es=[eps*(1+eg)**n for n in range(1,h+1)];d=[v*payout for v in es]
    if fixed is not None:multiple=fixed;exit_price=es[-1]*multiple
    else:
        multiple=(payout if keep else 1-g/roic)/(disc-g);exit_price=es[-1]*(1+g)*multiple
        if not keep:assert abs(float(multiple)-T.exit_pe(float(roic),float(g),float(disc))[0])<1e-7
    cf=d.copy();cf[-1]+=exit_price
    return dict(cash=cf,dividends=d,eps=es,multiple=multiple,exit=exit_price,divPV=pv(d,disc),termPV=exit_price/(1+disc)**h,pv=pv(cf,disc),irr=irr(cf))
def rnd(v):return str(v.quantize(D('.01')))
def summary(x):return {k:rnd(v) for k,v in x.items()}
def run():
    last=read('估值历史与横比.json')['sample_rows'][-1];assert p==D(I['market']['price_sina'])==D(last['CLOSE_PRICE']);assert cap==D(last['TOTAL_MARKET_CAP']); assert abs(cap/H-D(I['market']['market_cap_qq_yi']))<D('.0051')
    hist=read('估值历史与横比.json'); facts=read('财务对照.json')['items']; assert len(facts)==65 and all(D(a)==D(b) for _,_,a,b,_ in facts)
    cashflow=ttm('ocf')-ttm('capex'); buf=io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert F.verify_market_cap(p,sh,D(I['market']['market_cap_qq_yi'])*H,'CNY');F.verify_valuation(p,ttm('profit')/sh,D(Y['equity_parent'])/sh,cashflow/sh,D(I['historical_dividend_per_share']),ttm('revenue')/sh)
        F.three_scenario_valuation(p,eps,shares_yi,'.07','.03','-.03',22,18,14,years=3,currency='CNY')
        for date,name,a,b,_ in facts:F.cross_validate(date+' '+name,{'公司披露':a,'东方财富':b},'元',1)
    (HERE/'财务工具输出.txt').write_text(clean(buf.getvalue()),encoding='utf8')
    args=['audit','--currency','CNY','--r',str(r),'--roic',str(roic),'--g','0,.01,.02','--rf','.017','--beta','1','--discrete-risks','基地回报不及预期:情景,费用侵蚀:情景,食品安全:未建模']
    def cli(a):return subprocess.run([sys.executable,str(ROOT/'tools/terminal_value.py'),*a],capture_output=True,encoding='utf8',env={**os.environ,'PYTHONUTF8':'1'},check=True).stdout
    txt=cli(args);k=payout*eps/p; anchor=T.irr_from_terminal(float(eps*D('1.03')**10),float(p),T.exit_pe(.15,.01,.1)[0],10,float(k))*100
    for delta in ('.02','.01'):
        txt+=cli(['flip','--name','温和条件（各列相同，仅口径对照）','--currency','CNY','--r','.08','--delta',delta,'--roic','.15','--g','.01,.01,.01','--p','0,1,0','--irr10='+','.join([str(anchor)]*3),'--k',str(k),'--g-shift','0','--rf','.017'])
    (HERE/'终值工具输出.txt').write_text(clean(txt),encoding='utf8')
    snap=summary(dict(price=p,cap=cap/H,profit=ttm('profit')/H,deduct=ttm('adjusted_profit')/H,deductEPS=eps,PE=cap/ttm('profit'),deductPE=p/eps,hist_yield=100*D('.42')/p,OCF=ttm('ocf')/H,capex=ttm('capex')/H,fcf=cashflow/H,fcfYield=100*cashflow/cap,PB=cap/D(Y['equity_parent']),ps=cap/ttm('revenue'),intTTM=ttm('interest_income')/H,core=core,net_fin=fin,financial_assets_per_share=fin/shares_yi,hist_pct=100*D(hist['le_current'])/hist['count'],static_pe=cap/D(A['profit'])))
    cases={};sens={}
    for label,par in I['scenarios'].items():
        a,m,b,g=map(D,par); z3=path(3,a,g,r,m);z10=path(10,b,g,r);sens[label]={}
        cases[label]=summary(dict(eps3=z3['eps'][-1],eps10=z10['eps'][-1],dps3=sum(z3['dividends']),exit3=z3['exit'],pv3=z3['pv'],irr3=z3['irr'],pe10=z10['multiple'],exit10=z10['exit'],pv10=z10['pv'],irr10=z10['irr'],divPV10=z10['divPV'],termPV10=z10['termPV'],termShare=z10['termPV']/z10['pv']*100))
        for rate in map(D,('.06','.07','.08','.09','.10')):
            path1=path(10,b,g,rate);c=path1['cash'].copy();c[0]+=div
            sens[label][str(rate)]=dict(**summary(dict(irr=path1['irr'],pv=path1['pv'],with_interim_pv=pv(c,rate),with_interim_irr=irr(c))),in_band=rate<=D('.09'),spread_valid=rate-g>=D('.05'))
    a,m,b,g=map(D,I['scenarios']['温和改善']);z3=path(3,a,g,r,m);z10=path(10,b,g,r);alt=path(10,b,g,r,keep=True);reverse=root(lambda x:path(10,x,g,r)['pv'],p,D('-.1'),D('.25'))
    bridges=[]
    for v in map(D,K['phase2_allowances_yi']):
        pool=fin-sum(D(K[s]) for s in ('project1_and_IT_reserve_yi','working_capital_yi','safety_buffer_yi'))-v-shares_yi*div;present=pool/(1+r)**K['release_delay_years']; multiple=(cap/H-shares_yi*div-present)/core
        bridges.append(summary(dict(phase2=v,rest=pool,pvrest=present,implied_pe=multiple,price16=(16*core+present)/shares_yi+div,price14=(14*core+present)/shares_yi+div,price18=(18*core+present)/shares_yi+div)))
    add=summary(dict(rev_g=reverse*100,profit_in_ten=eps*sh/H*(1+reverse)**10,base_profit10=eps*sh/H*(1+b)**10,implied_exit_pe3=(p-z3['divPV'])*(1+r)**3/z3['eps'][-1],divPV3=z3['divPV'],termPV3=z3['termPV'],stay65PV10=alt['pv'],stay65IRR10=alt['irr'],wc_cost8_wan=D(5)*10000*r,annuity15_wan=D(5)*10000*r/(1-(1+r)**-15),delay2_wan=D(5)*10000*r*(1+r)**2/(1-(1+r)**-15),growth_on_retained=100*b/(1-payout),cash_delayed_slope=1/shares_yi/(1+r)**3,full_5_per_share=D(5)/shares_yi,div2025_payout=D('.42')*sh/D(A['profit'])*100))
    share0=sh/H; ni=ttm('profit'); ytd=lambda n:D(Y[n]); prior=lambda n:D(O[n]); h1=lambda n:D(B[n]); hp=lambda n:D(OB[n]);growth=lambda x,y:(x/y-1)*100
    operating=summary(dict(eps_total=ni/sh,EPS_adjusted=eps,ytd_profit=ytd('profit')/H,ytd_deduct=ytd('adjusted_profit')/H,ytd_rev=ytd('revenue')/H,single_profit=(ytd('profit')-h1('profit'))/H,single_deduct=(ytd('adjusted_profit')-h1('adjusted_profit'))/H,ytd_cash_growth=growth(ytd('ocf'),prior('ocf')),single_cash_growth=growth(ytd('ocf')-h1('ocf'),prior('ocf')-hp('ocf')),ytd_fcf=(ytd('ocf')-ytd('capex'))/H,trade_fin_yi=ytd('trading_assets')/H,ar_same=growth(ytd('ar'),prior('ar')),ar_year=growth(ytd('ar'),ytd('ar_start')),contra_same=growth(ytd('contract_liabilities'),prior('contract_liabilities')),gov_FY25_dps_yi=share0*D('.42'),income_yield=100*ni/cap,capex_delta=(ytd('capex')-prior('capex'))/H,OCF_sales_delta=(ytd('cash_received')-prior('cash_received'))/H,OCF_purchase_delta=(prior('purchase_cash')-ytd('purchase_cash'))/H))
    full=fin-D('24')-D('7')-D('1.5')-D('5')-div*share0
    inverse=summary(dict(full_cash_now_16=(16*core+full)/share0+div,full_cash_5yr_16=(16*core+full/(1+r)**5)/share0+div,require_fully_reserved_core_at16=(cap/H-div*share0-full/(1+r)**3)/16,base_dr3_at18=sum(z3['dividends']),moderate_exit3_preserve_nominal=(p-sum(z3['dividends']))/z3['eps'][-1],eps3=z3['eps'][-1],base_net_growth_by_volume=100*((1+b)**10-1),static_cashdeduct_PE=(cap/H-fin)/(ni/H),finshare=fin/(cap/H)*100,turnover0=(full/ share0),base_initial_div=z3['dividends'][0],no_date_pv6_gap=p-z10['pv'] if r==D('.06') else p-path(10,b,g,D('.06'))['pv'],before_capex_fcf_yield=(ttm('ocf')-ttm('capex'))*100/cap,capex_share_FY25=D(A['capex'])/D(A['ocf'])*100))
    out=dict(snapshot=snap,cases=cases,sensitivity=sens,asset_bridge=bridges,additional=add,business=operating,extra=inverse);save('复算输出.json',out);return out
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
