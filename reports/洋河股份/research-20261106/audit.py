"""Seeded table audit plus targeted checks; assumptions are not verified forecasts."""
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
REPORT=HERE.parent/'洋河股份研究报告-20261106.md'
sys.path.insert(0,str(ROOT/'tools'))
import report_audit as audit
from financial_rigor import exact as D
getcontext().prec=40
sys.stdout.reconfigure(encoding='utf-8')
I=json.loads((HERE/'inputs.json').read_text(encoding='utf-8'))
C=json.loads((HERE/'calculations.json').read_text(encoding='utf-8'))
Y=D('1e8')
body=REPORT.read_text(encoding='utf-8')
points=audit.extract_data_points(body)
noise={43:'Q3 period marker',50:'H1 period marker',52:'Q3 period marker',53:'Q3 period marker',57:'August month',58:'year label',60:'Q1 period marker',62:'Q3 period marker',104:'research year',105:'PDF page count',106:'PDF page count',107:'quote year',108:'quote minute',109:'quote minute'}
assert len(points)==109,'Review changed universe and exclusions before sampling'
excluded=[dict(p,exclusion_reason=noise[p['id']]) for p in points if p['id'] in noise]
valid=[p for p in points if p['id'] not in noise]
for row,col,value,unit,line,raw in audit._parse_md_tables(body.splitlines()):
    if row in ('2023','2024','2025'):
        valid.append({'id':110+sum(bool(p.get('supplemented')) for p in valid),'label':row+' · '+col,'reported_value':value,'unit':unit,'line_number':line,'raw_text':raw,'supplemented':True})
F={'营业收入':'revenue','归母净利润':'profit','扣非归母':'core','营业利润':'operating_profit','经营现金流':'cfo','资本开支付现':'capex','简化自由现金流':'simple_fcf'}
P={'2025前三季':'2025YTD','2026前三季':'2026YTD','2025单Q3':'2025Q3','2026单Q3':'2026Q3'}
B={'货币资金':'cash','现金及现金等价物':'cash_equivalents','交易性金融资产':'trading_financial_assets','其他非流动金融资产':'noncurrent_financial_assets','长期股权投资':'long_equity_investments','存货':'inventory','归母净资产':'parent_equity'}
S={s['name']:s for s in C['scenarios']}
debt=sum(D(I['balance']['2026Q3'][k]) for k in ('short_debt','long_debt','current_noncurrent_debt','lease_liability'))

def ref(p):
    row,col=p['label'].split(' · ',1)
    if row in F:return D(C['periods'][P[col]][F[row]]),'S1/S2 direct values or quarter difference','source_or_arithmetic'
    if row in ('2023','2024','2025'):return D(I['financial'][row][F[col]])/Y,'S3 annual comparison; S4 independently captured fields','source_fact'
    products={'中高档酒':'mid_high_liquor','普通酒':'ordinary_liquor','省内酒类':'liquor_in_province','省外酒类':'liquor_out_province'}
    if row in products:return D(I['products_h1'][products[row]]['revenue'])/Y,'S2 same-period liquor-specific segment table','single_primary'
    if row in ('预收货款','应付经销商未结算折扣折让'):
        prefix='prepayment_' if row=='预收货款' else 'unsettled_rebates_'
        suffix='2025end' if col=='2025年末' else '2026H1'
        return D(I['notes'][prefix+suffix])/Y,'S2/S3 note: prepayments versus unsettled rebates','single_primary'
    if row=='合同负债合计':
        key={'2025年末':'2025end','2026年6月末':'2026H1','2026年9月末':'2026Q3'}[col]
        return D(I['balance'][key]['contract_liabilities'])/Y,'S1/S2/S3 total only; no inferred September breakdown','single_primary'
    if row in B:
        if col=='判断边界':return D(C['valuation']['PB']),'S1 equity and S10 price','arithmetic'
        return D(I['balance']['2026Q3'][B[row]])/Y,'S1 consolidated balance sheet','single_primary'
    if row=='列示借款及租赁相关义务':return debt/Y,'S1 explicitly scoped debt and lease sum','arithmetic'
    if row.startswith('半年经销商净减'):return abs(D(I['volume_h1']['dealer_change'])),'S2 dealer count net change','single_primary'
    if row.startswith('2026Q1 TTM已是低点'):return D(C['ttm']['profit']),'Actual TTM counterexample to old conditional hypothesis','arithmetic'
    if row=='100%分红保障高股息':
        return (D('70'),'S5 old monetary floor explicitly not retained','historical_policy') if col=='本次结果' else (D('1.47'),'S6 paid 2025 DPS, explicitly not fixed future coupon','historical_fact')
    tm={'TTM营业收入':'revenue','TTM归母净利润':'profit','TTM扣非归母':'core','TTM经营现金流':'cfo','TTM简化自由现金流':'simple_fcf'}
    if row in tm:return D(C['ttm'][tm[row]]),'S3 plus S1 current minus prior YTD','arithmetic'
    if row in ('归母TTM PE','扣非TTM PE'):
        return D(C['valuation']['TTM_PE' if row=='归母TTM PE' else 'TTM_core_PE']),'Near-zero-denominator arithmetic, not normalized valuation','arithmetic'
    if row in ('压力','基准恢复','较强恢复'):
        s=S[{'压力':'bear','基准恢复':'base','较强恢复':'bull'}[row]]
        m=re.match(r'第([1-5])年',col)
        if m:return D(s['annual_profit'][int(m[1])-1]),'Explicit recovery path assumption, not financial guidance','model_assumption'
        key={'退出PE':'exit_PE','五年股息（元/股）':'dividend_sum_CNY','税前年化IRR':'IRR_pct'}[col]
        return D(s[key]),'Five-year equity model, no added financial assets','model_assumption' if key=='exit_PE' else 'model_arithmetic'
    if row in ('0亿元','100亿元','150亿元','180亿元'):
        asset=D(row.replace('亿元','')); multiple=D(re.match(r'\d+',col)[0])
        return (D(C['valuation']['market_cap'])-asset)/multiple,'Independent conditional asset/operating-profit reverse test; A is not proven net cash','model_arithmetic'
    raise ValueError(p)

checks=[]
for p in valid:
    value,source,kind=ref(p)
    digits=max(0,-Decimal(str(p['reported_value'])).as_tuple().exponent)
    checks.append(dict(p,fetched_exact=str(value),fetched_value=float(value.quantize(D(1).scaleb(-digits))),fetched_source=source,verification_kind=kind))
sample_ids={p['id'] for p in random.Random(20261106).sample(valid,math.ceil(len(valid)*.15))}
sample=[p for p in checks if p['id'] in sample_ids]
focused=[]
def focus(label,reported,value,source,kind='arithmetic'):
    focused.append({'id':2001+len(focused),'label':label,'reported_value':float(reported),'fetched_value':float(value),'fetched_exact':str(value),'fetched_source':source,'unit':'report units','verification_kind':kind})

focus('current close',37.86,I['quote']['price'],'S10 Tencent and Sina','source_fact')
focus('registered shares hundred million',15.06445074,D(I['shares'])/Y,'S1 registered capital','source_fact')
focus('market cap hundred million',570.34,C['valuation']['market_cap'],'Price times registered shares')
focus('historical yield',3.88,C['valuation']['trailing_paid_dividend_yield_pct'],'S6 historical DPS / current price, not future yield')
for period,label,field,value in [('2026Q3','gross margin','gross_margin_pct',55.48),('2025Q3','prior gross margin','gross_margin_pct',53.52),('2026Q3','sales expense ratio','sales_expense_revenue_pct',57.28),('2025Q3','prior sales expense ratio','sales_expense_revenue_pct',37.99),('2026Q3','admin ratio','admin_expense_revenue_pct',33.96),('2025Q3','prior admin ratio','admin_expense_revenue_pct',13.02)]:
    focus(label,value,C['periods'][period][field],'S1-S2 same-quarter formula')
focus('Q3 gross profit',7.11,D(C['periods']['2026Q3']['revenue'])-D(C['periods']['2026Q3']['cost']),'S1-S2 revenue less cost')
focus('Q3 fair value',-1.9275,C['periods']['2026Q3']['fair_value_income'],'S1-S2 fair-value line')
focus('Q3 investment income',.9150,C['periods']['2026Q3']['investment_income'],'S1-S2 investment-income line')
focus('Q3 impairment ten thousand',85.12,-D(C['periods']['2026Q3']['asset_impairment'])*D(10000),'CNY hundred million to ten thousand')
focus('Q4 2025 loss',-17.6894,D(I['primary_quarter_checks']['2025Q4']['profit'])/Y,'S3 direct quarterly table','source_fact')
focus('Q4 2025 CFO',-17.2928,D(I['primary_quarter_checks']['2025Q4']['cfo'])/Y,'S3 direct quarterly table','source_fact')
for key,reported in [('mid_high_liquor',-28.36),('ordinary_liquor',-32.24),('liquor_in_province',-38.34),('liquor_out_province',-19.72)]:
    focus(key+' H1 yoy',reported,I['products_h1'][key]['yoy_revenue_pct'],'S2 liquor table; tool omitted percentage cells','single_primary')
focus('liquid resources observation',182.4884,(D(I['balance']['2026Q3']['cash_equivalents'])+D(I['balance']['2026Q3']['trading_financial_assets'])-debt)/Y,'Scoped balance sum, NOT distributable net cash')
focus('paid dividend total',22.1447,D(I['notes']['dividend_paid_2026_total'])/Y,'S6 actual distribution','source_fact')
for name,price,pv in [('bear',6.37,5.24),('base',21.24,16.31),('bull',46.47,33.88)]:
    focus(name+' exit price',price,S[name]['terminal_price_CNY'],'Explicit scenario','model_arithmetic')
    focus(name+' discounted value',pv,S[name]['PV10_CNY'],'10% annual cash-flow discount, not liquidation value','model_arithmetic')
conditional=(D('150e8')+D('20e8')*16)/D(I['shares'])
focus('conditional value',31.20,conditional,'A=150, core earnings=20, M=16; assumptions not proven','model_arithmetic')
focus('conditional margin price',24.96,conditional*D('.8'),'20% margin on conditional value','model_arithmetic')
log=io.StringIO()
with redirect_stdout(log):
    selected=audit.render_verdict(sample+focused,REPORT.name+' random + directed')
    full=audit.render_verdict(checks,REPORT.name+' recognized table universe')
assert selected['verdict']==full['verdict']=='PASS' and selected['warn_count']==full['warn_count']==0
assert not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',body)
summary={'report_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'extracted':len(points),'excluded':len(excluded),'annual_supplement':12,'effective':len(valid),'seed':20261106,'random_count':len(sample),'random_coverage_pct':len(sample)/len(valid)*100,'directed_count':len(focused),'selected_verdict':selected,'full_table_verdict':full,'limits':'Table population plus targeted narrative checks, not every numeral in prose. Historical policy, current facts and forecast assumptions are tagged separately. PASS is not investment certainty.'}
for name,obj in [('audit-universe.json',points),('audit-exclusions.json',excluded),('audit-checks.json',checks),('audit-sample.json',sample),('audit-directed.json',focused),('audit-summary.json',summary)]:
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
clean='\n'.join(s.rstrip() for s in re.sub(r'\x1b\[[0-9;]*m','',log.getvalue()).splitlines()).rstrip()+'\n'
(HERE/'audit-verdict.txt').write_text(clean,encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
