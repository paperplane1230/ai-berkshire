"""Frozen-seed public-evidence audit; model assumptions are not external facts."""
import contextlib
import io
import json
import re
import sys
from decimal import Decimal as D
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/"tools"))
import report_audit

REPORT=HERE.parent/"国电南瑞研究报告-20261028.md"
I=json.loads((HERE/"inputs.json").read_text(encoding="utf-8"))
R=json.loads((HERE/"results.json").read_text(encoding="utf-8"))
N=I["ytd_2026q3"]
O=I["ytd_2025q3"]
E8=D("1e8")

# These are lexical false positives, identified from the whole extracted list
# before freezing the eligible population; no financial number is excluded.
NOISE={
    "国内主营收入（亿元） · 解释":"H1 period marker",
    "海外主营收入（亿元） · 解释":"H1 period marker",
    "电网行业收入（亿元） · 解释":"H1 period marker",
    "其他行业收入（亿元） · 解释":"H1 period marker",
    "系统级技术与工程能力 · 可以观察的证据":"year 2025",
    "持续研发并覆盖关键控制技术 · 已有结果":"year 2025",
    "电网外与海外拓展 · 已有结果":"H1 period marker",
    "分红与回购 · 已有结果":"year 2025; actual payout checked separately",
    "8月启动的市场回购 · 已有结果":"October date; actual buyback checked separately",
    "采购付款加快，同时持续清收 · 下一步核验":"Q4 period marker",
    "PACK中试线9月底、变流器线12月底投产 · 本次判断":"Q3 period marker",
    "总股本 · 口径":"Q3 period marker",
    "TTM营业收入 · 口径":"year 2025",
    "PB / PS · 口径":"September date",
    "历史股息率 · 口径":"year 2025",
    "研究日":"research date",
    "为10月29日，不代表28日晚仍不可得；观点网10月28日17":"time 17:38",
    "季节性不能忽略":"year 2025; quarterly weights checked separately"
}

def exclusion(p):
    label=p["label"]
    if label in NOISE:return NOISE[label]
    if label.endswith(" · 结论"):return "source identifier, not financial figure"
    if re.match(r"^S[0-9]+ ",label) and label not in {"S8 · 来源属性","S9 · 来源属性","S13 · 来源属性"}:
        return "source-title date, page or period marker"
    return None

points=report_audit.extract_data_points(REPORT.read_text(encoding="utf-8"))
excluded=[{**p,"reason":exclusion(p)} for p in points if exclusion(p)]
eligible=[p for p in points if not exclusion(p)]
sample=report_audit.sample_points(eligible,ratio=.15,seed=20261028)
if "--sample" in sys.argv:
    print(json.dumps({"raw":len(points),"excluded":len(excluded),"eligible":len(eligible),"sample":sample},ensure_ascii=False,indent=2))
    raise SystemExit(0)

def item(value,source,kind="disclosed",second=None,second_source=None):
    return (D(str(value)),source,kind,None if second is None else D(str(second)),second_source)

CHECKS={
    "营业收入（亿元） · 2026前三季度":item(D("43879577511.61")/E8,"S1 p1/p10, original PDF table","disclosed","438.80","S4 independent publication"),
    "营业收入（亿元） · 2025前三季度":item(D("38576507202.81")/E8,"S1 p10 comparative column; issuer-only underlying evidence"),
    "营业利润率 · 2026前三季度":item(D("5992709497.14")/D("43879577511.61")*100,"S1 p10-11 operating profit / revenue","derived"),
    "营业利润率 · 2025前三季度":item(D("5854758917.73")/D("38576507202.81")*100,"S1 p10-11 comparative operating profit / revenue","derived"),
    "归母净利率 · 2026前三季度":item(D("4911652568.60")/D("43879577511.61")*100,"S1 p1/p11 parent profit / revenue","derived"),
    "电网智能 · 2026H1收入":item(D("13306218193.62")/E8,"S2 MD&A product table","disclosed","133.06","S5 Lanjing 2026H1"),
    "工业互联 · 2026H1收入":item(D("953742816.01")/E8,"S2 MD&A product table","disclosed","9.54","S5 Lanjing 2026H1"),
    "工业互联 · H1收入同比":item("-23.38","S2 MD&A product table","disclosed","-23.38","S5 Lanjing 2026H1"),
    "工业互联 · 2025收入":item(D("3013877121.23")/E8,"S3 MD&A product table; issuer-only"),
    "集成及其他 · 2025毛利率":item((1-D("504036626.13")/D("687074851.90"))*100,"S3 product table revenue and cost, recomputed","derived"),
    "国内主营收入（亿元） · 2026H1":item(D("21805020628.21")/E8,"S2 domestic revenue table","disclosed","218.05","S5 Lanjing 2026H1"),
    "存货 · 2026年9月末":item(D("17009013061.26")/E8,"S1 p6 balance sheet; issuer-only"),
    "员工付款增加 · 对CFO同比变化的影响（亿元）":item(-(D("3931506150.00")-D("3566563159.40"))/E8,"S1 p13 payroll cash current minus prior with outflow sign","derived"),
    "PB / PS · 复算值":item(D("23.34")*D("8031756156")/D("52572913859.30"),"S1 p9 / S11 price; extractor selects PB, PS tested separately","derived"),
    "TTM简化FCF · 复算值":item(((D("12768702125.04")-D("2919538534.11")-D("4714110770.90"))-(D("2110354922.10")+D("1178331939.15")-D("1237649038.30")))/E8,"S1 p13-14 / S3 consolidated cashflow, exact TTM","derived"),
    "悲观 · 三年累计股息":item(sum(D(R["metrics"]["eps_adjusted_ttm"])*D(".98")**y*D(".60") for y in range(1,4)),"Three-year declared model cashflows, not forecast validation","scenario_calculation"),
    "乐观 · 第三年股价":item(D(R["metrics"]["eps_adjusted_ttm"])*D("1.12")**3*28,"EPS * (1.12)^3 * 28; independently recomputed","scenario_calculation"),
    "悲观 · 主观情景权重":item(D(I["ten_year_assumptions"]["scenarios"][0]["probability"])*100,"inputs.json subjective probability consistency only","assumption"),
    "基准 · 永续g":item(D(I["ten_year_assumptions"]["scenarios"][1]["terminal_g"])*100,"inputs.json terminal g, not observed economic data","assumption"),
    "基准 · 前十年利润年增速":item(D(I["ten_year_assumptions"]["scenarios"][1]["growth"])*100,"inputs.json assumed growth, not management guidance","assumption"),
    "基准 · 严格现金流IRR":item(R["ten_year"][1]["cashflow_irr_pct"],"Declared annual dividends plus year-11 earnings terminal, root checked in unit tests","scenario_calculation"),
    "乐观 · 第十年利润（亿元）":item(D("8049266037.85")*D("1.12")**10/E8,"TTM adjusted profit * (1.12)^10","scenario_calculation"),
    "乐观 · 严格现金流IRR":item(R["ten_year"][2]["cashflow_irr_pct"],"Declared yearly cashflows and numerical root; not return guarantee","scenario_calculation"),
    "S9 · 来源属性":item(".153","S9 implementation notice; paid 2026-09-29"),
    "2025归母 · 原件值":item(D("8278971723.32")/E8,"S3 main indicators and consolidated profit","disclosed","82.79","S6 Weekly on Stock publication"),
    "2026前三季归母 · 第二刊发渠道值":item("49.12","S4 extracted page","disclosed",D("4911652568.60")/E8,"S1 original PDF p1"),
    "2026前三季扣非 · 第二刊发渠道值":item("47.05","S4 extracted page","disclosed",D("4704912490.96")/E8,"S1 original PDF p1"),
    "2026前三季经营现金流 · 原件值":item(-D("2919538534.11")/E8,"S1 p2/p13 original","disclosed","-29.20","S4 extracted page")
}

TARGETS=[
    ("2023 restated revenue CNY100m",519.6131,D("51961306701.63")/E8,"S3 restated three-year indicators","disclosed"),
    ("2023 restated parent profit CNY100m",71.7897,D("7178970492.47")/E8,"S3 restated three-year indicators","disclosed"),
    ("2023 adjusted profit CNY100m",69.6035,D("6960354657.26")/E8,"S3 three-year indicators","disclosed"),
    ("2023 restated OCF CNY100m",113.1719,D("11317186613.54")/E8,"S3 restated three-year indicators","disclosed"),
    ("2024 restated revenue CNY100m",578.2917,D("57829172321.78")/E8,"S3 restated three-year indicators","disclosed"),
    ("2024 restated parent profit CNY100m",76.1024,D("7610235695.07")/E8,"S3 restated three-year indicators","disclosed"),
    ("2024 adjusted profit CNY100m",73.8856,D("7388560296.53")/E8,"S3 three-year indicators","disclosed"),
    ("2024 restated OCF CNY100m",110.8679,D("11086788479.77")/E8,"S3 restated three-year indicators","disclosed"),
    ("2025 revenue CNY100m",662.2896,D("66228963223.21")/E8,"S3 original; S6 662.29 confirms","disclosed"),
    ("2025 adjusted profit CNY100m",79.8296,D("7982955643.59")/E8,"S3 original; third-party annual summary 79.83","disclosed"),
    ("2025 OCF CNY100m",127.6870,D("12768702125.04")/E8,"S3 original; S6 127.69 confirms","disclosed"),
    ("2026 single Q3 OCF CNY100m",-35.1065,(D("-2919538534.11")-D("591109591.80"))/E8,"S1 p13 minus S2 H1 cashflow","derived"),
    ("Full CFO bridge CNY100m",-76.3365,sum(D(v) for v in R["cashflow_bridge"].values())/E8,"S1 p13 all seven change components, verified sum invariant","derived"),
    ("Cash plus trading CNY100m",129.4619,(D("6932263372.88")+D("6013927424.63"))/E8,"S1 p6; excludes cash equivalents duplicate","derived"),
    ("Current total shares",8031756156,D("8031756156"),"S1 p9, S12 current 10/28 disclosure, Tencent quote","disclosed"),
    ("Proposed cancellation shares",143730,D("143730"),"S13 proposal not completed cancellation","disclosed"),
    ("2025 payout per share",.622,D(".147")+D(".475"),"S3 interim dividend and S8 implemented final dividend","derived"),
    ("2026 latest repurchase amount CNY100m",1.51,D("151074034.40")/E8,"S12 actual cash spent, not planned CNY0.5-1.0bn","disclosed"),
    ("2026 latest repurchase shares 10k",659.2268,D("6592268")/D("10000"),"S12 buyback for employee incentive, not capital retirement","disclosed"),
    ("PS",2.62,D(R["metrics"]["ps_ttm"]),"S1/S3/S11 exact marketcap/TTM revenue","derived"),
    ("Forward terminal PE base",13.33,(1-D(".01")/D(".15"))/(D(".08")-D(".01")),"Perpetual formula; year11 profit multiplicand tested","scenario_calculation")
]

# Verify the typed high-risk inputs actually appear in the acquired primary
# documents. This is a transcribing check in addition to the human reading.
for filename,tokens in {
    "nari-q3.txt":["43,879,577,511.61","38,576,507,202.81","4,911,652,568.60","4,704,912,490.96","-2,919,538,534.11","17,009,013,061.26","8,031,756,156.00"],
    "nari-h1.txt":["13,306,218,193.62","953,742,816.01","21,805,020,628.21","591,109,591.80"],
    "nari-2025.txt":["66,228,963,223.21","8,278,971,723.32","12,768,702,125.04","51,961,306,701.63","7,178,970,492.47","3,013,877,121.23"]
}.items():
    content=(ROOT/"tmp/pdfs/nari-20261028"/filename).read_text(encoding="utf-8")
    for token in tokens:
        assert token in content,(filename,token)

def main():
    audited=[]
    for p in sample:
        if p["label"] not in CHECKS:
            raise ValueError("Evidence review required: "+p["label"])
        v,source,kind,v2,source2=CHECKS[p["label"]]
        item={**p,"fetched_value":float(v),"fetched_source":source,"audit_kind":kind}
        if v2 is not None:item.update(fetched_value2=float(v2),fetched_source2=source2)
        audited.append(item)
    for index,(label,reported,value,source,kind) in enumerate(TARGETS,1001):
        audited.append({"id":index,"label":label,"reported_value":float(reported),"fetched_value":float(value),"fetched_source":source,"audit_kind":kind,"unit":"as labeled"})
    log=io.StringIO()
    with contextlib.redirect_stdout(log):
        print(f"Seed 20261028; raw {len(points)}, nonfinancial exclusions {len(excluded)}, eligible {len(eligible)}, random checks {len(sample)}; targeted checks {len(TARGETS)}.")
        print("External public disclosures, arithmetic and assumptions have separate audit_kind. Issuer mirrors are one underlying source.")
        result=report_audit.render_verdict(audited,REPORT.name)
    payload={"seed":20261028,"sample_ratio":.15,"extracted_count":len(points),"excluded_non_financial":excluded,"eligible_count":len(eligible),"random_sample":sample,"checks":audited,"outcome":result,"limitations":["Q3/H1 unaudited","issuer-only notes not fully independently cross-checked","scenario consistency is not external verification","unmodelled extreme system-quality and overseas-policy risks"]}
    (HERE/"audit-results.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    plain=re.sub(r"\x1b\[[0-9;]*m","",log.getvalue())
    plain="\n".join(line.rstrip() for line in plain.splitlines()).strip()+"\n"
    (HERE/"audit-verdict.txt").write_text(plain,encoding="utf-8")
    print(plain)
    if result["verdict"]!="PASS":raise SystemExit(1)

if __name__=="__main__":main()
