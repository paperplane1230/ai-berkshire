"""Audit reported table values, excluding dates before fixed-seed sampling."""
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
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import report_audit as audit

report=HERE.parent/'海天味业研究报告-20261029.md'
body=report.read_text(encoding='utf-8')
data,out=calculate()
points=audit.extract_data_points(body)
excluded=[p for p in points if p['label']=='研究日' or p['line_number']>=next(i for i,s in enumerate(body.splitlines(),1) if s.startswith('- [S8]'))]
valid=[p for p in points if p not in excluded]
for row,col,value,unit,line,raw in audit._parse_md_tables(body.splitlines()):
    if row in ['2023','2024','2025']:
        valid.append({'id':len(points)+1+sum(p.get('supplemented',False) for p in valid),'label':row+' · '+col,'reported_value':value,'unit':unit,'line_number':line,'raw_text':raw,'supplemented':True})

financial={'营业收入':'revenue','归母净利润':'profit','扣非归母':'adjusted','经营现金流':'cfo','合并毛利率':'gross_margin_pct'}
periods={'2025前三季度':'2025YTD','2026前三季度':'2026YTD','2025Q3':'2025Q3','2026Q3':'2026Q3'}
products={'酱油':'soy','蚝油':'oyster','调味酱':'sauce','其他':'other'}
pm={'前三季度收入':'YTD_yi','累计同比':'YTD_growth_pct','Q3收入':'Q3_yi','Q3同比':'Q3_growth_pct'}
historical_margins={'酱油':'48.73','蚝油':'36.98','调味酱':'45.05','其他':'22.53'}
balance={'货币资金':'cash','交易性金融资产':'trading_assets','现金及现金等价物':'cash_equivalents','应付票据':'bills_payable','应收账款':'receivables','存货':'inventory','合同负债':'contract_liabilities','商誉':'goodwill'}
scenario_names={'压力':0,'基准':1,'乐观':2}
scenario_fields={'第五年EPS（元）':'year5_eps','五年股息合计（元）':'dividend_sum_CNY','A退出价（元）':'A_exit_CNY','H退出价（港元）':'H_exit_HKD','A税前IRR':'A_IRR_pct','H税前IRR':'H_IRR_pct'}

def reference(p):
    row,col=p['label'].split(' · ')
    if row in financial:
        key=financial[row]
        if col in periods: return out[periods[col]][key],'S1/S3, latest restated comparatives; exact arithmetic'
        if row=='合并毛利率': return out['2025Q3'][key]-out['2026Q3'][key],'S1/S3, decline in percentage points'
        return out['growth_YTD' if col=='累计同比' else 'growth_Q3'][key],'S1/S3, exact arithmetic'
    if row in products:
        if col=='2025产品毛利率': return D(historical_margins[row]),'S4 p30'
        return out['products'][products[row]][pm[col]],'S2 and S3 p21'
    if row=='列示借款及租赁相关负债': return out['balance']['named_debt_yi'],'S1 p7, explicitly scoped debt sum'
    if row in balance:
        if col=='对照及解释':
            if row in ['应收账款','存货']: return out['balance']['receivables_change_pct' if row=='应收账款' else 'inventory_change_pct'],'S1, change vs year end'
            return D(data['balance'][balance[row]+'_yearend'])/D('1e8'),'S1 p6-7 prior year-end column'
        return D(data['balance'][balance[row]])/D('1e8'),'S1 p5-12'
    if row=='当日收盘价': return D(data['quote']['A_CNY' if col=='A股' else 'H_HKD']),'S8 Tencent and Sina 2026-10-29'
    if row=='本类股份市值': return out['valuation']['A_cap_yi' if col=='A股' else 'H_cap_HKD_yi'],'S1/S8 class share count times own market price'
    if row in ['归母TTM PE','扣非TTM PE','PB（归母净资产口径）']:
        field=('A' if col=='A股' else 'H')+{'归母TTM PE':'_PE','扣非TTM PE':'_deducted_PE','PB（归母净资产口径）':'_PB'}[row]
        return out['valuation'][field],'S1/S3/S4/S8 derived valuation'
    if row in scenario_names:
        i=scenario_names[row]
        if col=='每股利润年增速': return D(data['scenarios'][i]['growth'])*100,'Explicit model assumption; not a forecast fact'
        if col=='A/H退出PE': return D(data['scenarios'][i]['A_exit_PE']),'Explicit A exit PE assumption; H checked in model tests'
        return out['scenarios'][i][scenario_fields[col]],'Exact scenario cash-flow model; not a forecast fact'
    if row in ['A股空仓','H股空仓']: return D('26' if row=='A股空仓' else '22'),'Research action threshold, not market fact'
    if row in ['2023','2024','2025']:
        keys={'营业收入':'revenue','归母净利润':'profit','扣非归母':'adjusted','经营现金流':'cfo','资本开支付现':'capex','简化自由现金流':'fcf'}
        return out[row][keys[col]],'S4 p8 and p94-95'
    raise ValueError(p)

checks=[]
for p in valid:
    exact,source=reference(p)
    places=max(0,-D(str(p['reported_value'])).as_tuple().exponent)
    rounded=exact.quantize(D('1').scaleb(-places))
    checks.append(dict(p,fetched_value=float(rounded),fetched_exact=str(exact),fetched_source=source))
sample_ids={p['id'] for p in random.Random(20261029).sample(valid,math.ceil(len(valid)*0.15))}
sample=[p for p in checks if p['id'] in sample_ids]
log=io.StringIO()
with contextlib.redirect_stdout(log):
    sampled_verdict=audit.render_verdict(sample,report.name+' fixed-seed sample')
    all_verdict=audit.render_verdict(checks,report.name+' full recognized financial table population')
assert sampled_verdict['fail_count']==sampled_verdict['warn_count']==0
assert all_verdict['fail_count']==all_verdict['warn_count']==0
assert not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',body)
record={'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),'tool_extracted':len(points),'excluded':excluded,'supplemented_annual':sum(p.get('supplemented',False) for p in valid),'effective_population':len(valid),'seed':20261029,'sample_count':len(sample),'coverage_pct':len(sample)/len(valid)*100,'sample_verdict':sampled_verdict,'full_recognized_population_verdict':all_verdict,'limitations':['Financial tables are covered; unstructured prose is additionally manually reviewed, not a fully enumerated random population.','Scenario verification checks arithmetic and stated assumptions, not forecast accuracy.','Rounding follows each report number display precision.']}
for name,value in [('audit-sample.json',sample),('audit-checks.json',checks),('audit-results.json',record)]:
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(HERE/'audit-verdict.txt').write_text(log.getvalue(),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False,indent=2))
