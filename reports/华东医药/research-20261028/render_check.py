"""Render exact primary filing pages for visual checks; requires PyMuPDF."""
from pathlib import Path
import fitz

ROOT=Path(__file__).resolve().parents[3]
DEST=ROOT/"tmp/pdfs/huadong-20261028"
for name,pages in (("huadong-h1",[171,203,204]),("huadong-q3",[20]),("huadong-2025",[12,163])):
    with fitz.open(DEST/(name+".pdf")) as doc:
        for page in pages:
            target=DEST/(name+"-verified-"+str(page)+".png")
            doc[page-1].get_pixmap(matrix=fitz.Matrix(1.6,1.6)).save(target)
            print(target)
