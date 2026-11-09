#!/usr/bin/env python3
"""Reference-style curved chronology, exported as linked PDF and SVG.

Dates and checkpoint qualifications live in document_timeline_sources.json.
Official organization avatars are cached beside this script with source URLs.
Unbranded papers receive a small task glyph, never an invented company logo.
The curve expresses chronology, not ancestry, ranking, or replacement.
"""
from __future__ import annotations

import base64
import html
import json
import shutil
from collections import defaultdict
from pathlib import Path
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name('document_timeline_sources.json')
LOGOS = Path(__file__).with_name('timeline_logos')
# Keep the PDF's original 1100x480 box so existing manuscript placement is stable.
W, H, SCALE = 1650, 720, 2/3
FONT, LEADING = 31, 46
INK, MUTED, YELLOW, YEAR = '#18202C', '#6C7786', '#FFF0B8', '#DDECF6'
ANCHORS = {
    2015: (95,558), 2018: (230,552), 2019: (380,539),
    2020: (510,511), 2021: (620,477), 2022: (717,376),
    2023: (791,252), 2024: (1030,130), 2025: (1440,82),
}
# year, slice, x, top baseline, side; years with many papers use two branches.
CLUSTERS = [
    (2015,0,None,107,639,'top'),
    (2018,0,None,87,447,'bottom'),
    (2019,0,None,351,638,'top'),
    (2020,0,None,303,431,'bottom'),
    (2021,0,None,571,638,'top'),
    (2022,0,None,548,291,'bottom'),
    (2023,0,None,849,631,'top'),
    (2024,0,4,1270,631,'top'),
    (2024,4,None,930,359,'top'),
    (2025,0,None,1415,428,'top'),
]
BRANDS = {
    'LayoutLM':'microsoft','LayoutLMv2':'microsoft','LayoutXLM':'microsoft',
    'LayoutLMv3':'microsoft','UDOP':'microsoft','Table-GPT':'microsoft',
    'GraphRAG':'microsoft','TAPAS':'google','Pix2Struct':'google',
    'PP-OCR':'PaddlePaddle','Donut':'clovaai',
    'Qwen-VL':'QwenLM','Qwen2-VL':'QwenLM','Qwen2.5-VL':'QwenLM',
    'ColPali':'illuin-tech','DocLayout-YOLO':'opendatalab',
    'TableGPT2':'tablegpt','InternVL 2.5':'OpenGVLab',
    'olmOCR':'allenai','SmolDocling':'ds4sd','DeepSeek-OCR':'deepseek-ai',
}
SVG = []


def esc(v): return html.escape(str(v),quote=True)
def sy(y): return H-y

def text(c,x,y,value,size=FONT,bold=True,color=INK,align='left'):
    c.setFont('Times-Bold' if bold else 'Times-Roman',size)
    c.setFillColor(HexColor(color))
    getattr(c,{'left':'drawString','center':'drawCentredString','right':'drawRightString'}[align])(x,y,value)
    anchor={'left':'start','center':'middle','right':'end'}[align]
    SVG.append(f'<text x="{x}" y="{sy(y)}" font-family="Times New Roman,Times,serif" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="{anchor}" fill="{color}">{esc(value)}</text>')


def rect(c,x,y,w,h,color,r=0):
    c.setFillColor(HexColor(color))
    c.roundRect(x,y,w,h,r,stroke=0,fill=1)
    SVG.append(f'<rect x="{x}" y="{sy(y+h)}" width="{w}" height="{h}" rx="{r}" fill="{color}"/>')


def path(c,points,width=2,color=INK):
    c.setStrokeColor(HexColor(color));c.setLineWidth(width)
    p=c.beginPath(); d=[]
    for op,args in points:
        getattr(p,{'M':'moveTo','L':'lineTo','C':'curveTo'}[op])(*args)
        conv=[]
        for i,v in enumerate(args):conv.append(v if i%2==0 else sy(v))
        d.append(op+' '+' '.join(str(v) for v in conv))
    c.drawPath(p,stroke=1,fill=0)
    SVG.append(f'<path d="{" ".join(d)}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')


def glyph(c,track,x,y):
    """Small original task marks only for papers with no verified brand asset."""
    color={'perception':'#397CA0','structured':'#238A77','visual':'#A568B1'}[track]
    if track=='perception':
        # Recognition brackets around a serif A.
        path(c,[('M',(x-13,y+12)),('L',(x-17,y+12)),('L',(x-17,y-10)),('L',(x-13,y-10))],2,color)
        path(c,[('M',(x+13,y+12)),('L',(x+17,y+12)),('L',(x+17,y-10)),('L',(x+13,y-10))],2,color)
        text(c,x,y-7,'A',size=24,color=color,align='center')
    elif track=='structured':
        # Three connected nodes communicate a structured-document method.
        path(c,[('M',(x-11,y-6)),('L',(x,y+10)),('L',(x+11,y-6)),('L',(x-11,y-6))],2,color)
        for dx,dy in [(-11,-6),(0,10),(11,-6)]:rect(c,x+dx-3,y+dy-3,6,6,color,3)
    else:
        # An outlined document with two observation strokes.
        path(c,[('M',(x-10,y-13)),('L',(x-10,y+13)),('L',(x+6,y+13)),('L',(x+12,y+7)),('L',(x+12,y-13)),('L',(x-10,y-13))],2,color)
        path(c,[('M',(x-4,y+4)),('L',(x+5,y+4))],2,color)
        path(c,[('M',(x-4,y-3)),('L',(x+5,y-3))],2,color)


def logo(c,entry,x,y):
    brand=BRANDS.get(entry['name'])
    if not brand:
        glyph(c,entry['track'],x,y);return
    f=LOGOS/(brand+'.png')
    assert f.is_file(),f
    size=33
    c.drawImage(str(f),x-size/2,y-size/2,width=size,height=size,mask='auto',preserveAspectRatio=True)
    data=base64.b64encode(f.read_bytes()).decode()
    SVG.append(f'<image x="{x-size/2}" y="{sy(y+size/2)}" width="{size}" height="{size}" href="data:image/png;base64,{data}"/>')


def model(c,entry,x,y):
    value=entry['name']+('\u2020' if entry['name'] in {'UDOP','ColPali'} else '')
    width=stringWidth(value,'Times-Bold',FONT)
    assert width<295,(value,width)
    paper=entry.get('paper_url') or 'https://arxiv.org/abs/'+entry['arxiv']
    weights=entry.get('weights_url')
    if weights:
        SVG.append(f'<a href="{esc(weights)}"><title>Official trained weights: {esc(entry["name"])}</title>')
        rect(c,x-5,y-5,width+10,34,YELLOW,4)
        SVG.append('</a>')
        # Paper-name and weight highlight have separate active areas.
        c.linkURL(weights,(x-5,y-5,x+width+5,y+1),relative=0,thickness=0)
    logo(c,entry,x-30,y+11)
    SVG.append(f'<a href="{esc(paper)}"><title>{esc(entry["name"])} · {esc(entry["date"])}</title>')
    text(c,x,y,value)
    SVG.append('</a>')
    c.linkURL(paper,(x-4,y+2,x+width+5,y+29),relative=0,thickness=0)
    return (entry['name'],x-49,y-7,x+width+6,y+32)


def branch(c,year,x,first,last,side):
    # Explicit perimeter leaders avoid running lines through names or logos.
    routes = {
        (2015,107): [(95,558),(55,625),(55,650)],
        (2018,87): [(230,552),(250,458),(240,458)],
        (2019,351): [(380,539),(285,615),(285,649),(300,649)],
        (2020,303): [(510,511),(440,442),(428,442)],
        (2021,571): [(620,477),(505,570),(505,603),(521,603)],
        (2022,548): [(717,376),(660,302),(640,302)],
        (2023,849): [(791,252),(785,550),(797,550)],
        (2024,1270): [(1030,130),(1240,220),(1240,460),(1200,504),(1214,504)],
        (2024,930): [(1030,130),(868,230),(868,278),(877,278)],
        (2025,1415): [(1440,82),(1345,255),(1360,255)],
    }
    route=routes[(year,x)]
    path(c,[('M',route[0])]+[('L',point) for point in route[1:]],1.9)
    return route


def build():
    SVG.clear()
    metadata=json.loads(SOURCE.read_text())
    grouped=defaultdict(list)
    for entry in metadata['entries']:
        grouped[int(entry['date'][:4])].append(entry)
        assert entry.get('sources')
    for group in grouped.values():group.sort(key=lambda e:(e['date'],e['name']))
    assert len(metadata['entries'])==27 and set(grouped)==set(ANCHORS)
    out=ROOT/'doc/figs/fig12.pdf'
    c=canvas.Canvas(str(out),pagesize=(1100,480),pageCompression=1,invariant=1)
    c.setTitle('Document intelligence: a visual chronology, 2015-2025')
    c.setAuthor('Beyond OCR survey authors')
    c.setSubject('First-public-paper years; yellow highlights indicate official trained checkpoints')
    c.scale(SCALE,SCALE)
    c.setFillColor(white);c.rect(0,0,W,H,stroke=0,fill=1)
    SVG.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc"><title id="title">Document intelligence: a visual chronology, 2015-2025</title><desc id="desc">27 representative models and methods arranged on a curved timeline by first public paper year. Pale yellow highlights mark verified official trained weights; daggers mark partial or component releases. Logos identify project or organization and imply no endorsement. The curve shows chronology, not model ancestry.</desc><rect width="1650" height="720" fill="white"/>')

    # Minimal key; the paper caption supplies methodological qualifications.
    rect(c,1295,676,317,35,YELLOW,5)
    text(c,1453,684,'Publicly available weights',size=26,align='center')
    text(c,38,687,'FIRST PUBLIC PAPER  /  2015-2025',size=20,bold=False,color=MUTED)
    text(c,38,27,'\u2020 Partial / component weights',size=20,bold=False,color=MUTED)

    # Sweeping descent matches the requested branching timeline vocabulary.
    path(c,[('M',(37,560)),('C',(250,555,505,552,650,460)),('C',(790,370,760,204,930,155)),('C',(1110,100,1360,80,1610,80))],3.5)
    path(c,[('M',(1600,89)),('L',(1621,80)),('L',(1600,71))],3.5)

    occupied=[];seen=[];routes=[]
    for year,start,stop,x,first,side in CLUSTERS:
        group=grouped[year][start:stop]
        assert group
        last=first-(len(group)-1)*LEADING
        routes.append(branch(c,year,x,first,last,side))
        for i,entry in enumerate(group):
            occupied.append(model(c,entry,x,first-i*LEADING));seen.append(entry['name'])
    for year,(x,y) in ANCHORS.items():
        rect(c,x-35,y-16,70,36,YEAR,4)
        text(c,x,y-7,str(year),size=28,align='center')
    assert sorted(seen)==sorted(e['name'] for e in metadata['entries'])
    for name,x0,y0,x1,y1 in occupied:assert 6<x0<x1<W-7 and 50<y0<y1<680,(name,x0,y0,x1,y1)
    for i,a in enumerate(occupied):
        for b in occupied[i+1:]:
            assert not(max(a[1],b[1])<min(a[3],b[3]) and max(a[2],b[2])<min(a[4],b[4])),(a[0],b[0])
    # Every sampled leader segment must remain outside every text/logo box.
    for route in routes:
        for a,b in zip(route,route[1:]):
            steps=max(int(abs(a[0]-b[0])),int(abs(a[1]-b[1])),1)
            for i in range(steps+1):
                x=a[0]+(b[0]-a[0])*i/steps;y=a[1]+(b[1]-a[1])*i/steps
                for name,x0,y0,x1,y1 in occupied:
                    assert not (x0-1<x<x1+1 and y0-1<y<y1+1), ('Leader crosses label',name,x,y)
    c.showPage();c.save()
    shutil.copyfile(out,ROOT/'figs_by_qixingyu/fig12.pdf')
    SVG.append('</svg>')
    (ROOT/'docs/images/document-timeline.svg').write_text('\n'.join(SVG)+'\n')
    print(f'{len(seen)} entries; {sum(bool(e.get("weights_url")) for e in metadata["entries"])} official checkpoints; {out}')


if __name__=='__main__':build()
