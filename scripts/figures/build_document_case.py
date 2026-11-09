#!/usr/bin/env python3
"""Author-drawn, fully vector running example for document evidence use.

The numbers are deliberately constructed, not reported model measurements.
Builds identical Figure 13 assets for the report and alternative manuscript.
All figure text is >= 18 pt on a 900 pt canvas (>= 9 pt at 450 pt width).
"""
from pathlib import Path
from math import atan2, cos, sin, pi
import shutil

from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
W, H = 900, 820
INK = HexColor('#263A42')
MUTED = HexColor('#596973')
LINE = HexColor('#B9C7CB')
BLUE = HexColor('#326782')
BLUE_TINT = HexColor('#EAF3F8')
GREEN = HexColor('#3D6C56')
GREEN_TINT = HexColor('#E8F3EB')
RUST = HexColor('#90553B')
WARM = HexColor('#FBF4E8')
WHITE = HexColor('#FFFFFF')


def text(c, x, y, value, size=18, bold=False, color=INK, align='left'):
    assert size >= 18
    font = 'Helvetica-Bold' if bold else 'Helvetica'
    c.setFont(font, size)
    c.setFillColor(color)
    {'left': c.drawString, 'center': c.drawCentredString,
     'right': c.drawRightString}[align](x, y, value)


def box(c, x, y, w, h, fill=WHITE, stroke=LINE, radius=7, lw=1.1):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(lw)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def arrow(c, x1, y1, x2, y2, color=MUTED, width=1.6):
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(width)
    c.line(x1, y1, x2, y2)
    angle = atan2(y2-y1, x2-x1)
    p = c.beginPath()
    p.moveTo(x2, y2)
    for delta in (-pi/6, pi/6):
        p.lineTo(x2-8*cos(angle+delta), y2-8*sin(angle+delta))
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def badge(c, x, y, value, color):
    c.setFillColor(color)
    c.circle(x, y, 15, fill=1, stroke=0)
    text(c, x, y-6.2, value, 19, True, WHITE, 'center')


def draw():
    out = ROOT / 'doc/figs/fig13.pdf'
    out.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out), pagesize=(W, H), invariant=1,
                      pageCompression=1)
    c.setTitle('A cross-page financial question: shared evidence, different representations')
    c.setAuthor('Beyond OCR survey authors')
    c.setSubject('Constructed financial example, not empirical model results')

    text(c, 20, 791, 'One question, two pages, a joint evidence requirement', 26, True)
    text(c, 20, 766, 'Constructed example: every route must preserve the same evidence.', 19, color=MUTED)

    box(c, 20, 695, 860, 54, WARM, HexColor('#D7C6AC'))
    text(c, 35, 727, 'Question: What is the year-on-year change in operating margin', 20, True)
    text(c, 35, 704, 'after applying the restatement in the footnote?', 20, True)

    # Two actual-looking page fragments, rather than generic document icons.
    for x in (20, 464):
        box(c, x, 378, 416, 300, WHITE, LINE, radius=2)
        c.setStrokeColor(LINE)
        c.line(x+17, 635, x+399, 635)
    text(c, 37, 650, 'Operating performance', 22, True)
    text(c, 37, 615, 'USD million; margin in %', 18, color=MUTED)

    tx, top, rh = 37, 601, 41
    widths = (200, 91, 91)
    edges = (tx, tx+200, tx+291, tx+382)
    rows = [
        ('', '2024', '2023'),
        ('Revenue', '1,000', '800'),
        ('Operating profit', '150', '96'),
        ('Operating margin', '15.0%', '12.0%'),
    ]
    c.setFillColor(HexColor('#F0F3F3'))
    c.rect(tx, top-rh, sum(widths), rh, fill=1, stroke=0)
    # A is the table evidence region: a label does not assert it is sufficient.
    c.setFillColor(BLUE_TINT)
    c.rect(tx, top-4*rh, sum(widths), 3*rh, fill=1, stroke=0)
    c.setFillColor(HexColor('#D5E9F3'))
    c.rect(edges[2]+1, top-4*rh+1, widths[2]-2, 2*rh-2, fill=1, stroke=0)
    for r, values in enumerate(rows):
        y = top-r*rh-27
        for col, value in enumerate(values):
            if col == 0:
                text(c, edges[col]+10, y, value, 19, r == 0)
            else:
                text(c, (edges[col]+edges[col+1])/2, y, value,
                     20, r == 0, align='center')
    c.setStrokeColor(LINE)
    c.setLineWidth(.9)
    for r in range(5):
        c.line(tx, top-r*rh, tx+sum(widths), top-r*rh)
    for x in edges:
        c.line(x, top-4*rh, x, top)
    c.setStrokeColor(BLUE)
    c.setLineWidth(2)
    c.rect(tx-2, top-4*rh-2, sum(widths)+4, 3*rh+4, fill=0, stroke=1)
    badge(c, 403, 615, 'A', BLUE)
    text(c, 37, 408, 'As originally reported', 18, color=MUTED)
    text(c, 413, 390, '12', 18, color=MUTED, align='right')

    text(c, 481, 650, 'Notes to the accounts', 22, True)
    text(c, 481, 615, 'Note 7. Comparative figures', 19, True)
    box(c, 481, 486, 382, 104, GREEN_TINT, GREEN, radius=3, lw=2)
    text(c, 495, 562, 'The 2023 operating profit is', 20)
    text(c, 495, 536, 'restated from 96 to 104.', 20, True, GREEN)
    text(c, 495, 510, 'Revenue remains 800.', 20)
    badge(c, 847, 606, 'B', GREEN)
    text(c, 481, 453, 'The 2024 figures are unchanged.', 18)
    for yy, length in ((430, 353), (416, 275)):
        c.setStrokeColor(HexColor('#DEE3E4'))
        c.setLineWidth(2)
        c.line(481, yy, 481+length, yy)
    text(c, 857, 390, '13', 18, color=MUTED, align='right')

    # The three routes are alternatives or combinations, not a performance rank.
    cards = [
        (20, 'OCR + layout', BLUE_TINT, BLUE,
         ['Text + cell coordinates', 'Keep row, year and unit.', 'Recover A and B together.']),
        (313, 'Direct visual', GREEN_TINT, GREEN,
         ['Page images / crops', 'Keep fine print readable.', 'Supply both relevant pages.']),
        (606, 'Hybrid retrieval', WARM, RUST,
         ['Text + visual evidence', 'Link table and footnote.', 'Retrieve both A and B.']),
    ]
    for x, title, fill, accent, lines in cards:
        box(c, x, 182, 274, 174, fill, LINE)
        text(c, x+14, 327, title, 22, True, accent)
        c.setStrokeColor(LINE)
        c.line(x+14, 313, x+260, 313)
        for i, line in enumerate(lines):
            assert stringWidth(line, 'Helvetica', 18) < 246, line
            text(c, x+14, 288-i*29, line, 18)
        text(c, x+14, 199, 'Shared evidence: A + B', 18, True, accent)
        arrow(c, x+137, 182, x+137, 157, accent)

    box(c, 20, 24, 860, 133, HexColor('#F5F7F7'), LINE)
    text(c, 36, 129, 'Apply the restatement, then compute the change', 22, True)
    text(c, 36, 99, '2023: 104 / 800 = 13.0%     2024: 150 / 1,000 = 15.0%', 21)
    text(c, 36, 69, 'Answer: +2.0 percentage points, supported by A + B.', 23, True, GREEN)
    text(c, 36, 40, 'Using 12.0% gives +3.0 points: valid arithmetic on unadjusted evidence.', 18, color=MUTED)

    c.showPage()
    c.save()
    alt = ROOT / 'figs_by_qixingyu/fig13.pdf'
    shutil.copyfile(out, alt)
    print(f'{out.relative_to(ROOT)} -> {alt.relative_to(ROOT)}')


if __name__ == '__main__':
    draw()
