"""Frozen-seed audit after documented extraction-noise filtering."""
import contextlib
import io
import json
import math
import random
import re
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
REPORT=OUT.parent/"长江电力研究报告-20261108.md"
sys.path.insert(0,str(ROOT/"tools"))
import report_audit
report_audit._force_utf8_stdio()

raw=report_audit.extract_data_points(REPORT.read_text(encoding="utf-8"))
excluded=[]
eligible=[]
text_columns={"经济含义","能说明什么","解释","研究动作","本次判定","修订依据","本期证据","判断","结论","可以证伪的边界","应跟踪的证据"}
for p in raw:
    col=p["label"].split(" · ")[-1]
    if col in text_columns or re.fullmatch(r"[SP]\d+",p["label"]) or (p["unit"]=="" and 1900<=p["reported_value"]<=2100 and "年" in p["raw_text"] and "已披露TTM" in p["label"]):
        excluded.append(dict(p,exclusion_reason="Text-column numeral, citation date, or year parsed instead of TTM amount"))
    else:
        eligible.append(p)
sample=sorted(random.Random(20261108).sample(eligible,math.ceil(len(eligible)*0.15)),key=lambda p:p["line_number"])
payload={"seed":20261108,"ratio":0.15,"raw_count":len(raw),"excluded_count":len(excluded),"eligible_count":len(eligible),"sample_count":len(sample),"excluded":excluded,"eligible":eligible,"sample":sample}
(OUT/"audit-extraction.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:payload[k] for k in ("raw_count","excluded_count","eligible_count","sample_count","sample")},ensure_ascii=False,indent=2))
results_path=OUT/"audit-results.json"
if results_path.exists():
    results=json.loads(results_path.read_text(encoding="utf-8"))
    expected={p["id"] for p in sample}
    if {r["id"] for r in results}!=expected:
        raise ValueError("Result ids do not match frozen sample")
    for r in results:
        original=next(p for p in sample if p["id"]==r["id"])
        if r["reported_value"]!=original["reported_value"]:
            raise ValueError("Report changed after audit")
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):
        verdict=report_audit.render_verdict(results,REPORT.name)
    (OUT/"audit-verdict.txt").write_text(re.sub(r"\x1b\[[0-9;]*m","",buf.getvalue()),encoding="utf-8")
    (OUT/"audit-verdict.json").write_text(json.dumps(verdict,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(verdict)
    if verdict["fail_count"] or verdict["warn_count"] or verdict["total"]!=len(sample):
        raise SystemExit(1)
