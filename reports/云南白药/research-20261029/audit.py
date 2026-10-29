"""Bind a reproducible 15% random sample and focused checks to the report."""
import hashlib
import io
import json
import sys
from contextlib import redirect_stdout
from decimal import Decimal as D
from pathlib import Path
HERE=Path(__file__).parent
ROOT=HERE.resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from report_audit import extract_data_points,sample_points,render_verdict
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
REPORT=HERE.parent/'云南白药研究报告-20261029.md'
text=REPORT.read_text(encoding='utf-8')
all_points=extract_data_points(text)
noise_reasons={
 71:'Calendar year in implementation explanation, not a financial amount',
 76:'Month in dividend implementation date, not a financial amount',
 78:'Attribution year in explanation, not a financial amount',
 79:'Year before customer concentration value; not the concentration percentage',
 107:'Research date year',
 108:'Quote timestamp year after source URL',
}
expected_noise_labels={71:'2025年特别分红 · 解释',76:'2026年特别分红 · 解释',78:'2026年上述两笔现金口径合计 · 解释',79:'客户集中度 · 已知信息',107:'研究日',108:'hq.sinajs.cn/list=sz000538)'}
assert {p['id']:p['label'] for p in all_points if p['id'] in noise_reasons}==expected_noise_labels, 'Report changed: re-review all exclusions before sampling'
excluded=[{**p,'exclusion_reason':noise_reasons[p['id']]} for p in all_points if p['id'] in noise_reasons]
points=[p for p in all_points if p['id'] not in noise_reasons]
if '--list' in sys.argv:
    print(json.dumps(all_points,ensure_ascii=False,indent=2))
    raise SystemExit(0)
sample=sample_points(points,ratio=.15,seed=20261029)
if '--sample' in sys.argv:
    print(json.dumps(sample,ensure_ascii=False,indent=2))
    raise SystemExit(0)
I=json.loads((HERE/'inputs.json').read_text(encoding='utf-8'))
R=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
Y=D('100000000')
checks={
 '经营现金流 · 2025年': (D(I['2025']['ocf'])/Y,'S3 年报页7；S4 NETCASH_OPERATE_PK 4599693880.44'),
 '营业利润 · 2025年前三季':(D(I['2025ytd']['operating'])/Y,'S1 三季报页11 上年同期'),
 '资本开支付现 · 2026年前三季':(D(I['2026ytd']['capex'])/Y,'S1 三季报页13，原始PDF视觉核验'),
 '基本/稀释EPS（元） · 2026年前三季':(D('2.70'),'S1 页3；S4 EPSJB=EPSXS=2.7'),
 '基本/稀释EPS（元） · 2025年前三季':(D('2.68'),'S1 页12 上年同期；S4 EPSJB=EPSXS=2.68'),
 '营业收入 · 2026年第三季':(D('10372987344.38')/Y,'S1 页3 本报告期直接披露值'),
 '营业利润率 · 2026年第三季':((D('5576562672.71')-D('4274084089.70'))/D('10372987344.38')*100,'S1累计营业利润减S2半年营业利润 / S1单季收入，独立公式'),
 '工业销售 · 2026上半年毛利率':(D('65.83'),'S2 页23 分行业表；仅原始财报单源'),
 '商业销售 · 2025年毛利率':(D('6.69'),'S3 页23 分行业表；仅原始财报单源'),
 '商业销售 · 2026上半年毛利率':(D('5.96'),'S2 页23 分行业表；仅原始财报单源'),
 '归母净资产 · 解读':(D(I['price'])*D(I['shares'])/D(I['balance']['equity']),'S1归母权益与股本、S5/S6价格重算PB'),
 'TTM扣非归母 · 计算结果':((D('4864568403.16')+D('4630906875.24')-D('4549939286.91'))/Y,'S1/S3原件和S4的TTM公式'),
 '悲观 · 派息率假设':(D('80'),'模型输入一致性；不是事实预测或外部验证'),
 '悲观 · 第五年退出PE':(D('14'),'模型输入一致性；不是事实预测或外部验证'),
 '悲观 · 第五年价格（元）':(D(R['valuation']['core_eps_ttm'])*D('.98')**5*14,'情景模型独立重算：起点扣非EPS乘增长系数五次方再乘PE'),
 '基准 · 每股利润年增长':(D('3'),'模型输入一致性；不是事实预测或外部验证'),
 '乐观 · 第五年退出PE':(D('22'),'模型输入一致性；不是事实预测或外部验证'),
 '简化FCF收益率 · 计算结果':(D(R['valuation']['fcf_ttm'])*Y/(D(I['price'])*D(I['shares']))*100,'三期经营现金与资本开支按TTM公式、股价乘原始股本'),
 '悲观 · 年化IRR':(D(R['scenarios']['bear']['irr_pct']),'逐年现金流折现求根；另有NPV独立测试'),
 '基准 · 五年股息合计（元）':(sum(D(R['valuation']['core_eps_ttm'])*D('1.03')**t*D('.85') for t in range(1,6)),'起点扣非EPS乘逐年增长和派息率后相加，模型重算'),
 '基准 · 派息率假设':(D('85'),'模型输入一致性；不是事实预测或外部验证'),
 '约42—44元，且主业未进一步恶化 · 空仓研究动作':(D('15'),'模型价格纪律区间下限；15倍乘扣非EPS为41.5763元，四舍五入约42元，非外部事实'),
}
results=[]
for point in sample:
    value,source=checks[point['label']]
    results.append({**point,'fetched_value':float(value),'fetched_source':source})
focused=[
 ('2026累计收入',322.5706,D(I['2026ytd']['revenue'])/Y,'S1页3；S4收入字段'),
 ('2026累计归母',48.2235,D(I['2026ytd']['profit'])/Y,'S1页3；S4归母字段'),
 ('2026累计扣非',46.3091,D(I['2026ytd']['core'])/Y,'S1页3；S4扣非字段'),
 ('2026累计经营现金',48.7415,D(I['2026ytd']['ocf'])/Y,'S1页13；S4现金字段'),
 ('2026单季归母',11.2118,D('1121182700.53')/Y,'S1页3直接值'),
 ('2026单季扣非',11.1249,D('1112491332.88')/Y,'S1页3直接值'),
 ('当日收盘价',52.93,D('52.930'),'S5腾讯；S6新浪独立报价'),
 ('总股本亿股',17.84262603,D('1784262603')/Y,'S1页3；S4 TOTAL_SHARE；S5'),
 ('市值亿元',944.4102,D('52.93')*D('1784262603')/Y,'股价乘原始股本；非市值倒推股本'),
 ('2025所属年度每股分红',2.602,D('1.019')+D('1.583'),'S3页2，年度与特别分红相加'),
 ('基准年化IRR',6.48,D(R['scenarios']['base']['irr_pct']),'逐年现金流折现求根；另有NPV独立测试'),
 ('乐观年化IRR',13.52,D(R['scenarios']['bull']['irr_pct']),'逐年现金流折现求根；另有NPV独立测试'),
]
for n,(label,reported,value,source) in enumerate(focused,1001):
    results.append({'id':n,'label':label,'reported_value':reported,'fetched_value':float(value),'fetched_source':source,'unit':''})
assert len(sample)/len(points)>=.15
assert all(r.get('fetched_value') is not None for r in results)
log=io.StringIO()
with redirect_stdout(log):verdict=render_verdict(results,REPORT.name)
assert verdict['verdict']=='PASS' and verdict['warn_count']==0 and verdict['total']==len(results)
summary={'report_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'all_extracted_points':len(all_points),'excluded_points':len(excluded),'valid_points':len(points),'seed':20261029,'random_count':len(sample),'random_coverage_pct':len(sample)/len(points)*100,'focused_count':len(focused),'total_checked':len(results),'verdict':verdict,'scope':'Numeric source/formula consistency. Scenario inputs are assumptions, not externally verified outcomes. Source gaps remain disclosed.'}
for name,obj in [('audit-all-points.json',all_points),('audit-excluded.json',excluded),('audit-sample.json',sample),('audit-results.json',results),('audit-summary.json',summary)]:
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(HERE/'audit-verdict.txt').write_text(log.getvalue(),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
