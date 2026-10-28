"""Local document cache helper; requires PyMuPDF. No network."""
from pathlib import Path
import fitz
ROOT=Path(__file__).resolve().parents[3]
CACHE=ROOT/"tmp/pdfs/xingqi-20261028"
for name,pages in (("xingqi-2025",[7,22,25]),("xingqi-h1",[17,18,47])):
    doc=fitz.open(CACHE/(name+".pdf"))
    (CACHE/(name+".txt")).write_text("\n".join(f"PDF PAGE {i+1}\n{p.get_text()}" for i,p in enumerate(doc)),encoding="utf-8")
    for i in pages:
        doc[i].get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(CACHE/f"{name}-page-{i+1}.png")
    print(name,len(doc))
