"""Frozen per-article sample and final structure checks; sources checked separately."""
import contextlib
import hashlib
import io
import json
import math
import random
import re
import sys
from pathlib import Path
from urllib.parse import unquote
HERE=Path(__file__).resolve().parent
SERIES=HERE.parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'tools'))
import report_audit as audit
audit._force_utf8_stdio()
SEED=20261114
def write(name,obj):
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def articles():return sorted(SERIES.glob('0[123]-*.md'))
def extract():
    records=[]
    for path in articles():
        text=path.read_text(encoding='utf-8')
        source_start=next((i for i,line in enumerate(text.splitlines(),1) if re.match(r'^## (?:来源|数据来源)',line)),len(text.splitlines())+1)
        raw=audit.extract_data_points(text)
        extra=[]
        for row,col,val,unit,line,context in audit._parse_md_tables(text.splitlines()):
            if re.fullmatch(r'20[0-9]{2}年?',row.strip()) and col not in ('来源','说明','备注'):
                extra.append({'id':len(raw)+len(extra)+1,'label':row+' · '+col,'reported_value':val,'unit':unit,'line_number':line,'raw_text':context,'supplement_reason':'Year-first financial table omitted by shared extractor'})
        eligible,excluded=[],[]
        for item in raw+extra:
            p=dict(item,report=path.name,key=path.name+'#'+str(item['id']))
            citation=bool(re.fullmatch(r'(?:S|H|O|D|E|Q|B|M|AGM)[0-9]*',p['label']))
            citation=citation or (p['line_number']>=source_start and '](' in p['raw_text'] and 1900<=p['reported_value']<=2100)
            date=p['reported_value'] in (2021,2022,2023,2024,2025,2026) and ('日期' in p['label'] or '截止' in p['label'])
            crosslink='对应篇目' in p['label'] and '](' in p['raw_text']
            if citation or date or crosslink:
                excluded.append(dict(p,reason='Citation, date or cross-reference numeral; not a financial observation'))
            else:eligible.append(p)
        count=min(len(eligible),max(3,math.ceil(len(eligible)*.15)))
        sample=sorted(random.Random(SEED).sample(eligible,count),key=lambda p:(p['line_number'],p['id']))
        records.append({'report':path.name,'sha256':hashlib.sha256(text.encode()).hexdigest(),'raw_count':len(raw),'supplement_count':len(extra),'excluded':excluded,'eligible':eligible,'sample':sample})
    result={'seed':SEED,'ratio':.15,'reports':records}
    write('audit-extraction.json',result)
    for record in records:
        print(record['report'],len(record['eligible']),'eligible;',len(record['sample']),'sampled')
        for p in record['sample']:print(json.dumps({k:p[k] for k in ('key','label','reported_value','unit','line_number')},ensure_ascii=False))
def verdict():
    records=json.loads((HERE/'audit-extraction.json').read_text(encoding='utf-8'))['reports']
    checked=json.loads((HERE/'audit-checked.json').read_text(encoding='utf-8'))
    points={p['key']:p for r in records for p in r['sample']}
    assert set(points)=={p['key'] for p in checked},'Missing or extra sample verification'
    for record in records:
        text=(SERIES/record['report']).read_text(encoding='utf-8')
        assert hashlib.sha256(text.encode()).hexdigest()==record['sha256'],'Text changed after sampling'
    for p in checked:
        assert p['reported_value']==points[p['key']]['reported_value'] and p.get('fetched_value') is not None and p.get('fetched_source')
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):result=audit.render_verdict(checked,'看懂山西汾酒三篇系列')
    clean='\n'.join(line.rstrip() for line in re.sub(r'\x1b\[[0-9;]*m','',buf.getvalue()).splitlines()).rstrip()+'\n'
    (HERE/'audit-verdict.txt').write_text(clean,encoding='utf-8')
    write('audit-verdict.json',result)
    print(clean)
    assert result['verdict']=='PASS'
def structure():
    files=articles();assert len(files)==3
    rows=[]
    for path in files:
        text=path.read_text(encoding='utf-8')
        assert text.endswith('\n') and not text.endswith('\n\n'),(path.name,'EOF whitespace')
        assert all(line==line.rstrip() for line in text.splitlines()),(path.name,'trailing whitespace')
        body=re.split(r'\n## (?:来源|数据来源)',text)[0]
        count=len(re.findall('[一-龥]',body))
        assert 8000<=count<=12000,(path.name,count)
        assert '## 本篇要点回顾' in text and '## 下期预告' in text
        assert text.rstrip().endswith('*本系列基于公开信息和价值投资框架研究，不构成任何投资建议。*')
        assert not re.search('显然|必然|一定|严重低估|教科书级别|神来之笔|完美|无可挑剔|我认为|我觉得',text),path.name
        assert not re.search(r'(?i)Users[/\\]|(?<![A-Za-z])[A-Z]:[/\\]|portfolio-latest|stocks[.]json|API_KEY',text),path.name
        for target in re.findall(r'\]\(([^)]+)\)',text):
            target=target.strip('<>')
            if target.startswith(('https:','http:','#')):continue
            assert (path.parent/unquote(target.split('#')[0])).exists(),(path.name,target)
        rows.append({'file':path.name,'body_han_characters':count,'total_han_characters':len(re.findall('[一-龥]',text)),'sha256':hashlib.sha256(text.encode()).hexdigest()})
    total=sum(row['body_han_characters'] for row in rows)
    assert 25000<=total<=31000,total
    result={'body_han_characters_total':total,'articles':rows,'links_privacy_terms':'pass'}
    write('structure-check.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':{'extract':extract,'verdict':verdict,'structure':structure}[sys.argv[1] if len(sys.argv)>1 else 'extract']()
