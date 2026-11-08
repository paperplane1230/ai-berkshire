"""Local-only research calculations. No network or shared-tool edits."""
import contextlib
import io
import json
import re
import sys
from decimal import Decimal, getcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import financial_rigor as rigor

getcontext().prec = 38
D = rigor.exact
I = json.loads((OUT / "model-inputs.json").read_text(encoding="utf-8"))
EM_ROWS = json.loads((ROOT/"local/三季报-20261108/yangtze/eastmoney.json").read_text(encoding="utf-8"))["result"]["data"]
EM = {row["REPORT_DATE"][:10]:row for row in EM_ROWS}
v = lambda key: D(I[key])
E = D("100000000")
P, S = v("price"), v("shares")

def irr(cashflows):
    lo, hi = D("-0.99"), D("10")
    for _ in range(220):
        mid = (lo + hi) / 2
        npv = sum(cf / (1 + mid) ** t for t, cf in enumerate(cashflows))
        if npv > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

def pv(cashflows, rate):
    return sum(cf / (1 + D(rate)) ** t for t, cf in enumerate(cashflows[1:], 1))

ttm = v("annual_2025_profit") - v("ytd_2025_profit") + v("ytd_2026_profit")
eps = ttm / S
out = {"ttm_profit_yuan": ttm, "ttm_eps": eps, "market_cap_yi": P*S/E,
       "pe": P/eps, "pb": P/(v("equity")/S), "bvps": v("equity")/S,
       "historical_dividend_yield_pct": 1/P*100,
       "ttm_payout70_dividend": eps*v("payout"),
       "ttm_payout70_yield_pct": eps*v("payout")/P*100,
       "revenue_yoy_pct": (v("ytd_2026_revenue")/v("ytd_2025_revenue")-1)*100,
       "profit_yoy_pct": (v("ytd_2026_profit")/v("ytd_2025_profit")-1)*100,
       "gross_margin_pct": (1-v("ytd_2026_cost")/v("ytd_2026_revenue"))*100,
       "gross_margin_prior_pct": (1-v("ytd_2025_cost")/v("ytd_2025_revenue"))*100,
       "cfo_profit_ratio_pct": v("cfo_2026")/v("ytd_2026_profit")*100,
       "simple_fcf_yi": (v("cfo_2026")-v("capex_2026"))/E,
       "simple_fcf_prior_yi": (v("cfo_2025")-v("capex_2025"))/E,
       "simple_fcf_growth_pct": ((v("cfo_2026")-v("capex_2026"))/(v("cfo_2025")-v("capex_2025"))-1)*100,
       "q3_cfo_yi": (v("cfo_2026")-v("h1_cfo_2026"))/E,
       "q3_cfo_prior_yi": (v("cfo_2025")-v("h1_cfo_2025"))/E,
       "q3_capex_yi": (v("capex_2026")-v("h1_capex_2026"))/E,
       "financial_expense_saving_yi": (v("financial_expense_2025")-v("financial_expense_2026"))/E,
       "investment_income_delta_yi": (v("investment_income_2026")-v("investment_income_2025"))/E,
       "investment_income_share_pretax_pct": v("investment_income_2026")/v("total_profit_2026")*100,
       "investment_cash_accounting_ratio_pct": v("investment_cash_2026")/v("investment_income_2026")*100,
       "ar_increase_pct": (v("receivable_2026")/v("receivable_2025")-1)*100,
       "liability_ratio_pct": v("liabilities")/v("assets")*100,
       "receivable_days_proxy": ((v("receivable_2026")+v("receivable_2025"))/2)/v("ytd_2026_revenue")*273,
       "net_debt_cash_repaid_yi": (v("repayment_cash_2026")-v("borrowing_cash_2026"))/E,
       "pretax_delta_yi": (v("total_profit_2026")-v("total_profit_2025"))/E,
       "tax_delta_yi": (v("tax_2026")-v("tax_2025"))/E,
       "minority_delta_yi": (v("minority_profit_2026")-v("minority_profit_2025"))/E}
debt = sum(map(D, I["debt_2026"]))
out.update({"identified_debt_yi": debt/E,
            "debt_upper_proxy_yi": (debt+v("other_current_2026"))/E,
            "identified_net_debt_yi": (debt-v("cash_2026"))/E,
            "net_debt_upper_proxy_yi": (debt+v("other_current_2026")-v("cash_2026"))/E,
            "identified_current_debt_yi": (D(I["debt_2026"][0])+D(I["debt_2026"][1]))/E,
            "current_debt_with_other_upper_yi": (D(I["debt_2026"][0])+D(I["debt_2026"][1])+v("other_current_2026"))/E,
            "cash_current_debt_cover_pct": v("cash_2026")/(D(I["debt_2026"][0])+D(I["debt_2026"][1]))*100,
            "debt_2025_including_scp_yi": (sum(map(D,I["debt_2025"]))+v("short_financing_2025"))/E})
out["quarters"] = [
    {"period":"2025Q4", "revenue_yi":(v("annual_2025_revenue")-v("ytd_2025_revenue"))/E, "profit_yi":(v("annual_2025_profit")-v("ytd_2025_profit"))/E},
    {"period":"2026Q1", "revenue_yi":v("q1_2026_revenue")/E, "profit_yi":v("q1_2026_profit")/E},
    {"period":"2026Q2", "revenue_yi":(v("h1_2026_revenue")-v("q1_2026_revenue"))/E, "profit_yi":(v("h1_2026_profit")-v("q1_2026_profit"))/E},
    {"period":"2026Q3", "revenue_yi":v("q3_2026_revenue")/E, "profit_yi":v("q3_2026_profit")/E}]
out["scenarios"] = {}
for name, inputs in I["scenarios"].items():
    annual_eps = [D(inputs["first_eps"])*(1+D(inputs["growth"]))**t for t in range(5)]
    dividends = [e*v("payout") for e in annual_eps]
    terminal = annual_eps[-1]*D(inputs["terminal_pe"])
    cashflows = [-P]+dividends
    cashflows[-1] += terminal
    out["scenarios"][name] = {"annual_eps":annual_eps, "annual_dividends":dividends,
        "terminal_price":terminal, "dividend_total":sum(dividends),
        "cashflows":cashflows, "irr_pct":irr(cashflows)*100,
        "pv8":pv(cashflows,"0.08"), "pv10":pv(cashflows,"0.10")}
base = out["scenarios"]["base"]
out["base_terminal_pe_for_8pct"] = ((P-sum(cf/D("1.08")**t for t,cf in enumerate(base["annual_dividends"],1)))*D("1.08")**5)/base["annual_eps"][-1]
out["base_entry_price_irr"] = {str(price):irr([-D(price)]+base["cashflows"][1:])*100 for price in (22,24,25,26,28,30,32)}
tests = []
def check(name, passed):
    tests.append({"test": name, "pass": bool(passed)})
check("Q3 income reconciles to YTD minus H1", v("q3_2026_revenue")==v("ytd_2026_revenue")-v("h1_2026_revenue"))
check("Q3 profit reconciles to YTD minus H1", v("q3_2026_profit")==v("ytd_2026_profit")-v("h1_2026_profit"))
check("Six plants YTD generation sum rounding",sum(map(D,I["generation_ytd"]))==D("2250.5810"))
check("Six plants Q3 generation sum rounding",sum(map(D,I["generation_q3"]))==D("923.1406"))
check("Quarter sum reconciles TTM profit",sum(x["profit_yi"] for x in out["quarters"])*E==ttm)
em_ttm = D(str(EM["2025-12-31"]["PARENTNETPROFIT"]))-D(str(EM["2025-09-30"]["PARENTNETPROFIT"]))+D(str(EM["2026-09-30"]["PARENTNETPROFIT"]))
check("TTM EPS matches independent Eastmoney data",em_ttm/S==eps)
check("Market cap agrees Tencent within rounding",abs(P*S-v("reported_cap"))<D("500000"))
check("Net profit bridge pretax-tax-minorities",v("total_profit_2026")-v("tax_2026")-v("minority_profit_2026")==v("ytd_2026_profit"))
check("Debt definition excludes ordinary liabilities",debt<v("liabilities"))
check("Every dividend uses 70%, not all earnings",all(all(d==e*v("payout") for d,e in zip(s["annual_dividends"],s["annual_eps"])) for s in out["scenarios"].values()))
check("IRR discounted NPV residual tiny",all(abs(sum(cf/(1+s["irr_pct"]/100)**t for t,cf in enumerate(s["cashflows"])))<D("1e-25") for s in out["scenarios"].values()))
check("PV8 entry gives 8% IRR",abs(irr([-base["pv8"]]+base["cashflows"][1:])-D("0.08"))<D("1e-25"))
check("Scenario ordered and payout not extra terminal cash",out["scenarios"]["bear"]["irr_pct"]<base["irr_pct"]<out["scenarios"]["bull"]["irr_pct"] and all(s["cashflows"][-1]==s["terminal_price"]+s["annual_dividends"][-1] for s in out["scenarios"].values()))
qq=(ROOT/"local/三季报-20261108/yangtze/qq.txt").read_text(encoding="utf-8").split("~")
sina=(ROOT/"local/三季报-20261108/yangtze/sina.txt").read_text(encoding="utf-8").split(",")
check("Independent quote date and close agree",D(qq[3])==P and D(sina[3])==P and qq[30].startswith("20261106") and sina[30]=="2026-11-06")
check("Q3 income and profit equal independent source",D(str(EM["2026-09-30"]["TOTALOPERATEREVE"]))==v("ytd_2026_revenue") and D(str(EM["2026-09-30"]["PARENTNETPROFIT"]))==v("ytd_2026_profit"))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rigor.verify_market_cap(P,S,v("reported_cap"),"CNY")
    rigor.verify_valuation(P,eps,v("equity")/S,None,D("1"))
    em = EM["2026-09-30"]
    for field,key in [("TOTALOPERATEREVE","ytd_2026_revenue"),("PARENTNETPROFIT","ytd_2026_profit")]:
        rigor.cross_validate(key,{"company_q3":v(key),"Eastmoney":D(str(em[field]))},"CNY",1.0)
    rigor.cross_validate("CFO",{"company_q3":v("cfo_2026"),"Eastmoney_MGJYXJJE_times_shares":D(str(em["MGJYXJJE"]))*S},"CNY",1.0)
    for day in ("2023-12-31","2024-12-31","2025-12-31"):
        primary={"2023-12-31":("78143535736.10","27244616815.27"),"2024-12-31":("84491870566.52","32496172808.65"),"2025-12-31":("86241940222.20","34502809176.39")}[day]
        for field,value in zip(("TOTALOPERATEREVE","PARENTNETPROFIT"),primary):
            rigor.cross_validate(day+field,{"annual_2025_three_year_table":D(value),"Eastmoney":D(str(EM[day][field]))},"CNY",1.0)
    for name,s in I["scenarios"].items():
        rigor.three_scenario_valuation(P,D(s["first_eps"]),S/E,D(s["growth"]),D(s["growth"]),D(s["growth"]),D(s["terminal_pe"]),D(s["terminal_pe"]),D(s["terminal_pe"]),4,"CNY")
(OUT/"calculations.json").write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
(OUT/"tests.json").write_text(json.dumps(tests,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(OUT/"financial-rigor.txt").write_text(re.sub(r"\x1b\[[0-9;]*m","",buf.getvalue()),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
print("Tests: %s/%s" % (sum(t["pass"] for t in tests),len(tests)))
if not all(t["pass"] for t in tests):
    raise SystemExit(1)
