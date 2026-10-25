"""Audit the frozen report sample; distinguish facts, derived values, and assumptions."""
import contextlib
import io
import json
import re
from pathlib import Path
import sys
from decimal import Decimal

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import report_audit

D = Decimal
inputs = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
result = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
report = HERE.parent / "东阿阿胶研究报告-20261025.md"
points = report_audit.extract_data_points(report.read_text(encoding="utf-8"))
sample = report_audit.sample_points(points, ratio=.15, seed=20261025)
q3 = inputs["ytd_2026q3"]
old = inputs["ytd_2025q3"]
metrics = result["metrics"]
three = result["three_year"]
ten = result["ten_year"]

checks = {
    "营业利润率 · 2025年前三季度": (D(old["operating_profit"])/D(old["revenue"])*100, "S1 p11 上年营业利润/收入；公式复算", "derived"),
    "销售费用率 · 2026年前三季度": (D(q3["selling"])/D(q3["revenue"])*100, "S1 p11 销售费用/收入；公式复算", "derived"),
    "经营现金流净额 · 2026年前三季度": (D(q3["ocf"])/D("1e8"), "S1 p13；S11观点网4.00亿元交叉", "disclosed"),
    "购建长期资产现金支出 · 2026年前三季度": (D(q3["capex"])/D("1e8"), "S1 p13原件；仅公司底层来源", "disclosed"),
    "营业收入 · 2024原披露": (D(inputs["annual_original"]["2024"]["revenue"])/D("1e8"), "S4 p9调整前列；S5 2024年报", "disclosed"),
    "营业收入 · 2024按2025年报重述": (D(inputs["annual_restated"]["2024"]["revenue"])/D("1e8"), "S4 p9调整后列，已视觉复核", "disclosed"),
    "营业收入 · 对原数增速": ((D(inputs["annual_original"]["2025"]["revenue"])/D(inputs["annual_original"]["2024"]["revenue"])-1)*100, "S4 p9；公式复算，非同口径有机增长", "derived"),
    "经营现金流 · 2025实际": (D(inputs["annual_original"]["2025"]["ocf"])/D("1e8"), "S4；S12新华社22.89亿元交叉", "disclosed"),
    "归母利润口径PE · 截至2026年9月TTM": (D(metrics["pe_ttm"]), "S1/S2/S4利润与S13股价/股本；Decimal复算", "derived"),
    "PB · 截至2026年9月TTM": (D(metrics["pb"]), "S1 p10归母净资产与S13市值；公式复算", "derived"),
    "毛驴养殖及驴肉／贸易 · 2025占比": (D("58386244.92")/D(inputs["annual_original"]["2025"]["revenue"])*100, "S4 p16产品表；公司披露单源", "disclosed"),
    "其他 · H1占比": (D("35825368.44")/D(inputs["h1_2026"]["revenue"])*100, "S3 p14产品表；公司披露单源", "disclosed"),
    "2026-03-31 · 应收账款净额": (D("506599547.50")/D("1e8"), "S6 2026Q1资产负债表", "disclosed"),
    "两项合计 · 金额": (D(metrics["cash_financial_assets"])/D("1e8"), "S1 p9货币资金加交易性资产，非现金等价物", "derived"),
    "悲观 · EPS年增速假设": (D("-5"), "inputs.json三年悲观增速；假设一致性，不是外部核验", "assumption"),
    "悲观 · 三年后EPS": (D(three[0]["eps_year3"]), "扣非TTM每股利润*(1-5%)^3；模型复算", "scenario_calculation"),
    "基准 · 三年后PE假设": (D("16"), "inputs.json三年基准PE；假设一致性，不是外部核验", "assumption"),
    "基准 · 含假设分红的年化IRR": (D(three[1]["cashflow_irr_pct"]), "三年各期分红与退出价现金流求根", "scenario_calculation"),
    "基准 · 对46.96元价格变化": (D(three[1]["price_change_pct"]), "三年基准退出价/现价-1；模型复算", "scenario_calculation"),
    "乐观 · 对46.96元价格变化": (D(three[2]["price_change_pct"]), "三年乐观退出价/现价-1；模型复算", "scenario_calculation"),
    "乐观 · 三年后价格": (D(three[2]["price_year3"]), "扣非TTM每股利润*(1+10%)^3*20；模型复算", "scenario_calculation"),
    "乐观 · 第十年利润（亿元）": (D(ten[2]["profit_year10"])/D("1e8"), "扣非TTM利润*(1+10%)^10；模型复算", "scenario_calculation"),
    "2025收入 · 第二来源": (D("67"), "S12新华网2026-03-25报道；与S4原件67.0047亿元相核", "disclosed")
}

# The generic extractor mistakes a year and a month inside prose for financial values.
excluded_labels = {
    "分红 · 已确认事实": "2025是年度，不是分红金额。分红执行状态另对S9法定公告核验。",
    "新一批拟注销 · 已确认事实": "10是公告月份，不是注销股数；拟注销状态另对S9核验。"
}
audited, excluded = [], []
for point in sample:
    if point["label"] in excluded_labels:
        excluded.append({**point,"reason":excluded_labels[point["label"]]})
        continue
    if point["label"] not in checks:
        raise ValueError("Review the new sampled item before publication: " + point["label"])
    value, source, kind = checks[point["label"]]
    audited.append({**point,"fetched_value":float(value),"fetched_source":source,"audit_kind":kind})

audited += [
    {"id":1001,"label":"重点复核：应收账款同季同比","reported_value":70.11,"unit":"%",
     "fetched_value":float(D(metrics["ar_yoy_pct"])),"fetched_source":"S1与S2应收原数相除；S11蓝鲸70.11%",
     "audit_kind":"derived"},
    {"id":1002,"label":"重点复核：完整经营现金桥净减少","reported_value":9.1004,"unit":"亿元",
     "fetched_value":float((D(old["ocf"])-D(q3["ocf"]))/D("1e8")),
     "fetched_source":"S1 p13逐项现金变化合计，并与累计OCF差额逐分对账", "audit_kind":"derived"}
]
log = io.StringIO()
with contextlib.redirect_stdout(log):
    print("Scope: sampled disclosed figures + formula checks. Assumptions are NOT externally verified facts.")
    print(f"Extracted {len(points)}; randomly selected {len(sample)}; date/month false positives {len(excluded)}; targeted additions 2.")
    outcome = report_audit.render_verdict(audited, report.name)
    print("Additional boundaries: issuer mirrors are one source; company disclosures do not verify terminal sell-through.")
payload = {"seed":20261025,"extracted_count":len(points),"random_sample":sample,
           "excluded_non_financial":excluded,"checks":audited,"outcome":outcome}
(HERE/"audit-results.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
plain_log = re.sub(r"\x1b\[[0-9;]*m", "", log.getvalue())
plain_log = "\n".join(line.rstrip() for line in plain_log.splitlines()).rstrip() + "\n"
(HERE/"audit-verdict.txt").write_text(plain_log,encoding="utf-8")
print(log.getvalue())
if outcome["verdict"] != "PASS":
    raise SystemExit(1)
