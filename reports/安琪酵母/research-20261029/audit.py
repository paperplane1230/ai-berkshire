"""Seeded valid-population audit plus targeted checks for extraction blind spots."""
from pathlib import Path
import sys, json, math, random, hashlib, io, contextlib
from decimal import Decimal as D
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from report_audit import extract_data_points, render_verdict
sys.stdout.reconfigure(encoding='utf-8')
OUT=Path(__file__).parent
REPORT=OUT.parent/'安琪酵母研究报告-20261029.md'
text=REPORT.read_text(encoding='utf-8')
raw=extract_data_points(text)
excluded=[p for p in raw if p['label']=='研究日' or 's.cn/list=sh600298)' in p['label'] or p['label']=='及15']
valid=[p for p in raw if p not in excluded]
sample=sorted(random.Random(20261029).sample(valid,math.ceil(len(valid)*.15)),key=lambda p:p['id'])
calc=json.loads((OUT/'calculations.json').read_text(encoding='utf-8'))
data=calc['data']; metrics=calc['metrics']; scenarios=calc['scenarios']; Y=D('1e8')
local=ROOT/'local/安琪酵母-20261029'
em=json.loads((OUT/'snapshot.json').read_text(encoding='utf-8'))['data']
def emval(date,key): return D(str(next(r for r in em if r['REPORT_DATE'].startswith(date))[key]))
refs={
 12:(D('1468784260.47')/Y,'S1 consolidated income statement operating profit'),
 24:(D(data['2026Q3']['revenue'])/Y,'S1 direct Q3; S1 minus S3 H1'),
 29:(D(data['2025Q3']['core_profit'])/Y,'S3 2025 annual quarterly table; comparative YTD minus H1'),
 35:(D(data['2025Q3']['net_margin']),'S3 quarterly profit / revenue, Decimal'),
 37:(D(data['2025Q3']['ocf'])/Y,'S3 2025 annual quarterly cash table; S1 comparative minus H1'),
 45:(D('984301.36')/10000,'S2 operating data, ten-thousand yuan converted to hundred-million'),
 55:(D('1858293874.84')/Y,'S1 consolidated balance sheet AR'),
 57:(D('4909507657.67')/Y,'S1 consolidated balance sheet inventory'),
 59:(D(metrics['debt'])/Y,'S1 five debt-related balance sheet items, sum; conservative approximation'),
 69:(D(scenarios['base']['growth']),'Model assumption 8 percent; consistency only, not future verification'),
 82:(emval('2026-09-30','TOTALOPERATEREVE')/Y,'S4 Eastmoney raw response; S1 exact match'),
 88:(emval('2026-06-30','TOTALOPERATEREVE')/Y,'S4 Eastmoney raw response; S3 H1 exact match'),
 89:(D(data['2025']['revenue'])/Y,'S3 2025 annual; S4 Eastmoney exact match'),
 94:(D('35.95'),'S5 Tencent field 3 and Sina field 3, 2026-10-29'),
}
results=[]
for p in sample:
 value,source=refs[p['id']]
 results.append({**p,'fetched_value':float(value),'fetched_source':source,'unrounded_reference':str(value),'audit_kind':'seeded'})

targeted=[]
def check(label,reported,value,source,needle=None):
 if needle is None: needle=str(reported)
 assert needle in text,(label,needle)
 targeted.append({'id':1000+len(targeted),'label':label,'reported_value':float(reported),'fetched_value':float(value),
 'unit':'','fetched_source':source,'unrounded_reference':str(value),'audit_kind':'targeted','raw_text':needle})

# Annual table is not emitted by the shared extractor when the row label is a year.
for date,rev,profit,core,ocf,roe in [
 ('2023-12-31','135.8528','12.7272','11.0574','13.2651','13.06'),
 ('2024-12-31','151.9691','13.2457','11.6974','16.4986','12.83'),
 ('2025-12-31','167.2884','15.4441','13.5914','24.7796','13.51')]:
 for key,reported in [('TOTALOPERATEREVE',rev),('PARENTNETPROFIT',profit),('KCFJCXSYJLR',core)]:
  check(date+' '+key,reported,emval(date,key)/Y,'S3 annual 3-year comparison and S4 Eastmoney')
 check(date+' ROE',roe,emval(date,'ROEJQ'),'S3 annual and S4 Eastmoney')
 # OCF is an issuer-source check, not a second independent-source claim.
 source_ocf={'2023-12-31':'1326513986.39','2024-12-31':'1649856927.18','2025-12-31':'2477959556.34'}[date]
 check(date+' OCF',ocf,D(source_ocf)/Y,'S3 annual 3-year comparison, issuer only')
for label,reported,key in [('market cap','311.98','market_cap_yi'),('TTM PE','19.51','pe'),('core PE','22.14','core_pe'),('PB','2.44','pb'),('dividend yield','1.53','dividend_yield'),('AR days','36.72','ar_days'),('inventory days','133.05','inventory_days')]:
 check(label,reported,D(metrics[key]),'S1/S3/S5 source inputs plus exact Decimal calculation')
for key,reported in [('profit','15.9916'),('core_profit','14.0910'),('ocf','19.7227'),('capex','17.6526'),('fcf','2.0701')]:
 check('TTM '+key,reported,D(data['TTM'][key])/Y,'Annual plus current YTD minus prior YTD; source S1/S3')
for name,values in [('bear',['27.66','1.66','-6.57']),('base',['46.45','1.94','10.41']),('bull',['61.19','2.13','20.76'])]:
 for key,reported in zip(['exit_price','dividend_sum','cagr'],values):
  check(name+' '+key,reported,D(scenarios[name][key]),'Explicit scenario assumptions recomputed; not a forecast fact')
check('base PV','36.50',D(scenarios['base']['present_value_10pct']),'Each year dividend discounted separately plus year-3 exit value')
check('reverse growth','7.59',D(metrics['reverse_growth_10pct']),'Bisection terminal-wealth return equation; not DCF')
check('rough fair low','31.11',D('1500000000')*18/D('867815671'),'1.5 billion yuan profit times 18 / shares')
check('rough fair high','39.18',D('1700000000')*20/D('867815671'),'1.7 billion yuan profit times 20 / shares')
results+=targeted
assert all(r['fetched_value'] is not None for r in results)
assert not any(ord(c)<32 and c not in '\n\r\t' for c in text)
log=io.StringIO()
with contextlib.redirect_stdout(log): outcome=render_verdict(results,report_name=REPORT.name)
package={'sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'seed':20261029,'extracted':len(raw),
 'excluded':excluded,'valid_population':len(valid),'random_sample':len(sample),'targeted_count':len(targeted),
 'coverage_percent':len(sample)/len(valid)*100,'results':results,'outcome':outcome}
(OUT/'audit-results.json').write_text(json.dumps(package,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'audit-verdict.txt').write_text(log.getvalue(),encoding='utf-8')
manifest=[]
for path in sorted(local.glob('*')):
 if path.suffix in ('.json','.txt') and not path.name.startswith(('listing','news','manifest')):
  manifest.append({'file':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size})
if manifest:
 (OUT/'source-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in package.items() if k not in ('results','excluded')},ensure_ascii=False,indent=2))
if outcome['verdict']!='PASS' or outcome['warn_count']: raise SystemExit(1)
