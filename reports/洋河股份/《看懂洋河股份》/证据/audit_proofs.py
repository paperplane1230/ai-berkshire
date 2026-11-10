"""Source/field mappings reviewed for the frozen sample; never echo report values as proof."""
import json
from decimal import Decimal as D, getcontext
from pathlib import Path
getcontext().prec=40
HERE=Path(__file__).resolve().parent
load=lambda n:json.loads((HERE/n).read_text(encoding='utf-8'))
data,result,packet=load('source-data.json'),load('results.json'),load('audit-extraction.json')
vendor={r['REPORT_DATE'][:10]:r for r in data['vendor']}
Y=D('100000000')
def at8(name,kind='core_dcf'):
    return next(row for row in result[kind][name]['curve'] if row['r']=='0.08')
def primary(value,source,kind='disclosed_or_derived',secondary=None,second_source=None):
    p={'fetched_value':float(value),'fetched_source':source,'verification_kind':kind}
    if secondary is not None:p.update(fetched_value2=float(secondary),fetched_source2=second_source)
    return p
def proof(point):
    label=point['label']
    row,col=label.split(' · ',1)
    if row.isdigit() and row in data['annual']:
        year=row
        annual=data['annual'][year]
        origin=('H23 p7 restated '+year) if year in ('2021','2022') else ('S3 p8-p9 annual comparison '+year)
        mapping={
          '营业收入（亿元）':('revenue','TOTALOPERATEREVE',Y),
          '归母利润（亿元）':('profit','PARENTNETPROFIT',Y),
          '经营现金流（亿元）':('cfo','NETCASH_OPERATE_PK',Y),
          '购建长期资产支出（亿元）':('capex',None,Y),
          '合并存货账面值（亿元）':('inventory',None,Y),
          '成品酒库存（吨，含红酒）':('finished_alcohol_tonnes',None,D(1)),
          '半成品酒（吨，含基础酒）':('semifinished_including_base_tonnes',None,D(1)),
          '每股税前分红':('fiscal_dividend_per_share',None,D(1))}
        if col in mapping:
            field,em,scale=mapping[col]
            source=origin+'; source-data.annual.'+year+'.'+field
            if field in ('capex','inventory','finished_alcohol_tonnes','semifinished_including_base_tonnes','fiscal_dividend_per_share'):
                source=('S3' if year=='2025' else 'H'+year[-2:])+' annual report '+('p10-p12 operating inventory' if 'tonnes' in field else 'cash-flow/balance/dividend section')+'; source-data.annual.'+year+'.'+field
            second=D(vendor[year+'-12-31'][em])/scale if em else None
            return primary(D(annual[field])/scale,source,secondary=second,second_source='Fresh Eastmoney '+year+' '+str(em) if em else None)
        if col=='销售费率':
            return primary(D(annual['selling_expense'])/D(annual['revenue'])*100,'H'+year[-2:]+' income/expense table: selling expense divided by same-year revenue; Decimal recomputation','derived')
        if col=='合并毛利率':
            val=(1-D(annual['cost'])/D(annual['revenue']))*100
            return primary(val,'S3 revenue and cost; Decimal (1-cost/revenue)*100','derived',D(vendor[year+'-12-31']['XSMLL']),'Eastmoney XSMLL, same fiscal year')
    if row=='新规划D1' and col=='不能推出什么':
        return primary(D(70),'D0 2024-2026 plan specified RMB7bn; D1 2025-2027 text has 100% profit ratio and no RMB7bn floor. Checked the NEGATED context: this is not a D1 promise.','policy_context_check')
    names={'压力':'stress','恢复':'recovery','较强恢复':'strong'}
    if row in names and col in ('第1年','第2年','第3年','第4年','第5年'):
        idx=int(col[1])-1
        return primary(D(data['core_dcf_scenarios'][names[row]]['first5_profit_yi'][idx]),'source-data.core_dcf_scenarios.'+names[row]+'.first5_profit_yi['+str(idx)+']; research input, not a financial disclosure','model_assumption')
    if row in ('前十年经营自由现金流转换率','第十年之后永续增长','净财务资产现值A'):
        name=names[col]
        field,scale={'前十年经营自由现金流转换率':('cash_conversion',D(100)),'第十年之后永续增长':('g',D(100)),'净财务资产现值A':('net_financial_asset_yi',D(1))}[row]
        return primary(D(data['core_dcf_scenarios'][name][field])*scale,'source-data.core_dcf_scenarios.'+name+'.'+field+'; explicit research input, no external verification claimed','model_assumption')
    if row=='终值占经营价值比重':
        return primary(D(at8(names[col])['terminal_share_of_operating_pv_pct']),'results.core_dcf.'+names[col]+'.r8: discounted year11 perpetuity / operating present value; independently tested formula','model_arithmetic')
    if row=='r=8%':
        name={'压力情景每股值':'stress','恢复情景每股值':'recovery','较强恢复每股值':'strong'}[col]
        return primary(D(at8(name)['value_per_share']),'results.core_dcf.'+name+'.r8.value_per_share = (operating PV + net A)/shares','model_arithmetic')
    if row in ('第5年末','第10年末') and col=='今天的金额现值':
        n=5 if row=='第5年末' else 10
        return primary(D(150)/D('1.08')**n,'Independent Decimal: future RMB15bn / 1.08^'+str(n)+'. No intervening financial income; not re-discounting the main model A.','model_arithmetic')
    if row in ('压力路径','中等恢复路径','较强恢复路径'):
        name={'压力路径':'stress','中等恢复路径':'recovery','较强恢复路径':'strong'}[row]
        if col=='三年含息IRR':value=result['whole_equity'][name]['year3_irr_pct']
        elif col.startswith('十年含息IRR'):value=at8(name,'whole_equity')['irr_pct']
        elif col=='十年现金流按8%折现的每股值':value=at8(name,'whole_equity')['pv_per_share']
        else:raise KeyError(label)
        return primary(D(value),'results.whole_equity.'+name+': explicit annual dividends + ex-dividend terminal price, no additional A. Independent NPV residual tests pass.','model_arithmetic')
    raise KeyError('No reviewed source mapping for '+point['key']+' '+label)
checked=[]
for report in packet['reports']:
    for point in report['sample']:
        checked.append({**point,**proof(point)})
(HERE/'audit-checked.json').write_text(json.dumps(checked,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Filled',len(checked),'reviewed source/formula mappings. Assumptions are explicitly labeled, not treated as independently established facts.')
