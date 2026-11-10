"""Frozen-seed numeric sampling and final structure checks; no auto-filled proofs."""
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
SEED=20261110
def save(name,value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def files():return sorted(SERIES.glob('0[123]-*.md'))
def extraction():
    reports=[]
    for file in files():
        text=file.read_text(encoding='utf-8')
        raw=audit.extract_data_points(text)
        supplemental=[]
        # Shared extractor drops rows whose first cell is only a year.
        for row,col,value,unit,line,context in audit._parse_md_tables(text.splitlines()):
            if re.fullmatch(r'20[0-9]{2}',row.strip()) and col not in ('说明','备注','来源'):
                supplemental.append({'id':len(raw)+len(supplemental)+1,'label':row+' · '+col,'reported_value':value,'unit':unit,'line_number':line,'raw_text':context,'supplement_reason':'Year-first numeric table row omitted by shared extractor'})
        eligible,excluded=[],[]
        for point in raw+supplemental:
            p=dict(point,report=file.name,key=file.name+'#'+str(point['id']))
            citation=bool(re.fullmatch(r'(?:S|H|IR|D|G|B|EM|Q)[0-9]*',p['label']))
            date=(p['reported_value'] in (2021,2022,2023,2024,2025,2026) and ('截止' in p['label'] or '日期' in p['label']))
            crosslink='对应篇目' in p['label'] and '](' in p['raw_text']
            if citation or date or crosslink:
                excluded.append(dict(p,reason='Citation/date/cross-reference numeral, not a financial observation'))
            else:eligible.append(p)
        n=max(3,math.ceil(len(eligible)*.15)) if eligible else 0
        sample=sorted(random.Random(SEED).sample(eligible,min(n,len(eligible))),key=lambda p:(p['line_number'],p['id']))
        reports.append({'report':file.name,'sha256':hashlib.sha256(text.encode()).hexdigest(),'raw_count':len(raw),'supplement_count':len(supplemental),'excluded':excluded,'eligible':eligible,'sample':sample})
    result={'seed':SEED,'ratio':.15,'reports':reports}
    save('audit-extraction.json',result)
    for report in reports:
        print(report['report'],len(report['eligible']),'eligible;',len(report['sample']),'sampled')
        for p in report['sample']:print(json.dumps({k:p[k] for k in ('key','label','reported_value','unit','line_number')},ensure_ascii=False))
    return result
def verdict():
    packet=json.loads((HERE/'audit-extraction.json').read_text(encoding='utf-8'))
    checked=json.loads((HERE/'audit-checked.json').read_text(encoding='utf-8'))
    sampled={p['key']:p for r in packet['reports'] for p in r['sample']}
    assert set(sampled)=={p['key'] for p in checked},'Every sampled point needs a source/formula check'
    for report in packet['reports']:
        text=(SERIES/report['report']).read_text(encoding='utf-8')
        assert hashlib.sha256(text.encode()).hexdigest()==report['sha256'],'Report changed after sampling'
    for p in checked:
        assert p['reported_value']==sampled[p['key']]['reported_value']
        assert p.get('fetched_value') is not None and p.get('fetched_source')
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):out=audit.render_verdict(checked,'看懂洋河股份三篇系列')
    clean='\n'.join(line.rstrip() for line in re.sub(r'\x1b\[[0-9;]*m','',buf.getvalue()).splitlines()).rstrip()+'\n'
    (HERE/'audit-verdict.txt').write_text(clean,encoding='utf-8')
    save('audit-verdict.json',out)
    print(clean)
    assert out['verdict']=='PASS'
def structure():
    paths=files()
    assert len(paths)==3,'Three articles required'
    rows=[]
    for path in paths:
        text=path.read_text(encoding='utf-8')
        body=re.split(r'\n## (?:来源|数据来源)',text)[0]
        count=len(re.findall('[一-龥]',body))
        assert 8000<=count<=12000,(path.name,count)
        assert '## 本篇要点回顾' in text and '## 下期预告' in text
        assert text.rstrip().endswith('*本系列基于公开信息和价值投资框架研究，不构成任何投资建议。*')
        assert not re.search(r'显然|必然|一定|严重低估|教科书级别|神来之笔|完美|无可挑剔|我认为|我觉得',text),path.name
        assert not re.search(r'(?i)Users[/\\]|(?<![A-Za-z])[A-Z]:[/\\]|portfolio-latest|stocks[.]json|API_KEY',text),path.name
        for link in re.findall(r'\]\(([^)]+)\)',text):
            target=link.strip('<>')
            if target.startswith(('https:','http:','#')):continue
            assert (path.parent/unquote(target.split('#')[0])).exists(),(path.name,target)
        rows.append({'file':path.name,'body_han_characters':count,'file_han_characters':len(re.findall('[一-龥]',text)),'sha256':hashlib.sha256(text.encode()).hexdigest()})
    total=sum(x['body_han_characters'] for x in rows)
    assert 25000<=total<=32000,total
    result={'body_han_characters_total':total,'articles':rows,'links_and_privacy_patterns':'pass'}
    save('structure-check.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'extract'
    {'extract':extraction,'verdict':verdict,'structure':structure}[mode]()
