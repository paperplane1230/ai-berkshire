"""Fixed-seed source/arithmetic audit. Forecast assumptions are not facts."""
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

HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'五粮液研究报告-20261105.md'
sys.path.insert(0,str(HERE.parents[2]/'tools'))
import report_audit as audit
sys.stdout.reconfigure(encoding='utf-8')
I=json.loads((HERE/'inputs.json').read_text(encoding='utf-8'))
C=json.loads((HERE/'calculations.json').read_text(encoding='utf-8'))
body=REPORT.read_text(encoding='utf-8')
Y=D('100000000')
points=audit.extract_data_points(body)
noise={59:'Q3 marker, not a financial amount',61:'June month',62:'fiscal year label',94:'research year',95:'August month',96:'PDF page count',97:'PDF page count',98:'PDF page count',99:'quote month',100:'quote minute',101:'quote minute',102:'URL port',103:'June month'}
assert len(points)==103,'Report changed: reclassify population before sampling'
excluded=[dict(p,exclusion_reason=noise[p['id']]) for p in points if p['id'] in noise]
valid=[p for p in points if p['id'] not in noise]
for row,col,value,unit,line,raw in audit._parse_md_tables(body.splitlines()):
    if row in ('2023','2024','2025'):
        valid.append({'id':104+sum(bool(p.get('supplemented')) for p in valid),
          'label':row+' · '+col,'reported_value':value,'unit':unit,
          'line_number':line,'raw_text':raw,'supplemented':True})

financial={'营业收入':'revenue','归母净利润':'profit','扣非归母':'core','经营现金流':'cfo','资本开支付现':'capex','简化自由现金流':'simple_fcf'}
periods={'2025前三季':'2025YTD','2026前三季':'2026YTD','2025单Q3':'2025Q3','2026单Q3':'2026Q3'}
balances={'货币资金':'cash','应收款项融资':'bills_financing','存货':'inventory','合同负债':'contract_liabilities','其他流动负债总额':'other_current_liabilities'}
dates={'2025年末':'2025end','2026年6月末':'2026H1','2026年9月末':'2026Q3'}
scenarios={s['name']:s for s in C['scenarios']}

def reference(p):
    row,col=p['label'].split(' · ',1)
    if row in financial:
        key=financial[row]
        if col in periods:return D(C['periods'][periods[col]][key]),'S1/S2, corrected comparatives and quarter subtraction','arithmetic'
        old,new=('2025YTD','2026YTD') if col=='累计同比' else ('2025Q3','2026Q3')
        return (D(C['periods'][new][key])/D(C['periods'][old][key])-1)*100,'S1/S2 exact year-over-year formula','arithmetic'
    if row in ('2023','2024','2025'):
        return D(I['financial'][row][financial[col]])/Y,'S3 annual comparative table; S5 vendor cross-check','source_fact'
    if row in ('五粮液产品','其他酒产品'):
        v=I['products_h1']['wuliangye' if row=='五粮液产品' else 'other_liquor']
        if col=='上半年收入（亿元）':value=D(v['revenue'])/Y
        elif col=='收入同比':value=D(v['yoy_revenue_pct'])
        elif col=='毛利率':value=(1-D(v['cost'])/D(v['revenue']))*100
        else:value=D(v['volume_tonnes'])
        return value,'S2 product table; issuer-only source','single_primary'
    if row in balances:
        return D(I['balance'][dates[col]][balances[row]])/Y,'S1/S2 consolidated balance sheet','single_primary'
    if row in ('其中：监管商品款项','其他流动资产中的监管商品'):
        prefix='regulatory_receipts_' if row.startswith('其中') else 'regulatory_goods_'
        return D(I['notes'][prefix+dates[col]])/Y,'S2 note: distinguish liability component from total; not a release flow','single_primary'
    if row.startswith('每年分红200亿元'):
        return D('70'),'S7 shareholder plan percentage; correction of old inference','policy_parameter'
    if row=='2025所属年度中期加末期':
        return (D('10006785436.89')+D('10006785262.74'))/Y,'S3 2025 interim plus S8 actual final payment','source_fact'
    if row=='2025末期实际每股派息':return D('2.5796852'),'S8 implementation notice: entitled shares basis','source_fact'
    if row=='2026前三季合并分红、利润或利息付现':return D(I['financial']['2026YTD']['dividend_interest_cash'])/Y,'S1 consolidated financing cashflow','source_fact'
    if row=='2026所属年度规划金额下限':return D('200'),'S7 existing 2024-2026 plan, not already declared cash','policy_parameter'
    ttm={'TTM营业收入':'revenue','TTM归母净利润':'profit','TTM扣非归母':'core','TTM经营现金流':'cfo','TTM简化自由现金流':'simple_fcf'}
    if row in ttm:return D(C['ttm'][ttm[row]]),'S3 + S1 current - S1 corrected prior YTD','arithmetic'
    if row=='归母TTM PE':return D(C['valuation']['TTM_PE']),'S1/S3/S5/S6 valuation','arithmetic'
    if row=='扣非TTM PE':
        if col=='口径':return D('220'),'R1 prior approximate hypothesis explicitly NOT adopted as current profit','historical_hypothesis'
        return D(C['valuation']['TTM_core_PE']),'S1/S3/S5/S6 core valuation','arithmetic'
    if row in ('压力','基准','乐观'):
        s=scenarios[{'压力':'bear','基准':'base','乐观':'bull'}[row]]
        key={'每股盈利年增速':'growth','第五年EPS（元）':'year5_EPS_CNY','退出PE':'exit_PE','第五年价格（元）':'terminal_price_CNY','五年股息合计（元）':'dividend_sum_CNY','税前年化IRR':'IRR_pct'}[col]
        v=D(s[key])*(100 if key=='growth' else 1)
        kind='model_assumption' if key in ('growth','exit_PE') else 'model_arithmetic'
        return v,'Explicit five-year model; NOT future facts',kind
    if row=='当前75.82元附近':return D('200'),'Reference to rejected perpetual 200bn assumption, not a forecast','historical_hypothesis'
    raise ValueError(p)

checks=[]
for p in valid:
    value,source,kind=reference(p)
    # Keep unrounded reference, then compare at report display precision.
    digits=max(0,-D(str(p['reported_value'])).as_tuple().exponent)
    shown=value.quantize(D('1').scaleb(-digits))
    checks.append(dict(p,fetched_value=float(shown),fetched_exact=str(value),fetched_source=source,verification_kind=kind))
sample_ids={p['id'] for p in random.Random(20261105).sample(valid,math.ceil(len(valid)*.15))}
sample=[p for p in checks if p['id'] in sample_ids]
focused=[]
def focus(label,reported,value,source,kind='arithmetic'):
    focused.append({'id':2001+len(focused),'label':label,'reported_value':float(reported),'fetched_value':float(value),'fetched_exact':str(value),'fetched_source':source,'unit':'report units','verification_kind':kind})

focus('现价',75.82,I['quote']['price'],'S6 two quote snapshots','source_fact')
focus('注册总股本亿股',38.81608005,D(I['shares'])/Y,'S1 registered capital; not treasury-adjusted','source_fact')
focus('市值亿元',2943.04,C['valuation']['market_cap'],'Registered shares times dual-source price')
focus('历史年度股息率',6.80,(D('2.578')+D('2.5796852'))/D(I['quote']['price'])*100,'S3 interim dividend and S8 actual final DPS; not future yield')
focus('累计毛利率',79.89,C['periods']['2026YTD']['gross_margin_pct'],'S1 income/cost')
focus('累计销售费率',23.73,C['periods']['2026YTD']['sales_expense_revenue_pct'],'S1 sales expense/revenue')
focus('单Q3毛利率',77.32,C['periods']['2026Q3']['gross_margin_pct'],'S1-S2 income/cost')
focus('单Q3销售费率',33.23,C['periods']['2026Q3']['sales_expense_revenue_pct'],'S1-S2 sales expense/revenue')
focus('单Q3归母净利率',21.56,C['periods']['2026Q3']['parent_margin_pct'],'S1 direct quarter profit/revenue')
focus('商品酒期末库存吨',49291,I['volume_h1']['end_inventory_tonnes'],'S2 physical volume table','single_primary')
focus('现金等价物亿元',1086.31,D(I['balance']['2026Q3']['cash_equivalents'])/Y,'S1 consolidated cashflow ending balance','single_primary')
focus('到期及租赁负债合计亿元',2.17,(D(I['balance']['2026Q3']['current_noncurrent_debt'])+D(I['balance']['2026Q3']['lease_liability']))/Y,'S1 explicitly scoped obligations','single_primary')
focus('集团财务公司存款亿元',466.80,D(I['notes']['finance_company_deposit_2026H1'])/Y,'S2 H1 note, not assumed September balance','single_primary')
focus('70%对应200亿的利润门槛',285.71,D(200)/D('.70'),'Policy arithmetic, not cash sustainability threshold')
focus('220亿净利分200亿派息比例',90.91,D(200)/D(220)*100,'Explicit counterexample arithmetic')
focus('已回购金额亿元',18.0074,D('1800737009.41')/Y,'S9 actual through 2026-10-31, not plan','source_fact')
focus('已回购股数万股',2453.7438,D('24537438')/D(10000),'S9 actual share count','source_fact')
for name,value in [('bear','32.91'),('base','62.68'),('bull','93.58')]:
    focus(name+' 10%折现价',value,scenarios[name]['PV10_CNY'],'Explicit model discounted annual cashflows','model_arithmetic')
focus('无首年固定200亿基准IRR',4.66,scenarios['base']['all_years_70pct_sensitivity']['IRR_pct'],'Explicit sensitivity, not prediction','model_arithmetic')
focus('无首年固定200亿基准PV',60.04,scenarios['base']['all_years_70pct_sensitivity']['PV10_CNY'],'Explicit sensitivity, not prediction','model_arithmetic')
focus('10%回报所需增长',10.60,C['required_growth_for_10pct_IRR_at_20PE']['growth_pct'],'Reverse model requirement; NOT management guidance','model_arithmetic')
log=io.StringIO()
with redirect_stdout(log):
    sampled=audit.render_verdict(sample+focused,REPORT.name+' random + directed')
    whole=audit.render_verdict(checks,REPORT.name+' full recognized table universe')
assert sampled['verdict']==whole['verdict']=='PASS'
assert sampled['warn_count']==whole['warn_count']==0
assert not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',body)
assert '<!-- SCENARIO' not in body and '<!-- ACTION' not in body
summary={'report_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'raw_points':len(points),'excluded':len(excluded),'supplemented_annual':12,'effective_table_points':len(valid),'seed':20261105,'random_count':len(sample),'random_coverage_pct':len(sample)/len(valid)*100,'directed_count':len(focused),'random_plus_directed':sampled,'full_table_verdict':whole,'scope':'Numeric consistency of source facts, policies and model assumptions, separately tagged; not forecast validation. Narrative values are targeted, not exhaustively sampled.'}
for name,obj in [('audit-universe.json',points),('audit-exclusions.json',excluded),('audit-sample.json',sample),('audit-checks.json',checks),('audit-directed.json',focused),('audit-summary.json',summary)]:
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
clean=lambda s:'\n'.join(line.rstrip() for line in re.sub(r'\x1b\[[0-9;]*m','',s).splitlines()).rstrip()+'\n'
(HERE/'audit-verdict.txt').write_text(clean(log.getvalue()),encoding='utf-8')
if C.get('financial_rigor',{}).get('log'):
    (HERE/'financial-rigor.txt').write_text(clean(C['financial_rigor']['log']),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
