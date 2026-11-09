#!/usr/bin/env python3
"""Render the paper's selected evaluation-resource chronology (Figure 10).

Dates below are the first public *paper* dates from the linked official arXiv
submission histories, checked 2026-11-09. They are not conference dates or a
claim about the first dataset upload. No online request is made when building.
The focus rows are reading aids with overlapping scopes, not exclusive classes.
LONG2RAG replaces the former ambiguous ``LongRAG`` label: the cited benchmark
is Long^2RAG (2410.23000), not either of the similarly named LongRAG methods.
"""
from pathlib import Path
import shutil

from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = [ROOT / "doc/figs/fig10.pdf", ROOT / "figs_by_qixingyu/fig10.pdf"]

# name, focus, first public paper date, official arXiv identifier, display label.
RESOURCES = [
    ("DocVQA", "Visual document QA", "2020-07-01", "2007.00398", "DocVQA"),
    ("InfographicVQA", "Visual document QA", "2021-04-26", "2104.12756", "InfographicVQA"),
    ("DUDE", "Visual document QA", "2023-05-15", "2305.08455", "DUDE"),
    ("DocCollection VQA", "Long / collection QA", "2021-04-27", "2104.14336", "DocCollection\nVQA"),
    ("PDFVQA", "Long / collection QA", "2023-04-13", "2304.06447", "PDFVQA"),
    ("PDFTriage", "Long / collection QA", "2023-09-16", "2309.08872", "PDFTriage*"),
    ("SlideVQA", "Long / collection QA", "2023-01-12", "2301.04883", "SlideVQA"),
    ("MMLongBench-Doc", "Long / collection QA", "2024-07-01", "2407.01523", "MMLongBench-\nDoc"),
    ("LongDocURL", "Long / collection QA", "2024-12-24", "2412.18424", "LongDocURL"),
    ("M-LongDoc", "Long / collection QA", "2024-11-09", "2411.06176", "M-LongDoc"),
    ("Loong (Leave No Document Behind)", "Long / collection QA", "2024-06-25", "2406.17419", "Loong"),
    ("RAGProbe", "RAG evaluation", "2024-09-24", "2409.19019", "RAGProbe*"),
    ("CRAG", "RAG evaluation", "2024-06-07", "2406.04744", "CRAG"),
    ("LONG2RAG", "RAG evaluation", "2024-10-30", "2410.23000", "LONG2RAG"),
    ("MultiHop-RAG", "RAG evaluation", "2024-01-27", "2401.15391", "MultiHop-RAG"),
    ("REAL-MM-RAG", "RAG evaluation", "2025-02-17", "2502.12342", "REAL-MM-RAG"),
    ("T2-RAGBench", "RAG evaluation", "2025-06-04", "2506.12071", "T2-RAGBench"),
    ("FreshStack", "RAG evaluation", "2025-04-17", "2504.13128", "FreshStack"),
    ("PubLayNet", "Layout / OCR", "2019-08-16", "1908.07836", "PubLayNet"),
    ("DocLayNet", "Layout / OCR", "2022-06-02", "2206.01062", "DocLayNet"),
    ("OCRBench", "Layout / OCR", "2023-05-13", "2305.07895", "OCRBench"),
    ("RoDLA", "Layout / OCR", "2024-03-21", "2403.14442", "RoDLA"),
    # The arXiv ID begins 2501, but the official v1 history is 2024-12-31.
    ("OCRBench v2", "Layout / OCR", "2024-12-31", "2501.00321", "OCRBench v2"),
    ("OmniDocBench", "Layout / OCR", "2024-12-10", "2412.07626", "OmniDocBench"),
]

ROWS = [
    ("Visual document QA", "Visual\ndocument QA", 88, "#8C1515", "#FBF3F1"),
    ("Long / collection QA", "Long /\ncollection QA", 142, "#2E614C", "#F1F7F3"),
    ("RAG evaluation", "RAG\nevaluation", 116, "#8B5B22", "#FBF7EF"),
    ("Layout / OCR", "Layout / OCR", 104, "#355B88", "#F1F5FA"),
]


def text_lines(pdf, lines, x, centre_y, font, size, colour, leading=22):
    pdf.setFont(font, size)
    pdf.setFillColor(colors.HexColor(colour))
    first_y = centre_y + (len(lines) - 1) * leading / 2 - size * .33
    for i, line in enumerate(lines):
        pdf.drawCentredString(x, first_y - i * leading, line)


def build():
    assert len(RESOURCES) == len({row[0] for row in RESOURCES}) == 24
    width, height = 1080, 574
    left, col_width, top = 170, 126, 500
    years = range(2019, 2026)
    output = OUTPUTS[0]
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output), pagesize=(width, height), invariant=1)
    pdf.setTitle("Selected evaluation resources by first public paper year")
    pdf.setAuthor("Beyond OCR survey authors")
    pdf.setSubject("First public paper dates; source links embedded in resource labels")
    pdf.setFillColor(colors.HexColor("#8C1515"))
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(16, 545, "Selected datasets and evaluation frameworks")
    pdf.setFont("Helvetica", 16)
    pdf.setFillColor(colors.HexColor("#555555"))
    pdf.drawRightString(width - 18, 545, "First public paper year")
    for index, year in enumerate(years):
        pdf.setFillColor(colors.HexColor("#333333"))
        pdf.setFont("Helvetica-Bold", 19)
        pdf.drawCentredString(left + col_width * (index + .5), 513, str(year))

    y = top
    for focus, label, row_height, accent, background in ROWS:
        bottom = y - row_height
        pdf.setFillColor(colors.HexColor(background))
        pdf.rect(12, bottom, width - 24, row_height, stroke=0, fill=1)
        pdf.setFillColor(colors.HexColor(accent))
        pdf.rect(12, bottom, 5, row_height, stroke=0, fill=1)
        text_lines(pdf, label.split("\n"), 88, bottom + row_height / 2,
                   "Helvetica-Bold", 17.5, accent)
        for index, year in enumerate(years):
            x0 = left + index * col_width
            entries = sorted([r for r in RESOURCES if r[1] == focus and int(r[2][:4]) == year],
                             key=lambda r: (r[2], r[0]))
            total_lines = sum(len(r[4].split("\n")) for r in entries)
            size, leading, item_gap = 17, 20, 7
            block_height = total_lines * leading + max(0, len(entries) - 1) * item_gap
            base_y = bottom + (row_height + block_height) / 2 - size
            for entry in entries:
                lines = entry[4].split("\n")
                start_y = base_y
                for line in lines:
                    assert stringWidth(line, "Helvetica", size) <= col_width - 4, line
                    pdf.setFillColor(colors.HexColor(accent))
                    pdf.setFont("Helvetica", size)
                    pdf.drawCentredString(x0 + col_width / 2, base_y, line)
                    base_y -= leading
                pdf.linkURL("https://arxiv.org/abs/" + entry[3],
                            (x0 + 2, base_y + 4, x0 + col_width - 2, start_y + size),
                            relative=0, thickness=0)
                base_y -= item_gap
        pdf.setStrokeColor(colors.HexColor("#D7D7D7"))
        pdf.setLineWidth(.7)
        pdf.line(12, bottom, width - 12, bottom)
        y = bottom
    for index in range(8):
        x = left + index * col_width
        pdf.setStrokeColor(colors.HexColor("#E0E0E0"))
        pdf.setLineWidth(.6)
        pdf.line(x, top + 3, x, y)
    pdf.setFont("Helvetica", 13)
    pdf.setFillColor(colors.HexColor("#555555"))
    pdf.drawString(16, 32, "Years follow official paper submission histories, not conference publication years. Focus rows overlap; this selection is not exhaustive.")
    pdf.drawString(16, 14, "* Evaluation framework (PDFTriage also provides a dataset). Labels link to primary papers; LONG2RAG denotes Long-squared RAG.")
    pdf.showPage()
    pdf.save()
    for destination in OUTPUTS[1:]:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output, destination)
    print("Rendered 24 verified resources to " + ", ".join(str(p.relative_to(ROOT)) for p in OUTPUTS))


if __name__ == "__main__":
    build()
