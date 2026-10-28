"""Frozen-seed audit with no 30-point cap; sources and assumptions stay distinct."""
import contextlib
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
REPORT=HERE.parent/"兴齐眼药研究报告-20261028.md"
I=json.loads((HERE/"inputs.json").read_text(encoding="utf-8"))
R=json.loads((HERE/"results.json").read_text(encoding="utf-8"))
md=REPORT.read_text(encoding="utf-8")
points=report_audit.extract_data_points(md)
excluded=[]
valid=[]
for p in points:
    label=p["label"]
    if label.endswith(" · 口径") or label.endswith(" · 结果") or label.startswith("已有合理小仓位 ·") or re.match(r"^S\d+ ·",label) or label in ("研究日","结论"):
        excluded.append({**p,"reason":"Date, quarter token, source identifier or audit tolerance, not a financial observation"})
    else:
        valid.append(p)
# The generic extractor omits year-only row labels and discount-rate rows.
# Recover their numeric cells from the actual report rather than excluding history.
for row,col,value,unit,line,raw in report_audit._parse_md_tables(md.splitlines()):
    if re.fullmatch(r"20\d{2}",row) or (re.fullmatch(r"\d+%",row) and col=="含股息加权IRR"):
        valid.append({"id":1000+len(valid),"label":row+" · "+col,"reported_value":value,"unit":unit,"line_number":line,"raw_text":raw})
sample=sorted(Random(20261028).sample(valid,math.ceil(len(valid)*.15)),key=lambda p:p["line_number"])
if "--prepare" in sys.argv:
    print(json.dumps({"raw_count":len(points),"excluded_count":len(excluded),"valid_count":len(valid),"sample_count":len(sample),"sample":sample},ensure_ascii=False,indent=2))
    raise SystemExit(0)

E8=D("1e8")
checks={
    "2023 · 归母净利润|2.4004":(D("240036047.12")/E8,"S3 p8三年比较列，原件已读；单一底层来源","disclosed"),
    "2023 · 经营现金流|3.1757":(D("317568222.76")/E8,"S3 p8三年比较列，原件已读；单一底层来源","disclosed"),
    "2024 · 经营现金流|4.1698":(D("416982963.18")/E8,"S3 p8及p84合并现金流量表比较列","disclosed"),
    "2024 · 归母净利率|17.4":(D("338061776.59")/D("1943387835.59")*100,"S3 p8归母利润/收入，Decimal独立复算","derived"),
    "2025 · 简化FCF|4.8286":((D("753388785.68")-D("270526699.17"))/E8,"S3 p84-85经营净现金减购建长期资产付现","derived"),
    "2025 · 归母净利率|28.14":(D("695855596.25")/D("2472852236.79")*100,"S3 p8归母利润/收入，复算","derived"),
    "2025 · 经营现金流|7.5339":(D("753388785.68")/E8,"S3 p8及p84合并现金流原件","disclosed"),
    "营业收入（亿元） · 2026前三季度|22.3762":(D("2237615141.00")/E8,"S1 p1/p7；S4财中社独立刊发22.4亿元","disclosed"),
    "营业收入（亿元） · 2025前三季度|19.0373":(D("1903728804.18")/E8,"S1 p1/p7比较列；S3分季收入可加总","disclosed"),
    "销售费用（亿元） · 2026前三季度|6.4724":(D("647237182.59")/E8,"S1 p7合并年初到期末利润表","disclosed"),
    "销售费用（亿元） · 2025前三季度|5.5547":(D("555474170.54")/E8,"S1 p7合并年初到期末利润表比较列","disclosed"),
    "研发费用（亿元） · 2026前三季度|2.3282":(D("232818102.90")/E8,"S1 p3/p7研发费用，非研发总投入","disclosed"),
    "经营现金流（亿元） · 2025单Q3|2.6897":(D("268970302.72")/E8,"S3 p8分季度表直接披露，并与S1减S2比较列勾稽","disclosed"),
    "其他 · 收入占比|0.81":(D("19942396.63")/D("2472852236.79")*100,"S3 p22分产品其他收入/总收入","derived"),
    "滴眼剂 · 收入占比|80.06":(D("1121535827.84")/D("1400873956.41")*100,"S2 p19分产品收入/总收入；S5报道80.06%","derived"),
    "滴眼剂 · 毛利率|86.45":((1-D("151961240.42")/D("1121535827.84"))*100,"S2 p19原表及截图视觉核验","derived"),
    "其他合并余项 · 收入（亿元）|0.8081":((D("1400873956.41")-D("1121535827.84")-D("198523750.83"))/E8,"S2 p18-19总收入减两大披露剂型，不是独立分部","derived"),
    "应收账款 · 判断|23.83":((D("325649803.68")/D("262985341.15")-1)*100,"S1 p5期末与年初比较，不是同比","derived"),
    "定增计划终止 · 已发生或已披露事实|7.8979":(D("78978.56")/D("10000"),"S2 p35-36拟募资78978.56万元及5/25终止；S5报道7.9亿","disclosed"),
    "2025静态PE · 当前值|16.76":(D("32.86")*D("354917774")/D("695855596.25"),"S10双源行情乘S1股本除S3年度利润","derived"),
    "基准 · 派息率假设|40.0":(D(I["three_year"][1]["payout"])*100,"inputs.json三年基准假设一致性；不是事实预测验证","assumption"),
    "乐观 · 含股息年化IRR|35.99":(D(R["three_year"][2]["cashflow_irr_pct"]),"calculate.py逐年股利求根；test_calculation独立浮点NPV校验","scenario_calculation"),
    "基准 · r减g|7.0":((D(I["ten_year"]["r"])-D(I["ten_year"]["scenarios"][1]["terminal_g"]))*100,"参数差值；terminal audit确认分母合格","scenario_calculation"),
    "基准 · 永续g|1.0":(D(I["ten_year"]["scenarios"][1]["terminal_g"])*100,"inputs.json假设一致性，不是永久增长已获验证","assumption"),
    "乐观 · 第十年利润（亿元）|18.6781":(D("816767814.56")*D("1.15")**3*D("1.06")**7/E8,"TTM扣非及明确两段增长假设独立复算","scenario_calculation"),
    "乐观 · 派息率|45.0":(D(I["ten_year"]["scenarios"][2]["payout"])*100,"inputs.json假设一致性，不是未来派息承诺","assumption"),
    "乐观 · 现值（元/股）|47.57":(D(R["ten_year"][2]["pv_price"]),"逐年股利加第十一年利润乘前瞻PE后折现；测试验证","scenario_calculation"),
    "6% · 含股息加权IRR|8.54":(D(R["sensitivity"][0]["weighted_cashflow_irr_pct"]),"严格现金流重算；乐观分母仅4pp，不可据此准出买入","scenario_calculation"),
    "2025归母 · 独立刊发值（亿元）|6.96":(D("6.96"),"S5北京商报2026-08-31正文6.96亿元，已实际extract读取","disclosed")
}

audited=[]
for p in sample:
    key=p["label"]+"|"+str(p["reported_value"])
    if key not in checks:
        raise ValueError("Missing evidence: "+key)
    value,source,kind=checks[key]
    record={**p,"fetched_value":float(value),"fetched_source":source,"audit_kind":kind}
    if p["label"]=="营业收入（亿元） · 2026前三季度":
        record.update(fetched_value2=22.4,fetched_source2="S4财中社2026-10-28正文")
    if p["label"]=="滴眼剂 · 收入占比":
        record.update(fetched_value2=80.06,fetched_source2="S5北京商报H1产品结构正文")
    if p["label"]=="2025归母 · 独立刊发值（亿元）":
        record.update(fetched_value2=float(D("695855596.25")/E8),fetched_source2="S3年报原件")
    audited.append(record)
targeted=[
    ("当前总股本",354917774,D("357322814")-D("2405040"),"S2 p36注销说明与S1股本；腾讯行情同值","disclosed"),
    ("单Q3收入亿元",8.3674,D("836741184.59")/E8,"S1 p1直接单季披露；S4独立刊发8.37亿","disclosed"),
    ("单Q3归母亿元",2.7470,D("274701563.62")/E8,"S1 p1直接披露；S4独立刊发2.75亿","disclosed"),
    ("单Q3销售费用率",27.94,(D("647237182.59")-D("413478661.58"))/D("836741184.59")*100,"S1累计减S2半年复算","derived"),
    ("单Q3研发费用率",8.55,(D("232818102.90")-D("161302852.97"))/D("836741184.59")*100,"S1累计减S2半年复算","derived"),
    ("净现金参考亿元",4.3224,(D("537820310.34")-D("88000000")-D("7272603.80")-D("10306303.18"))/E8,"S1资产负债表；未将现金等价物重复相加","derived"),
    ("2026H1研发资本化金额",0,D("0"),"S2 p147-148全额费用化及空白资本化栏原件，明确非全年推断","disclosed"),
    ("同SKU收入盈亏平衡量增百分数",26.97,(D("298")/D("234.7")-1)*100,"S7两终端价的纯算术敏感性，不是公司销量预测","scenario_calculation"),
    ("阿托品同规格价格降幅百分数",-21.24,(D("234.7")/D("298")-1)*100,"S7新快报正文与采购公示线索，终端价格非厂家净价","derived"),
    ("H1研发中心在建亿元",4.1366,D("413658106.27")/E8,"S2 p117项目在建余额，不是所有在建工程","disclosed"),
    ("恒瑞环孢素已商业化状态",1,D("1"),"S8官网正文：2026-06-23获批、08-17首发，状态核验而非财务金额","status_check")
]
for index,(label,reported,value,source,kind) in enumerate(targeted,2001):
    audited.append({"id":index,"label":label,"reported_value":reported,"fetched_value":float(value),"fetched_source":source,"audit_kind":kind,"unit":"as labeled"})
log=io.StringIO()
with contextlib.redirect_stdout(log):
    print(f"Seed 20261028; raw {len(points)}, nonfinancial excluded {len(excluded)}, valid population including recovered annual/sensitivity cells {len(valid)}, random sample {len(sample)} ({len(sample)/len(valid):.2%}). No 30-point cap.")
    print("Assumption checks are not external validation. Issuer mirrors are one source; independent note coverage incomplete.")
    outcome=report_audit.render_verdict(audited,REPORT.name)
payload={"seed":20261028,"ratio":.15,"raw_count":len(points),"excluded_non_financial":excluded,"valid_population_count":len(valid),"random_sample":sample,"targeted_count":len(targeted),"checks":audited,"outcome":outcome,"limitations":["Random population is machine-extractable financial/model points, not every number in prose","No independent second source for all note details","Assumption and scenario checks are not external validation of future results","2025 annual total dividend reconciliation unresolved and no full-year dividend yield asserted"]}
(HERE/"audit-results.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
plain=re.sub(r"\x1b\[[0-9;]*m","",log.getvalue())
plain="\n".join(line.rstrip() for line in plain.splitlines()).strip()+"\n"
(HERE/"audit-verdict.txt").write_text(plain,encoding="utf-8")
print(plain)
if outcome["verdict"]!="PASS" or outcome["warn_count"] or outcome["total"]!=len(audited):
    raise SystemExit(1)
