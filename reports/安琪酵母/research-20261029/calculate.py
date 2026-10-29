"""Reproduce Angel Yeast numbers using financial_rigor Decimal arithmetic."""
from pathlib import Path
import sys, json, io, contextlib
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from financial_rigor import exact as D, verify_market_cap, verify_valuation, cross_validate
sys.stdout.reconfigure(encoding='utf-8')
OUT = Path(__file__).parent
Y = D('1e8')
data = {
 '2025': ['16728842770.37','1544409068.94','1359139575.38','2477959556.34','1700512297.57','12595747716.27'],
 '2026YTD': ['13607950841.86','1171183084.93','1015391704.63','1712444648.30','1305256138.34','10161781474.84'],
 '2025YTD': ['11786451197.65','1116432180.40','965428795.53','2218132355.03','1240509324.36','8776270273.80'],
 '2026H1': ['9186922783.90','880947198.63','794013248.51','199858157.50','743226600.55','6725016762.52'],
 '2025H1': ['7899297546.76','799358009.92','741952237.64','262260022.03','835373017.01','5838738282.23'],
}
names = ['revenue','profit','core_profit','ocf','capex','cost']
data = {p: dict(zip(names,map(D,values))) for p,values in data.items()}
for year in ('2025','2026'):
 data[year+'Q3'] = {k:data[year+'YTD'][k]-data[year+'H1'][k] for k in names}
data['TTM'] = {k:data['2025'][k]+data['2026YTD'][k]-data['2025YTD'][k] for k in names}
for p,row in data.items():
 row['fcf'] = row['ocf']-row['capex']
 row['gross_margin'] = (1-row['cost']/row['revenue'])*100
 row['net_margin'] = row['profit']/row['revenue']*100
 row['cash_conversion'] = row['ocf']/row['profit']*100
price,shares = D('35.95'),D('867815671')
cap = price*shares
metrics = {'market_cap_yi':cap/Y,'pe':cap/data['TTM']['profit'],'core_pe':cap/data['TTM']['core_profit'],
 'pb':cap/D('12801455652.47'),'dividend_yield':D('.55')/price*100,
 'debt':sum(map(D,['3969000588.92','507945224.64','2162380884.88','1994705028.48','106297281.36'])),
 'debt_prior':sum(map(D,['4573269538.53','1503478981.17','1071998521.96','997086052.29','8288881.87'])),
 'ar_days':(D('1858293874.84')+D('1843548354.08'))/2/data['2026YTD']['revenue']*270,
 'inventory_days':(D('4909507657.67')+D('5105429678.33'))/2/data['2026YTD']['cost']*270,
 'q3_ocf_yoy':(data['2026Q3']['ocf']/data['2025Q3']['ocf']-1)*100,
 'q3_fcf_yoy':(data['2026Q3']['fcf']/data['2025Q3']['fcf']-1)*100,
 'overseas_share':D('585060.26')/D('1352778.75')*100,
 'yeast_share':D('984301.36')/D('1352778.75')*100,
 'ytd_fcf_yoy':(data['2026YTD']['fcf']/data['2025YTD']['fcf']-1)*100,
}
metrics['net_debt_cash'] = metrics['debt']-D('3141665201.81')
metrics['net_debt_equivalents'] = metrics['debt']-D('2898625824.66')
scenarios={}
for name,g,pe in [('bear','0','15'),('base','.08','20'),('bull','.13','23')]:
 profit=D('1600000000')
 div=D(0)
 for _ in range(3):
  profit*=1+D(g)
  div+=profit*D('.30')/shares
 exit_price=profit*D(pe)/shares
 terminal_total=exit_price+div
 scenarios[name]={'growth':D(g)*100,'exit_pe':D(pe),'profit_yi':profit/Y,'exit_price':exit_price,
  'dividend_sum':div,'total_return':(terminal_total/price-1)*100,
  'cagr':((terminal_total/price)**(D(1)/3)-1)*100,
  'present_value_10pct':sum((D('1600000000')*(1+D(g))**i*D('.30')/shares/(D('1.10')**i)) for i in range(1,4))+exit_price/D('1.10')**3}
metrics['reverse_growth_10pct'] = D('0.10')
# Find growth for 10% terminal-wealth annual return, 20x exit PE, 30% payout.
lo,hi=D('-.5'),D('1')
for _ in range(100):
 g=(lo+hi)/2
 total=(D('1600000000')*(1+g)**3*20+sum(D('1600000000')*(1+g)**i*D('.30') for i in range(1,4)))/shares
 if total < price*D('1.10')**3: lo=g
 else: hi=g
metrics['reverse_growth_10pct']=hi*100
raw={'data':data,'metrics':metrics,'scenarios':scenarios}
(OUT/'calculations.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
log=io.StringIO()
with contextlib.redirect_stdout(log):
 verify_market_cap(price,shares,D('31198000000'),'CNY')
 verify_valuation(price,eps=data['TTM']['profit']/shares,bvps=D('12801455652.47')/shares,dividend=D('.55'))
 em=json.loads((OUT/'snapshot.json').read_text(encoding='utf-8'))['data']
 for period,date in [('2026YTD','2026-09-30'),('2026H1','2026-06-30'),('2025','2025-12-31'),('2025YTD','2025-09-30')]:
  row=next(x for x in em if x['REPORT_DATE'].startswith(date))
  for field,key in [('revenue','TOTALOPERATEREVE'),('profit','PARENTNETPROFIT'),('core_profit','KCFJCXSYJLR')]:
   cross_validate(period+' '+field,{'issuer filing':data[period][field], 'Eastmoney':row[key]},tolerance_pct=1)
  cross_validate(period+' gross margin',{'issuer calculation':data[period]['gross_margin'],'Eastmoney':row['XSMLL']},unit='%',tolerance_pct=1)
(OUT/'financial-rigor.txt').write_text(log.getvalue(),encoding='utf-8')
assert data['2026Q3']['revenue']==D('4421028057.96')
assert data['2026Q3']['profit']==D('290235886.30')
assert data['2026Q3']['core_profit']==D('221378456.12')
assert data['2025Q3']['profit']==D('317074170.48')
assert data['TTM']['profit']==D('1599159973.47')
assert abs(cap/Y-D('311.98'))<D('.01')
assert (D('767718.49')+D('585060.26'))==D('1352778.75')
assert sum(map(D,['984301.36','100717.40','31880.38','168035.30','67844.31']))==D('1352778.75')
assert data['2026YTD']['fcf']<data['2025YTD']['fcf']
print(json.dumps(raw,ensure_ascii=False,indent=2,default=str))
print('9 consistency assertions passed; 16 cross-source checks logged.')
