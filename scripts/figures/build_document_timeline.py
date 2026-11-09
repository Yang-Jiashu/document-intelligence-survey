#!/usr/bin/env python3
"""Draw a branched, first-public-paper chronology of document intelligence.

All factual entries and availability evidence live in the adjacent JSON file.
The geometry is authored for this survey. Branches do not imply a genealogy,
replacement, or a performance comparison. Yellow means an official public
pretrained checkpoint was verified; it is not an open-source license judgment.

Run: python scripts/figures/build_document_timeline.py
"""
from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name('document_timeline_sources.json')
W, H = 1350, 960
FONT = 27
INK = HexColor('#25343D')
MUTED = HexColor('#52646D')
PAPER = white
YELLOW = HexColor('#FFF0B5')
YEAR = HexColor('#DCEBF3')
TRACKS = {
    'perception': ('OCR / layout', '#2F6288'),
    'structured': ('Structured / reasoning', '#2D7058'),
    'visual': ('Visual / document', '#84527A'),
}
# The chronological trunk descends so the denser recent branches have room.
ANCHORS = {
    2015: (65, 720), 2018: (155, 711), 2019: (245, 692),
    2020: (360, 645), 2021: (500, 555), 2022: (680, 355),
    2023: (865, 232), 2024: (1050, 171), 2025: (1240, 152),
}
# Left edge and first text baseline for each chronological model cluster.
CLUSTERS = {
    2015: (32, 620), 2018: (60, 485), 2019: (166, 350),
    2020: (300, 570), 2021: (430, 310), 2022: (600, 780),
    2023: (790, 780), 2024: (975, 780), 2025: (1160, 780),
}


def text(c, x, y, value, size=FONT, bold=False, color=INK, align='left'):
    c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
    c.setFillColor(color)
    getattr(c, {'left': 'drawString', 'center': 'drawCentredString',
                'right': 'drawRightString'}[align])(x, y, value)


def wrap_name(value, width=170):
    """Keep recognizable name components intact, without shrinking text."""
    value = value.replace('\n', ' ')
    if stringWidth(value, 'Helvetica-Bold', FONT) <= width:
        return [value]
    special = {
        'DocLayout-YOLO': ['DocLayout-', 'YOLO'],
        'DeepSeek-OCR': ['DeepSeek-', 'OCR'],
        'mPLUG-DocOwl 1.5': ['mPLUG-', 'DocOwl 1.5'],
        'mPLUG-DocOwl1.5': ['mPLUG-', 'DocOwl 1.5'],
    }
    if value in special:
        lines = special[value]
    else:
        words = re.findall(r'[^\s-]+-?|\S+', value)
        lines = []
        current = ''
        for word in words:
            candidate = (current + ' ' + word).strip()
            if current and stringWidth(candidate, 'Helvetica-Bold', FONT) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    assert all(stringWidth(line, 'Helvetica-Bold', FONT) <= width for line in lines), value
    return lines


def display_name(entry):
    name = entry['name']
    return name + ('\u2020' if name in {'UDOP', 'ColPali'} else '')


def model(c, entry, x, baseline):
    lines = wrap_name(display_name(entry))
    low = baseline - (len(lines) - 1) * 32
    top = baseline + 25
    high_width = max(stringWidth(line, 'Helvetica-Bold', FONT) for line in lines) + 12
    if entry.get('weights_url'):
        c.setFillColor(YELLOW)
        c.roundRect(x - 5, low - 6, high_width, top - low + 9,
                    5, stroke=0, fill=1)
    color = HexColor(TRACKS[entry['track']][1])
    c.setFillColor(color)
    c.roundRect(x - 15, low - 2, 4, top - low, 2, stroke=0, fill=1)
    for i, line in enumerate(lines):
        text(c, x, baseline - i * 32, line, bold=True)
    paper = entry.get('paper_url') or ('https://arxiv.org/abs/' + entry['arxiv'])
    c.linkURL(paper, (x - 6, low - 6, x + high_width, top + 3),
              relative=0, thickness=0)
    # A small link target at the stream bar opens the verified checkpoint.
    if entry.get('weights_url'):
        c.linkURL(entry['weights_url'], (x - 20, low - 6, x - 8, top + 3),
                  relative=0, thickness=0)
    return low - 57


def branch(c, year, bottom, top):
    ax, ay = ANCHORS[year]
    x, baseline = CLUSTERS[year]
    c.setStrokeColor(MUTED)
    c.setLineWidth(2.3)
    p = c.beginPath()
    p.moveTo(ax, ay)
    if year <= 2021:
        end = (x + 60, top + 15)
        p.lineTo(ax, end[1] + 24)
        p.lineTo(end[0], end[1])
    else:
        end = (x + 68, bottom - 20)
        p.lineTo(ax, end[1] - 27)
        p.lineTo(end[0], end[1])
    c.drawPath(p, stroke=1, fill=0)


def build():
    metadata = json.loads(SOURCE.read_text())
    entries = metadata['entries']
    grouped = defaultdict(list)
    for entry in entries:
        grouped[int(entry['date'][:4])].append(entry)
        assert entry['track'] in TRACKS, entry
        assert 'availability_note' in entry and entry.get('sources'), entry
    assert set(grouped) <= set(ANCHORS), set(grouped)
    assert len(entries) <= 29
    for group in grouped.values():
        group.sort(key=lambda e: (e['date'], e['name']))
    destination = ROOT / 'doc/figs/fig12.pdf'
    c = canvas.Canvas(str(destination), pagesize=(W, H),
                      pageCompression=1, invariant=1)
    c.setTitle('A chronology of representative document-intelligence models and methods')
    c.setAuthor('Beyond OCR survey authors')
    c.setSubject('First-public-paper dates; official public pretrained checkpoints highlighted in yellow')
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    text(c, 32, 918, 'A decade of document intelligence', size=38, bold=True)
    c.setFillColor(YELLOW)
    c.roundRect(934, 910, 384, 40, 6, fill=1, stroke=0)
    text(c, 1126, 921, 'Publicly available weights', size=27, bold=True, align='center')
    text(c, 32, 876, 'Selected models and methods, organized by first public paper date.', size=27, color=MUTED)
    for x, track in zip((32, 390, 850), TRACKS):
        label, color = TRACKS[track]
        c.setFillColor(HexColor(color))
        c.circle(x + 8, 837, 7, stroke=0, fill=1)
        text(c, x + 27, 829, label, size=26, color=HexColor(color))

    # Draw one continuous chronological curve. It is a reading guide, not a
    # graph of scientific ancestry. Label clusters connect only to their year.
    c.setStrokeColor(INK)
    c.setLineWidth(4.3)
    p = c.beginPath()
    p.moveTo(30, 724)
    p.curveTo(225, 721, 357, 666, 463, 586)
    p.curveTo(552, 515, 594, 423, 680, 355)
    p.curveTo(827, 225, 1002, 151, 1315, 151)
    c.drawPath(p, stroke=1, fill=0)
    c.setFillColor(INK)
    arrow = c.beginPath()
    arrow.moveTo(1333, 151)
    arrow.lineTo(1306, 162)
    arrow.lineTo(1313, 151)
    arrow.lineTo(1306, 140)
    arrow.close()
    c.drawPath(arrow, stroke=0, fill=1)

    occupied = []
    for year in sorted(grouped):
        x, baseline = CLUSTERS[year]
        y = baseline
        for entry in grouped[year]:
            lines = wrap_name(display_name(entry))
            low = y - (len(lines) - 1) * 32
            occupied.append((entry['name'], x - 15, low - 6,
                             x + max(stringWidth(s, 'Helvetica-Bold', FONT) for s in lines) + 7,
                             y + 28))
            y = model(c, entry, x, y)
        branch(c, year, y + 57, baseline + 25)

    # Years are shown last with opaque light-blue tabs, keeping curve crossings
    # behind the labels and preventing a line from cutting through date text.
    for year in sorted(grouped):
        ax, ay = ANCHORS[year]
        c.setFillColor(YEAR)
        c.roundRect(ax - 42, ay - 16, 84, 37, 5, fill=1, stroke=0)
        text(c, ax, ay - 7, str(year), size=28, bold=True, align='center')

    text(c, 32, 112, '\u2020 Partial / component weights; base-model access may differ.', size=24, color=MUTED)
    text(c, 32, 76, 'Dates are paper dates, not checkpoint-release or venue-publication dates.', size=24, color=MUTED)
    text(c, 32, 40, 'Branches do not imply influence, replacement or performance. Yellow does not classify licenses.', size=24, color=MUTED)
    c.showPage()
    c.save()
    shutil.copyfile(destination, ROOT / 'figs_by_qixingyu/fig12.pdf')
    # Geometry checks catch accidental factual updates making label clusters
    # collide or extend out of frame. They complement actual PDF rendering.
    for name, x0, y0, x1, y1 in occupied:
        assert x0 >= 0 and x1 < W - 5 and y0 > 110 and y1 < 812, (name, x0, y0, x1, y1)
    for i, first in enumerate(occupied):
        for second in occupied[i+1:]:
            _, ax0, ay0, ax1, ay1 = first
            _, bx0, by0, bx1, by1 = second
            assert not (max(ax0, bx0) < min(ax1, bx1) and max(ay0, by0) < min(ay1, by1)), (first[0], second[0])
    print(f'{len(entries)} entries; {sum(bool(e.get("weights_url")) for e in entries)} public checkpoints; {destination}')


if __name__ == '__main__':
    build()
