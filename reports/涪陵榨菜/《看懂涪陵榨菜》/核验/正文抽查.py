"""Per-article 15% sampling of numeric table cells plus separate targeted prose review.

Table labels, dates used as row headings, scenario names and citations are not observations.
Persist the population, seed and matched report digest; never silently skip unmatched checks.
"""
import contextlib, hashlib, io, json, math, random, re, sys
from pathlib import Path
from urllib.parse import unquote
HERE=Path(__file__).resolve().parent; SERIES=HERE.parent
sys.path.insert(0,str(HERE.parents[3]/'tools'))
import report_audit as A
SEED=20261126
def write(name,obj):(HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def articles():return sorted(SERIES.glob('0[1-3]-*.md'))
def parts(text):return re.split(r'\n(?:\*\*资料来源|## (?:数据来源|资料与|来源|资料来源)|\*\*主要来源)',text,1)[0]
def tablepoints(body):
    out=[];hdr=None;lines=body.splitlines();pat=r'(?<![\w.])(?:[+−–－-])?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
    for idx,line in enumerate(lines):
        if not line.startswith('|'):hdr=None;continue
        cells=[c.strip().replace('**','') for c in line.strip().strip('|').split('|')]
        if idx+1<len(lines) and re.fullmatch(r'[\s|:\-]+',lines[idx+1]) and lines[idx+1].startswith('|'):
            hdr=cells;continue
        if not hdr or re.fullmatch(r'[\s|:\-]+',line):continue
        for col,cell in zip(hdr[1:],cells[1:]):
            if col in ('不能据此认定什么','此处最重的假设','这个口径回答什么'):continue
            raw=re.sub(r'\[\d+\]|\]\([^)]*\)','',cell)
            # Quantitative cells start with an amount (or approx prefix); mixed descriptive
            # cells are checked by the separate qualitative/targeted review.
            if not re.match(r'^(?:调整后\s*|设计\s*|总预算约\s*|约\s*|≥\s*|≤\s*)?[+−–－-]?[\d.]',raw):continue
            for j,m in enumerate(re.finditer(pat,raw.replace('约',' ').replace('亿元',' ').replace('元',' ').replace('倍',' '))):
                val=A._clean_num(m[0]); assert val is not None
                out.append(dict(id=len(out)+1,label=cells[0]+' · '+col+(' · '+str(j+1) if j else ''),reported_value=val,cell=cell,line=idx+1))
    return out
def extract():
    out={}
    for path in articles():
        body=parts(path.read_text(encoding='utf8'));pool=tablepoints(body);sample=A.sample_points([{**v,'line_number':v['line']} for v in pool],.15,SEED)
        assert pool and len(sample)>=math.ceil(len(pool)*.15)
        out[path.name]={'sha256':hashlib.sha256(path.read_text(encoding='utf8').encode('utf8')).hexdigest(),'pool':pool,'sample_ids':[s['id'] for s in sample]}
        print(path.name,len(pool),[(s['id'],s['label'],s['reported_value']) for s in sample])
    write('正文抽检样本.json',out)
def verdict():
    pop=json.loads((HERE/'正文抽检样本.json').read_text(encoding='utf8'));proofs=json.loads((HERE/'正文抽检依据.json').read_text(encoding='utf8'));checked=[]
    assert set(pop)=={p.name for p in articles()} and len(pop)==3
    for filename,p in pop.items():
        assert hashlib.sha256((SERIES/filename).read_text(encoding='utf8').encode('utf8')).hexdigest()==p['sha256']; selected={r['id']:r for r in p['pool'] if r['id'] in p['sample_ids']}; given=proofs[filename[:2]];assert set(map(int,given))==set(selected)
        for i,row in selected.items():
            value,source=given[str(i)];assert source and abs(value-row['reported_value'])<=max(.001,abs(row['reported_value'])*.01);checked.append({**row,'label':filename[:2]+' '+row['label'],'fetched_value':value,'fetched_source':source})
    with contextlib.redirect_stdout(io.StringIO()): v=A.render_verdict(checked,'涪陵榨菜系列')
    assert v['total']==v['pass_count']==len(checked) and v['warn_count']==0
    v['scope']='各篇数据表数字单元抽查；不含所有叙述与预测。证实测算不是验证未来。';write('正文抽检结果.json',v);print(v)
def structure():
    rows=[]
    for p in sorted(SERIES.glob('0?-*.md')):
        t=p.read_text(encoding='utf8');body=parts(t); assert all(line.rstrip()==line for line in t.splitlines());assert t.endswith('\n')
        if not p.name.startswith('00'):
            assert all(x in t for x in ('## 本篇要点回顾','## 下期预告','阅读','不构成任何投资建议'));assert not re.search(r'显然|必然|严重低估|教科书级别|神来之笔|完美|无可挑剔|我觉得|我认为',t)
        for href in re.findall(r'\]\(([^)]+)\)',t):
            if href.startswith(('https://','http://','#')):continue
            assert (p.parent/unquote(href.split('#')[0])).exists(),(p.name,href)
        rows.append({'file':p.name,'han_in_body':len(re.findall(r'[\u3400-\u9fff]',body)),'sha256':hashlib.sha256(t.encode('utf8')).hexdigest()})
    assert len(rows)==4;write('篇幅与版本.json',rows);print(rows)
if __name__=='__main__':{'extract':extract,'verdict':verdict,'structure':structure}[sys.argv[1]]()
