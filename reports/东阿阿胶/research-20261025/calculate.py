"""Reproduce report arithmetic. No network, holdings access, or trading actions."""
import contextlib
import io
import json
import re
from pathlib import Path
import subprocess
import sys
from decimal import Decimal, getcontext

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import financial_rigor as rigor
import terminal_value as terminal

getcontext().prec = 28
D = rigor.exact


def clean_log(text):
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).rstrip() + "\n"


data = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
price, shares = D(data["price"]), D(data["shares"])
mcap = price * shares
a = {k: D(v) for k, v in data["annual_original"]["2025"].items()}
old = {k: D(v) for k, v in data["ytd_2025q3"].items()}
new = {k: D(v) for k, v in data["ytd_2026q3"].items()}
h1 = {k: D(v) for k, v in data["h1_2026"].items()}
oldh1 = {k: D(v) for k, v in data["h1_2025_restated_in_2026"].items()}


def pct(now, before):
    return (now / before - 1) * 100


ttm = {key: a[key] + new[key] - old[key]
       for key in ("revenue", "profit", "adjusted_profit", "ocf", "capex")}
ttm["fcf"] = ttm["ocf"] - ttm["capex"]
eps = ttm["adjusted_profit"] / shares
metrics = {
    "market_cap": mcap,
    "pe_ttm": mcap / ttm["profit"], "pe_adjusted_ttm": mcap / ttm["adjusted_profit"],
    "eps_ttm": ttm["profit"] / shares, "eps_adjusted_ttm": eps,
    "pb": mcap / new["equity_parent"], "ps_ttm": mcap / ttm["revenue"],
    "bvps": new["equity_parent"] / shares,
    "fcf_yield_pct": ttm["fcf"] / mcap * 100,
    "ocf_profit_ratio": new["ocf"] / new["profit"],
    "fcf_ytd": new["ocf"] - new["capex"],
    "cash_financial_assets": new["cash"] + new["trading_assets"],
    "net_cash_reference": new["cash"] + new["trading_assets"] - new["bank_debt"] - new["lease_current"] - new["lease_noncurrent"],
    "q3_ocf": new["ocf"] - h1["ocf"],
    "q3_ocf_prior_from_comparable_h1": old["ocf"] - oldh1["ocf"],
    "ar_yoy_pct": pct(new["ar"], old["ar"]),
    "contract_yoy_pct": pct(new["contract_liabilities"], old["contract_liabilities"]),
    "ar_year_start_pct": pct(new["ar"], new["ar_start"]),
    "ar_since_h1": new["ar"] - h1["ar"],
    "ending_ar_days_proxy_current": new["ar"] / new["revenue"] * 273,
    "ending_ar_days_proxy_prior": old["ar"] / old["revenue"] * 273,
    "ar_days_average_current": (new["ar"] + new["ar_start"]) / 2 / new["revenue"] * 273,
    "inventory_days_average_current": (new["inventory"] + new["inventory_start"]) / 2 / new["cost"] * 273,
    "inventory_year_start_pct": pct(new["inventory"], new["inventory_start"]),
    "gross_margin_pct": (1 - new["cost"] / new["revenue"]) * 100,
    "gross_margin_prior_pct": (1 - old["cost"] / old["revenue"]) * 100,
    "operating_margin_pct": new["operating_profit"] / new["revenue"] * 100,
    "operating_margin_prior_pct": old["operating_profit"] / old["revenue"] * 100,
    "selling_ratio_pct": new["selling"] / new["revenue"] * 100,
    "selling_ratio_prior_pct": old["selling"] / old["revenue"] * 100,
    "rd_yoy_pct": pct(new["rd"], old["rd"]),
    "cash_received_yoy_pct": pct(new["cash_received"], old["cash_received"]),
    "goodwill_assets_pct": new["goodwill"] / new["assets"] * 100,
    "intangibles_assets_pct": new["intangibles"] / new["assets"] * 100,
    "capex_profit_pct": new["capex"] / new["profit"] * 100,
}
metrics["q3_ocf_yoy_pct"] = pct(metrics["q3_ocf"], metrics["q3_ocf_prior_from_comparable_h1"])
metrics["net_cash_pct_market_cap"] = metrics["net_cash_reference"] / mcap * 100
metrics["gross_margin_change_pp"] = metrics["gross_margin_pct"] - metrics["gross_margin_prior_pct"]
bridge = {key: (new[key] - old[key]) * sign for key, sign in (
    ("cash_received", 1), ("tax_refund", 1), ("other_inflow", 1),
    ("purchase_cash", -1), ("staff_cash", -1), ("tax_cash", -1), ("other_outflow", -1))}
assert sum(bridge.values()) == new["ocf"] - old["ocf"]


def irr(cashflows):
    # Exact decimal bisection of dated annual cash flows; unlike the toolkit's additive approximation.
    low, high = D("-0.95"), D("3")
    for _ in range(150):
        rate = (low + high) / 2
        npv = sum(cf / (1 + rate) ** i for i, cf in enumerate(cashflows))
        if npv > 0:
            low = rate
        else:
            high = rate
    return (low + high) / 2


three = []
for s in data["three_year_assumptions"]:
    growth, multiple = D(s["growth"]), D(s["pe"])
    end_eps = eps * (1 + growth) ** 3
    terminal_price = end_eps * multiple
    dividends = [eps * (1 + growth) ** year * D("0.70") for year in range(1, 4)]
    cfs = [-price] + dividends
    cfs[-1] += terminal_price
    three.append({**s, "eps_year3": end_eps, "price_year3": terminal_price,
                  "price_change_pct": pct(terminal_price, price),
                  "dividends_total": sum(dividends), "cashflow_irr_pct": irr(cfs) * 100,
                  "pv_at_8pct": sum(cf / D("1.08") ** i for i, cf in enumerate(cfs) if i > 0)})

assumptions = data["ten_year_assumptions"]
r, roic, payout = map(D, (assumptions["r"], assumptions["roic"], assumptions["payout_ratio"]))
normal_profit = ttm["adjusted_profit"]
k = payout * normal_profit / mcap
ten = []
anchors = []
for s in assumptions["scenarios"]:
    growth, g = D(s["growth"]), D(s["terminal_g"])
    profit10 = normal_profit * (1 + growth) ** 10
    pe = (1 - g / roic) / (r - g)
    # Gordon's multiplier prices the NEXT period's distributable earnings at t=10.
    profit11 = profit10 * (1 + g)
    terminal_cap = profit11 * pe
    dividends = [normal_profit * (1 + growth) ** year * payout for year in range(1, 11)]
    cfs = [-mcap] + dividends
    cfs[-1] += terminal_cap
    pv = sum(cf / (1 + r) ** i for i, cf in enumerate(cfs) if i > 0)
    pe10 = terminal.exit_pe(float(roic), float(g), .10)[0]
    anchor = terminal.irr_from_terminal(float(profit10), float(mcap), pe10, payout=float(k)) * 100
    anchors.append(anchor)
    toolkit_irr = terminal.irr_from_terminal(float(profit10), float(mcap), float(pe), payout=float(k)) * 100
    ten.append({**s, "profit_year10": profit10, "profit_year11":profit11, "exit_pe": pe, "spread_pp": (r-g)*100,
                "pv_equity": pv, "pv_price": pv / shares, "cashflow_irr_pct": irr(cfs)*100,
                "toolkit_approx_irr_pct": toolkit_irr,
                "terminal_pv_weight_pct": terminal_cap / (1+r)**10 / pv * 100})

spec = {"roic":float(roic), "g":[float(D(s["terminal_g"])) for s in assumptions["scenarios"]],
        "p":[float(D(s["probability"])) for s in assumptions["scenarios"]], "irr10":anchors, "k":float(k)}
rf_tool = float(D(assumptions["rf_tool_reference"]))
flip = terminal.flip_analysis(spec, float(r), .02, 0, 10, rf_tool, terminal.CURRENCY_BANDS["CNY"])
flip1 = terminal.flip_analysis(spec, float(r), .01, 0, 10, rf_tool, terminal.CURRENCY_BANDS["CNY"])
weighted_value = sum(D(s["probability"])*s["pv_price"] for s in ten)
weighted_irr = sum(D(s["probability"])*s["cashflow_irr_pct"] for s in ten)
weighted_approx = sum(float(D(s["probability"]))*s["toolkit_approx_irr_pct"] for s in ten)

# Numerical reverse valuation: constant annual earnings growth that prices the current equity at r=8%.
low, high = D("-0.05"), D("0.20")
g_terminal = D("0.015")
terminal_pe = (1-g_terminal/roic)/(r-g_terminal)
for _ in range(100):
    growth = (low+high)/2
    value = sum(normal_profit*(1+growth)**y*payout/(1+r)**y for y in range(1,11))
    value += normal_profit*(1+growth)**10*(1+g_terminal)*terminal_pe/(1+r)**10
    if value < mcap:
        low = growth
    else:
        high = growth

result = {"metrics":metrics,"ttm":ttm,"cashflow_bridge":bridge,"three_year":three,"ten_year":ten,
          "toolkit_k":k,"weighted_pv_price":weighted_value,"weighted_cashflow_irr_pct":weighted_irr,
          "weighted_toolkit_approx_irr_pct":weighted_approx,"flip_2pp":flip,"flip_1pp":flip1,
          "reverse_earnings_growth_pct":(low+high)/2*100,
          "weighted_value_20pct_discount":weighted_value*D("0.8"),
          "assumptions_note":"Probabilities and all valuation parameters are judgmental, not forecasts; no separate cash add-back."}

(HERE/"results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str)+"\n",encoding="utf-8")
(HERE/"terminal-config.json").write_text(json.dumps({"东阿阿胶":spec},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

log = io.StringIO()
with contextlib.redirect_stdout(log):
    rigor.verify_market_cap(price, shares, D(data["reported_market_cap"]), "CNY")
    rigor.verify_valuation(price, eps=ttm["profit"]/shares, bvps=metrics["bvps"],
                           fcf_per_share=ttm["fcf"]/shares)
    rigor.cross_validate("2025收入", {"公司年报":a["revenue"],"新华社亿元换算":D("6700000000")}, "CNY", tolerance_pct=1)
    rigor.cross_validate("2025归母", {"公司年报":a["profit"],"新华社亿元换算":D("1739000000")}, "CNY", tolerance_pct=1)
    rigor.cross_validate("2025经营现金流", {"公司年报":a["ocf"],"新华社亿元换算":D("2289000000")}, "CNY", tolerance_pct=1)
    rigor.cross_validate("2026Q3应收", {"公司季报":new["ar"],"蓝鲸亿元换算":D("893000000")}, "CNY", tolerance_pct=1)
    rigor.cross_validate("2026Q3经营现金流", {"公司季报":new["ocf"],"观点网亿元换算":D("400000000")}, "CNY", tolerance_pct=1)
    rigor.three_scenario_valuation(price, eps, shares/D("100000000"), D(".10"),D(".05"),D("-.05"),20,16,12,years=3,currency="CNY")
(HERE/"financial-rigor.txt").write_text(clean_log(log.getvalue()),encoding="utf-8")

commands = {
    "terminal-audit.txt": ["audit","--currency","CNY","--r",str(r),"--roic",str(roic),"--g","0,0.015,0.02","--rf",str(rf_tool),"--beta","1.0","--discrete-risks",assumptions["discrete_risks"]],
    "terminal-flip-2pp.txt": ["flip","--config",str(HERE/"terminal-config.json"),"--name","东阿阿胶","--r",str(r),"--delta","0.02","--currency","CNY","--g-shift","0","--rf",str(rf_tool)],
    "terminal-flip-1pp.txt": ["flip","--config",str(HERE/"terminal-config.json"),"--name","东阿阿胶","--r",str(r),"--delta","0.01","--currency","CNY","--g-shift","0","--rf",str(rf_tool)]}
for filename, args in commands.items():
    process = subprocess.run([sys.executable,str(ROOT/"tools/terminal_value.py"),*args],capture_output=True,text=True,encoding="utf-8")
    (HERE/filename).write_text(clean_log(process.stdout+process.stderr),encoding="utf-8")
    if process.returncode:
        raise RuntimeError(filename + " failed: " + process.stdout + process.stderr)
print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
