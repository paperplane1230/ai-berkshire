"""Public-data-only Decimal arithmetic. No network or private portfolio access."""
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
getcontext().prec = 36
D = rigor.exact

def dec(raw):
    return {k:D(v) for k,v in raw.items()}

def pct(now, old):
    return (now / old - 1) * 100

def irr(cfs):
    low, high = D("-.99"), D("5")
    for _ in range(160):
        r = (low + high) / 2
        npv = sum(v / (1 + r) ** y for y,v in enumerate(cfs))
        if npv > 0:
            low = r
        else:
            high = r
    return (low + high) / 2

def clean(value):
    plain = re.sub(r"\x1b\[[0-9;]*m", "", value)
    return "\n".join(line.rstrip() for line in plain.splitlines()).strip() + "\n"

def metrics(n):
    out = {"net_margin_pct": n["profit"] / n["revenue"] * 100, "ocf_profit_ratio": n["ocf"] / n["profit"]}
    for k in ("selling","rd","admin","operating_profit"):
        if k in n:
            out[k + "_ratio_pct"] = n[k] / n["revenue"] * 100
    if "cost" in n:
        out["gross_margin_pct"] = (1 - n["cost"] / n["revenue"]) * 100
    if "capex" in n:
        out["fcf"] = n["ocf"] - n["capex"]
    return out

def main():
    data = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
    price, shares = D(data["price"]), D(data["shares"])
    mcap = price * shares
    annual = {y:dec(v) for y,v in data["annual"].items()}
    new, old = map(dec, (data["ytd_2026q3"], data["ytd_2025q3"]))
    hn, ho = map(dec, (data["h1_2026"], data["h1_2025"]))
    qn = {k:new[k]-hn[k] for k in hn if k in new}
    qo = {k:old[k]-ho[k] for k in ho if k in old}
    ttm = {k:annual["2025"][k]+new[k]-old[k] for k in ("revenue","profit","adjusted_profit","ocf","capex") if k in annual["2025"]}
    if "capex" in ttm:
        ttm["fcf"] = ttm["ocf"]-ttm["capex"]
    eps = ttm["adjusted_profit"] / shares
    valuation = {"market_cap":mcap,"eps_ttm":ttm["profit"]/shares,"eps_adjusted_ttm":eps,"pe_ttm":mcap/ttm["profit"],"pe_adjusted_ttm":mcap/ttm["adjusted_profit"],"pe_2025":mcap/annual["2025"]["profit"],"ps_ttm":mcap/ttm["revenue"],"pb":mcap/new["equity"],"net_cash_before_leases":new["cash"]-new["bank_debt"],"net_cash_after_leases":new["cash"]-new["bank_debt"]-new["lease_current_upper"]-new["lease_noncurrent"],"liabilities_assets_pct":new["liabilities"]/new["assets"]*100,"ar_growth_vs_year_start_pct":pct(new["ar"],new["ar_start"]),"inventory_growth_vs_year_start_pct":pct(new["inventory"],new["inventory_start"]),"ar_days_proxy":(new["ar"]+new["ar_start"])/2/new["revenue"]*273,"inventory_days_proxy":(new["inventory"]+new["inventory_start"])/2/new["cost"]*273,"construction_increase":new["construction"]-new["construction_start"],"other_payables_increase":new["other_payables"]-new["other_payables_start"],"price_cut_pct":pct(D("234.7"),D("298")),"required_volume_lift_pct":pct(D("298"),D("234.7")),"ytd_nonrecurring":new["profit"]-new["adjusted_profit"],"q3_nonrecurring":qn["profit"]-qn["adjusted_profit"],"control_share_pct":D("102396407")/shares*100}
    valuation["ev_revenue_reference"] = (mcap-valuation["net_cash_after_leases"])/ttm["revenue"]
    if "fcf" in ttm:
        valuation["fcf_yield_pct"] = ttm["fcf"]/mcap*100
    if "dividends_2025_total" in data:
        div = D(data["dividends_2025_total"])/shares
        valuation.update(dividend_per_current_share_equivalent=div,dividend_yield_pct=div/price*100,historical_payout_pct=D(data["dividends_2025_total"])/annual["2025"]["profit"]*100)
    bridge={k:(new[k]-old[k])*sign for k,sign in (("cash_received",1),("other_inflow",1),("purchase_cash",-1),("staff_cash",-1),("tax_cash",-1),("other_outflow",-1))}
    assert sum(bridge.values()) == new["ocf"]-old["ocf"]
    three=[]
    for s in data["three_year"]:
        growth, pe, payout = map(D,(s["growth"],s["pe"],s["payout"]))
        end_eps=eps*(1+growth)**3
        dividends=[eps*(1+growth)**y*payout for y in range(1,4)]
        target=end_eps*pe
        cfs=[-price]+dividends
        cfs[-1]+=target
        three.append({**s,"end_eps":end_eps,"target_price":target,"price_change_pct":pct(target,price),"dividends":sum(dividends),"cashflow_irr_pct":irr(cfs)*100,"present_value_at_8pct":sum(cf/D("1.08")**y for y,cf in enumerate(cfs) if y>0)})
    ten_input=data["ten_year"]
    roic, r = D(ten_input["roic"]), D(ten_input["r"])
    def long(s, discount, override_growth=None):
        first,next7,g,payout=map(D,(s["growth_first3"],s["growth_next7"],s["terminal_g"],s["payout"]))
        if override_growth is not None:
            first=next7=override_growth
        profits=[ttm["adjusted_profit"]*(1+first)**min(y,3)*(1+next7)**max(0,y-3) for y in range(1,11)]
        pe=(1-g/roic)/(discount-g)
        profit11=profits[-1]*(1+g)
        exit_value=profit11*pe
        cfs=[-mcap]+[p*payout for p in profits]
        cfs[-1]+=exit_value
        pv=sum(cf/(1+discount)**y for y,cf in enumerate(cfs) if y>0)
        return {**s,"profit10":profits[-1],"profit11":profit11,"exit_pe":pe,"spread_pp":(discount-g)*100,"pv_price":pv/shares,"cashflow_irr_pct":irr(cfs)*100,"price_only_tool_irr_pct":terminal.irr_from_terminal(float(profit11),float(mcap),float(pe),years=10,payout=0)*100,"terminal_pv_weight_pct":exit_value/(1+discount)**10/pv*100,"cfs":cfs}
    ten=[long(s,r) for s in ten_input["scenarios"]]
    anchors=[long(s,D(".10"))["price_only_tool_irr_pct"] for s in ten_input["scenarios"]]
    spec={"roic":float(roic),"g":[float(D(s["terminal_g"])) for s in ten],"p":[float(D(s["probability"])) for s in ten],"irr10":anchors,"k":0}
    assert sum(D(s["probability"]) for s in ten)==1
    sensitivity=[]
    for rate in map(D,[".06",".07",".08",".09",".10"]):
        rows=[long(s,rate) for s in ten_input["scenarios"]]
        weighted=sum(D(s["probability"])*s["cashflow_irr_pct"] for s in rows)
        sensitivity.append({"r":rate,"weighted_cashflow_irr_pct":weighted,"covers_hurdle":weighted>=rate*100,"spreads_pp":[s["spread_pp"] for s in rows],"valid_currency_band":D(".06")<=rate<=D(".09"),"all_spreads_valid":all(s["spread_pp"]>=5 for s in rows)})
    low,high=D("-.10"),D(".40")
    base=ten_input["scenarios"][1]
    for _ in range(150):
        growth=(low+high)/2
        if long(base,r,growth)["pv_price"]<price:
            low=growth
        else:
            high=growth
    result={"valuation":valuation,"ttm":ttm,"q3_current":qn,"q3_prior":qo,"annual_metrics":{y:metrics(v) for y,v in annual.items()},"ytd_metrics":metrics(new),"prior_ytd_metrics":metrics(old),"q3_metrics":metrics(qn),"prior_q3_metrics":metrics(qo),"q3_growth_pct":{k:pct(qn[k],qo[k]) for k in qn if k in qo and qo[k]},"ytd_growth_pct":{k:pct(new[k],old[k]) for k in old if old[k]},"cashflow_bridge":bridge,"three_year":three,"ten_year":ten,"sensitivity":sensitivity,"weighted_pv_price":sum(D(s["probability"])*s["pv_price"] for s in ten),"weighted_cashflow_irr_pct":sum(D(s["probability"])*s["cashflow_irr_pct"] for s in ten),"reverse_constant_growth_pct":(low+high)/2*100}
    products={}
    for key in ("products_2025","products_h1_2026"):
        if key in data:
            total=annual["2025"]["revenue"] if key.endswith("2025") else hn["revenue"]
            products[key]={}
            for name,raw in data[key].items():
                p=dec(raw)
                products[key][name]={"share_pct":p["revenue"]/total*100,**({"gross_margin_pct":(1-p["cost"]/p["revenue"])*100} if "cost" in p else {})}
                if "volume" in p:
                    products[key][name]["average_revenue_per_unit"]=p["revenue"]/p["volume"]
            assert abs(sum(D(v["revenue"]) for v in data[key].values())-total)<D(".01")
    result["products"]=products
    (HERE/"results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    (HERE/"terminal-config.json").write_text(json.dumps({"兴齐眼药":spec},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    log=io.StringIO()
    with contextlib.redirect_stdout(log):
        rigor.verify_market_cap(price,shares,D(data["reported_market_cap"]),"CNY")
        rigor.verify_valuation(price,eps=ttm["profit"]/shares,bvps=new["equity"]/shares,fcf_per_share=ttm.get("fcf",D(0))/shares,dividend=valuation.get("dividend_per_current_share_equivalent",D(0)))
        for label,v1,v2 in (("2025收入",annual["2025"]["revenue"],"2473000000"),("2025归母",annual["2025"]["profit"],"696000000"),("2026Q3累计收入",new["revenue"],"2240000000"),("2026Q3累计归母",new["profit"],"705000000"),("2026Q3累计扣非",new["adjusted_profit"],"716000000"),("2026Q3累计OCF",new["ocf"],"713000000")):
            rigor.cross_validate(label,{"公司原件":v1,"财中社或北京商报独立刊发":D(v2)},"元",tolerance_pct=1)
        rigor.cross_validate("最新总股本",{"公司Q3原件":shares,"腾讯行情":D("354917774")},"股",tolerance_pct=1)
        rigor.cross_validate("2026-10-28收盘价",{"腾讯":price,"新浪":D("32.860")},"元",tolerance_pct=1)
        rigor.cross_validate("刘继东持股",{"102396407股除当前总股本":valuation["control_share_pct"],"Q3披露比例":D("28.85")},"%",tolerance_pct=1)
        rigor.three_scenario_valuation(price,eps,shares/D("1e8"),D(".15"),D(".06"),D("-.10"),22,17,12,years=3,currency="CNY")
        print("Cash and note details: issuer-only underlying evidence; not independently cross-verified.")
    (HERE/"financial-rigor.txt").write_text(clean(log.getvalue()),encoding="utf-8")
    commands={"terminal-audit.txt":["audit","--currency","CNY","--r",str(r),"--roic",str(roic),"--g","0,0.01,0.02","--rf",ten_input["rf_reference"],"--beta","1","--discrete-risks","阿托品降价:情景,干眼竞争:情景,临床失败:情景,严重药品安全事件:未建模"]}
    for delta in ("0.02","0.01"):
        commands["terminal-flip-"+delta+".txt"]=["flip","--config",str(HERE/"terminal-config.json"),"--name","兴齐眼药","--r",str(r),"--delta",delta,"--currency","CNY","--g-shift","0","--rf",ten_input["rf_reference"]]
    for filename,args in commands.items():
        process=subprocess.run([sys.executable,str(ROOT/"tools/terminal_value.py"),*args],capture_output=True,text=True,encoding="utf-8")
        (HERE/filename).write_text(clean(process.stdout+process.stderr),encoding="utf-8")
        if process.returncode:
            raise RuntimeError(filename+" failed: "+process.stdout+process.stderr)
    print(json.dumps({k:result[k] for k in ("valuation","ttm","three_year","ten_year","sensitivity","weighted_pv_price","weighted_cashflow_irr_pct","reverse_constant_growth_pct")},ensure_ascii=False,indent=2,default=str))

if __name__ == "__main__":
    main()
