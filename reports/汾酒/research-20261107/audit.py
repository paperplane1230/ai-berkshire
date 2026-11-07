"""Reproducible sample, complete recognized tables and directed narrative checks."""
import hashlib
import io
import json
import math
from pathlib import Path
import random
import re
import sys
from contextlib import redirect_stdout
from decimal import Decimal, getcontext
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REPORT=HERE.parent/'山西汾酒研究报告-20261107.md'
sys.path.insert(0,str(ROOT/'tools'))
import report_audit as audit
from financial_rigor import exact as D
getcontext().prec=40
sys.stdout.reconfigure(encoding='utf-8')
load=lambda n:json.loads((HERE/n).read_text(encoding='utf-8'))
I=load('inputs.json'); C=load('calculations.json'); O=load('operating-inputs.json')
Y=D('1e8');body=REPORT.read_text(encoding='utf-8')
points=audit.extract_data_points(body)
noise={37:'Q3 marker',45:'Q2 marker',48:'July month',49:'Q1 marker',52:'June month',55:'year label',86:'research year',87:'PDF page count',89:'meeting year',90:'quote month',91:'quote minute',92:'quote minute'}
assert len(points)==92,'Reclassify changed report universe before seeded sampling'
excluded=[dict(p,reason=noise[p['id']]) for p in points if p['id'] in noise]
valid=[p for p in points if p['id'] not in noise]
for row,col,value,unit,line,raw in audit._parse_md_tables(body.splitlines()):
    if row in ('2023','2024','2025','2025Q4','2026Q1','2026Q2','2026Q3') or (row in ('品牌','渠道','地区') and col=='同比'):
        valid.append({'id':93+sum(bool(p.get('supplemented')) for p in valid),'label':row+' · '+col,'reported_value':value,'unit':unit,'line_number':line,'raw_text':raw,'supplemented':True})
F={'营业收入':'revenue','归母净利润':'profit','扣非归母':'core','营业利润':'operating_profit','经营现金流':'cfo','资本开支付现':'capex','简化自由现金流':'simple_fcf'}
P={'2025前三季':'2025YTD','2026前三季':'2026YTD','2025单Q3':'2025Q3','2026单Q3':'2026Q3'}
B={'货币资金':'cash','其他流动资产':'other_current_assets','应收款项融资':'bills_financing','租赁负债':'lease_liability','一年内到期非流动负债':'current_noncurrent_debt','使用权资产':'right_of_use','在建工程':'construction','归母净资产':'parent_equity'}
S={s['name']:s for s in C['scenarios']}
def reference(p):
    if p['id']==88:return D(I['notes']['dividend_paid_2026_per_share']),'S5 actual distribution','historical_fact'
    row,col=p['label'].split(' · ',1)
    if row in F:return D(C['periods'][P[col]][F[row]]),'S1/S2 consolidated values and quarter difference','source_or_arithmetic'
    if row in ('2023','2024','2025'):return D(I['financial'][row][F[col]])/Y,'S3 annual table; S4 independent vendor fields','source_fact'
    if row in ('2025Q4','2026Q1','2026Q2','2026Q3'):
        f={'收入（亿元）':'revenue','归母（亿元）':'profit','经营现金（亿元）':'cfo','毛利率':'gross_margin_pct'}[col]
        return D(C['periods'][row][f]),'S1/S2/S3/S6, consistent quarterly sequence','arithmetic'
    if row in ('品牌','渠道','地区'):
        item=[t.strip() for t in p['raw_text'].strip('|').split('|')][1]
        if col=='同比':return D(O['rows'][item]['yoy']),'S9 issuer operating announcement','single_primary'
        return D(O['rows'][item]['revenue'])/Y,'S9 original ten-thousand CNY to yuan to 100 million','single_primary'
    if row in B:
        period='2026H1' if col=='判断边界' else '2026Q3'
        return D(I['balance'][period][B[row]])/Y,'S1/S2 balance sheet; period explicitly distinguished','single_primary'
    if row.startswith('2026利润微降'):return (D(I['financial']['2026YTD']['profit'])/D(I['financial']['2025YTD']['profit'])-1)*100,'S1 same-period profit change','arithmetic'
    if row=='零有息债务、只有少量租赁':return D(I['balance']['2026Q3']['lease_liability'])/Y,'S1 noncurrent lease liabilities','single_primary'
    if row.startswith('12.9倍、'):return D(C['ttm']['profit']),'Current reported TTM replacing old denominator','arithmetic'
    if row in ('2025年度现金分红','历史已付股息率'):
        if row=='历史已付股息率' and col=='数值':return D(C['valuation']['trailing_paid_dividend_yield_pct']),'S5 actual DPS / S10 current price','arithmetic'
        return D(I['notes']['dividend_paid_2026_per_share']),'S5 implemented DPS, not future promise','historical_fact'
    if row=='市场与渠道投入':return (D(I['financial']['2026YTD']['sales_expense'])/D(I['financial']['2025YTD']['sales_expense'])-1)*100,'S1 sales expense year over year','arithmetic'
    if row=='TTM营业收入':return D(C['ttm']['revenue']),'S3 + S1 current - prior YTD','arithmetic'
    if row=='TTM归母 / 扣非归母':return D(C['ttm']['profit']),'TTM parent; core checked separately','arithmetic'
    if row=='归母 / 扣非TTM PE':
        if col=='含义':return D('12.9'),'R1 old rounded PE, explicitly not current valuation','historical_fact'
        return D(C['valuation']['TTM_PE']),'S1/S3/S10 parent valuation; core checked separately','arithmetic'
    if row=='TTM经营现金 / 简化FCF':return D(C['ttm']['cfo']),'TTM CFO; FCF checked separately','arithmetic'
    if row=='TTM简化FCF收益率':return D(C['valuation']['simple_FCF_yield_pct']),'Simple FCF / current market cap','arithmetic'
    if row in ('压力','基准','较强恢复'):
        s=S[{'压力':'bear','基准':'base','较强恢复':'bull'}[row]]
        keys={'年利润增速':'annual_growth_pct','退出PE':'exit_PE','第5年股价（元）':'terminal_price_CNY','五年股息（元/股）':'dividend_sum_CNY','税前年化IRR':'IRR_pct','10%折现现值（元）':'PV10_CNY'}
        value=s['annual_profit'][-1] if col=='第5年利润（亿元）' else s[keys[col]]
        return D(value),'Explicit five-year assumption/model, not a financial disclosure','model_assumption' if col in ('年利润增速','退出PE') else 'model_arithmetic'
    if row.startswith('95—105') or row.startswith('约147'):return D('10'),'Explicit discount hurdle, not guaranteed return','model_assumption'
    raise ValueError(p)
checks=[]
for p in valid:
    value,source,kind=reference(p)
    digits=max(0,-Decimal(str(p['reported_value'])).as_tuple().exponent)
    checks.append(dict(p,fetched_value=float(value.quantize(D(1).scaleb(-digits))),fetched_exact=str(value),fetched_source=source,verification_kind=kind))
sample_ids={p['id'] for p in random.Random(20261107).sample(valid,math.ceil(len(valid)*.15))}
sample=[p for p in checks if p['id'] in sample_ids]
targeted=[]
def target(label,reported,value,source,kind='arithmetic'):
    targeted.append({'id':2001+len(targeted),'label':label,'reported_value':float(reported),'fetched_value':float(value),'fetched_exact':str(value),'fetched_source':source,'unit':'report units','verification_kind':kind})
target('last trading day close',132,I['quote']['price'],'S10 two 2026-11-06 snapshots; research day is Saturday','source_fact')
target('shares hundred million',12.19964222,D(I['shares'])/Y,'S1 independent registered capital','source_fact')
target('market cap',1610.35,C['valuation']['market_cap'],'Price times registered shares')
target('PB',4.03,C['valuation']['PB'],'S1 equity and S10 quote')
target('TTM core profit',91.7883,C['ttm']['core'],'TTM reconstruction')
target('TTM core PE',17.54,C['valuation']['TTM_core_PE'],'TTM core reconstruction')
target('TTM FCF',71.6238,C['ttm']['simple_fcf'],'Cashflow less cash capital expenditure')
target('Q3 gross margin',70.04,C['periods']['2026Q3']['gross_margin_pct'],'Same-quarter difference formula')
target('Q3 sales fee ratio',13.64,C['periods']['2026Q3']['sales_expense_revenue_pct'],'Same-quarter difference formula')
target('Q3 cash/profit',67.56,C['periods']['2026Q3']['cfo_parent_ratio_pct'],'CFO divided by parent profit')
target('YTD cash/profit',95.16,C['periods']['2026YTD']['cfo_parent_ratio_pct'],'CFO divided by parent profit')
target('Q3 sales cash',61.6170,C['periods']['2026Q3']['sale_cash'],'S1-S2 sales cash')
target('DIO days',532,C['cash_and_quality']['DIO_273_days'],'273 days and mean balance, NOT dealer inventory days')
target('narrow cash less obligations',46.3303,C['cash_and_quality']['cash_equivalents_less_named_debt'],'Scoped observation, NOT full net cash')
target('H1 term deposits',256.6969,D(I['notes']['h1_term_deposits_interest'])/Y,'S2 footnote; not Q3 amount','single_primary')
target('H1 pledged term deposits',25.6907,D(I['notes']['h1_term_deposit_pledged'])/Y,'S2 restriction detail','single_primary')
target('2030 project budget',91.0182,D(I['notes']['h1_capex_project_2030_budget'])/Y,'S2 project budget, not remaining irrevocable spend','single_primary')
target('project paid percentage',31.72,I['notes']['h1_capex_project_2030_spent_pct'],'S2 project table','single_primary')
target('paid dividend total',80.0297,D(I['notes']['dividend_paid_2026_total'])/Y,'S5 implemented distribution','source_fact')
target('9m FCF/paid prior-year dividend',91.36,D(C['periods']['2026YTD']['simple_fcf'])/(D(I['notes']['dividend_paid_2026_total'])/Y)*100,'Period mismatch disclosed: not annual sustainability verdict')
target('TTM 65% policy sensitivity',59.6681,D(C['ttm']['profit'])*D('.65'),'Mechanical sensitivity, not declared dividend','model_arithmetic')
target('growth required for 10% return',7.83,C['required_growth_for_10pct_IRR']['annual_growth_pct'],'PE16/payout65%/5-year reverse model','model_arithmetic')
target('classified dealer count',4321,sum(row[0] for row in O['dealer_rows']),'S9 category count, not deduplicated entities','single_primary')
target('net dealer reduction',134,sum(row[2]-row[1] for row in O['dealer_rows']),'S9 category movement','single_primary')
target('online/direct share',7.38,D(O['rows']['直销、电商']['revenue'])/D(O['total'])*100,'S9 wine revenue denominator')
log=io.StringIO()
with redirect_stdout(log):
    chosen=audit.render_verdict(sample+targeted,REPORT.name+' random + directed')
    full=audit.render_verdict(checks,REPORT.name+' recognized and supplemented tables')
assert chosen['verdict']==full['verdict']=='PASS' and chosen['warn_count']==full['warn_count']==0
assert not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',body)
summary={'report_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'extracted':len(points),'excluded':len(excluded),'supplemented':sum(bool(p.get('supplemented')) for p in valid),'effective_table_points':len(valid),'seed':20261107,'random_count':len(sample),'random_coverage_pct':len(sample)/len(valid)*100,'directed_count':len(targeted),'selected_verdict':chosen,'full_table_verdict':full,'limits':'Recognized tables plus explicit annual/quarter/operating supplements, not exhaustive prose numerals. Facts, policies and model assumptions separately tagged. PASS does not validate forecasts.'}
for name,obj in [('audit-universe.json',points),('audit-exclusions.json',excluded),('audit-checks.json',checks),('audit-sample.json',sample),('audit-directed.json',targeted),('audit-summary.json',summary)]:
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
clean='\n'.join(line.rstrip() for line in re.sub(r'\x1b\[[0-9;]*m','',log.getvalue()).splitlines()).rstrip()+'\n'
(HERE/'audit-verdict.txt').write_text(clean,encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
