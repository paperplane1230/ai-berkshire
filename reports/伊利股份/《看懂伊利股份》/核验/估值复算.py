"""Offline reader calculator. Currency CNY. Calendar 2027 is the first full model year."""
import contextlib, io, json, os, subprocess, sys
from decimal import Decimal as D
from pathlib import Path

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'tools'))
import financial_rigor as F
import terminal_value as T
DATA=json.loads((HERE/'财务与模型输入.json').read_text(encoding='utf-8'))
H=D('1e8'); R=D(DATA['assumptions']['r_CNY']); ROIC=D(DATA['assumptions']['incremental_return'])
PRICE=D(DATA['quotes']['qq']['price']); SH=D(DATA['shares_filing']); CAP=PRICE*SH
FLOOR=D(DATA['assumptions']['payout_floor_2027']); MINP=D(DATA['assumptions']['policy_min_fraction_2027'])
FY=DATA['annual']['2025']['income']; I=DATA['interims']; B=DATA['balance']['2026q3']
def ttm(key,annual):return D(FY[annual])+D(I['2026ytd'][key])-D(I['2025ytd'][key])
E=ttm('profit','归属于上市公司股东的净利润')/SH
DE=ttm('deduct','归属于上市公司股东的扣除非经常性损益的净利润')/SH
FCF=ttm('ocf','经营活动产生的现金流量净额')-ttm('capex','购建固定资产、无形资产和其他长期资产支付的现金')
def pv(flows,r):return sum(v/(1+r)**t for t,v in enumerate(flows,1))
def solve(fn,target,lo,hi,increasing=True):
    assert min(fn(lo),fn(hi))<=target<=max(fn(lo),fn(hi))
    for _ in range(110):
        mid=(lo+hi)/2
        if (fn(mid)<target)==increasing:lo=mid
        else:hi=mid
    assert abs(fn(mid)-target)<D('0.000001'); return mid
def irr(flows):return 100*solve(lambda r:pv(flows,r),PRICE,D('-.4'),D('1'),False)
def timeline(case,start=E,r=R,permanent_payout=False,policy=True):
    a,b,p,g,pe=map(D,case)
    profits=[start*(1+a)**min(n,3)*(1+b)**max(0,n-3) for n in range(1,11)]
    dividends=[eps*p for eps in profits]
    if policy:dividends[0]=max(dividends[0],profits[0]*MINP,FLOOR)
    c3=dividends[:3]; c3[-1]+=profits[2]*pe
    if r<=g or ROIC<=g:raise ValueError('Invalid perpetual-growth assumptions')
    multiple=(p if permanent_payout else 1-g/ROIC)/(r-g)
    if not permanent_payout:assert abs(D(str(T.exit_pe(float(ROIC),float(g),float(r))[0]))-multiple)<D('1e-10')
    terminal=profits[-1]*(1+g)*multiple; c10=dividends.copy(); c10[-1]+=terminal
    return dict(eps=profits,dividends=dividends,terminalPE=multiple,exit3=profits[2]*pe,exit10=terminal,flows3=c3,flows10=c10)
def fmt(x):return str(x.quantize(D('.01')))
def show(obj):return {k:fmt(v) for k,v in obj.items()}
def run():
    assert PRICE==D(DATA['quotes']['sina']['price']) and SH==D(DATA['quotes']['qq']['shares'])
    assert abs(CAP/H-D(DATA['quotes']['qq']['cap_yi']))<D('.006')
    scenarios={}; sens={}; model=DATA['cases']; base=model['经营改善']; raw=timeline(base)
    for tag,case in model.items():
        c=timeline(case); dr=c['dividends']; f3=c['flows3']; f10=c['flows10']
        scenarios[tag]=show(dict(eps3=c['eps'][2],dps1=dr[0],dps3total=sum(dr[:3]),exit3=c['exit3'],pv3=pv(f3,R),irr3=irr(f3),eps10=c['eps'][-1],pe10=c['terminalPE'],pv10=pv(f10,R),irr10=irr(f10),terminalPVshare=c['exit10']/(1+R)**10/pv(f10,R)*100))
        sens[tag]={}
        for rt in map(D,['.06','.07','.08','.09','.10']):
            c=timeline(case,r=rt); f=c['flows10']; n=irr(f); spread=rt-D(case[3]);sens[tag][fmt(rt*100)]={'irr':fmt(n),'pv':fmt(pv(f,rt)),'pe':fmt(c['terminalPE']),'spread_pp':fmt(spread*100),'spread_ok':spread>=D('.05'),'currency_band':rt<=D('.09'),'meets_r':n>=100*rt}
    cg=solve(lambda a:pv(timeline([a,*base[1:]])['flows10'],R),PRICE,D('-.1'),D('.5')); z=timeline(base,permanent_payout=True)
    rv=solve(lambda eps:pv(timeline(base,start=eps)['flows10'],R),PRICE,D('.5'),D('5'))
    exitpe=(PRICE*(1+R)**3-sum(raw['dividends'][n]*(1+R)**(2-n) for n in range(3)))/raw['eps'][2]
    log=io.StringIO()
    with contextlib.redirect_stdout(log):
        assert F.verify_market_cap(PRICE,SH,D(DATA['quotes']['qq']['cap_yi'])*H,'CNY')
        F.verify_valuation(PRICE,E,D(B['equity'])/SH,FCF/SH,D(DATA['dividend_FY2025']),ttm('revenue','营业收入')/SH)
        F.three_scenario_valuation(PRICE,E,SH/H,'.10','.06','0',20,16,13,3,'CNY')
        for pair in json.loads((HERE/'财务双渠道对照.json').read_text(encoding='utf-8')):
            assert D(pair['filing_yuan'])==D(pair['vendor_yuan']); F.cross_validate(pair['field'],{'公司定期报告':pair['filing_yuan'],'东方财富':pair['vendor_yuan']},'元',1)
    (HERE/'严谨性工具输出.txt').write_text('\n'.join(s.rstrip() for s in log.getvalue().splitlines()).rstrip()+'\n',encoding='utf8')
    audit=subprocess.run([sys.executable,str(ROOT/'tools/terminal_value.py'),'audit','--currency','CNY','--r','.08','--roic','.14','--g','0,.01,.02','--rf','.017','--beta','1','--discrete-risks','食品安全:未建模,澳优持续亏损:情景,渠道让价:情景'],encoding='utf8',capture_output=True,check=True,env={**os.environ,'PYTHONUTF8':'1'})
    (HERE/'终值口径检查.txt').write_text('\n'.join(line.rstrip() for line in audit.stdout.strip().splitlines())+'\n',encoding='utf8')
    snap=dict(price=PRICE,cap_yi=CAP/H,ttm_profit=E*SH/H,ttm_deduct=DE*SH/H,eps=E,deductEPS=DE,pe=PRICE/E,deductPE=PRICE/DE,divyield=D(DATA['dividend_FY2025'])/PRICE*100,ttmFCF=FCF/H,ttmFCFyield=FCF/CAP*100,pb=CAP/D(B['equity']),ttmRevenue=ttm('revenue','营业收入')/H,ps=CAP/ttm('revenue','营业收入'))
    alt=dict(implied_growth_first3=cg*100,implied_normal_eps=rv,implied_normal_profit=rv*SH/H,required_pe3=exitpe,base_fixed_payout_pv=pv(z['flows10'],R),base_fixed_payout_irr=irr(z['flows10']),base_deduct_pv=pv(timeline(base,start=DE)['flows10'],R),stress_without_policy=pv(timeline(model['压力'],policy=False)['flows10'],R))
    normalized=D(FY['归属于上市公司股东的净利润'])/SH; restored=timeline(base,start=normalized)
    alt.update(FY25EPS=normalized,FY25StartingPV=pv(restored['flows10'],R),FY25StartingIRR=irr(restored['flows10']),baseMargin20=pv(raw['flows10'],R)*D('.80'),min75ForwardReturn=D(base[0])/(1-D(base[2]))*100,implied_eps3=E*(1+cg)**3,implied_profit3=E*SH/H*(1+cg)**3,static_fy25_pe=PRICE/normalized)
    ladder=[]
    for t in (1,2,3,5,10):ladder.append({'year':t,'eps':fmt(raw['eps'][t-1]),'dividends':fmt(raw['dividends'][t-1]),'dividend_pv':fmt(raw['dividends'][t-1]/(1+R)**t)})
    alt.update(baseAt8DividendPV=pv(raw['dividends'],R),baseAt8TerminalPV=raw['exit10']/(1+R)**10,baseExit10=raw['exit10'],baseExit3PV=raw['exit3']/(1+R)**3,baseDPS3PV=pv(raw['dividends'][:3],R),baseExtraInterimIllustrativePV=D('.42')/(1+R)**(D(1)/12))
    out={'snapshot':show(snap),'scenarios':scenarios,'sensitivity':sens,'reverse_and_alternatives':show(alt),'base_cash_ladder':ladder}; (HERE/'估值结果.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return out
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
