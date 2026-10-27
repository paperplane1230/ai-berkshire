"""Frozen-seed audit: disclosed figures, derived figures and assumptions stay separate."""
import contextlib
import io
import json
import re
import sys
from decimal import Decimal as D
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0,str(ROOT / "tools"))
import report_audit

I=json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
R=json.loads((HERE / "results.json").read_text(encoding="utf-8"))
REPORT=HERE.parent / "涪陵榨菜研究报告-20261027.md"
points=report_audit.extract_data_points(REPORT.read_text(encoding="utf-8"))
sample=report_audit.sample_points(points,ratio=.15,seed=20261027)
N=I["ytd_2026q3"]
O=I["ytd_2025q3"]
E8=D("1e8")

checks={
    "合并毛利率 · 2025前三季度": ((1-D(O["cost"])/D(O["revenue"]))*100,"S1 PDF p9 上年同期收入及营业成本，复算","derived"),
    "合并毛利率 · 2026前三季度": ((1-D(N["cost"])/D(N["revenue"]))*100,"S1 PDF p9 当期收入及营业成本，复算","derived"),
    "经营现金流（亿元） · 2025前三季度": (D("446958791.53")/E8,"S1 PDF p11 比较列，已核原件；单一底层来源","disclosed"),
    "资本开支付现（亿元） · 2025前三季度": (D("306326512.76")/E8,"S1 PDF p11 比较列；单一底层来源","disclosed"),
    "扣非归母（亿元） · 2025单Q3": (D("200232387.69")/E8,"S3 PDF p8 分季度主表；单一底层来源","disclosed"),
    "销售费用（亿元） · 2026单Q3": ((D("334204388.24")-D("229597242.17"))/E8,"S1 p9 与S2 p50累计减H1，复算","derived"),
    "榨菜 · H1收入同比": ((D("1151418864.12")/D("1122632937.52")-1)*100,"S2 PDF p21-22产品表原件；单一底层来源","derived"),
    "萝卜 · H1毛利率": ((1-D("21371857.18")/D("26427445.01"))*100,"S2 PDF p22产品表原件；单一底层来源","derived"),
    "泡菜 · H1毛利率": ((1-D("72777021.28")/D("108294582.75"))*100,"S2 PDF p22产品表原件；单一底层来源","derived"),
    "其他产品 · H1收入同比": ((D("77395853.11")/D("36545560.96")-1)*100,"S2 PDF p21；单一底层来源","derived"),
    "其他业务 · H1收入同比": ((D("1921191.39")/D("1724269.17")-1)*100,"S2 PDF p21；单一底层来源","derived"),
    "其他业务 · 2025收入占比": (D("4152586.16")/D("2431922780.17")*100,"S3 PDF p22原件；单一底层来源","derived"),
    "吨均营业收入（万元/吨） · 2025全年": (D("2059471664.42")/D("111800")/D("10000"),"S3收入/销量；销量披露精度仅0.01万吨，非同SKU提价","derived"),
    "吨均营业收入（万元/吨） · 2026H1": (D("1151418864.12")/D("61000")/D("10000"),"S2收入/销量；非同SKU提价","derived"),
    "现金及现金等价物 · 金额（亿元）": (D("545725523.24")/E8,"S1 PDF p11原件；不能与货币资金重复相加","disclosed"),
    "其他流动资产总额 · 金额（亿元）": (D("215335664.71")/E8,"S1 PDF p7原件；不全视作金融资产","disclosed"),
    "2026年6月末 · 合同负债（亿元）": (D("58557983.45")/E8,"S2合并资产负债表；单一底层来源","disclosed"),
    "市值 · 最新复算值": (D("11.22")*D("1153919028")/E8,"S17腾讯/新浪收盘与S1股本复算；腾讯报129.47亿","derived"),
    "TTM归母利润 · 最新复算值": ((D("768034038.98")+D("613891650.82")-D("672969983.10"))/E8,"S1/S3全年加累计减同期；公式复算","derived"),
    "扣非PE · 最新复算值": (D(I["price"])*D(I["shares"])/D(R["ttm"]["adjusted_profit"]),"S1/S3/S17；精确市值除扣非TTM","derived"),
    "基准 · 含股息年化IRR": (D(R["three_year"][1]["cashflow_irr_pct"]),"三年65%派息与退出价逐年求根；另有独立单元测试","scenario_calculation"),
    "基准 · 三年后价格": (D(R["metrics"]["eps_adjusted_ttm"])*D("1.03")**3*18,"模型输入与Decimal复算，不是外部预测","scenario_calculation"),
    "中性 · 现金若第三年才兑现的参考": ((D(R["sotp_core_profit_proxy"])*16+D("3200000000")/D("1.08")**3)/D(I["shares"]),"SOTP公式复算；未计等待期利息","scenario_calculation"),
    "基准 · 前十年利润年增速": (D(I["ten_year_assumptions"]["scenarios"][1]["growth"])*100,"inputs.json假设一致性，不是已验证未来增长","assumption"),
    "2026前三季收入 · 原件值（亿元）": (D("2067509518.74")/E8,"S1 PDF p3；S8观点20.68亿元交叉","disclosed"),
    "2026前三季收入 · 独立刊发媒体值（亿元）": (D("20.68"),"S8观点网10/27 16:49全文；公司原件20.6750951874亿元","disclosed"),
    "2026前三季经营现金流 · 原件值（亿元）": (D("691282029.56")/E8,"S1 PDF p3/p11；S8观点6.91亿元交叉","disclosed")
}
exclusions={
    "巨潮原件落款为10月28日，但观点网在10月27日16":"16:49的分钟数被错当财务金额；S8时间戳已核，不属财务抽检",
    "财联社在17":"17:15的分钟数被错当财务金额；S9时间戳已核，不属财务抽检",
    "现金分红 · 已发生结果":"2025是利润所属年度，不是分红金额；另增分红0.42元专项复核"
}
audited,excluded=[],[]
for point in sample:
    if point["label"] in exclusions:
        excluded.append({**point,"reason":exclusions[point["label"]]})
        continue
    if point["label"] not in checks:
        raise ValueError("New sample requires human/evidence review: "+point["label"])
    value,source,kind=checks[point["label"]]
    audited.append({**point,"fetched_value":float(value),"fetched_source":source,"audit_kind":kind})

# The generic table extractor skips rows whose labels are years. Add annual history
# and high-risk quarter/cash/credit items explicitly, rather than silently ignoring them.
targets=[
    ("2021追溯后扣非亿元",6.9449,D("694494519.76")/E8,"S4 2023年报2021比较列，解释16号追溯","disclosed"),
    ("2022追溯后归母亿元",8.9880,D("898803656.42")/E8,"S4 2023年报2022调整后比较列","disclosed"),
    ("2024归母亿元",7.9935,D("799346652.13")/E8,"S3 2025年报比较列；已排除S10错误7.80亿","disclosed"),
    ("2025合并毛利率百分数",51.63,(1-D("1176382059.33")/D("2431922780.17"))*100,"S3合并利润表；不同于食品加工51.78%","derived"),
    ("Q3单季OCF同比百分数",.70,D(R["q3_comparison"]["ocf_growth_pct"]),"S1累计减S2半年，对比S3单季","derived"),
    ("Q3应收同季同比百分数",18.79,(D("143583620.28")/D("120875334.19")-1)*100,"S1/S5资产负债表；不是年初比较","derived"),
    ("Q3合同负债同季同比百分数",38.78,(D("57348047.73")/D("41323458.09")-1)*100,"S1/S5；方向为同比增加","derived"),
    ("完整OCF变化桥亿元",2.4432,sum(D(v) for v in R["cashflow_bridge"].values())/E8,"S1 PDF p10-11逐项对账；不是仅选有利项","derived"),
    ("2025所属年度每股分红",.42,(D("230783805.60")+D("253862186.16"))/D(I["shares"]),"S2/S3已宣告和现金支付桥；不含2026H1未批准预案","derived"),
    ("十年基准前瞻退出PE",13.33,(1-D(".01")/D(".15"))/(D(".08")-D(".01")),"永续公式与terminal_value audit；非同业类比","scenario_calculation"),
    ("SOTP中性超额现金假设亿元",32,D(I["sotp_assumptions"]["surplus_cash"][1])/E8,"输入假设一致性；不是会计披露或现金返还承诺","assumption"),
    ("Q3去假设税后存款利息经营代理同比百分数",.54,D(R["metrics"]["q3_core_profit_proxy_growth_pct"]),"S1/S2扣非减存款利息*85%，不是公司分部净利润","scenario_calculation")
]
for index,(label,reported,value,source,kind) in enumerate(targets,1001):
    audited.append({"id":index,"label":label,"reported_value":reported,"fetched_value":float(value),"fetched_source":source,"audit_kind":kind,"unit":"as labeled"})
log=io.StringIO()
with contextlib.redirect_stdout(log):
    print(f"Seed 20261027; extracted {len(points)}, selected {len(sample)} (15% rounded), excluded nonfinancial {len(excluded)}, targeted additions {len(targets)}.")
    print("Assumption checks are not external verification. Issuer mirrors are one source; full independent coverage of notes is incomplete.")
    outcome=report_audit.render_verdict(audited,REPORT.name)
payload={"seed":20261027,"sample_ratio":.15,"extracted_count":len(points),"random_sample":sample,"excluded_non_financial":excluded,"checks":audited,"outcome":outcome,"limitations":["Q3/H1 unaudited","no independent second source for all balance-sheet notes","scenario arithmetic is not validation of assumptions","timing of interim dividend and board nomination checked against S16/S15; proposals not implementation"]}
(HERE/"audit-results.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
plain=re.sub(r"\x1b\[[0-9;]*m","",log.getvalue())
plain="\n".join(line.rstrip() for line in plain.splitlines()).rstrip()+"\n"
(HERE/"audit-verdict.txt").write_text(plain,encoding="utf-8")
print(plain)
if outcome["verdict"] != "PASS":
    raise SystemExit(1)
