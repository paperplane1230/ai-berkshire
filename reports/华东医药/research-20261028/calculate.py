"""Public-source Huadong research arithmetic; no networking or portfolio access."""
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

getcontext().prec = 34
D = rigor.exact
E8 = D("1e8")

def decmap(obj):
    return {k: D(v) for k, v in obj.items()}

def pct(a, b):
    return (a / b - 1) * 100

def irr(cfs):
    lo, hi = D("-.99"), D("5")
    for _ in range(180):
        mid = (lo + hi) / 2
        npv = sum(v / (1 + mid) ** i for i, v in enumerate(cfs))
        if npv > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

def clean(s):
    plain = re.sub(r"\x1b\[[0-9;]*m", "", s)
    return "\n".join(line.rstrip() for line in plain.splitlines()).strip() + "\n"

def main():
    x = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
    price, shares = D(x["price"]), D(x["shares"])
    mcap = price * shares
    n, o, hn, ho = [decmap(x[k]) for k in ("ytd_2026q3", "ytd_2025q3", "h1_2026", "h1_2025")]
    annual = {year: decmap(v) for year, v in x["annual"].items()}
    ttm = {k: annual["2025"][k] + n[k] - o[k] for k in ("revenue", "profit", "adjusted_profit", "ocf", "capex")}
    ttm["fcf"] = ttm["ocf"] - ttm["capex"]
    qn, qo = [{k: y[k] - h[k] for k in h} for y, h in ((n, hn), (o, ho))]
    eps = ttm["adjusted_profit"] / shares
    def operating(z):
        return {"gross_margin_pct": (1-z["cost"]/z["revenue"])*100, "net_margin_pct": z["profit"]/z["revenue"]*100, "operating_margin_pct": z["operating_profit"]/z["revenue"]*100, "ocf_profit_ratio": z["ocf"]/z["profit"], "fcf": z["ocf"]-z["capex"], "selling_ratio_pct": z["selling"]/z["revenue"]*100, "rd_ratio_pct": z["rd"]/z["revenue"]*100}
    comparisons = {key: {k+"_growth_pct": pct(a[k],b[k]) for k in a if k in b and b[k] != 0} for key,a,b in (("ytd",n,o),("q3",qn,qo),("h1",hn,ho))}
    debt = n["short_debt"]+n["long_debt"]+n["current_noncurrent_debt"]+n["lease_noncurrent"]
    metrics = {"market_cap":mcap,"eps_ttm":ttm["profit"]/shares,"eps_adjusted_ttm":eps,"pe_ttm":mcap/ttm["profit"],"pe_adjusted_ttm":mcap/ttm["adjusted_profit"],"pe_2025":mcap/annual["2025"]["profit"],"pb":mcap/n["equity_parent"],"ps_ttm":mcap/ttm["revenue"],"dividend_yield_pct":D(x["historical_dividend_per_share"])/price*100,"fcf_yield_pct":ttm["fcf"]/mcap*100,"debt_reference":debt,"net_cash_reference":n["cash"]+n["trading_assets"]-debt,"liabilities_assets_pct":n["liabilities"]/n["assets"]*100,"goodwill_assets_pct":n["goodwill"]/n["assets"]*100,"goodwill_equity_pct":n["goodwill"]/n["equity_parent"]*100,"minority_profit_pct":n["minority_profit"]/(n["profit"]+n["minority_profit"])*100,"ar_growth_year_start_pct":pct(n["ar"],n["ar_start"]),"inventory_growth_year_start_pct":pct(n["inventory"],n["inventory_start"]),"ar_days_proxy":(n["ar"]+n["ar_start"])/2/n["revenue"]*273,"inventory_days_proxy":(n["inventory"]+n["inventory_start"])/2/n["cost"]*273,"development_change":n["development"]-n["development_start"],"nonrecurring_ytd":n["profit"]-n["adjusted_profit"],"nonrecurring_q3":qn["profit"]-qn["adjusted_profit"]}
    metrics["ev_revenue_reference"]=(mcap-metrics["net_cash_reference"]+n["minority_equity"])/ttm["revenue"]
    dev=decmap(x["development_h1"])
    sinclair=decmap(x["sinclair_h1_test"])
    extra={"h1_capitalization_ratio_2026_pct":dev["2026_capitalized"]/dev["2026_total"]*100,"h1_capitalization_ratio_2025_pct":dev["2025_capitalized"]/dev["2025_total"]*100,"h1_capitalized_change":dev["2026_capitalized"]-dev["2025_capitalized"],"h1_rd_total_change_pct":pct(dev["2026_total"],dev["2025_total"]),"h1_capitalization_change_after_15pct_tax":(dev["2026_capitalized"]-dev["2025_capitalized"])*D(".85"),"h1_reported_profit_change":hn["profit"]-ho["profit"],"sinclair_headroom":sinclair["recoverable"]-sinclair["carrying"],"sinclair_headroom_pct":pct(sinclair["recoverable"],sinclair["carrying"]),"lu_liang_direct_ownership_pct":D("200000")/shares*100,"controlling_ownership_pct":D("730938157")/shares*100,"controller_pledged_fraction_pct":D("144810000")/D("730938157")*100,"missed_procurement_industrial_share_pct":D("4634000000")/D("14783948709.90")*100,"industrial_profit_share_ytd_pct":D("2660000000")/n["profit"]*100,"rd_ytd_decline":o["rd"]-n["rd"],"sum_goodwill_intangible_development":n["goodwill"]+n["intangible"]+n["development"]}
    extra["sum_goodwill_intangible_development_equity_pct"]=extra["sum_goodwill_intangible_development"]/n["equity_parent"]*100
    extra["innovative_revenue_increment_ytd_approx"]=D("2528000000")-D("2528000000")/D("1.4833")
    extra["industrial_revenue_increment_ytd_approx"]=D("11617000000")-D("11617000000")/D("1.0519")
    extra["legacy_revenue_increment_ytd_proxy"]=extra["industrial_revenue_increment_ytd_approx"]-extra["innovative_revenue_increment_ytd_approx"]
    extra["goodwill_half_impairment_tail"]=n["goodwill"]*D(".5")
    extra["tail_earnings_haircut_pe15_price"]=eps*D(".7")*15
    bridge={k:(n[k]-o[k])*sign for k,sign in (("cash_received",1),("tax_refund",1),("other_inflow",1),("purchase_cash",-1),("staff_cash",-1),("tax_cash",-1),("other_outflow",-1))}
    assert sum(bridge.values()) == n["ocf"]-o["ocf"]
    segments={}
    for period,items in x["segments"].items():
        segments[period]={name:{"revenue":D(v["revenue"]),"cost":D(v["cost"]),"gross_margin_pct":(1-D(v["cost"])/D(v["revenue"]))*100} for name,v in items.items()}
    three=[]
    for s in x["three_year_assumptions"]:
        growth, pe, payout = D(s["growth"]),D(s["pe"]),D(s["payout"])
        target=eps*(1+growth)**3*pe
        divs=[eps*(1+growth)**y*payout for y in range(1,4)]
        cfs=[-price]+divs
        cfs[-1]+=target
        three.append({**s,"price_year3":target,"price_change_pct":pct(target,price),"dividends_total":sum(divs),"cashflow_irr_pct":irr(cfs)*100,"pv_price_8pct":sum(cf/D("1.08")**y for y,cf in enumerate(cfs) if y>0)})
    a=x["ten_year_assumptions"]
    r,roic,payout=D(a["r"]),D(a["roic"]),D(a["payout"])
    p0=ttm["adjusted_profit"]
    k=p0*payout/mcap
    def long_value(s,discount):
        growth,g=D(s["growth"]),D(s["terminal_g"])
        pe=(1-g/roic)/(discount-g)
        p10=p0*(1+growth)**10
        p11=p10*(1+g)
        tv=p11*pe
        cfs=[-mcap]+[p0*(1+growth)**y*payout for y in range(1,11)]
        cfs[-1]+=tv
        pv=sum(cf/(1+discount)**y for y,cf in enumerate(cfs) if y>0)
        approx=terminal.irr_from_terminal(float(p10),float(mcap),float(pe),payout=float(k))*100
        return {**s,"profit_year10":p10,"profit_year11":p11,"exit_pe":pe,"spread_pp":(discount-g)*100,"pv_price":pv/shares,"cashflow_irr_pct":irr(cfs)*100,"toolkit_approx_irr_pct":approx,"terminal_pv_weight_pct":tv/(1+discount)**10/pv*100}
    ten=[long_value(s,r) for s in a["scenarios"]]
    assert sum(D(s["probability"]) for s in ten)==1
    sensitivity=[]
    for rate in map(D,[".06",".07",".08",".09",".10"]):
        rows=[long_value(s,rate) for s in a["scenarios"]]
        weighted=sum(D(s["probability"])*s["cashflow_irr_pct"] for s in rows)
        sensitivity.append({"r":rate,"weighted_cashflow_irr_pct":weighted,"covers_hurdle":weighted>=rate*100,"spreads_pp":[s["spread_pp"] for s in rows],"valid_currency_band":D(".06")<=rate<=D(".09"),"all_spreads_valid":all(s["spread_pp"]>=5 for s in rows)})
    lo,hi=D("-.15"),D(".3")
    for _ in range(140):
        growth=(lo+hi)/2
        pv=long_value({"growth":str(growth),"terminal_g":".01","name":"reverse","probability":"1"},r)["pv_price"]
        if pv < price: lo=growth
        else: hi=growth
    result={"metrics":metrics,"extra":extra,"ttm":ttm,"q3_current":qn,"q3_prior":qo,"comparisons":comparisons,"operating":{label:operating(z) for label,z in (("ytd2026",n),("ytd2025",o),("q32026",qn),("q32025",qo),*[(year,v) for year,v in annual.items()])},"cashflow_bridge":bridge,"segments":segments,"three_year":three,"ten_year":ten,"sensitivity":sensitivity,"weighted_pv_price":sum(D(s["probability"])*s["pv_price"] for s in ten),"weighted_cashflow_irr_pct":sum(D(s["probability"])*s["cashflow_irr_pct"] for s in ten),"reverse_growth_pct":(lo+hi)/2*100}
    (HERE/"results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    spec={"roic":float(roic),"g":[float(D(s["terminal_g"])) for s in ten],"p":[float(D(s["probability"])) for s in ten],"irr10":[long_value(s,D(".10"))["toolkit_approx_irr_pct"] for s in a["scenarios"]],"k":float(k)}
    (HERE/"terminal-config.json").write_text(json.dumps({"华东医药":spec},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    log=io.StringIO()
    with contextlib.redirect_stdout(log):
        rigor.verify_market_cap(price,shares,D(x["reported_market_cap"]),"CNY")
        rigor.verify_valuation(price,eps=ttm["profit"]/shares,bvps=n["equity_parent"]/shares,fcf_per_share=ttm["fcf"]/shares,dividend=D(x["historical_dividend_per_share"]))
        for item in x["cross_checks"]:
            rigor.cross_validate(item["field"],{item["source1"]:D(item["value1"]),item["source2"]:D(item["value2"])},item["unit"],tolerance_pct=1)
        rigor.three_scenario_valuation(price,eps,shares/E8,D(x["three_year_assumptions"][2]["growth"]),D(x["three_year_assumptions"][1]["growth"]),D(x["three_year_assumptions"][0]["growth"]),D(x["three_year_assumptions"][2]["pe"]),D(x["three_year_assumptions"][1]["pe"]),D(x["three_year_assumptions"][0]["pe"]),years=3,currency="CNY")
    (HERE/"financial-rigor.txt").write_text(clean(log.getvalue()),encoding="utf-8")
    commands={"terminal-audit.txt":["audit","--currency","CNY","--r",str(r),"--roic",str(roic),"--g",",".join(s["terminal_g"] for s in a["scenarios"]),"--rf",a["rf_reference"],"--beta","1","--discrete-risks",a["discrete_risks"]]}
    for delta in ("0.02","0.01"):
        commands["terminal-flip-"+delta+".txt"]=["flip","--config",str(HERE/"terminal-config.json"),"--name","华东医药","--r",str(r),"--delta",delta,"--currency","CNY","--g-shift","0","--rf",a["rf_reference"]]
    for file,args in commands.items():
        p=subprocess.run([sys.executable,str(ROOT/"tools/terminal_value.py"),*args],capture_output=True,text=True,encoding="utf-8")
        (HERE/file).write_text(clean(p.stdout+p.stderr),encoding="utf-8")
        if p.returncode: raise RuntimeError(file+" failed: "+p.stdout+p.stderr)
    print(json.dumps({k:result[k] for k in ("metrics","ttm","three_year","ten_year","sensitivity","reverse_growth_pct")},ensure_ascii=False,indent=2,default=str))

if __name__ == "__main__":
    main()
