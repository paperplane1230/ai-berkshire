"""Reproducible public-company arithmetic; no networking or portfolio access."""
import contextlib
import io
import json
import re
import subprocess
import sys
from decimal import Decimal, getcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import financial_rigor as rigor
import terminal_value as terminal

getcontext().prec = 32
D = rigor.exact


def decmap(obj):
    return {k: D(v) for k, v in obj.items()}


def pct(now, before):
    return (now / before - 1) * 100


def irr(cfs):
    low, high = D("-.95"), D("3")
    for _ in range(160):
        rate = (low + high) / 2
        npv = sum(cf / (1 + rate) ** i for i, cf in enumerate(cfs))
        if npv > 0:
            low = rate
        else:
            high = rate
    return (low + high) / 2


def clean(text):
    plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return "\n".join(line.rstrip() for line in plain.splitlines()).rstrip() + "\n"


def main():
    data = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
    price, shares = D(data["price"]), D(data["shares"])
    mcap = price * shares
    new, old = map(decmap, (data["ytd_2026q3"], data["ytd_2025q3"]))
    hnew, hold = map(decmap, (data["h1_2026"], data["h1_2025"]))
    annual = {year: decmap(values) for year, values in data["annual"].items()}
    a = annual["2025"]
    ttm = {k: a[k] + new[k] - old[k] for k in ("revenue", "profit", "adjusted_profit", "ocf", "capex", "interest_income")}
    ttm["fcf"] = ttm["ocf"] - ttm["capex"]
    eps = ttm["adjusted_profit"] / shares
    qnew = {k: new[k] - hnew[k] for k in hnew}
    qold = {k: old[k] - hold[k] for k in hold}

    def operating_metrics(n, o):
        values = {k + "_growth_pct": pct(n[k], o[k]) for k in n if k in o and o[k] != 0}
        for label, item in (("new", n), ("prior", o)):
            values[label + "_gross_margin_pct"] = (1 - item["cost"] / item["revenue"]) * 100
            values[label + "_net_margin_pct"] = item["profit"] / item["revenue"] * 100
            values[label + "_selling_ratio_pct"] = item["selling"] / item["revenue"] * 100
            values[label + "_ocf_profit_ratio"] = item["ocf"] / item["profit"]
        values["gross_margin_change_pp"] = values["new_gross_margin_pct"] - values["prior_gross_margin_pct"]
        values["selling_ratio_change_pp"] = values["new_selling_ratio_pct"] - values["prior_selling_ratio_pct"]
        return values

    metrics = {
        "market_cap": mcap, "eps_ttm": ttm["profit"] / shares, "eps_adjusted_ttm": eps,
        "pe_ttm": mcap / ttm["profit"], "pe_adjusted_ttm": mcap / ttm["adjusted_profit"],
        "pe_2025": mcap / a["profit"], "pb": mcap / new["equity_parent"],
        "ps_ttm": mcap / ttm["revenue"], "bvps": new["equity_parent"] / shares,
        "dividend_yield_pct": D(data["historical_dividend_per_share"]) / price * 100,
        "historical_payout_pct": D(data["historical_dividend_per_share"]) * shares / a["profit"] * 100,
        "fcf_yield_pct": ttm["fcf"] / mcap * 100,
        "fcf_ytd": new["ocf"] - new["capex"], "fcf_prior_ytd": old["ocf"] - old["capex"],
        "liquid_assets_reference": new["cash"] + new["trading_assets"],
        "net_cash_reference": new["cash"] + new["trading_assets"] - new["bank_debt"] - new["lease_current"] - new["lease_noncurrent"],
        "cash_not_equivalents": new["cash"] - new["cash_equivalents"],
        "ar_year_start_pct": pct(new["ar"], new["ar_start"]),
        "contract_year_start_pct": pct(new["contract_liabilities"], new["contract_start"]),
        "ar_days_average_proxy": (new["ar"] + new["ar_start"]) / 2 / new["revenue"] * 273,
        "inventory_days_average_proxy": (new["inventory"] + new["inventory_start"]) / 2 / new["cost"] * 273,
        "inventory_year_start_pct": pct(new["inventory"], new["inventory_start"]),
        "construction_year_start_pct": pct(new["construction"], new["construction_start"]),
        "liabilities_assets_pct": new["liabilities"] / new["assets"] * 100,
        "goodwill_assets_pct": new["goodwill"] / new["assets"] * 100,
        "rd_increment": new["rd"] - old["rd"],
        "investment_income_change": new["investment_income"] - old["investment_income"],
        "q3_nonrecurring_current": qnew["profit"] - qnew["adjusted_profit"],
        "q3_nonrecurring_prior": qold["profit"] - qold["adjusted_profit"],
        "q3_financial_income_change": sum(qnew[k] - qold[k] for k in ("interest_income", "investment_income", "fair_value_gain")),
    }
    metrics["liquid_assets_mcap_pct"] = metrics["liquid_assets_reference"] / mcap * 100
    metrics["ev_revenue_reference"] = (mcap - metrics["net_cash_reference"]) / ttm["revenue"]
    metrics["q3_nonrecurring_decline_share_pct"] = (metrics["q3_nonrecurring_prior"] - metrics["q3_nonrecurring_current"]) / (qold["profit"] - qnew["profit"]) * 100
    if "ar" in old:
        metrics["ar_yoy_pct"] = pct(new["ar"], old["ar"])
        metrics["contract_yoy_pct"] = pct(new["contract_liabilities"], old["contract_liabilities"])
        metrics["inventory_yoy_pct"] = pct(new["inventory"], old["inventory"])
    metrics["profit_2025_vs_2022_pct"] = pct(a["profit"],annual["2022"]["profit"])
    metrics["revenue_2025_vs_2021_pct"] = pct(a["revenue"],annual["2021"]["revenue"])
    bridge = {k: (new[k] - old[k]) * sign for k, sign in (("cash_received", 1), ("tax_refund", 1), ("other_inflow", 1), ("purchase_cash", -1), ("staff_cash", -1), ("tax_cash", -1), ("other_outflow", -1))}
    assert sum(bridge.values()) == new["ocf"] - old["ocf"]
    products = {}
    for key, total in (("products_2025", a["revenue"]), ("products_h1_2026", hnew["revenue"])):
        products[key] = {}
        for name, raw in data[key].items():
            p = decmap(raw)
            values = {"share_pct":p["revenue"] / total * 100, "revenue_growth_pct":pct(p["revenue"],p["prior_revenue"])}
            if "cost" in p:
                values["gross_margin_pct"] = (1 - p["cost"] / p["revenue"]) * 100
            if "volume_tonnes" in p:
                values["revenue_per_tonne"] = p["revenue"] / p["volume_tonnes"]
                values["volume_growth_pct"] = pct(p["volume_tonnes"], p["prior_volume_tonnes"])
                values["revenue_per_tonne_growth_pct"] = pct(p["revenue"] / p["volume_tonnes"], p["prior_revenue"] / p["prior_volume_tonnes"])
            products[key][name] = values
        assert sum(D(p["revenue"]) for p in data[key].values()) == total
    metrics["new_products_revenue_increment_share_pct"] = (D(data["products_h1_2026"]["其他产品"]["revenue"]) - D(data["products_h1_2026"]["其他产品"]["prior_revenue"])) / (hnew["revenue"] - hold["revenue"]) * 100
    three = []
    for s in data["three_year_assumptions"]:
        growth, pe = D(s["growth"]), D(s["pe"])
        end_eps = eps * (1 + growth) ** 3
        target = end_eps * pe
        dividends = [eps * (1 + growth) ** y * D(".65") for y in range(1, 4)]
        cfs = [-price] + dividends
        cfs[-1] += target
        three.append({**s,"eps_year3":end_eps,"price_year3":target,"price_change_pct":pct(target,price),"dividends_total":sum(dividends),"cashflow_irr_pct":irr(cfs)*100,"pv_at_8pct":sum(cf/D("1.08")**i for i,cf in enumerate(cfs) if i>0)})
    assumption = data["ten_year_assumptions"]
    r, roic, payout = map(D,(assumption["r"],assumption["roic"],assumption["payout_ratio"]))
    profit = ttm["adjusted_profit"]
    k = profit * payout / mcap
    ten, anchors = [], []

    def long_value(s, discount):
        growth, g = D(s["growth"]), D(s["terminal_g"])
        pe = (1 - g/roic) / (discount-g)
        p10 = profit * (1+growth)**10
        terminal_cap = p10 * (1+g) * pe
        cfs = [-mcap] + [profit*(1+growth)**y*payout for y in range(1,11)]
        cfs[-1] += terminal_cap
        pv = sum(cf/(1+discount)**i for i,cf in enumerate(cfs) if i>0)
        approximate = terminal.irr_from_terminal(float(p10),float(mcap),float(pe),payout=float(k))*100
        return {**s,"profit_year10":p10,"profit_year11":p10*(1+g),"exit_pe":pe,"spread_pp":(discount-g)*100,"pv_price":pv/shares,"cashflow_irr_pct":irr(cfs)*100,"toolkit_approx_irr_pct":approximate,"terminal_pv_weight_pct":terminal_cap/(1+discount)**10/pv*100}

    for s in assumption["scenarios"]:
        ten.append(long_value(s,r))
        anchors.append(long_value(s,D(".10"))["toolkit_approx_irr_pct"])
    spec = {"roic":float(roic),"g":[float(D(s["terminal_g"])) for s in ten],"p":[float(D(s["probability"])) for s in ten],"irr10":anchors,"k":float(k)}
    assert sum(D(s["probability"]) for s in ten) == 1
    sensitivity = []
    for rate in map(D,[".06",".07",".08",".09",".10"]):
        rows = [long_value(s,rate) for s in assumption["scenarios"]]
        w = sum(D(s["probability"])*s["cashflow_irr_pct"] for s in rows)
        sensitivity.append({"r":rate,"weighted_cashflow_irr_pct":w,"covers_hurdle":w>=rate*100,"spreads_pp":[s["spread_pp"] for s in rows],"valid_currency_band":D(".06")<=rate<=D(".09"),"all_spreads_valid":all(s["spread_pp"]>=5 for s in rows)})
    low, high = D("-.10"), D(".25")
    for _ in range(120):
        g10 = (low+high)/2
        s = {"growth":str(g10),"terminal_g":".01","name":"reverse","probability":"1"}
        pv = long_value(s,r)["pv_price"]
        if pv < price:
            low = g10
        else:
            high = g10
    cash_assumptions = data["sotp_assumptions"]
    core_profit = profit - ttm["interest_income"]*(1-D(cash_assumptions["interest_tax_rate"]))
    metrics["q3_core_profit_proxy"] = qnew["adjusted_profit"] - qnew["interest_income"] * (1-D(cash_assumptions["interest_tax_rate"]))
    metrics["q3_core_profit_proxy_prior"] = qold["adjusted_profit"] - qold["interest_income"] * (1-D(cash_assumptions["interest_tax_rate"]))
    metrics["q3_core_profit_proxy_growth_pct"] = pct(metrics["q3_core_profit_proxy"],metrics["q3_core_profit_proxy_prior"])
    sotp = [{"core_pe":D(pe),"surplus_cash":D(cash),"price":(core_profit*D(pe)+D(cash))/shares,"price_cash_delayed_three_years":(core_profit*D(pe)+D(cash)/(1+r)**3)/shares} for pe,cash in zip(cash_assumptions["core_pe"],cash_assumptions["surplus_cash"])]
    result = {"metrics":metrics,"ttm":ttm,"q3_current":qnew,"q3_prior":qold,"ytd_comparison":operating_metrics(new,old),"q3_comparison":operating_metrics(qnew,qold),"h1_comparison":operating_metrics(hnew,hold),"cashflow_bridge":bridge,"products":products,"three_year":three,"ten_year":ten,"sensitivity":sensitivity,"weighted_pv_price":sum(D(s["probability"])*s["pv_price"] for s in ten),"weighted_cashflow_irr_pct":sum(D(s["probability"])*s["cashflow_irr_pct"] for s in ten),"reverse_growth_pct":(low+high)/2*100,"sotp_core_profit_proxy":core_profit,"sotp":sotp,"annual_derived":{y:{"net_margin_pct":v["profit"]/v["revenue"]*100,"gross_margin_pct":(1-v["cost"]/v["revenue"])*100,"ocf_profit_ratio":v["ocf"]/v["profit"],"fcf":v["ocf"]-v["capex"]} for y,v in annual.items()}}
    (HERE/"results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    (HERE/"terminal-config.json").write_text(json.dumps({"涪陵榨菜":spec},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        rigor.verify_market_cap(price,shares,D(data["reported_market_cap"]),"CNY")
        rigor.verify_valuation(price,eps=ttm["profit"]/shares,bvps=metrics["bvps"],fcf_per_share=ttm["fcf"]/shares,dividend=D(data["historical_dividend_per_share"]))
        for label,v1,v2 in (("2025收入",a["revenue"],"2432000000"),("2025归母",a["profit"],"768000000"),("2025经营现金流",a["ocf"],"657000000"),("2026Q3累计收入",new["revenue"],"2068000000"),("2026Q3累计归母",new["profit"],"614000000"),("2026Q3累计扣非",new["adjusted_profit"],"582000000"),("2026Q3累计经营现金流",new["ocf"],"691000000")):
            rigor.cross_validate(label,{"公司原件":v1,"独立刊发媒体亿元换算":D(v2)},"CNY",tolerance_pct=1)
        rigor.cross_validate("最新股本",{"公司Q3":shares,"腾讯行情":D("1153919028")},"股",tolerance_pct=1)
        rigor.cross_validate("10月27日收盘价",{"腾讯":price,"新浪":D("11.22")},"CNY",tolerance_pct=1)
        print("Cash-reference 6,392,447,505.51 CNY: issuer-only underlying evidence; mirrors not independent confirmation.")
        rigor.three_scenario_valuation(price,eps,shares/D("1e8"),D(".07"),D(".03"),D("-.03"),22,18,14,years=3,currency="CNY")
    (HERE/"financial-rigor.txt").write_text(clean(log.getvalue()),encoding="utf-8")
    commands = {"terminal-audit.txt":["audit","--currency","CNY","--r",str(r),"--roic",str(roic),"--g","0,0.01,0.02","--rf",assumption["rf_tool_reference"],"--beta","1","--discrete-risks",assumption["discrete_risks"]]}
    for delta in ("0.02","0.01"):
        commands["terminal-flip-"+delta+".txt"] = ["flip","--config",str(HERE/"terminal-config.json"),"--name","涪陵榨菜","--r",str(r),"--delta",delta,"--currency","CNY","--g-shift","0","--rf",assumption["rf_tool_reference"]]
    for filename,args in commands.items():
        process = subprocess.run([sys.executable,str(ROOT/"tools/terminal_value.py"),*args],capture_output=True,text=True,encoding="utf-8")
        (HERE/filename).write_text(clean(process.stdout+process.stderr),encoding="utf-8")
        if process.returncode:
            raise RuntimeError(filename + " failed: " + process.stdout + process.stderr)
    print(json.dumps({k:result[k] for k in ("metrics","ttm","three_year","ten_year","sensitivity","weighted_pv_price","weighted_cashflow_irr_pct","reverse_growth_pct","sotp")},ensure_ascii=False,indent=2,default=str))


if __name__ == "__main__":
    main()
