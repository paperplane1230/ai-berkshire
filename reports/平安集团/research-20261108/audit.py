"""Report-local deterministic audit; shared audit tooling is not changed."""
import contextlib
import hashlib
import io
import json
import math
import random
import re
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools"))
import report_audit as audit
OUT=Path(__file__).resolve().parent
REPORT=OUT.parent/"中国平安研究报告-20261108.md"
SEED=20261108
def dump(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def extract():
    text=REPORT.read_text(encoding="utf-8")
    points=audit.extract_data_points(text)
    kept=[]
    excluded=[]
    # Do this before random selection. Exclude narrative columns, not financial facts.
    duplicate_rows={"NBV连续高增，寿险拐点已确认","财险COR改善即可支持利润上升","银行息差持续收窄","资管拖累减少","分红历史增长提供等待报酬"}
    for p in points:
        parts=p["label"].split(" · ")
        column=parts[-1]
        is_year=column=="口径" and p["reported_value"] in (2025,2026)
        is_duplicate=column=="新证据或纠错" and parts[0] in duplicate_rows
        is_metadata=(p["label"]=="DIV" and p["reported_value"]==2026) or (" · " not in p["label"] and bool(re.search(r"\d{2}:\d{2}:\d{2}",p["raw_text"])))
        if is_year or is_duplicate or is_metadata:
            reason="来源年份或行情时间中的分钟被误识别为财务数值" if is_year or is_metadata else "旧论点复核表重复的同一财务观察，保留其前文首次出现"
            excluded.append(dict(p,reason=reason))
        else:
            kept.append(p)
    # Shared extractor ignores percent-only row labels; include the nine DDM outputs explicitly.
    for line_no,line in enumerate(text.splitlines(),1):
        m=re.match(r"^\| (9|10|11)% \| ([0-9.]+)元 \| ([0-9.]+)元 \| ([0-9.]+)元 \|$",line)
        if m:
            for g,value in zip((2,3,4),m.groups()[1:]):
                kept.append({"id":len(points)+1+len(kept),"label":f"DDM r={m[1]}% g={g}%", "reported_value":float(value),"unit":"元","line_number":line_no,"raw_text":line})
    count=math.ceil(len(kept)*0.15)
    sampled=sorted(random.Random(SEED).sample(kept,count),key=lambda p:(p["line_number"],p["id"]))
    dump("audit-raw-extract.json",points)
    dump("audit-excluded.json",excluded)
    dump("audit-universe.json",kept)
    dump("audit-sample.json",sampled)
    dump("audit-selection.json",{"seed":SEED,"ratio":0.15,"raw":len(points),"excluded":len(excluded),"eligible_with_supplements":len(kept),"sample":count,"coverage":count/len(kept),"sha256":hashlib.sha256(text.encode()).hexdigest()})
    print(json.dumps(sampled,ensure_ascii=False,indent=2))

def verdict():
    selected=json.loads((OUT/"audit-sample.json").read_text(encoding="utf-8"))
    checks=json.loads((OUT/"audit-checked.json").read_text(encoding="utf-8"))
    assert {x["id"] for x in selected}=={x["id"] for x in checks},"Sample must be complete, no omissions"
    for x in checks:
        assert x.get("fetched_value") is not None and x.get("fetched_source"),x
    log=io.StringIO()
    with contextlib.redirect_stdout(log):
        result=audit.render_verdict(checks,report_name=REPORT.name)
    clean="\n".join(line.rstrip() for line in re.sub(r"\x1b\[[0-9;]*m","",log.getvalue()).splitlines())+"\n"
    (OUT/"audit-verdict.txt").write_text(clean,encoding="utf-8")
    dump("audit-verdict.json",result)
    print(clean)
    assert result["verdict"]=="PASS"

if __name__=="__main__":
    (verdict if len(sys.argv)>1 and sys.argv[1]=="verdict" else extract)()
