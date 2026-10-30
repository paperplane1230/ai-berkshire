"""Seeded sample after noise exclusion; facts and scenarios are not conflated."""
import hashlib
import io
import json
import math
import random
import re
import sys
from contextlib import redirect_stdout
from decimal import Decimal as D
from pathlib import Path
from calculate import calculate
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/'tools'))
import report_audit as audit
REPORT=HERE.parent/'同仁堂研究报告-20261030.md'
I,rows,R=calculate()
Y=D('100000000')
body=REPORT.read_text(encoding='utf-8')
points=audit.extract_data_points(body)
noise_labels={'保持股东回报 · 可见结果','研究日','php?stockid=600085&id=12684555)','hq.sinajs.cn/list=sh600085)','月30日分别为16'}
excluded=[p for p in points if p['label'] in noise_labels]
assert len(points)==97 and len(excluded)==5, 'Review extraction universe after report edits'
valid=[p for p in points if p not in excluded]
for row,col,value,unit,line,raw in audit._parse_md_tables(body.splitlines()):
    if row in ('2023','2024','2025'):
        valid.append({'id':100+sum(x.get('supplemented',False) for x in valid),'label':row+' · '+col,
            'reported_value':value,'unit':unit,'line_number':line,'raw_text':raw,'supplemented':True})

fields={'营业收入':'revenue','归母净利润':'profit','扣非归母':'core','营业利润':'operating','合并净利润':'group_profit',
        '经营现金流':'ocf','资本开支付现':'capex','简化自由现金流':'fcf'}
periods={'2025累计':'2025YTD','2026累计':'2026YTD','2025单Q3':'2025Q3','2026单Q3':'2026Q3'}
business={'医药工业':('h1_industrial_revenue','42.52','-16.12'),'医药商业':('h1_commercial_revenue','25.19','-19.28'),
          '其他行业':('h1_other_revenue','6.99','57.41'),'主营合计':('h1_main_revenue','42.21','-14.22')}
balance={'货币资金':'cash','交易性金融资产':'trading','应收账款':'ar','存货':'inventory','应付账款':'payables','合同负债':'contract'}
scenarios={'压力':'bear','基准恢复':'base','较强恢复':'bull'}
scenario_fields={'每股盈利年增速':'growth','第五年EPS（元）':'eps5','退出PE':'exit_pe','第五年价格（元）':'exit_price','五年股息合计（元）':'dividend_sum','税前年化IRR':'irr_pct'}

def reference(p):
    row,col=p['label'].split(' · ')
    if row in fields:return R['periods'][periods[col]][fields[row]],'S1/S2 consolidated statement or same-period difference','financial_calculation'
    if row in business:
        key,margin,growth=business[row]
        if col=='上半年收入':return D(I['business'][key])/Y,'S2 industry table; single issuer source','source_fact'
        return D(margin if col=='毛利率' else growth),'S2 industry table; single issuer source','source_fact'
    if row=='行业间抵销':return -D(I['business']['h1_elimination'])/Y,'S2 industry elimination, not standalone sales','source_fact'
    if row=='同仁堂科技（01666）':return D('46.85'),'S2 subsidiaries and control note','source_fact'
    if row=='同仁堂商业':return D('51.98'),'S2 subsidiary ownership','source_fact'
    if row=='同仁堂国药（03613）':
        value=D('33.62') if col=='600085直接持股' else D('38.05') if col=='其他合并层级持股' else R['business']['guoyao_lookthrough_stake']
        return value,'S2 direct and indirect stake, multiplied not simply added','ownership_calculation'
    if row=='列示借款及租赁相关负债':return R['balance']['opening' if col=='2025年末' else 'current']['specified_debt'],'S1 named debt scope, including current noncurrent liabilities','financial_calculation'
    if row in balance:
        if col=='阅读重点':return R['balance']['ar_growth'],'S1 current versus opening AR, not year-on-year','financial_calculation'
        return D(I['balance']['opening' if col=='2025年末' else 'current'][balance[row]])/Y,'S1 consolidated balance sheet','source_fact'
    if row=='精准营销、优化销售费用':return abs(R['growth']['YTD']['sales']),'S1 same-period sales expense decline','financial_calculation'
    if row=='推进原料与质量研究':return R['growth']['YTD']['rd'],'S1 same-period R&D expense growth','financial_calculation'
    if row in ('TTM营业收入','TTM归母净利润','TTM扣非归母','TTM简化自由现金流'):
        key={'TTM营业收入':'revenue','TTM归母净利润':'profit','TTM扣非归母':'core','TTM简化自由现金流':'fcf'}[row]
        return R['periods']['TTM'][key],'S1+S3 annual-minus-prior-YTD formula','financial_calculation'
    if row in ('当前股本口径TTM扣非EPS','归母TTM PE','扣非TTM PE'):
        key={'当前股本口径TTM扣非EPS':'core_eps','归母TTM PE':'pe','扣非TTM PE':'core_pe'}[row]
        return R['valuation'][key],'Current registered shares and TTM, not weighted historical EPS','financial_calculation'
    if row in scenarios:return R['scenarios'][scenarios[row]][scenario_fields[col]],'Explicit finite-horizon cash-flow model; not externally verified forecast','model_assumption_or_calculation'
    if row in ('2023','2024','2025'):return R['periods'][row][fields[col]],'S3 annual comparison table; source precision preserved','source_fact'
    raise ValueError(p)

checks=[]
for p in valid:
    value,source,kind=reference(p)
    checks.append({**p,'fetched_value':float(value),'fetched_exact':str(value),'fetched_source':source,'verification_kind':kind})
sample_ids={p['id'] for p in random.Random(20261030).sample(valid,math.ceil(len(valid)*.15))}
sample=[p for p in checks if p['id'] in sample_ids]
directed=[]
def add(label,reported,value,source,kind='financial_calculation'):
    directed.append({'id':1000+len(directed),'label':label,'reported_value':float(reported),'fetched_value':float(value),
        'fetched_exact':str(value),'fetched_source':source,'verification_kind':kind,'unit':'as described in report'})
add('当日收盘价',25.07,I['price'],'S8 Tencent and Sina 2026-10-30 both 25.07','source_fact')
add('股本亿股',13.71470262,D(I['shares'])/Y,'S1 consolidated balance sheet; not cap divided by price','source_fact')
add('市值亿元',343.83,R['valuation']['market_cap_yi'],'S1 shares times S8 same-day close')
add('历史派息元',.50,I['dividend_2025'],'S5 implementation announcement, not future promise','source_fact')
add('历史股息率',1.99,R['valuation']['historical_dividend_yield'],'S5 dividend divided by current S8 price')
add('单Q3收入同比',-24.28,R['growth']['Q3']['revenue'],'S1 direct disclosed rate and unrounded difference')
add('单Q3归母同比',-39.87,R['growth']['Q3']['profit'],'S1 direct disclosed rate and unrounded difference')
add('单Q3扣非同比',-41.45,R['growth']['Q3']['core'],'S1 direct disclosed rate; source rounding below report precision')
add('Q3当前毛利率',38.21,R['periods']['2026Q3']['gross_margin'],'S1-S2 revenue and costs')
add('Q3上年毛利率',42.69,R['periods']['2025Q3']['gross_margin'],'S1-S2 latest comparatives')
add('Q3少数股东损益亿元',-.1766,R['periods']['2026Q3']['minority_profit'],'Group net income minus parent net income')
add('合并流动资源减指定负担亿元',75.8787,R['balance']['current']['liquid_minus_debt'],'CCE+trading assets minus specified debt; not parent distributable cash')
add('应收周转天数',28.83,R['balance']['ar_days_270'],'S1 average balance / YTD revenue x270; vendor agrees')
add('存货周转天数',417.37,R['balance']['inventory_days_270'],'S1 average balance / YTD cost x270; vendor agrees')
add('库存释放H1亿元',11.6466,D(I['business']['inventory_release_h1'])/Y,'S2 cash-flow reconciliation, not perpetual free cash','source_fact')
add('基准10%折现价格',14.91,R['scenarios']['base']['pv_10pct'],'Finite five-year annual dividends and exit multiple','model_assumption_or_calculation')
add('反向盈利增长要求',20.35,R['reverse_growth_10pct'],'10% hurdle, 24x exit PE, 60% payout, five years','model_assumption_or_calculation')
add('委托贷款合计亿元',.7560,(D('4330')+D('3230'))/10000,'S6 explicitly disclosed loan amounts; not completed equity conversion','source_fact')

log=io.StringIO()
with redirect_stdout(log):
    v_sample=audit.render_verdict(sample,REPORT.name+' fixed-seed sample')
    v_full=audit.render_verdict(checks+directed,REPORT.name+' recognized tables and directed facts')
assert v_sample['verdict']==v_full['verdict']=='PASS'
assert v_sample['warn_count']==v_full['warn_count']==0
record={'report_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'tool_extracted':len(points),'excluded':len(excluded),
    'supplemented_annual':sum(p.get('supplemented',False) for p in valid),'effective_population':len(valid),
    'seed':20261030,'random_count':len(sample),'random_coverage_pct':len(sample)/len(valid)*100,
    'directed_count':len(directed),'full_table_and_directed_count':len(checks)+len(directed),'sample_verdict':v_sample,'full_verdict':v_full,
    'scope':'Recognized financial tables plus annual supplementation, not every number in prose. Model checks validate arithmetic and stated assumptions, not forecast truth.'}
for name,value in [('audit-universe.json',points),('audit-exclusions.json',excluded),('audit-sample.json',sample),('audit-checks.json',checks+directed),('audit-summary.json',record)]:
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
clean='\n'.join(x.rstrip() for x in re.sub(r'\x1b\[[0-9;]*m','',log.getvalue()).splitlines())+'\n'
(HERE/'audit-verdict.txt').write_text(clean,encoding='utf-8')
print(json.dumps(record,ensure_ascii=False,indent=2))
