"""Pre-filter numeric noise, supplement annual rows, then sample deterministically."""
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
REPORT=HERE.parent/'达仁堂研究报告-20261030.md'
sys.path.insert(0,str(HERE.parents[2]/'tools'))
import report_audit as audit
sys.stdout.reconfigure(encoding='utf-8')
I,raw,R=calculate()
text=REPORT.read_text(encoding='utf-8')
points=audit.extract_data_points(text)
noise_ids={58,60,63,88,89,90,91,92}
assert len(points)==92,'Report changed; recheck exclusions before sampling'
excluded=[dict(p,reason='year/month/time or URL port; not a financial measure') for p in points if p['id'] in noise_ids]
valid=[p for p in points if p['id'] not in noise_ids]
added=[]
for row,col,value,unit,line,body in audit._parse_md_tables(text.splitlines()):
    if row in ('2023','2024','2025'):
        added.append({'id':100+len(added),'label':row+' · '+col,'reported_value':value,'unit':unit,'line_number':line,'raw_text':body,'supplemented':True})
valid+=added
financial={'营业收入':'revenue','归母净利润':'profit','扣非归母':'core','营业利润':'operating','经营现金流':'cfo','资本开支付现':'capex','简化自由现金流':'fcf'}
periods={'2025前三季':'2025YTD','2026前三季':'2026YTD','2025单Q3':'2025Q3','2026单Q3':'2026Q3'}
balance={'货币资金':'cash','应收账款':'receivables','存货':'inventory','其他应付款':'other_payables','其中应付股利':'dividend_payable'}

def reference(p):
    row,col=p['label'].split(' · ')
    if row in financial:
        key=financial[row]
        if col in periods:return R['periods'][periods[col]][key],'S1/S2 consolidated statement or exact difference','financial_calculation'
        return R['growth']['YTD' if col=='累计同比' else 'Q3'][key],'S1/S2 unrounded year-on-year calculation','financial_calculation'
    if row in ('工业','贸易及商业'):
        key='industrial' if row=='工业' else 'trade'
        if col=='2025收入（亿元）':return D(I['annual_segments'][key])/D('1e8'),'S3 segment table','single_primary'
        if col=='合并收入占比':return R['annual_weights'][key],'S3 segment/current revenue','single_primary_calculation'
        return D('75.18' if row=='工业' else '36.05'),'S3 historical segment margin','single_primary'
    if row in balance:
        key=balance[row]+('_previous' if col=='2025年末' else '')
        return D(I['balance'][key])/D('1e8'),'S1 consolidated balance sheet','single_primary'
    if row in ('2025前三季度利润分配','2025年度末期分配','上述两期合计'):
        return D({'2025前三季度利润分配':'2.45','2025年度末期分配':'2.34','上述两期合计':'4.79'}[row]),'S3/S6 disclosed completed distributions; not future payout','historical_distribution'
    ttm={'TTM营业收入':'revenue','TTM归母净利润':'profit','TTM扣非归母':'core','TTM简化自由现金流':'fcf'}
    if row in ttm:
        return (R['valuation']['fcf_yield'] if col=='口径' else R['periods']['TTM'][ttm[row]]),'S1/S2/S3 exact TTM; current A price equivalent','financial_calculation'
    if row in ('TTM扣非每股收益','A股归母PE','A股扣非PE'):
        return R['valuation'][{'TTM扣非每股收益':'core_eps','A股归母PE':'gaap_pe','A股扣非PE':'core_pe'}[row]],'Exact current share-count valuation','financial_calculation'
    if row in ('压力','基准','乐观'):
        index={'压力':0,'基准':1,'乐观':2}[row]
        s=I['scenarios'][index]
        if col in ('每股盈利年增速','派息率假设','退出PE'):
            key={'每股盈利年增速':'growth','派息率假设':'payout','退出PE':'exit_pe'}[col]
            return D(s[key])*(100 if key!='exit_pe' else 1),'Explicit modelling input, not a proven forecast','assumption'
        key={'第五年价格（元）':'terminal_price','五年股息合计（元）':'dividend_sum','年化IRR':'irr_pct'}[col]
        return R['scenarios'][s['name']][key],'Finite five-year cashflow calculation; not forecast validation','model_calculation'
    if row in ('2023','2024','2025'):
        return R['periods'][row][financial[col]],'S3 audited three-year comparison; S4 independent capture','financial_fact'
    raise ValueError(p)

checks=[]
for p in valid:
    v,source,kind=reference(p)
    checks.append(dict(p,fetched_value=float(v),fetched_exact=str(v),fetched_source=source,verification_kind=kind))
chosen={p['id'] for p in random.Random(20261030).sample(valid,math.ceil(len(valid)*.15))}
sample=[p for p in checks if p['id'] in chosen]
focused=[]
def add(label,reported,value,source,kind='financial_calculation'):
    focused.append({'id':1000+len(focused),'label':label,'reported_value':reported,'fetched_value':float(value),'fetched_exact':str(value),'fetched_source':source,'unit':'specified in report','verification_kind':kind})
add('A股收盘价',40.30,D(I['price']),'S5 Tencent and Sina same-date quote','financial_fact')
add('A类股数亿股',5.70094356,D(I['a_shares'])/D('1e8'),'S3 class shares; S2 no change; S1 total unchanged','financial_fact')
add('S类股数亿股',2,D(I['s_shares'])/D('1e8'),'S3 class shares and S2 no change','financial_fact')
add('A类市值亿元',229.75,R['valuation']['a_class_cap_yi'],'A shares including restricted shares x own price')
add('A价等价市值亿元',310.35,R['valuation']['a_equivalent_cap_yi'],'Total shares x A price, not combined traded cap')
add('两期历史股息率',11.89,R['valuation']['historical_2025_dividend_yield'],'S3/S6 two distributions divided by current A price')
add('历史两期合计派息比例',173.10,R['dividend_payout_2025'],'Not annual-report final-only 84.56%')
add('两期合计派息亿元',36.8875,R['dividend_total_2025'],'Current unchanged share count times 4.79')
add('机械75%派息收益率',2.15,R['valuation']['mechanical_core_payout75_yield'],'Scenario sensitivity, not guidance','assumption_calculation')
add('Q3当前毛利额亿元',7.3820,R['periods']['2026Q3']['gross_profit'],'S1-S2 sales minus cost')
add('Q3上期毛利额亿元',7.7256,R['periods']['2025Q3']['gross_profit'],'S1-S2 comparable sales minus cost')
add('Q3销售费用节约亿元',1.6924,R['q3_sales_saving'],'S1-S2 sales expense difference')
add('单Q3销售费率',23.61,R['periods']['2026Q3']['sales_ratio'],'S1-S2 current expense/current revenue')
add('期末列示借款租赁亿元',.9491,R['balance']['named_debt_yi'],'S1 specifically defined liabilities')
add('现金减限定负担亿元',11.8651,R['balance']['cash_less_scoped_burden_yi'],'Not free surplus cash, excludes other operating obligations')
add('应收周转天数',73.94,R['balance']['dso_273'],'Average beginning/end AR and 273 days')
add('存货周转天数',381.43,R['balance']['dio_273'],'Average beginning/end inventory, 273 days, consolidated COGS')
add('基准10%现值',33.59,R['scenarios']['base']['pv_at_10pct'],'Distribution timing and finite exit value','model_calculation')
add('目标10%所需增长率',12.21,R['growth_for_10pct_return'],'Reverse bisection; not growth forecast','model_calculation')
add('2025第四季扣非亏损亿元',.2282,-(raw['2025']['core']-raw['2025YTD']['core'])/D('1e8'),'S3 standalone Q4 and annual minus YTD')
add('分配股利利润或付息现金亿元',36.6207,D(I['cash_note']['dividend_interest_paid'])/D('1e8'),'S1 p13 cashflow, not pure dividends','financial_fact')
log=io.StringIO()
with redirect_stdout(log):
    sampled=audit.render_verdict(sample+focused,REPORT.name+' random sample plus directed')
    complete=audit.render_verdict(checks,REPORT.name+' all recognized/supplemented table values')
assert sampled['fail_count']==sampled['warn_count']==complete['fail_count']==complete['warn_count']==0
assert not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',text)
summary={'report_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'tool_extracted':len(points),'excluded':len(excluded),'supplemented':len(added),'effective_table_population':len(valid),'seed':20261030,'random_sample':len(sample),'random_coverage_pct':len(sample)/len(valid)*100,'directed':len(focused),'sample_and_directed':sampled,'full_table_check':complete,'limits':'Assumptions are labelled, source mirrors not independent audits; prose not exhaustively enumerated by the parser.'}
for file,obj in [('audit-universe.json',valid),('audit-excluded.json',excluded),('audit-sample.json',sample),('audit-checks.json',checks),('audit-directed.json',focused),('audit-summary.json',summary)]:
    (HERE/file).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
clean=re.sub(r'\x1b\[[0-9;]*m','',log.getvalue())
(HERE/'audit-verdict.txt').write_text('\n'.join(x.rstrip() for x in clean.splitlines())+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
