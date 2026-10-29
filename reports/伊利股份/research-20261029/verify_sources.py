"""Capture selected public vendor values and compare with primary transcriptions.

Re-running acquisition requires local source downloads. Stored cross_checks.json
is self-contained and calculate.py can verify it without network or local cache.
"""
import json
import hashlib
from decimal import Decimal as D
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LOCAL=ROOT/'local'/'伊利股份-20261029'
I=json.loads((HERE/'inputs.json').read_text(encoding='utf-8'))
tables={name:{r['REPORT_DATE'][:10]:r for r in json.loads((LOCAL/(name+'.txt')).read_text(encoding='utf-8'),parse_float=D)['result']['data']} for name in ('em-indicators','em-cash','em-balance')}
mapping={'revenue':('em-indicators','TOTAL_OPERATE_INCOME-INTEREST_NI'),
         'total_revenue':('em-indicators','TOTAL_OPERATE_INCOME'),
         'profit':('em-indicators','PARENT_NETPROFIT'),
         'deduct':('em-indicators','DEDUCT_PARENT_NETPROFIT'),
         'cost':('em-indicators','OPERATE_COST'),
         'operating':('em-indicators','OPERATE_PROFIT'),
         'pbt':('em-indicators','TOTAL_PROFIT'),
         'tax':('em-indicators','INCOME_TAX'),
         'sales':('em-indicators','SALE_EXPENSE'),
         'ocf':('em-cash','NETCASH_OPERATE'),
         'capex':('em-cash','CONSTRUCT_LONG_ASSET')}
checks=[]
for period,values in {**I['periods'],**I['annual']}.items():
    year=period[:4]
    date=year+('-09-30' if period.endswith('ytd') else '-06-30' if period.endswith('h1') else '-12-31')
    for metric,primary in values.items():
        if metric not in mapping: continue
        table,field=mapping[metric]
        row=tables[table][date]
        secondary=D(str(row['TOTAL_OPERATE_INCOME']))-D(str(row['INTEREST_NI'])) if '-' in field else D(str(row[field]))
        p=D(primary)
        checks.append({'field':period+'/'+metric,'primary':primary,'secondary':str(secondary),
            'primary_source':'S1/S3/S4 consolidated statements; see inputs.json',
            'secondary_source':table,'date':date,'vendor_field':field,
            'difference_pct':str(abs(p-secondary)/abs(p)*100),'exact_match':p==secondary})
for period,date in [('2026q3','2026-09-30'),('2025end','2025-12-31'),('2025q3','2025-09-30'),('2024end','2024-12-31')]:
    for metric,field in [('cash','MONETARYFUNDS'),('ar','ACCOUNTS_RECE'),('inventory','INVENTORY'),('payables','ACCOUNTS_PAYABLE'),('assets','TOTAL_ASSETS')]:
        if metric not in I['balance'][period]: continue
        p=D(I['balance'][period][metric]); s=D(str(tables['em-balance'][date][field]))
        checks.append({'field':period+'/'+metric,'primary':str(p),'secondary':str(s),'primary_source':'S1/S4 balance sheet; 2025q3 comparative vendor snapshot','secondary_source':'em-balance','date':date,'vendor_field':field,'difference_pct':str(abs(p-s)/abs(p)*100),'exact_match':p==s,
                       'note':'2025q3 ar/inventory single vendor: NOT counted as independent source check' if period=='2025q3' else ''})
# The 2025Q3 working-capital base has not been independently transcribed from its
# old original filing; retain it as a clearly tagged source gap, not a fake pass.
single=[x for x in checks if x.get('note')]
checks=[x for x in checks if not x.get('note')]
(HERE/'cross_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(HERE/'source-gaps.json').write_text(json.dumps(single,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
metadata={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in LOCAL.glob('*.meta.json')}
metadata['q3_original_pdf']={'pages':15,'sha256':hashlib.sha256((LOCAL/'q3-pdf.pdf').read_bytes()).hexdigest(),'download_date':'2026-10-29','document_date':'2026-10-30','visual_checked_pages':[1,9,10]}
(HERE/'source-manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert all(c['exact_match'] for c in checks), 'Cross-source discrepancy'
print('Exact financial matches:',len(checks),'Tagged single-source points:',len(single))
