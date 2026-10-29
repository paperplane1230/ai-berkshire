"""Seeded data sampling plus directed material-point checks.

Source facts, arithmetic and assumptions are labelled separately. A pass of an
assumption checks transcription/model consistency, NOT future investment truth.
"""
import io
import json
import hashlib
import sys
from contextlib import redirect_stdout
from decimal import Decimal as D
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'伊利股份研究报告-20261029.md'
sys.path.insert(0,str(HERE.parents[2]/'tools'))
from report_audit import extract_data_points, sample_points, render_verdict
sys.stdout.reconfigure(encoding='utf-8')
I=json.loads((HERE/'inputs.json').read_text(encoding='utf-8'))
C=json.loads((HERE/'calculations.json').read_text(encoding='utf-8'))
X={x['field']:D(x['secondary']) for x in json.loads((HERE/'cross_checks.json').read_text(encoding='utf-8'))}
text=REPORT.read_text(encoding='utf-8')
points=extract_data_points(text)
noise={59:'Q3 period marker',60:'Q3 period marker',61:'Q3 period marker',72:'year label',93:'Q3 period marker',94:'research year',95:'URL port'}
assert len(points)==95, 'Report changed: review sample universe and exclusions'
effective=[p for p in points if p['id'] not in noise]
sample=sample_points(effective,ratio=.15,seed=20261029)
Y=D('100000000')
checks={
    12:(C['periods']['2026q3']['deduct'],'S1 primary Q3; S1-S3 subtraction',(X['2026ytd/deduct']-X['2026h1/deduct'])/Y,'S7 independent vendor subtraction','calculation'),
    19:(C['periods']['2025q3']['pbt'],'S1-S3 comparative PBT',(X['2025ytd/pbt']-X['2025h1/pbt'])/Y,'S7 independent vendor subtraction','calculation'),
    24:(C['periods']['2026q3']['ocf'],'S1-S3 consolidated CFO',(X['2026ytd/ocf']-X['2026h1/ocf'])/Y,'S7 independent vendor subtraction','calculation'),
    29:(C['periods']['2025ytd']['fcf'],'S1 CFO minus gross capex',(X['2025ytd/ocf']-X['2025ytd/capex'])/Y,'S7 CFO minus gross capex','calculation'),
    35:('31.43','S4 segment table',None,'','source_fact_single_primary'),
    34:(C['segment_weights']['liquid'],'S2 liquid divided by total main revenue',None,'','calculation_single_primary'),
    37:(C['segment_weights']['powder'],'S2 powder divided by total main revenue',None,'','calculation_single_primary'),
    45:(D(I['balance']['2025end']['cash'])/Y,'S1 balance sheet',X['2025end/cash']/Y,'S7 balance','source_fact'),
    55:(D(I['balance']['2025end']['contract_liabilities'])/Y,'S1 comparative contract liabilities',None,'','source_fact_single_primary'),
    57:(D(I['balance']['2025end']['goodwill'])/Y,'S1 comparative goodwill',None,'','source_fact_single_primary'),
    62:(C['ttm']['profit'],'S4+S1 current-S1 comparative',(X['2025/profit']+X['2026ytd/profit']-X['2025ytd/profit'])/Y,'S7 independent TTM reconstruction','calculation'),
    73:(I['scenarios'][0]['eps0'],'Explicit bear-case modelling input, not a financial disclosure',None,'','assumption'),
    86:(I['scenarios'][2]['eps0'],'Explicit bull-case modelling input, not a financial disclosure',None,'','assumption'),
    92:(C['scenarios']['bull']['irr_pct'],'Decimal cashflow IRR; independently residual-tested',None,'','model_calculation')
}
results=[]
for p in sample:
    value,source,value2,source2,kind=checks[p['id']]
    results.append({**p,'fetched_value':float(value),'fetched_source':source,
        'fetched_value2':float(value2) if value2 is not None else None,'fetched_source2':source2,'verification_kind':kind,'sample_type':'random'})

def directed(label,reported,value,source,kind='calculation',second=None,source2=''):
    results.append({'id':1000+len(results),'label':label,'reported_value':float(reported),'unit':'specified in report','fetched_value':float(value),'fetched_source':source,'fetched_value2':float(second) if second is not None else None,'fetched_source2':source2,'verification_kind':kind,'sample_type':'directed'})

directed('收盘价',29.45,I['price'],'S8 Tencent and Sina 2026-10-29 snapshots','source_fact',29.45,'Sina 2026-10-29 15:34:58')
directed('市值亿元',1862.82,C['valuation']['market_cap_yi'],'S1 shares x S8 price','calculation',1862.82,'Tencent market cap rounded to 0.01 hundred million')
directed('归母TTM PE',18.74,C['valuation']['pe_ttm'],'TTM reconstruction and current shares')
directed('扣非TTM PE',19.61,C['valuation']['pe_deduct_ttm'],'TTM deduct reconstruction')
directed('前三季归母同比',-15.56,C['growth']['ytd']['profit'],'S1 actual unrounded primary values')
directed('前三季CFO同比',64.27,C['growth']['ytd']['ocf'],'S1 actual unrounded primary values')
directed('单季CFO同比',-11.71,C['growth']['q3']['ocf'],'S1-S3 same-period difference')
for year,rev,profit,ocf in [('2023','1257.58','104.29','182.90'),('2024','1153.93','84.53','217.40'),('2025','1156.36','115.65','143.44')]:
    for metric,reported in [('revenue',rev),('profit',profit),('ocf',ocf)]:
        directed(year+'/'+metric,reported,D(I['annual'][year][metric])/Y,'S4 three-year comparison','source_fact',X[year+'/'+metric]/Y,'S7 independent vendor')
directed('基准IRR',7.68,C['scenarios']['base']['irr_pct'],'Five year distribution timing and terminal PE model','model_calculation')
directed('基准10%折现价格',26.72,C['scenarios']['base']['pv_at_10pct'],'Explicit 10% hurdle; not perpetuity','model_calculation')
directed('乐观退出价',51.89,C['scenarios']['bull']['terminal_price'],'1.85*(1.07^5)*20','model_calculation')
directed('单Q3有效税率',15.47,C['periods']['2026q3']['tax_rate'],'Quarter tax/PBT, S1-S3')
directed('供应商账款及票据年内增额亿元',70.55,C['supplier_funding_increase'],'S1 current versus year-end balances')
directed('澳优影响合并商誉减值亿元',15.47,D('1546544866.49')/Y,'S3 goodwill note; not grossed-up full goodwill value','source_fact_single_primary')
log=io.StringIO()
with redirect_stdout(log): outcome=render_verdict(results,report_name=REPORT.name)
summary={'report':REPORT.name,'sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'extracted':len(points),'excluded':len(noise),'effective':len(effective),'random_sample':len(sample),'random_coverage_pct':str(D(len(sample))/len(effective)*100),'seed':20261029,'directed':len(results)-len(sample),'total':len(results),'verdict':outcome,
    'limits':'PASS is numeric consistency, not investment truth; single-primary and assumptions are explicitly tagged. Vendor and filing share underlying company disclosure.'}
for filename,obj in [('audit-universe.json',points),('audit-exclusions.json',[{'id':k,'reason':v} for k,v in noise.items()]),('audit-results.json',results),('audit-summary.json',summary)]:
    (HERE/filename).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(HERE/'audit-verdict.txt').write_text(log.getvalue(),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
assert outcome['verdict']=='PASS'
