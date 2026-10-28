"""Public NARI research arithmetic. No portfolio access, orders or networking."""
import contextlib
import io
import json
import re
import subprocess
import sys
from decimal import getcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import financial_rigor as rigor
import terminal_value as terminal

D = rigor.exact
getcontext().prec = 36

def decmap(o):
    return {k:D(v) for k,v in o.items()}

def pct(n,o):
    return (n/o-1)*100

def irr(cfs):
    lo, hi = D("-.95"), D("3")
    for _ in range(180):
        r=(lo+hi)/2
        value=sum(v/(1+r)**t for t,v in enumerate(cfs))
        if value>0: lo=r
        else: hi=r
    return (lo+hi)/2

def clean(s):
    plain = re.sub(r"\x1b\[[0-9;]*m", "", s)
    return "\n".join(line.rstrip() for line in plain.splitlines()).strip()+"\n"

def main():
    x=json.loads((HERE/"inputs.json").read_text(encoding="utf-8"))
    price,shares=D(x["price"]),D(x["shares"])
    mcap=price*shares
    n,o,h,oh=map(decmap,[x["ytd_2026q3"],x["ytd_2025q3"],x["h1_2026"],x["h1_2025"]])
    annual={y:decmap(v) for y,v in x["annual"].items()}
    a=annual["2025"]
    ttm={k:a[k]+n[k]-o[k] for k in ("revenue","profit","adjusted_profit","ocf","capex")}
    ttm["fcf"]=ttm["ocf"]-ttm["capex"]
    qn={k:n[k]-h[k] for k in h if k in n}
    qo={k:o[k]-oh[k] for k in oh if k in o}
    def operating(z):
        return {"gross_margin_pct":(1-z["cost"]/z["revenue"])*100,"net_margin_pct":z["profit"]/z["revenue"]*100,"operating_margin_pct":z["operating_profit"]/z["revenue"]*100,"ocf_profit_ratio":z["ocf"]/z["profit"],"fcf":z["ocf"]-z["capex"]}
    eps=ttm["adjusted_profit"]/shares
    metrics={"market_cap":mcap,"eps_ttm":ttm["profit"]/shares,"eps_adjusted_ttm":eps,"pe_ttm":mcap/ttm["profit"],"pe_adjusted_ttm":mcap/ttm["adjusted_profit"],"pe_2025":mcap/a["profit"],"ps_ttm":mcap/ttm["revenue"],"pb":mcap/n["equity_parent"],"bvps":n["equity_parent"]/shares,"fcf_yield_pct":ttm["fcf"]/mcap*100,"dividend_yield_pct":D(x["dividend_2025_per_share"])/price*100,"cash_plus_trading":n["cash"]+n["trading_assets"],"known_debt_incl_lease":n["short_debt"]+n["long_debt"]+n["current_noncurrent_liabilities"]+n["lease_noncurrent"],"ar_start_growth_pct":pct(n["ar"],a["ar"]),"inventory_start_growth_pct":pct(n["inventory"],a["inventory"]),"ap_start_growth_pct":pct(n["ap"],a["ap"]),"contract_asset_start_growth_pct":pct(n["contract_assets"],a["contract_assets"]),"contract_liability_start_growth_pct":pct(n["contract_liabilities"],a["contract_liabilities"]),"ar_days_273_proxy":(n["ar"]+a["ar"])/2/n["revenue"]*273,"inventory_days_273_proxy":(n["inventory"]+a["inventory"])/2/n["cost"]*273,"q4_2025_profit_share_pct":(a["profit"]-o["profit"])/a["profit"]*100,"q4_2025_ocf_share_pct":(a["ocf"]-o["ocf"])/a["ocf"]*100}
    metrics["net_cash_reference"]=metrics["cash_plus_trading"]-metrics["known_debt_incl_lease"]
    metrics["ev_revenue_reference"]=(mcap+D(x["minority_equity_q3"])-metrics["net_cash_reference"])/ttm["revenue"]
    bridge={k:(n[k]-o[k])*s for k,s in [("cash_received",1),("tax_refund",1),("other_inflow",1),("purchase_cash",-1),("staff_cash",-1),("tax_cash",-1),("other_outflow",-1)]}
    assert sum(bridge.values())==n["ocf"]-o["ocf"]
    products={}
    for period,total in [("products_2025",a["revenue"]),("products_h1_2026",h["revenue"])]:
        products[period]={}
        for name,raw in x[period].items():
            v=decmap(raw)
            products[period][name]={"share_pct":v["revenue"]/total*100,"gross_margin_pct":(1-v["cost"]/v["revenue"])*100}
        assert sum(D(v["revenue"]) for v in x[period].values())==total
    three=[]
    for s in x["three_year_assumptions"]:
        growth,pe,payout=map(D,[s["growth"],s["pe"],s["payout"]])
        future_eps=eps*(1+growth)**3
        target=future_eps*pe
        divs=[eps*(1+growth)**y*payout for y in range(1,4)]
        cfs=[-price]+divs
        cfs[-1]+=target
        three.append({**s,"eps_year3":future_eps,"price_year3":target,"dividends_total":sum(divs),"price_return_pct":pct(target,price),"cashflow_irr_pct":irr(cfs)*100,"pv_price_at_8pct":sum(cf/D("1.08")**y for y,cf in enumerate(cfs) if y>0)})
    l=x["ten_year_assumptions"]
    r,roic,payout=map(D,[l["r"],l["roic"],l["payout"]])
    profit=ttm["adjusted_profit"]
    k=profit*payout/mcap
    def longvalue(s,discount):
        growth,g=map(D,[s["growth"],s["terminal_g"]])
        pe=(1-g/roic)/(discount-g)
        p10=profit*(1+growth)**10
        p11=p10*(1+g)
        tv=p11*pe
        cfs=[-mcap]+[profit*(1+growth)**y*payout for y in range(1,11)]
        cfs[-1]+=tv
        pv=sum(cf/(1+discount)**y for y,cf in enumerate(cfs) if y>0)
        approx=terminal.irr_from_terminal(float(p10),float(mcap),float(pe),payout=float(k))*100
        return {**s,"exit_forward_pe":pe,"profit_year10":p10,"profit_year11":p11,"terminal_market_cap":tv,"cashflow_irr_pct":irr(cfs)*100,"pv_price":pv/shares,"toolkit_approx_irr_pct":approx,"spread_pp":(discount-g)*100,"terminal_pv_share_pct":tv/(1+discount)**10/pv*100}
    ten=[longvalue(s,r) for s in l["scenarios"]]
    assert sum(D(s["probability"]) for s in ten)==1
    spec={"roic":float(roic),"g":[float(D(s["terminal_g"])) for s in ten],"p":[float(D(s["probability"])) for s in ten],"irr10":[longvalue(s,D(".10"))["toolkit_approx_irr_pct"] for s in ten],"k":float(k)}
    sensitivity=[]
    for rate in map(D,[".06",".07",".08",".09",".10"]):
        values=[longvalue(s,rate) for s in l["scenarios"]]
        weighted=sum(D(s["probability"])*s["cashflow_irr_pct"] for s in values)
        sensitivity.append({"r":rate,"weighted_cashflow_irr_pct":weighted,"covers_hurdle":weighted>=rate*100,"currency_band_valid":D(".06")<=rate<=D(".09"),"all_spreads_valid":all(s["spread_pp"]>=5 for s in values),"spreads_pp":[s["spread_pp"] for s in values]})
    lo,hi=D("-.10"),D(".30")
    for _ in range(160):
        mid=(lo+hi)/2
        pv=longvalue({"growth":str(mid),"terminal_g":".01","name":"reverse","probability":"1"},r)["pv_price"]
        if pv<price:lo=mid
        else:hi=mid
    result={"metrics":metrics,"ttm":ttm,"q3_current":qn,"q3_prior":qo,"cashflow_bridge":bridge,"products":products,"period_metrics":{label:operating(z) for label,z in [("ytd2026",n),("ytd2025",o),("h1_2026",h),("h1_2025",oh),("q3_2026",qn),("q3_2025",qo)]},"growth_ytd_pct":{v:pct(n[v],o[v]) for v in h if v in n and v in o and o[v]!=0},"growth_q3_pct":{v:pct(qn[v],qo[v]) for v in qn if v in qo and qo[v]!=0},"annual_derived":{y:{"net_margin_pct":v["profit"]/v["revenue"]*100,"ocf_profit_ratio":v["ocf"]/v["profit"]} for y,v in annual.items()},"three_year":three,"ten_year":ten,"sensitivity":sensitivity,"weighted_ten_irr_pct":sum(D(s["probability"])*s["cashflow_irr_pct"] for s in ten),"weighted_ten_pv":sum(D(s["probability"])*s["pv_price"] for s in ten),"reverse_growth_pct":(lo+hi)/2*100}
    (HERE/"results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    (HERE/"terminal-config.json").write_text(json.dumps({"国电南瑞":spec},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    log=io.StringIO()
    with contextlib.redirect_stdout(log):
        rigor.verify_market_cap(price,shares,D(x["reported_market_cap"]),"CNY")
        rigor.verify_valuation(price,eps=ttm["profit"]/shares,bvps=metrics["bvps"],fcf_per_share=ttm["fcf"]/shares,dividend=D(x["dividend_2025_per_share"]))
        for label,a1,b1 in [("2025收入",a["revenue"],"66229000000"),("2025归母",a["profit"],"8279000000"),("2025CFO",a["ocf"],"12769000000"),("2026Q3累计收入",n["revenue"],"43880000000"),("2026Q3累计归母",n["profit"],"4912000000"),("2026Q3累计扣非",n["adjusted_profit"],"4705000000"),("2026Q3累计CFO",n["ocf"],"-2920000000")]:
            rigor.cross_validate(label,{"公司原件":a1,"独立刊发媒体":D(b1)},"CNY",tolerance_pct=1)
        rigor.cross_validate("最新股本",{"公司Q3":shares,"行情":D(x["shares_quote"])},"股",tolerance_pct=1)
        rigor.cross_validate("收盘价",{"腾讯":price,"新浪":D(x["price_second"])},"CNY",tolerance_pct=1)
        print("Cash and note details have issuer-only underlying evidence. Mirrors are not independent financial audit.")
        rigor.three_scenario_valuation(price,eps,shares/D("1e8"),D(".12"),D(".07"),D("-.02"),28,22,18,years=3,currency="CNY")
    (HERE/"financial-rigor.txt").write_text(clean(log.getvalue()),encoding="utf-8")
    cmds={"terminal-audit.txt":["audit","--currency","CNY","--r",str(r),"--roic",str(roic),"--g","0,0.01,0.02","--rf",l["rf_reference"],"--beta","1","--discrete-risks",l["discrete_risks"]]}
    for delta in ["0.02","0.01"]:
        cmds["terminal-flip-"+delta+".txt"]=["flip","--config",str(HERE/"terminal-config.json"),"--name","国电南瑞","--r",str(r),"--delta",delta,"--currency","CNY","--g-shift","0","--rf",l["rf_reference"]]
    for file,args in cmds.items():
        p=subprocess.run([sys.executable,str(ROOT/"tools/terminal_value.py"),*args],capture_output=True,text=True,encoding="utf-8")
        (HERE/file).write_text(clean(p.stdout+p.stderr),encoding="utf-8")
        if p.returncode:raise RuntimeError(file+" failed")
    print(json.dumps({k:result[k] for k in ["metrics","ttm","three_year","ten_year","sensitivity","reverse_growth_pct"]},ensure_ascii=False,indent=2,default=str))

if __name__=="__main__":
    main()
