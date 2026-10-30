"""Capture minimal vendor fields from the fetched public local response."""
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path
HERE=Path(__file__).resolve().parent
LOCAL=HERE.parents[2]/'local'/'三季报-20261030'/'darentang'
raw=(LOCAL/'eastmoney.json').read_bytes()
rows=json.loads(raw,parse_float=D)['result']['data']
I=json.loads((HERE/'inputs.json').read_text(encoding='utf-8'))
mapping={'revenue':'TOTALOPERATEREVE','profit':'PARENTNETPROFIT','core':'KCFJCXSYJLR','cfo':'NETCASH_OPERATE_PK'}
V={'source':'Eastmoney RPT_F10_FINANCE_MAINFINADATA','retrieved':'2026-10-30','response_sha256':hashlib.sha256(raw).hexdigest(),'financial':{}}
for name in I['periods']:
    date=name[:4]+('-09-30' if name.endswith('YTD') else '-06-30' if name.endswith('H1') else '-12-31')
    row=next(x for x in rows if x['REPORT_DATE'].startswith(date))
    V['financial'][name]={k:str(row[field]) for k,field in mapping.items()}
    for k in mapping:assert D(I['periods'][name][k])==D(V['financial'][name][k]),(name,k)
V['quotes']={'qq':(LOCAL/'qq.txt').read_text(encoding='utf-8'),'sina':(LOCAL/'sina.txt').read_text(encoding='utf-8')}
(HERE/'vendor-snapshot.json').write_text(json.dumps(V,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
M={}
for p in LOCAL.glob('*.meta.json'):
    if p.stem.startswith(('q3','h1','annual','qq','sina','eastmoney','s-share','related-sale')):
        M[p.stem]=json.loads(p.read_text(encoding='utf-8'))
(HERE/'source-manifest.json').write_text(json.dumps(M,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('28 exact cross-source matches captured')
