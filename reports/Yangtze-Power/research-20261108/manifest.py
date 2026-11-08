"""Inventory only public source snapshots and this report's validation artifacts."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
LOCAL=ROOT/"local/三季报-20261108/yangtze"
items=[]
for path in sorted(LOCAL.iterdir()):
    if path.suffix not in (".txt",".json",".pdf",".png",".md") or path.name.endswith("-links.json"):
        continue
    payload=path.read_bytes()
    item={"path":path.relative_to(ROOT).as_posix(),"bytes":len(payload),"sha256":hashlib.sha256(payload).hexdigest()}
    if path.name.endswith(".meta.json"):
        source=json.loads(payload.decode("utf-8"))
        item.update({k:source[k] for k in ("url","retrieved_at") if k in source})
        item["original_response_sha256"]=source.get("sha256")
    items.append(item)
result={"cutoff":"2026-11-08","quote_date":"2026-11-06","raw_public_sources":items,
        "visual_review":{"q3-pdf.pdf":[1,7,9,12],"h1-pdf.pdf":[99]},
        "visual_findings":"Inspected rendered table headers, periods, units and figures. No mismatch between PDF figures and extracted report inputs on these pages. Other pages used as text, not claimed visually audited."}
(OUT/"source-manifest.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("Public source manifest entries:",len(items))
