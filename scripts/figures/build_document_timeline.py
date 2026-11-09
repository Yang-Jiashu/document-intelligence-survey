#!/usr/bin/env python3
"""Draw a compact, branched chronology from verified source metadata.

Dates, official checkpoint links and partial-weight qualifications remain in
`document_timeline_sources.json`. Branch geometry organizes the reading order;
it does not assert scientific ancestry, replacement, or a performance ranking.
The yellow underline denotes publicly available pretrained weights, not license
classification. Names link to papers; underlines link to checkpoints.
"""
from __future__ import annotations

import json
import shutil
from collections import defaultdict
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name('document_timeline_sources.json')
W, H = 1100, 480
FONT, LEADING, GAP = 22, 25, 10
INK = HexColor('#243746')
MUTED = HexColor('#697D89')
BRANCH = HexColor('#8B9CA6')
YELLOW = HexColor('#F3D27D')
YEAR = HexColor('#EDF3F5')
TRACKS = {
    'perception': ('Layout / OCR', '#255C7B'),
    'structured': ('Structure / reasoning', '#2D8B7B'),
    'visual': ('Visual / documents', '#D57060'),
}
ANCHORS = {
    2015: (65, 244), 2018: (135, 247), 2019: (210, 248),
    2020: (310, 245), 2021: (415, 237), 2022: (520, 230),
    2023: (640, 225), 2024: (800, 230), 2025: (1020, 246),
}
# Recent years have two branches, preserving within-year paper-date order.
# tuple: year, [start:end] of that year's papers, x, first baseline, side.
CLUSTERS = [
    (2015, 0, None, 23, 330, 'top'),
    (2018, 0, None, 35, 145, 'bottom'),
    (2019, 0, None, 145, 370, 'top'),
    (2020, 0, None, 245, 165, 'bottom'),
    (2021, 0, None, 340, 405, 'top'),
    (2022, 0, None, 440, 165, 'bottom'),
    (2023, 0, None, 570, 405, 'top'),
    (2024, 0, 4, 735, 405, 'top'),
    (2024, 4, None, 745, 165, 'bottom'),
    (2025, 0, 3, 940, 405, 'top'),
    (2025, 3, None, 950, 165, 'bottom'),
]


def text(c, x, y, value, size=FONT, bold=False, color=INK, align='left'):
    c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
    c.setFillColor(color)
    getattr(c, {'left': 'drawString', 'center': 'drawCentredString',
                'right': 'drawRightString'}[align])(x, y, value)


def icon(c, track, x, y, size=12):
    """Small semantic glyphs, not institution or company logos."""
    c.setStrokeColor(HexColor(TRACKS[track][1]))
    c.setLineWidth(1.5)
    if track == 'perception':
        d = size / 2
        for sx, sy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            p = c.beginPath()
            p.moveTo(x + sx*d, y + sy*d*0.35)
            p.lineTo(x + sx*d, y + sy*d)
            p.lineTo(x + sx*d*0.35, y + sy*d)
            c.drawPath(p, stroke=1, fill=0)
    elif track == 'structured':
        c.rect(x-size/2, y-size/2, size, size, stroke=1, fill=0)
        c.line(x-size/2, y, x+size/2, y)
        c.line(x, y-size/2, x, y+size/2)
    else:
        p = c.beginPath()
        p.moveTo(x-size/2, y)
        p.curveTo(x-size/6, y+size*.55, x+size/6, y+size*.55, x+size/2, y)
        p.curveTo(x+size/6, y-size*.55, x-size/6, y-size*.55, x-size/2, y)
        c.drawPath(p, stroke=1, fill=0)
        c.setFillColor(HexColor(TRACKS[track][1]))
        c.circle(x, y, size*.12, stroke=0, fill=1)


def display_name(entry):
    name = entry['name']
    return name + ('\u2020' if name in {'UDOP', 'ColPali'} else '')


def wrap_name(value, width=150):
    if stringWidth(value, 'Helvetica-Bold', FONT) <= width:
        return [value]
    special = {
        'DocLayout-YOLO': ['DocLayout-', 'YOLO'],
        'DeepSeek-OCR': ['DeepSeek-', 'OCR'],
        'mPLUG-DocOwl 1.5': ['mPLUG-', 'DocOwl 1.5'],
        'mPLUG-DocOwl1.5': ['mPLUG-', 'DocOwl 1.5'],
    }
    assert value in special, 'New long label needs deliberate wrapping: ' + value
    return special[value]


def model(c, entry, x, baseline):
    lines = wrap_name(display_name(entry))
    low = baseline - (len(lines)-1) * LEADING
    width = max(stringWidth(line, 'Helvetica-Bold', FONT) for line in lines)
    # A slim yellow marker, rather than a large filled card, preserves the
    # weight-availability signal without turning the timeline into a card grid.
    if entry.get('weights_url'):
        c.setFillColor(YELLOW)
        for i, line in enumerate(lines):
            y = baseline - i*LEADING
            c.roundRect(x-1, y-2.5, stringWidth(line, 'Helvetica-Bold', FONT)+2,
                        5.5, 2, stroke=0, fill=1)
    icon(c, entry['track'], x-13, baseline+8, 11)
    for i, line in enumerate(lines):
        text(c, x, baseline-i*LEADING, line, bold=True)
    paper = entry.get('paper_url') or ('https://arxiv.org/abs/' + entry['arxiv'])
    c.linkURL(paper, (x-3, low+4, x+width+3, baseline+19),
              relative=0, thickness=0)
    if entry.get('weights_url'):
        for i, line in enumerate(lines):
            y = baseline-i*LEADING
            c.linkURL(entry['weights_url'],
                      (x-2, y-4, x+stringWidth(line, 'Helvetica-Bold', FONT)+3, y+4),
                      relative=0, thickness=0)
    return low-GAP-LEADING, (entry['name'], x-20, low-5, x+width+4, baseline+21)


def branch(c, year, x, first, last, side):
    ax, ay = ANCHORS[year]
    tx = x + 53
    ty = last-13 if side == 'top' else first+31
    c.setStrokeColor(BRANCH)
    c.setLineWidth(1.35)
    p = c.beginPath()
    p.moveTo(ax, ay)
    mid = (ay+ty)/2
    p.curveTo(ax, mid, tx, mid, tx, ty)
    c.drawPath(p, stroke=1, fill=0)


def build():
    metadata = json.loads(SOURCE.read_text())
    entries = metadata['entries']
    grouped = defaultdict(list)
    for entry in entries:
        grouped[int(entry['date'][:4])].append(entry)
        assert entry['track'] in TRACKS and entry.get('sources')
    for group in grouped.values():
        group.sort(key=lambda e: (e['date'], e['name']))
    assert len(entries) == 27 and set(grouped) == set(ANCHORS)

    out = ROOT/'doc/figs/fig12.pdf'
    c = canvas.Canvas(str(out), pagesize=(W,H), pageCompression=1, invariant=1)
    c.setTitle('Representative document-intelligence models: first-public-paper timeline')
    c.setAuthor('Beyond OCR survey authors')
    c.setSubject('First-public-paper dates; yellow underlines denote public pretrained weights')
    c.setFillColor(white)
    c.rect(0,0,W,H,stroke=0,fill=1)

    # Two compact legend rows; methodological qualifications belong in the
    # manuscript caption and source metadata, not repeated as plot paragraphs.
    for x, track in zip((20,225,515), TRACKS):
        label, color = TRACKS[track]
        icon(c,track,x+6,466,13)
        text(c,x+23,460,label,size=18,color=HexColor(color))
    c.setFillColor(YELLOW)
    c.roundRect(818,457,255,5.5,2,stroke=0,fill=1)
    text(c,818,460,'Publicly available weights',size=18,bold=True)
    text(c,20,437,'\u2020 Partial weights / separate base model',size=16.5,color=MUTED)
    text(c,1080,437,'First public paper year',size=16.5,color=MUTED,align='right')

    # Gentle horizontal curve leaves comparable space above and below.
    c.setStrokeColor(INK)
    c.setLineWidth(2.65)
    p = c.beginPath()
    p.moveTo(17,240)
    p.curveTo(205,268,410,230,640,225)
    p.curveTo(825,217,980,267,1082,244)
    c.drawPath(p,stroke=1,fill=0)
    c.setFillColor(INK)
    p = c.beginPath()
    p.moveTo(1094,241)
    p.lineTo(1079,251)
    p.lineTo(1082,244)
    p.lineTo(1077,237)
    p.close()
    c.drawPath(p,stroke=0,fill=1)

    occupied, seen = [], []
    for year, start, stop, x, first, side in CLUSTERS:
        group = grouped[year][start:stop]
        assert group
        y = first
        for entry in group:
            seen.append(entry['name'])
            y, box = model(c,entry,x,y)
            occupied.append(box)
        last = y+GAP+LEADING
        branch(c,year,x,first,last,side)
    assert sorted(seen) == sorted(entry['name'] for entry in entries)

    for year, (x,y) in ANCHORS.items():
        c.setFillColor(YEAR)
        c.roundRect(x-27,y-11,54,25,3,stroke=0,fill=1)
        text(c,x,y-5.5,str(year),size=19,bold=True,align='center')

    c.showPage()
    c.save()
    shutil.copyfile(out, ROOT/'figs_by_qixingyu/fig12.pdf')
    for name,x0,y0,x1,y1 in occupied:
        assert 1 < x0 < x1 < W-3 and 20 < y0 < y1 < 427, (name,x0,y0,x1,y1)
    for i, a in enumerate(occupied):
        for b in occupied[i+1:]:
            assert not (max(a[1],b[1]) < min(a[3],b[3]) and
                        max(a[2],b[2]) < min(a[4],b[4])), (a[0],b[0])
    print(f'{len(entries)} entries; {sum(bool(e.get("weights_url")) for e in entries)} public checkpoints; {W}x{H}; {out}')


if __name__ == '__main__':
    build()
