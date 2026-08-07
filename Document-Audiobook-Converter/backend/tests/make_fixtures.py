#!/usr/bin/env python3
"""Build one test document of each supported kind, all with the same text.

Extraction differs per format but should land on the same passages, so the same
wording in all three makes them comparable. Includes a rule of the sort found
above a stat block, because a passage that is only a rule used to stop playback.

    pip install python-docx pymupdf
    python tests/make_fixtures.py

Writes into tests/fixtures/, which is ignored - open them from the reader and
check each gives the same passages with no errors.
"""
import pathlib

import docx
import fitz  # PyMuPDF

OUT = pathlib.Path(__file__).parent / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)

PARAGRAPHS = [
    "The lighthouse blinked twice across the bay tonight.",
    "Someone was already awake inside the cottage on the hill.",
    "---------------------------",
    "The road down to the water was still wet from the rain.",
    "A gull settled on the iron railing and watched the boats.",
    "Nobody spoke until the tide had finally started to turn.",
]

(OUT / "smoke.txt").write_text("\n\n".join(PARAGRAPHS), encoding="utf-8")

document = docx.Document()
for paragraph in PARAGRAPHS:
    document.add_paragraph(paragraph)
document.save(OUT / "smoke.docx")

pdf = fitz.open()
page = pdf.new_page()
y = 72
for paragraph in PARAGRAPHS:
    page.insert_text((72, y), paragraph, fontsize=12)
    y += 28
pdf.save(OUT / "smoke.pdf")
pdf.close()

for made in sorted(OUT.iterdir()):
    print(f"{made.name:12} {made.stat().st_size:>7} bytes")
