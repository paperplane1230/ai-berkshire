"""Seeded audit with exclusions before sampling and annual-table supplementation."""
import contextlib
import hashlib
import io
import json
import math
import random
import re
import sys
from decimal import Decimal as D
from pathlib import Path
from calculate import calculate

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]/'tools'))
import report_audit as audit
REPORT=HERE.parent/'中国中免研究报告-20261030.md'
body=REPORT.read_text(encoding='utf-8')
I,C=calculate()
points=audit.extract_data_points(body)
excluded=[p for p in points if p['label'] in ('研究日','京沪机场与线上整合能否带来增长 · 本次追踪') or p['label'].startswith('cny)，')]
assert len(excluded)==3,'Review changed extraction noise before sampling'
valid=[p for p in points if p not in excluded]
for row,col,value,unit,line,raw in audit._parse_md_tables(body.splitlines()):
    if row in ('2023','2024','2025'):
        valid.append({'id':len(points)+1+sum(p.get('supplemented',False) for p in valid),'label':row+' · '+col,'reported_value':value,'unit':unit,'line_number':line,'raw_text':raw,'supplemented':True})

financial={'营业收入':'revenue','归母净利润':'profit','扣非归母':'adjusted','合并净利润':'net_profit','营业利润':'operating_profit','经营现金流':'cfo','资本开支付现':'capex','简化自由现金流':'simple_fcf'}
periods={'2025累计':'2025YTD','2026累计':'2026YTD','2025单Q3':'2025Q3','2026单Q3':'2026Q3'}
products={'免税商品':'duty_free','有税商品':'taxed'}
product_fields={'2025收入（亿元）':'annual_revenue_yi','2025毛利率':'annual_margin_pct','2026H1收入（亿元）':'h1_revenue_yi','2026H1毛利率':'h1_margin_pct'}
assets={'三亚市内免税店':'sanya','海口免税城公司':'haikou','海免公司':'haimian'}
asset_fields={'总资产':'assets','半年收入':'revenue','半年净利润':'profit','简化净利率':'net_margin_pct'}
balance={'货币资金':'cash','存货':'inventory','应收账款':'receivables','应付账款':'payables','使用权资产':'right_of_use','租赁负债（非流动）':'lease_liability','一年内到期非流动负债':'current_noncurrent_debt','商誉':'goodwill'}
snames={'压力':0,'基准':1,'乐观':2}
sfields={'第五年EPS（元）':'year5_eps','五年股息合计（元）':'dividend_sum_CNY','A退出价（元）':'A_exit_CNY','H退出价（港元）':'H_exit_HKD','A税前IRR':'A_IRR_pct','H税前IRR':'H_IRR_pct'}

def reference(p):
    row,col=p['label'].split(' · ')
    if row in financial:
        key=financial[row]
        if col in periods:return C['periods'][periods[col]][key],'S1/S2, raw consolidated inputs and exact difference','financial_calculation'
        return C['growth']['YTD' if col=='累计同比' else 'Q3'][key],'S1/S2, same-period growth','financial_calculation'
    if row in products:return C['products'][products[row]][product_fields[col]],'S2/S3 product tables; issuer single source','single_source_calculation'
    if row in assets:return C['operating_assets'][assets[row]][asset_fields[col]],'S2 subsidiary table, converted from ten-thousand yuan; single source','single_source_calculation'
    if row in balance:
        key=balance[row]+('_yearend' if col=='2025年末' else '')
        return D(I['balance'][key])/D('1e8'),'S1 consolidated balance sheet; single source','single_source_fact'
    if row in ('TTM归母净利润','TTM扣非归母','当前股本口径TTM EPS'):
        return C['ttm'][{'TTM归母净利润':'profit','TTM扣非归母':'adjusted','当前股本口径TTM EPS':'eps'}[row]],'S1/S2/S3 TTM with current legal shares','financial_calculation'
    if row in ('归母TTM PE','扣非TTM PE','PB','历史税前股息率'):
        key=('H' if col=='H股' else 'A')+{'归母TTM PE':'_PE','扣非TTM PE':'_adjusted_PE','PB':'_PB','历史税前股息率':'_historical_dividend_yield_pct'}[row]
        return C['valuation'][key],'Current quotes and exact same-GAAP numerator/denominator','financial_calculation'
    if row in snames:
        n=snames[row]
        if col=='每股盈利年增长':return D(I['scenarios'][n]['growth'])*100,'Explicit growth assumption, not a financial fact','assumption'
        if col=='A/H退出PE':return D(I['scenarios'][n]['A_exit_PE']),'Explicit A exit PE assumption; H values separately checked','assumption'
        return C['scenarios'][n][sfields[col]],'Finite five-year distribution and exit model, not an outcome forecast','model_calculation'
    if row in ('2023','2024','2025'):
        return C['periods'][row][financial[col]],'S3 three-year primary table, S4 independent vendor cross-check','source_fact'
    raise ValueError(p)

checks=[]
for p in valid:
    exact,source,kind=reference(p)
    # Compare at the displayed report precision; retain the unrounded reference.
    places=max(0,-D(str(p['reported_value'])).as_tuple().exponent)
    rounded=exact.quantize(D('1').scaleb(-places))
    checks.append({**p,'fetched_value':float(rounded),'fetched_exact':str(exact),'fetched_source':source,'verification_kind':kind})
sample_ids={p['id'] for p in random.Random(20261030).sample(valid,math.ceil(len(valid)*.15))}
sample=[p for p in checks if p['id'] in sample_ids]
focused=[]
def add(label,reported,value,source,kind='financial_calculation'):
    focused.append({'id':1000+len(focused),'label':label,'reported_value':reported,'fetched_value':float(value),'fetched_source':source,'verification_kind':kind,'unit':''})
add('A current price',50.30,D('50.30'),'S5 Tencent and Sina 2026-10-30','source_fact')
add('H current price HKD',42.44,D('42.44'),'S5 Tencent and Sina 2026-10-30','source_fact')
add('Combined A/H cap CNY hundred million',1027.20,C['valuation']['combined_cap_CNY_yi'],'A shares*A price + H shares*H price*same-day FX')
add('H discount percent',28.45,C['valuation']['H_discount_pct'],'A/H quotes, single-source same-day FX')
add('YTD minority bridge CNY hundred million',4.73,C['growth']['YTD']['minority_bridge_yi'],'S1 net profit less attributable profit bridge')
add('H1 FCF after financing lease cash',13.82,C['periods']['2026H1']['fcf_after_lease_cash'],'S2 OCF less capex less lease financing payments, not all rent')
add('TTM simple FCF',35.16,C['ttm']['simple_fcf'],'S1/S2/S3, not lease-adjusted FCFE')
add('Named debt sum',104.49,C['balance']['named_debt_yi'],'S1 short/long loans, current noncurrent debt, leases')
add('Debt-obligation-subtracted cash observation',129.59,C['balance']['cash_minus_named_debt_yi'],'S1 explicit boundary, not freely distributable surplus')
add('Base A 10-percent present value',41.77,C['scenarios'][1]['A_PV10_CNY'],'Model cashflow discounted at 10%; CNY','model_calculation')
add('Base H 10-percent present value CNY',33.47,C['scenarios'][1]['H_PV10_CNY'],'Model cashflow discounted at 10%; CNY not HKD','model_calculation')
add('2026 announced distribution per share',.40,D('.40'),'S10 approved by board under shareholder delegation; implementation pending','single_source_fact')
for n,label in enumerate(('bear','base','bull')):
    add(label+' H exit PE assumption',int(I['scenarios'][n]['H_exit_PE']),D(I['scenarios'][n]['H_exit_PE']),'Explicit H-model input; not company guidance','assumption')
add('2025 fiscal-year dividend per old share',.70,D('.25')+D('.45'),'S3 interim and S9 final distribution; historical reference only','source_fact')
log=io.StringIO()
with contextlib.redirect_stdout(log):
    verdict=audit.render_verdict(sample+focused,REPORT.name+' random sample plus directed')
    full=audit.render_verdict(checks,REPORT.name+' all recognized and supplemented tables')
assert verdict['verdict']==full['verdict']=='PASS'
assert verdict['warn_count']==full['warn_count']==0
assert not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',body)
summary={'report_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'tool_extracted':len(points),'excluded':len(excluded),'supplemented_annual':sum(p.get('supplemented',False) for p in valid),'effective_table_population':len(valid),'seed':20261030,'random_count':len(sample),'random_coverage_pct':len(sample)/len(valid)*100,'focused_count':len(focused),'total_sample_and_focused':len(sample)+len(focused),'verdict':verdict,'full_table_verdict':full,'limits':'Recognized/supplemented financial tables; prose separately directed, not a claim of exhaustive all-prose extraction. Model inputs are not financial facts. Display precision is applied and unrounded values retained.'}
for name,value in [('audit-universe.json',points),('audit-excluded.json',excluded),('audit-all-checks.json',checks),('audit-sample.json',sample),('audit-results.json',sample+focused),('audit-summary.json',summary)]:
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
clean=re.sub(r'\x1b\[[0-9;]*m','',log.getvalue())
(HERE/'audit-verdict.txt').write_text('\n'.join(x.rstrip() for x in clean.splitlines())+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
