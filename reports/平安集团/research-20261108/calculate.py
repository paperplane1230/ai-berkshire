"""Reproducible, report-local Decimal calculations; no network or private data."""
import contextlib
import io
import json
import re
import sys
sys.dont_write_bytecode=True
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import financial_rigor as rigor

OUT = Path(__file__).resolve().parent
def dec(value):
    return rigor.exact(value)

def calculate():
    a, h, fx = dec("54.50"), dec("53.15"), dec("0.8517017000")
    ash, hsh = dec("10660065083"), dec("7447576912")
    shares = ash + hsh
    scale = dec("100000000")
    profit_ttm = dec("1347.78") + dec("966.45") - dec("1328.56")
    opat_ttm = dec("1344.15") + dec("1259.05") - dec("1162.64")
    eps = profit_ttm * scale / shares
    ops = opat_ttm * scale / shares
    bvps = dec("10443.66") * scale / shares
    evps = dec("15678.00") * scale / shares
    hrmb = h * fx
    market = {"a_price_cny": a, "h_price_hkd": h, "h_price_cny": hrmb,
              "fx_cny_per_hkd": fx, "a_shares": ash, "h_shares": hsh, "all_shares": shares,
              "a_class_cap_cny_yi": a * ash / scale, "h_class_cap_hkd_yi": h * hsh / scale,
              "h_class_cap_cny_yi": h * hsh * fx / scale,
              "actual_combined_cap_cny_yi": (a*ash + h*hsh*fx)/scale,
              "a_reference_all_cap_cny_yi": a*shares/scale,
              "h_discount_to_a_pct": (1-hrmb/a)*100,
              "net_profit_ttm_yi": profit_ttm, "opat_ttm_yi": opat_ttm,
              "economic_eps": eps, "economic_opat_per_share": ops, "bvps": bvps, "h1_evps": evps}
    for label, price in (("a", a), ("h", hrmb)):
        market.update({label+"_pe":price/eps, label+"_popat":price/ops, label+"_pb":price/bvps,
                       label+"_pev_h1":price/evps, label+"_yield_pct":dec("2.73")/price*100,
                       label+"_reverse_div_growth_r10_pct":(price*dec("0.10")-dec("2.73"))/(price+dec("2.73"))*100})
    derivations = {"nbv_q3_2026": dec("309.87")-dec("248.47"),
                   "nbv_q3_2025": dec("357.24")-dec("223.35"),
                   "q3_net_profit": dec("966.45")-dec("925.85"),
                   "q3_opat": dec("1259.05")-dec("841.96"),
                   "ex_am_opat_growth_pct": ((dec("1259.05")-dec("194.23"))/(dec("1162.64")-dec("26.54"))-1)*100,
                   "am_increment": dec("194.23")-dec("26.54"),
                   "normalization_nine_month": dec("1259.05")-(dec("194.23")-dec("26.54")),
                   "parent_invest_cash_less_div_interest": dec("440.24")-dec("427.58"),
                   "normalized_profit_base_yi": dec("1400")}
    derivations["nbv_q3_yoy_pct"] = (derivations["nbv_q3_2026"]/derivations["nbv_q3_2025"]-1)*100
    derivations["normalization_annualized_sensitivity"] = derivations["normalization_nine_month"]*4/3
    cases=[]
    for name,p,m in (("bear","1100","6"),("base","1400","8"),("bull","1600","10")):
        value=dec(p)*dec(m)*scale/shares
        cases.append({"case":name,"normalized_opat_yi":dec(p),"multiple":dec(m),"immediate_value_cny":value,
                      "hkd_equivalent_at_snapshot_fx":value/fx,"a_price_gap_pct":(value/a-1)*100,
                      "h_price_gap_pct":(value/hrmb-1)*100})
    ddm=[]
    for r in ("0.09","0.10","0.11"):
        for g in ("0.02","0.03","0.04"):
            value=dec("2.73")*(1+dec(g))/(dec(r)-dec(g))
            ddm.append({"r":dec(r),"g":dec(g),"value_cny":value})
    return {"market":market,"derivations":derivations,"immediate_scenarios":cases,"perpetual_ddm_sensitivity":ddm}

def main():
    data=calculate()
    (OUT/"calculations.json").write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    log=io.StringIO()
    with contextlib.redirect_stdout(log):
        rigor.verify_market_cap("54.50","10660065083","580973547023.50","CNY-A class")
        rigor.verify_market_cap("53.15","7447576912","395838712872.80","HKD-H class")
        rigor.verify_valuation("54.50",eps=data["market"]["economic_eps"],bvps=data["market"]["bvps"],dividend="2.73")
        rigor.verify_valuation(data["market"]["h_price_cny"],eps=data["market"]["economic_eps"],bvps=data["market"]["bvps"],dividend="2.73")
        raw=json.loads((ROOT/"local/三季报-20261108/pingan/eastmoney.json").read_text(encoding="utf-8"))["result"]["data"]
        q3=next(x for x in raw if x["REPORT_DATE"].startswith("2026-09-30"))
        for name,value,field in (("2026九月收入",728134000000,"TOTALOPERATEREVE"),("2026九月归母",96645000000,"PARENTNETPROFIT"),
                                 ("2026九月NBV",30987000000,"NBV_LIFE"),("2026九月经营现金流",566872000000,"NETCASH_OPERATE_PK"),
                                 ("2026九月保险服务收入",422944000000,"EARNED_PREMIUM"),("基本EPS",5.55,"EPSJB"),("稀释EPS",4.79,"EPSXS")):
            rigor.cross_validate(name,{"公司原始报告":value,"东方财富独立采集":q3[field]},tolerance_pct=1)
    clean="\n".join(line.rstrip() for line in re.sub(r"\x1b\[[0-9;]*m","",log.getvalue()).splitlines())+"\n"
    (OUT/"financial-rigor.txt").write_text(clean,encoding="utf-8")
    print(json.dumps(data,ensure_ascii=False,indent=2,default=str))

if __name__ == "__main__":
    main()
