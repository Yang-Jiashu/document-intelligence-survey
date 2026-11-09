#!/usr/bin/env python3
"""Build Figures 4 and 7 from verified first-public-paper years.

All dates are from official arXiv submission histories, checked 2026-11-09.
They describe papers, not model-release dates or conference publication years.
These are overlapping reading groups, not an exclusive taxonomy, and chronology
does not imply that one route replaced or outperformed another.
VISTA-OCR deliberately refers to arXiv:2504.03621v1 (2025); v2 was renamed PILOT.
"""
from pathlib import Path
import shutil

from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]

# display name, first public paper date, primary identifier, reading group.
MILESTONES = [
    ("Calamari", "2018-07-05", "1807.02004", 0),
    ("PP-OCR", "2020-09-21", "2009.09941", 0),
    ("VISTA-OCR", "2025-04-04", "2504.03621v1", 0),
    ("OCRBench*", "2023-05-13", "2305.07895", 0),
    ("MonkeyOCR", "2025-06-05", "2506.05218", 0),
    ("DeepSeek-OCR", "2025-10-21", "2510.18234", 0),
    ("LayoutLM", "2019-12-31", "1912.13318", 1),
    ("LayoutLMv2", "2020-12-29", "2012.14740", 1),
    ("LiLT", "2022-02-28", "2202.13669", 1),
    ("DocLayout-\nYOLO", "2024-10-16", "2410.12628", 1),
    ("DLAFormer", "2024-05-20", "2405.11757", 1),
    ("PP-DocLayout", "2025-03-21", "2503.17213", 1),
    ("TAPAS", "2020-04-05", "2004.02349", 2),
    ("OmniTab", "2022-07-08", "2207.03637", 2),
    ("Chain-of-Table", "2024-01-09", "2401.04398", 2),
    ("Table-GPT", "2023-10-13", "2310.09263", 2),
    ("TableGPT2", "2024-11-04", "2411.02059", 2),
    ("Table-R1", "2025-05-29", "2505.23621", 2),
    ("Donut", "2021-11-30", "2111.15664", 3),
    ("Pix2Struct", "2022-10-07", "2210.03347", 3),
    ("GraphRAG", "2024-04-24", "2404.16130", 3),
    ("ColPali", "2024-06-27", "2407.01449", 3),
    ("Qwen2-VL", "2024-09-18", "2409.12191", 3),
    ("Qwen2.5-VL", "2025-02-19", "2502.13923", 3),
    ("Qwen3-VL", "2025-11-26", "2511.21631", 3),
]

VLM_TRACKS = [
    ("LayoutXLM", "2021-04-18", "2104.08836", 0),
    ("VinVL", "2021-01-02", "2101.00529", 0),
    ("FLAVA", "2021-12-08", "2112.04482", 0),
    ("UDOP", "2022-12-05", "2212.02623", 0),
    ("KOSMOS-2", "2023-06-26", "2306.14824", 0),
    # arXiv identifier starts 2401; actual first submission was 2023-12-31.
    ("DocLLM\n(text + boxes)", "2023-12-31", "2401.00908", 0),
    ("Qwen2-VL", "2024-09-18", "2409.12191", 0),
    ("Qwen2.5-VL", "2025-02-19", "2502.13923", 0),
    ("Qwen3-VL", "2025-11-26", "2511.21631", 0),
    ("Monkey", "2023-11-11", "2311.06607", 1),
    ("Qwen-VL", "2023-08-24", "2308.12966", 1),
    ("mPLUG-DocOwl\n1.5", "2024-03-19", "2403.12895", 1),
    ("TinyChart-3B", "2024-04-25", "2404.16635", 1),
    ("MiniCPM-V", "2024-08-03", "2408.01800", 1),
    ("InternVL 2.5", "2024-12-06", "2412.05271", 1),
    ("Donut", "2021-11-30", "2111.15664", 2),
    ("Pix2Struct", "2022-10-07", "2210.03347", 2),
    ("mPLUG-DocOwl2", "2024-09-05", "2409.03420", 2),
    ("SmolDocling", "2025-03-14", "2503.11576", 2),
    ("DocSLM", "2025-11-14", "2511.11313", 2),
    ("olmOCR", "2025-02-25", "2502.18443", 2),
    ("Docopilot", "2025-07-19", "2507.14675", 3),
    ("CogDoc", "2025-12-14", "2512.12658", 3),
]

COLORS = [("#355B88", "#F1F5FA"), ("#8B5B22", "#FBF7EF"),
          ("#2E614C", "#F1F7F3"), ("#8C1515", "#FBF3F1")]


def draw(number, title, data, years, groups, heights, left, cell, font, footer):
    width = left + len(years) * cell + 18
    height = sum(heights) + 120
    top = height - 75
    out = ROOT / f"doc/figs/fig{number:02}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(out), pagesize=(width, height), invariant=1)
    pdf.setTitle(title)
    pdf.setAuthor("Beyond OCR survey authors")
    pdf.setSubject("First-public-paper chronology; source hyperlinks in labels")
    pdf.setFont("Helvetica-Bold", 22)
    pdf.setFillColor(colors.HexColor("#8C1515"))
    pdf.drawString(16, height - 31, title)
    pdf.setFont("Helvetica", 15)
    pdf.setFillColor(colors.HexColor("#555555"))
    pdf.drawRightString(width - 18, height - 31, "First public paper year")
    for i, year in enumerate(years):
        pdf.setFont("Helvetica-Bold", 19)
        pdf.setFillColor(colors.HexColor("#333333"))
        pdf.drawCentredString(left + (i + .5) * cell, top + 13, str(year))
    y = top
    for row, (label, row_height) in enumerate(zip(groups, heights)):
        accent, bg = COLORS[row]
        bottom = y - row_height
        pdf.setFillColor(colors.HexColor(bg))
        pdf.rect(12, bottom, width - 24, row_height, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor(accent))
        pdf.rect(12, bottom, 5, row_height, fill=1, stroke=0)
        lines = label.split("\n")
        for j, line in enumerate(lines):
            pdf.setFont("Helvetica-Bold", 17)
            pdf.drawCentredString((left + 12) / 2,
                                 bottom + row_height / 2 + (len(lines)-1)*10 - j*20 - 6, line)
        for i, year in enumerate(years):
            entries = sorted([r for r in data if r[3] == row and int(r[1][:4]) == year], key=lambda r: r[1])
            leading, gap = font + 4, 7
            line_count = sum(len(r[0].split("\n")) for r in entries)
            block_height = line_count * leading + max(0, len(entries)-1) * gap
            assert block_height < row_height, (number, row, year, block_height)
            base = bottom + (row_height + block_height) / 2 - font
            x0 = left + i * cell
            for entry in entries:
                start = base
                for line in entry[0].split("\n"):
                    actual_font = min(font, (cell-8) * font / max(1, stringWidth(line, "Helvetica", font)))
                    assert actual_font >= 14, (number, line, actual_font)
                    pdf.setFont("Helvetica", actual_font)
                    pdf.setFillColor(colors.HexColor(accent))
                    pdf.drawCentredString(x0 + cell/2, base, line)
                    base -= leading
                pdf.linkURL("https://arxiv.org/abs/" + entry[2],
                            (x0+2, base+3, x0+cell-2, start+font), relative=0, thickness=0)
                base -= gap
        pdf.setStrokeColor(colors.HexColor("#D7D7D7"))
        pdf.setLineWidth(.7)
        pdf.line(12, bottom, width-12, bottom)
        y = bottom
    for i in range(len(years)+1):
        x = left + i*cell
        pdf.setStrokeColor(colors.HexColor("#E0E0E0"))
        pdf.setLineWidth(.6)
        pdf.line(x, y, x, top+3)
    pdf.setFont("Helvetica", 12.5)
    pdf.setFillColor(colors.HexColor("#555555"))
    pdf.drawString(16, 26, "Years follow official paper histories, not conference dates. Groups overlap; chronology does not imply replacement or performance superiority.")
    pdf.drawString(16, 9, footer)
    pdf.showPage()
    pdf.save()
    destination = ROOT / f"figs_by_qixingyu/fig{number:02}.pdf"
    shutil.copyfile(out, destination)
    print(f"Figure {number}: {len(data)} labels -> {out.relative_to(ROOT)} and {destination.relative_to(ROOT)}")


def build():
    draw(4, "Selected perception and document reasoning resources", MILESTONES,
         list(range(2018, 2026)),
         ["OCR / document\nparsing", "Layout / spatial\nrepresentation", "Table modeling /\nreasoning", "Document QA /\nretrieval"],
         [112, 112, 112, 112], 178, 116, 16.5,
         "* OCRBench is an evaluation resource. VISTA-OCR refers to the 2025 v1 paper. Labels link to primary papers; the selection is not exhaustive.")
    draw(7, "Selected multimodal and layout-aware document models", VLM_TRACKS,
         list(range(2021, 2026)),
         ["Multimodal /\nlayout foundations", "High-resolution /\nefficient scale", "OCR-free /\nvisual parsing", "Document-level\nmodels / agents"],
         [128, 152, 120, 90], 194, 166, 18,
         "DocLLM uses text and bounding boxes without an image encoder. The final row includes native document models as well as agentic systems.")


if __name__ == "__main__":
    build()
