"""Offline Fenjiu evidence calculations; Decimal inputs, no live fetches.

Run with --refresh-manifest to inventory the existing local source cache.
Inputs and vendor-snapshot are portable; caches are optional for arithmetic.
"""
import argparse
import contextlib
import hashlib
import io
import json
import re
import sys
from decimal import Decimal, getcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import financial_rigor as rigor

D = rigor.exact
getcontext().prec = 40
Y = D("100000000")
METRICS = ("revenue", "profit", "core", "cfo")


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"), parse_float=Decimal)


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def pv(flows, rate):
    return sum((value / (1 + rate) ** year for year, value in enumerate(flows, 1)), D(0))


def irr(price, flows):
    if price <= 0 or any(value < 0 for value in flows) or not any(flows):
        raise ValueError("Positive price and nonnegative receipts required")
    lo, hi = D("-.9999"), D("3")
    while pv(flows, hi) > price:
        hi = hi * 2 + 1
    for _ in range(180):
        mid = (lo + hi) / 2
        if pv(flows, mid) > price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def scenario(item, terms, shares, price, initial_core_profit):
    profits = [initial_core_profit*(1+D(item["annual_growth"]))**year for year in range(1, terms["years"]+1)]
    payouts = [D(value) for value in terms["annual_payouts"]]
    if len(profits) != len(payouts) or len(profits) != terms["years"]:
        raise ValueError("Scenario length mismatch")
    eps = [value / shares for value in profits]
    dividends = [value * payout for value, payout in zip(eps, payouts)]
    terminal = eps[-1] * D(item["exit_pe"])
    flows = dividends[:-1] + [dividends[-1] + terminal]
    rate = irr(price, flows)
    return {"name": item["name"], "annual_growth_pct": D(item["annual_growth"])*100,
            "initial_core_profit": initial_core_profit/Y, "initial_EPS_CNY": initial_core_profit/shares,
            "annual_profit": [value / Y for value in profits],
            "annual_EPS_CNY": eps, "annual_payouts": payouts, "exit_PE": D(item["exit_pe"]),
            "annual_dividend_CNY": dividends, "dividend_sum_CNY": sum(dividends),
            "terminal_price_CNY": terminal, "cashflows_CNY": [-price] + flows,
            "IRR_pct": rate * 100, "IRR_residual_CNY": pv(flows, rate) - price,
            "PV10_CNY": pv(flows, D(terms["discount_rate"])),
            "NPV10_CNY": pv(flows, D(terms["discount_rate"])) - price,
            "no_dividend_IRR_pct": irr(price, [D(0)] * (len(flows)-1) + [terminal]) * 100}


def required_growth(initial_eps, price, payout, multiple, rate, years):
    def value(growth):
        eps = [initial_eps*(1+growth)**year for year in range(1, years+1)]
        flows = [value*payout for value in eps]
        flows[-1] += eps[-1]*multiple
        return pv(flows, rate)
    lo, hi = D("-.9999"), D("1")
    while value(hi) < price:
        hi = hi*2+1
    for _ in range(180):
        mid = (lo+hi)/2
        if value(mid) < price:
            lo = mid
        else:
            hi = mid
    growth = (lo+hi)/2
    return {"annual_growth_pct": growth*100, "price_CNY": price, "exit_PE": multiple,
        "payout": payout, "target_IRR_pct": rate*100, "years": years,
        "PV_residual_CNY": value(growth)-price}


def calculate():
    data = load("inputs.json")
    fin = {period: {key: D(value) for key, value in row.items()} for period, row in data["financial"].items()}
    for year in ("2025", "2026"):
        a, b = fin[year+"YTD"], fin[year+"H1"]
        fin[year+"Q3"] = {key: a[key]-b[key] for key in a.keys() & b.keys()}
    a, b = fin["2025"], fin["2025YTD"]
    fin["2025Q4"] = {key: a[key]-b[key] for key in a.keys() & b.keys()}
    fin["2026Q1"] = {key: D(value) for key, value in data["primary_quarter_checks"]["2026Q1"].items()}
    a, b = fin["2026H1"], fin["2026Q1"]
    fin["2026Q2"] = {key: a[key]-b[key] for key in a.keys() & b.keys()}
    out = {"cutoff": data["cutoff"], "source_header": data["source_header"],
           "units": "Amounts CNY 100 million unless key says CNY, pct, days, shares or multiple; pct is percent.",
           "periods": {}, "growth": {}}
    for period, row in fin.items():
        result = {key: value/Y for key, value in sorted(row.items())}
        result.update(parent_margin_pct=row["profit"]/row["revenue"]*100,
                      core_margin_pct=row["core"]/row["revenue"]*100,
                      nonrecurring_profit=(row["profit"]-row["core"])/Y,
                      cfo_parent_ratio_pct=row["cfo"]/row["profit"]*100 if row["profit"] > 0 else None)
        if "cost" in row:
            result["gross_margin_pct"] = (1-row["cost"]/row["revenue"])*100
        for field in ("sales_expense", "admin_expense", "rd_expense", "tax_surcharges", "sale_cash"):
            if field in row:
                result[field+"_revenue_pct"] = row[field]/row["revenue"]*100
        if "income_tax" in row:
            result["effective_income_tax_pct"] = row["income_tax"]/row["pbt"]*100
        if "capex" in row:
            result["simple_fcf"] = (row["cfo"]-row["capex"])/Y
        out["periods"][period] = result
    for suffix in ("H1", "YTD", "Q3"):
        now, old = fin["2026"+suffix], fin["2025"+suffix]
        out["growth"][suffix] = {key: {"absolute_change": (now[key]-old[key])/Y,
            "pct": (now[key]-old[key])/abs(old[key])*100 if old[key] else None}
            for key in sorted(now.keys() & old.keys())}
        out["growth"][suffix]["margin_changes_pp"] = {key: out["periods"]["2026"+suffix][key]-out["periods"]["2025"+suffix][key]
            for key in ("gross_margin_pct", "parent_margin_pct", "sales_expense_revenue_pct", "tax_surcharges_revenue_pct", "effective_income_tax_pct")}
    ttm = {key: fin["2025"][key]+fin["2026YTD"][key]-fin["2025YTD"][key]
           for key in fin["2025"].keys() & fin["2026YTD"].keys() & fin["2025YTD"].keys()}
    shares, price = D(data["shares"]), D(data["quote"]["price"])
    cap = price*shares
    out["ttm"] = {key: value/Y for key, value in sorted(ttm.items())}
    out["ttm"].update(EPS_CNY=ttm["profit"]/shares, core_EPS_CNY=ttm["core"]/shares,
                      simple_fcf=(ttm["cfo"]-ttm["capex"])/Y)
    bal = {period: {key: D(value) for key, value in row.items()} for period, row in data["balance"].items()}
    now, old = bal["2026Q3"], bal["2025end"]
    out["balance"] = {period: {key: value/Y for key, value in row.items()} for period, row in bal.items()}
    out["balance_changes"] = {period+"_to_2026Q3": {key: {"change": (now[key]-base[key])/Y,
        "pct": (now[key]/base[key]-1)*100 if base[key] else None} for key in sorted(now.keys() & base.keys())}
        for period, base in bal.items() if period != "2026Q3"}
    out["valuation"] = {"price_CNY": price, "registered_shares": shares, "market_cap": cap/Y,
        "TTM_PE": cap/ttm["profit"], "TTM_core_PE": cap/ttm["core"],
        "PB": cap/now["parent_equity"], "BVPS_CNY": now["parent_equity"]/shares,
        "paid_2025_earnings_dividend_CNY": D(data["notes"]["dividend_paid_2026_per_share"]),
        "trailing_paid_dividend_yield_pct": D(data["notes"]["dividend_paid_2026_per_share"])/price*100,
        "paid_dividend_to_FY2025_profit_pct": D(data["notes"]["dividend_paid_2026_total"])/fin["2025"]["profit"]*100,
        "same_dividend_to_TTM_profit_pct": D(data["notes"]["dividend_paid_2026_total"])/ttm["profit"]*100,
        "TTM_earnings_yield_pct": ttm["profit"]/cap*100,
        "simple_FCF_yield_pct": (ttm["cfo"]-ttm["capex"])/cap*100,
        "caveat": "Paid DPS belongs to FY2025 and is backward-looking, not a forward promised dividend. TTM is FY2025 + 2026YTD - 2025YTD, never YTD annualisation."}
    debt = sum(now[key] for key in ("short_debt", "long_debt", "bonds", "current_noncurrent_debt", "lease_liability"))
    out["cash_and_quality"] = {
        "cash_equivalents": now["cash_equivalents"]/Y,
        "named_lease_and_current_noncurrent_debt": debt/Y,
        "cash_equivalents_less_named_debt": (now["cash_equivalents"]-debt)/Y,
        "other_current_assets_excluded_pending_breakdown": now["other_current_assets"]/Y,
        "bills_financing_excluded_from_cash": now["bills_financing"]/Y,
        "Q3_freely_distributable_excess_cash": None,
        "cash_caveat": data["notes"]["q3_liquidity_caveat"],
        "debt_caveat": data["notes"]["q3_lease_caveat"],
        "DSO_receivables_only_273_days": (now["receivables"]+old["receivables"])/2/fin["2026YTD"]["revenue"]*273,
        "DSO_including_bills_financing_273_days": (now["receivables"]+old["receivables"]+now["bills_financing"]+old["bills_financing"])/2/fin["2026YTD"]["revenue"]*273,
        "DIO_273_days": (now["inventory"]+old["inventory"])/2/fin["2026YTD"]["cost"]*273,
        "goodwill_intangibles_assets_pct": (now["goodwill"]+now["intangibles"])/now["assets"]*100,
        "turnover_caveat": "273 days and mean opening/closing balances. Company inventory is not dealer inventory, DIO not a channel clearance forecast. Sales cash includes tax and settlement timing; revenue excludes VAT.",
        "investment_cash_net_outflow_YTD": (D(data["notes"]["ytd_investment_paid"])-D(data["notes"]["ytd_investment_recovered"]))/Y,
        "YTD_simple_fcf_less_all_other_financing_outflow": (fin["2026YTD"]["cfo"]-fin["2026YTD"]["capex"]-D(data["notes"]["ytd_other_financing_outflow"]))/Y,
        "fcf_caveat": "CFO minus cash capex is a simple measure, not owner earnings. New noncash leases do not appear in cash capex. Subtracting all other financing cash outflow is a conservative sensitivity, not a fully identified lease-payment figure."}
    notes = data["notes"]
    out["H1_liquidity_notes"] = {key: D(notes[key])/Y for key in ("h1_term_deposits_interest", "yearend_term_deposits_interest", "h1_term_deposit_pledged", "h1_long_deposit_pledged", "h1_bills_pledged", "h1_restricted_assets_total", "h1_cash_restricted", "h1_current_long_deposit")}
    out["H1_liquidity_notes"]["restricted_assets_reconcile"] = sum(D(notes[key]) for key in ("h1_term_deposit_pledged", "h1_long_deposit_pledged", "h1_bills_pledged", "h1_cash_restricted")) == D(notes["h1_restricted_assets_total"])
    out["capex_commitment_notes"] = {"project_2030_budget": D(notes["h1_capex_project_2030_budget"])/Y,
        "project_2030_spent_pct": D(notes["h1_capex_project_2030_spent_pct"]),
        "fenqing_project_budget": D(notes["h1_capex_project_fenqing_budget"])/Y,
        "fenqing_project_spent_pct": D(notes["h1_capex_project_fenqing_spent_pct"]),
        "note": "H1 project table, budget not a new unconditional payment commitment. Cash capex excludes noncash lease additions, some engineering/materials can be settled by notes payable; low period cash capex is not proof of low future investment need."}
    out["inventory_split_H1"] = {key: D(notes[key])/Y for key in ("h1_finished_goods", "yearend_finished_goods", "h1_semi_finished", "yearend_semi_finished")}
    out["inventory_split_H1"].update(finished_goods_change_pct=(D(notes["h1_finished_goods"])/D(notes["yearend_finished_goods"])-1)*100,
        semi_finished_change_pct=(D(notes["h1_semi_finished"])/D(notes["yearend_semi_finished"])-1)*100,
        finished_goods_inventory_pct=D(notes["h1_finished_goods"])/bal["2026H1"]["inventory"]*100)
    q, p = fin["2026Q3"], fin["2025Q3"]
    bridge = {"revenue_change": q["revenue"]-p["revenue"]}
    for field in ("cost", "sales_expense", "admin_expense", "rd_expense", "finance_expense", "tax_surcharges", "income_tax"):
        bridge[field+"_effect"] = p[field]-q[field]
    bridge["other_pretax_effect"] = q["pbt"]-p["pbt"]-sum(value for key,value in bridge.items() if key != "income_tax_effect")
    bridge["minority_effect"] = (p["net_profit"]-p["profit"])-(q["net_profit"]-q["profit"])
    out["Q3_parent_profit_bridge"] = {key: value/Y for key,value in bridge.items()}
    out["Q3_parent_profit_bridge"]["sum_equals_profit_change"] = sum(bridge.values()) == q["profit"]-p["profit"]
    out["primary_quarter_reconciliation"] = [{"period": period, "metric": key, "calculated_CNY": fin[period][key],
        "issuer_CNY": D(value), "passed": fin[period][key] == D(value)}
        for period, checks in data["primary_quarter_checks"].items() for key,value in checks.items()]
    out["scenarios"] = [scenario(item, data["scenario_terms"], shares, price, ttm["core"]) for item in data.get("scenarios", [])]
    if data.get("scenario_terms"):
        out["scenario_terms"] = data["scenario_terms"]
        out["required_growth_for_10pct_IRR"] = required_growth(ttm["core"]/shares, price, D("0.65"), D("16"), D("0.10"), 5)
        out["flat_profit_requirement"] = {}
        payouts = [D(value) for value in data["scenario_terms"]["annual_payouts"]]
        for pe in ("15", "18", "22"):
            flows = payouts[:-1]+[payouts[-1]+D(pe)]
            eps = price/pv(flows, D(data["scenario_terms"]["discount_rate"]))
            out["flat_profit_requirement"][pe] = {"annual_profit_for_10pct_return": eps*shares/Y}
    return data, out


def cross_source(data):
    vendor = load("vendor-snapshot.json")
    checks = []
    for period, values in vendor["financial"].items():
        for metric in METRICS:
            a, b = D(data["financial"][period][metric]), D(values[metric])
            deviation = abs(a-b)/abs(a)*100 if a else (D(0) if b == 0 else None)
            result = rigor.cross_validate(period+":"+metric, {"issuer_filing": a, "Eastmoney": b}, unit="CNY yuan", tolerance_pct=1)
            checks.append({"label": period+":"+metric, "period": period, "metric": metric, "primary": a, "secondary": b,
                "primary_source": data["notes"]["source_primary_period_map"][period], "secondary_source": "S4 vendor-snapshot.json",
                "deviation_pct_primary_denominator": deviation, "tolerance_pct": 1,
                "passed": deviation is not None and deviation <= 1 and result["all_consistent"]})
    return checks


def refresh_manifest():
    cache = ROOT / "local" / "山西汾酒-20261107" / "fenjiu"
    records = {}
    for meta in sorted(cache.glob("*.meta.json")):
        name = meta.name.removesuffix(".meta.json")
        item = json.loads(meta.read_text(encoding="utf-8"))
        item["response_sha256_as_recorded_at_capture"] = item.pop("sha256", None)
        item["cached_artifacts"] = []
        for ext in (".pdf", ".html", ".txt", ".json"):
            path = cache / (name+ext)
            if path.exists():
                item["cached_artifacts"].append({"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        records[name] = item
    for path in sorted(cache.glob("*-tavily.md")):
        records[path.stem] = {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "retrieved_on": "2026-11-07", "note": "Full issuer-announcement HTML mirror read through Tavily extract, original raw response timestamp not persisted."}
    previous = load("source-manifest.json") if (HERE / "source-manifest.json").exists() else {}
    save("source-manifest.json", {"cutoff": "2026-11-07", "sources": records,
        "source_ids": load("inputs.json")["sources"],
        "visual_review": previous.get("visual_review", {"status": "pending"}),
        "independence": "Issuer documents and Eastmoney are separate publishing channels, not independent audits. Quote providers are checked separately; exact shares from issuer statements and dividend notice.",
        "portable_scope": "Offline inputs and vendor snapshot reproduce arithmetic and 28 cross-source checks without local cache.",
        "gaps": ["Q3 unaudited and lacks full footnotes.", "Q3 term-deposit composition and encumbrances are not refreshed; other current assets not wholly cash.",
                 "No verified freely distributable excess cash balance; bills and inventory excluded.", "Dealer sell-through/inventory unavailable from accounting inventory.",
                 "Maintenance versus expansion cash capex not separately disclosed; noncash lease additions excluded from simple FCF."]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-manifest", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    data, out = calculate()
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        market_ok = rigor.verify_market_cap(data["quote"]["price"], data["shares"], data["quote"]["reported_market_cap"], "CNY")
        value_check = rigor.verify_valuation(data["quote"]["price"], out["ttm"]["EPS_CNY"], out["valuation"]["BVPS_CNY"],
            fcf_per_share=out["ttm"]["simple_fcf"]*Y/D(data["shares"]), dividend=data["notes"]["dividend_paid_2026_per_share"])
        rows = cross_source(data)
    clean = re.sub(r"\x1b\[[0-9;]*m", "", log.getvalue())
    clean = "\n".join(line.rstrip() for line in clean.splitlines())+"\n"
    out["financial_rigor"] = {"market_cap_passed": market_ok, "valuation_checks": value_check,
        "cross_source_count": len(rows), "cross_source_all_passed": all(row["passed"] for row in rows)}
    (HERE / "financial-rigor.txt").write_text(clean, encoding="utf-8")
    save("calculations.json", out)
    save("cross-source.json", rows)
    if args.refresh_manifest:
        refresh_manifest()
    print(json.dumps({"valuation": out["valuation"], "ttm": out["ttm"], "scenarios": out["scenarios"],
        "cross_source_count": len(rows), "cross_source_all_passed": all(row["passed"] for row in rows)}, ensure_ascii=False, indent=2, default=str))
    if not market_ok or len(rows) != 28 or not all(row["passed"] for row in rows) or not all(row["passed"] for row in out["primary_quarter_reconciliation"]):
        raise SystemExit("Verification failed")


if __name__ == "__main__":
    main()
