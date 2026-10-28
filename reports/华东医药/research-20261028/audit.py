"""Frozen-seed financial audit. Assumptions never count as external verification."""
import contextlib
import hashlib
import io
import json
import math
import re
import sys
from decimal import Decimal as D
from pathlib import Path
from random import Random

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/"tools"))
import report_audit

REPORT=HERE.parent/"华东医药研究报告-20261028.md"
I=json.loads((HERE/"inputs.json").read_text(encoding="utf-8"))
R=json.loads((HERE/"results.json").read_text(encoding="utf-8"))
# Freeze the eligible population after reviewing the complete extraction list.
# Exclusions are lexical noise only, never unfavourable financial figures.
NOISE={
    "医药工业/中美华东，含CSO · 盈利与资本特征":"2025 is the reporting year, not an amount",
    "医药商业 · 盈利与资本特征":"2025 is the reporting year, not an amount",
    "MediBeacon TGFR系统 · 截至本次资料的事实层级":"10 is the month in October 20, not sales or a patient count",
    "HDM1005，GLP-1/GIP · 不能提前计入什么":"2005 is part of the different drug identifier HDM2005",
    "HDM2005，ROR1 ADC · 不能提前计入什么":"-1 is part of the target name GLP-1, not a financial return",
    "收购Sinclair并扩展海外医美 · 已观察到的结果":"2025 is the impairment reporting year",
    "增加分红 · 已观察到的结果":"2025 is the dividend entitlement year; actual payout is checked separately",
    "DR10624肝病Ⅱ期预计Q3读出顶线 · 本次看到的证据":"3 is the quarter marker Q3",
    "HDM1002预计Q4递交NDA · 本次看到的证据":"3 is the quarter marker Q3",
    "季度现金波动，全年更健康 · 本次看到的证据":"2 is the quarter marker Q2",
    "TTM归母利润（亿元） · 口径":"4 is the numerator in an explicitly rejected 4/3 annualization formula, not a financial observation",
    "PB · 口径":"3 is the quarter marker Q3",
    "已有适度仓位 · 后续条件":"4 is the quarter marker Q4",
    "研究日":"2026 is the research-date year",
    "原件还有两个需要诚实保留的口径缺口":"2025 is a reporting-year marker; segment amounts are not excluded",
    "n/list=sz000963)，2026-10-28分别16":"14 is the minute field of a quote timestamp"
}
def exclusion(p):
    if p["label"] in NOISE:
        return NOISE[p["label"]]
    if p["label"].endswith(" · 对照渠道"):
        return "Number inside source identifier S1/S2/S3, not a financial observation"
    return None

points=report_audit.extract_data_points(REPORT.read_text(encoding="utf-8"))
excluded=[{**p,"reason":exclusion(p)} for p in points if exclusion(p)]
eligible=[p for p in points if not exclusion(p)]
sample_size=math.ceil(len(eligible)*.15)
sample=sorted(Random(20261028).sample(eligible,sample_size),key=lambda p:p["line_number"])
assert len(sample)==math.ceil(len(eligible)*.15)
assert not any(exclusion(p) for p in sample)
(HERE/"audit-sample.json").write_text(json.dumps(sample,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if "--sample" in sys.argv:
    print(json.dumps({"raw":len(points),"excluded":len(excluded),"eligible":len(eligible),"sample_size":len(sample),"sample":sample},ensure_ascii=False,indent=2))
    raise SystemExit(0)

checks=json.loads((HERE/"audit-checks.json").read_text(encoding="utf-8"))
audited=[]
for p in sample:
    if p["label"] not in checks:
        raise ValueError("Unreviewed sample: "+p["label"])
    c=checks[p["label"]]
    if "exclude" in c:
        raise ValueError("An eligible sampled financial point cannot be excluded: "+p["label"])
    audited.append({**p,**c,"fetched_value":float(D(c["fetched_value"]))})

# The generic extractor omits pure-year row labels. Audit all five historical years
# and high-risk reconciliations explicitly, in addition to the random 15%.
targets=[]
report_lines=REPORT.read_text(encoding="utf-8").splitlines()
for year,row in {**I["older_core"],**I["annual"]}.items():
    actual=next([c.strip().strip("*") for c in line.strip().strip("|").split("|")] for line in report_lines if line.startswith("| "+year+" |") or line.startswith("| **"+year+"** |"))
    for column,key in enumerate(("revenue","profit","adjusted_profit","ocf"),1):
        raw=D(row[key])/D("1e8")
        targets.append((f"{year} {key} 亿元",D(actual[column]),raw,"S3/S8 primary annual table; actual report cell parsed, independent second coverage incomplete","disclosed"))
targets += [
    ("Q3单季OCF亿元",D("-6.3864"),(D("1860782257.63")-D("2499419530.63"))/D("1e8"),"S1 p19 minus S2 p104; exact sign and period verified","derived"),
    ("Q3单季capex亿元",D(".3089"),(D("749385798.03")-D("718496969.99"))/D("1e8"),"S1 p20 minus S2 p105; cash paid is not accrual additions","derived"),
    ("TTM归母亿元",D("34.3830"),(D("3414335326.41")+D("2771876687.23")-D("2747916019.11"))/D("1e8"),"S1/S3 full-year plus YTD minus prior YTD","derived"),
    ("H1研发资本化比例百分数",D("32.66"),D("362398636.97")/D("1109486581.09")*100,"S2 p203; raw capitalization/total, no external independent audit","derived"),
    ("Sinclair安全垫百分数",D("2.18"),(D("2740768580.00")/D("2682208991.65")-1)*100,"S2 p171 impairment table; recoverable is an estimate, not market value","derived"),
    ("TTM简化FCF亿元",D("22.5714"),(D("3495534684.62")-D("1238392654.96"))/D("1e8"),"S1/S2/S3 period-consistent cashflow subtraction, not owner distributable cash","derived"),
    ("十年前瞻PE时点",D("13.10"),(1-D(".01")/D(".12"))/(D(".08")-D(".01")),"Perpetuity formula, multiplied by year11 profit; numerical assumption check","scenario_calculation")
]
for idx,(label,reported,value,source,kind) in enumerate(targets,10001):
    audited.append({"id":idx,"label":label,"reported_value":float(reported),"fetched_value":float(value),"fetched_source":source,"audit_kind":kind,"unit":"as labeled"})
log=io.StringIO()
with contextlib.redirect_stdout(log):
    print(f"Seed 20261028; raw {len(points)}, nonfinancial exclusions {len(excluded)}, eligible {len(eligible)}, random checks {len(sample)} = ceil(eligible * 15%), effective coverage {len(sample)/len(eligible):.4%}; targeted additions {len(targets)}.")
    print("Assumption checks are not external verification. Issuer mirrors are one source; full independent coverage of notes is incomplete.")
    outcome=report_audit.render_verdict(audited,REPORT.name)
payload={"seed":20261028,"sample_ratio":.15,"sampling_method":"Random(seed).sample(eligible, ceil(len(eligible)*0.15)); no 30-item cap","eligible_count":len(eligible),"random_sample_count":len(sample),"actual_sample_ratio":len(sample)/len(eligible),"report_sha256":hashlib.sha256(REPORT.read_bytes()).hexdigest(),"extracted_count":len(points),"random_sample":sample,"excluded_non_financial":excluded,"checks":audited,"outcome":outcome,"limitations":["Q3/H1 unaudited","no independent second source for all financial notes","clinical evidence primarily issuer disclosed","future assumptions not verified facts","market quotes are frozen snapshots, URLs roll"]}
(HERE/"audit-results.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
plain=re.sub(r"\x1b\[[0-9;]*m","",log.getvalue())
plain="\n".join(line.rstrip() for line in plain.splitlines()).strip()+"\n"
(HERE/"audit-verdict.txt").write_text(plain,encoding="utf-8")
print(plain)
if outcome["verdict"] != "PASS":
    raise SystemExit(1)
