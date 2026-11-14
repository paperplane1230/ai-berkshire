"""Reviewed source/formula routes for the frozen sample, not report-value echoes."""
import json
from decimal import Decimal as D, getcontext
from pathlib import Path
getcontext().prec=40
HERE=Path(__file__).resolve().parent
load=lambda f:json.loads((HERE/f).read_text(encoding='utf-8'))
data,result,selection=load('source-data.json'),load('results.json'),load('audit-extraction.json')
vendors={x['REPORT_DATE'][:10]:x for x in data['vendors']}
def checked(value,source,kind,secondary=None,second_source=None):
    out={'fetched_value':float(value),'fetched_source':source,'verification_kind':kind}
    if secondary is not None:out.update(fetched_value2=float(secondary),fetched_source2=second_source)
    return out
def proof(point):
    row,col=point['label'].split(' · ',1)
    year=row.removesuffix('年')
    if year in data['annual']:
        source=data['annual'][year]
        m={'营业收入（亿元）':('revenue','TOTALOPERATEREVE'),'归母利润（亿元）':('profit','PARENTNETPROFIT'),'经营现金流（亿元）':('cfo','NETCASH_OPERATE_PK')}
        if col in m:
            key,field=m[col]
            return checked(D(source[key])/D('1e8'),'Issuer annual/restated table: source-data.annual.'+year+'.'+key,'disclosed_primary',D(vendors[year+'-12-31'][field])/D('1e8'),'Eastmoney '+year+' '+field+'; restatement difference retained where applicable')
        if col=='合并毛利率':
            return checked((1-D(source['cost'])/D(source['revenue']))*100,'Annual income statement: (1-cost/revenue)*100, same-year group scope','derived',D(vendors[year+'-12-31']['XSMLL']),'Eastmoney XSMLL')
        if col=='销售费率':
            return checked(D(source['selling_expense'])/D(source['revenue'])*100,'Issuer annual cost/expense table: selling expense / same-year revenue, Decimal recomputation','derived_single_origin')
        if col=='简化余量（亿元）':
            return checked((D(source['cfo'])-D(source['capex']))/D('1e8'),'Issuer annual cash-flow statement: CFO minus cash purchases of long-term assets; not FCFE','derived_single_origin')
    if row=='省内' and col=='2026年单Q3收入（亿元）':
        return checked((D('1053902.30')-D('793815.09'))/D(10000),'O2 and O1 regional tables in CNY10000; subtract YTD-H1 and divide10000 to CNY100m','derived',D(26),'B1 Q3 broker report: regional revenue26.0亿元 (RMB2.60bn), rounded independent publication')
    if row=='省内其他酒类' and col=='公告列示户数':
        return checked(D(data['operating_ytd']['dealer_rows'][1][0]),'O2 dealer table: province/other alcohol row, ending257; category count, not de-duplicated entities','disclosed_primary')
    if col in ('2025Q3（亿元）','2026Q3（亿元）'):
        period=col[:6]
        field={'营业收入':'revenue','毛利额':'gross_profit','税金及附加':'tax_surcharges'}[row]
        return checked(D(result['periods'][period][field]),'S1/S2 consolidated income statements: nine months minus half-year; results.periods.'+period+'.'+field,'derived_single_origin')
    if row.startswith('2022年报提出2023收入') and col=='后来披露结果':
        return checked((D(data['annual']['2023']['revenue'])/D(data['annual']['2022']['revenue'])-1)*100,'H22 target context and H23/H22 actual revenue ratio; target is not a guarantee','derived')
    if row.startswith('2023年报提出2024收入') and col=='后来披露结果':
        return checked((D(data['annual']['2024']['revenue'])/D(data['annual']['2023']['revenue'])-1)*100,'H23 target context and H24/H23 actual revenue ratio; target is not a guarantee','derived')
    if row=='归母TTM利润' and col=='数值':
        f=data['financial'];value=(D(f['2025']['profit'])+D(f['2026YTD']['profit'])-D(f['2025YTD']['profit']))/D('1e8')
        v=(D(vendors['2025-12-31']['PARENTNETPROFIT'])+D(vendors['2026-09-30']['PARENTNETPROFIT'])-D(vendors['2025-09-30']['PARENTNETPROFIT']))/D('1e8')
        return checked(value,'S3 FY2025 + S1 YTD2026 - comparative YTD2025','derived',v,'Same three dates independently extracted from Eastmoney')
    if row=='历史每股现金股息' and col=='数值':
        return checked(D(data['notes']['dividend_paid_2026_per_share']),'D2 FY2025 distribution implementation, payment2026-07-31; not a future dividend','disclosed_primary')
    names={'压力':'stress','基准':'base','较强恢复':'strong'}
    if row in names and col=='含逐年股利IRR':
        return checked(D(result['models'][names[row]]['three_year_irr_pct']),'results.models.'+names[row]+'.three_year_irr_pct; explicit dividends and PE exit, independent NPV identity tested','model_arithmetic')
    if row in names and col=='第三年退出PE':
        return checked(D(data['model']['cases'][names[row]]['pe3']),'Declared source-data.model.cases.'+names[row]+'.pe3; research assumption, not an observed future multiple','model_assumption')
    if row=='新增留存资本回报代理R':
        return checked(D(data['model']['incremental_retained_capital_return_proxy'])*100,'Declared retained-capital-return proxy .20; NOT measured ROIC or FCFE conversion','model_assumption')
    if row.startswith('r='):
        rate=D(row[2:].removesuffix('%'))/100
        name,mode={'基准：能力现值':('base','capacity'),'基准：65%股利现值':('base','policy65'),'较强：能力现值':('strong','capacity'),'较强：65%股利现值':('strong','policy65')}[col]
        value=next(x for x in result['models'][name]['curves'] if D(x['r'])==rate)[mode]['pv']
        return checked(D(value),'results.models.'+name+'.r='+str(rate)+'.'+mode+'.pv; same earnings, distinct terminal cash assumption','model_arithmetic')
    if row=='十年能力情景' and col=='固定的退出条件':
        return checked(D('.01')*100,'Reverse-growth comparison fixes terminal g1% for BOTH ten-year modes; research input, not company guidance','model_assumption')
    if row in ('国金证券','东吴证券') and col=='2027归母预测':
        source=next(x for x in data['brokers']['selected_sources'] if x['institution']==row)
        return checked(D(source['parent_profit_forecasts']['2027'])/100,source['id']+' '+source['date_on_report']+' original PDF text, forecast in CNYmillion divided100 to CNY100m; historical view not current consensus','historical_broker_forecast')
    raise KeyError('No reviewed source route: '+point['key']+' '+point['label'])
rows=[]
for report in selection['reports']:
    for point in report['sample']:rows.append({**point,**proof(point)})
(HERE/'audit-checked.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Resolved',len(rows),'source/formula mappings; model assumptions and forecasts are not claimed as established facts.')
