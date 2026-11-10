#!/usr/bin/env python3
"""Draw a linked, four-branch chronology of document intelligence.

All dates, track assignments and checkpoint qualifications come from the
adjacent metadata file. Branches describe coexisting research directions, not
model ancestry. Year bands intentionally group early, sparse years. The PDF is
native 1100 x 720 pt: it must not be squeezed into the former 1100 x 480 box.
"""
from __future__ import annotations

import base64
import html
import json
import shutil
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name('document_timeline_sources.json')
LOGOS = Path(__file__).with_name('timeline_logos')
W, H = 1100, 720
FONT, MIN_FONT, LEADING, ICON = 17.5, 15.0, 24, 19
LABEL_WIDTH = 134
INK, MUTED, YELLOW, YEAR = '#202B35', '#65717B', '#FFF0B8', '#E2EDF5'
TRACKS = {
    'perception': {'label': 'OCR / layout perception', 'y': 535, 'color': '#437C9A'},
    'understanding': {'label': 'Document models / VQA', 'y': 375, 'color': '#96704D'},
    'structured': {'label': 'Tables / structured reasoning', 'y': 215, 'color': '#3E8270'},
    'retrieval': {'label': 'Document retrieval / agents', 'y': 55, 'color': '#826B9D'},
}
# label, inclusive first and last year, text x. Only the first two bands pool
# years; those entries also carry their first-public-paper year beside the name.
BANDS = [('2019–2021', 2019, 2021, 245), ('2022–2023', 2022, 2023, 415),
         ('2024', 2024, 2024, 585), ('2025', 2025, 2025, 755),
         ('2026', 2026, 2026, 925)]
ALIASES = {'mPLUG-DocOwl 1.5': 'DocOwl 1.5', 'mPLUG-DocOwl': 'DocOwl',
           'mPLUG-DocOwl2': 'DocOwl2', 'mPLUG-DocOwl 2': 'DocOwl2'}
SVG: list[str] = []


def esc(value):
    return html.escape(str(value), quote=True)


def sy(y):
    return H-y


def text(c, x, y, value, size=FONT, bold=True, color=INK, align='left'):
    c.setFont('Times-Bold' if bold else 'Times-Roman', size)
    c.setFillColor(HexColor(color))
    getattr(c, {'left': 'drawString', 'center': 'drawCentredString',
                'right': 'drawRightString'}[align])(x, y, value)
    anchor = {'left': 'start', 'center': 'middle', 'right': 'end'}[align]
    SVG.append(f'<text x="{x:g}" y="{sy(y):g}" font-family="Times New Roman,Times,serif" font-size="{size:g}" font-weight="{700 if bold else 400}" text-anchor="{anchor}" fill="{color}">{esc(value)}</text>')


def rect(c, x, y, width, height, color, radius=0):
    c.setFillColor(HexColor(color))
    c.roundRect(x, y, width, height, radius, stroke=0, fill=1)
    SVG.append(f'<rect x="{x:g}" y="{sy(y+height):g}" width="{width:g}" height="{height:g}" rx="{radius:g}" fill="{color}"/>')


def circle(c, x, y, r, color):
    c.setFillColor(HexColor(color))
    c.circle(x, y, r, stroke=0, fill=1)
    SVG.append(f'<circle cx="{x:g}" cy="{sy(y):g}" r="{r:g}" fill="{color}"/>')


def path(c, points, width=1.5, color=INK):
    c.setStrokeColor(HexColor(color)); c.setLineWidth(width)
    p = c.beginPath(); data = []
    for op, values in points:
        getattr(p, {'M': 'moveTo', 'L': 'lineTo', 'C': 'curveTo'}[op])(*values)
        converted = [v if i % 2 == 0 else sy(v) for i, v in enumerate(values)]
        data.append(op+' '+' '.join(f'{v:g}' for v in converted))
    c.drawPath(p, stroke=1, fill=0)
    SVG.append(f'<path d="{" ".join(data)}" fill="none" stroke="{color}" stroke-width="{width:g}" stroke-linecap="round" stroke-linejoin="round"/>')


def glyph(c, track, x, y, kind=None):
    """Small original task symbols where no verified organization asset exists."""
    color = TRACKS.get(track, TRACKS['perception'])['color']
    if kind == 'benchmark':
        # A neutral evaluation mark, not an invented model/organization logo.
        path(c,[('M',(x-8,y-8)),('L',(x-8,y+8)),('M',(x-8,y-8)),
                ('L',(x+8,y-8)),('M',(x-4,y-5)),('L',(x-4,y)),
                ('M',(x+1,y-5)),('L',(x+1,y+4)),
                ('M',(x+6,y-5)),('L',(x+6,y+8))],1.3,color)
    elif track == 'perception':
        for dx, dy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            path(c, [('M',(x+dx*5,y+dy*8)),('L',(x+dx*8,y+dy*8)),
                     ('L',(x+dx*8,y+dy*5))], 1.1, color)
        text(c,x,y-4,'A',size=12,color=color,align='center')
    elif track == 'structured':
        path(c,[('M',(x-8,y-7)),('L',(x-8,y+7)),('L',(x+8,y+7)),
                ('L',(x+8,y-7)),('L',(x-8,y-7)),('M',(x,y-7)),
                ('L',(x,y+7)),('M',(x-8,y)),('L',(x+8,y))],1.1,color)
    elif track == 'retrieval':
        path(c,[('M',(x-6,y+5)),('L',(x+5,y+5)),('M',(x-6,y)),
                ('L',(x+3,y)),('M',(x+3,y-4)),('L',(x+8,y-9))],1.1,color)
        circle(c,x-6,y+5,2,color); circle(c,x+5,y+5,2,color)
        circle(c,x-6,y,2,color); circle(c,x+3,y-4,2,color)
    else:
        path(c,[('M',(x-7,y-8)),('L',(x-7,y+8)),('L',(x+3,y+8)),
                ('L',(x+8,y+3)),('L',(x+8,y-8)),('L',(x-7,y-8)),
                ('M',(x-3,y+2)),('L',(x+3,y+2)),
                ('M',(x-3,y-3)),('L',(x+3,y-3))],1.1,color)


def asset_mapping():
    source = json.loads((LOGOS/'sources.json').read_text())
    assets = {a['id'].lower(): a for a in source['assets']}
    names = {name: a for a in source['assets'] for name in a.get('applies_to', [])}
    return assets, names


def entry_brand(entry, assets, names):
    if entry.get('kind') == 'benchmark':
        return None
    if entry['name'] in names:
        return names[entry['name']]
    # Exact official repository owners in verified entry metadata can reuse a
    # cached organization avatar. Do not infer affiliation from model prefixes.
    urls = list(entry.get('sources', []))
    urls += [entry.get(k, '') for k in ('project_url','repo_url','weights_url')]
    for address in urls:
        u = urlparse(address)
        if u.netloc.lower() == 'github.com':
            owner = u.path.strip('/').split('/')[0].lower()
            if owner in assets:
                return assets[owner]
    return None


def logo(c, entry, x, y, assets, names):
    asset = entry_brand(entry, assets, names)
    if not asset:
        glyph(c,entry['track'],x,y,entry.get('kind'))
        return None
    filename = LOGOS/asset['file']
    assert filename.is_file(), filename
    c.drawImage(str(filename),x-ICON/2,y-ICON/2,width=ICON,height=ICON,
                mask='auto',preserveAspectRatio=True)
    data = base64.b64encode(filename.read_bytes()).decode()
    SVG.append(f'<image x="{x-ICON/2:g}" y="{sy(y+ICON/2):g}" width="{ICON}" height="{ICON}" href="data:image/png;base64,{data}"/>')
    return asset['id']


def partial_weights(entry):
    # Preserve verified partial-release markers from the previous figure;
    # additional metadata can explicitly mark a component/adapter release.
    return (entry['name'] in {'UDOP','ColPali'} or entry.get('partial_weights')
            or entry.get('weights_scope') in {'partial','component','adapter'})


def model(c, entry, x, y, assets, names, show_year=False, max_width=LABEL_WIDTH):
    full_name = entry['name']
    value = entry.get('display_name') or ALIASES.get(full_name, full_name)
    if partial_weights(entry): value += '†'
    year = entry['date'][:4] if show_year else ''
    date_width = stringWidth(year,'Times-Roman',9.5)+4 if year else 0
    size = FONT
    while stringWidth(value,'Times-Bold',size)+date_width > max_width and size > MIN_FONT:
        size -= .25
    width = stringWidth(value,'Times-Bold',size)
    assert width+date_width <= max_width, (full_name, width+date_width, max_width)
    paper = entry.get('paper_url') or 'https://arxiv.org/abs/'+entry['arxiv']
    weights = entry.get('weights_url')
    if weights:
        SVG.append(f'<a href="{esc(weights)}"><title>Official trained weights: {esc(full_name)}</title>')
        rect(c,x-3,y-3,width+6,18.5,YELLOW,2.5)
        SVG.append('</a>')
        c.linkURL(weights,(x-3,y-3,x+width+3,y+.5),relative=0,thickness=0)
    brand = logo(c,entry,x-16,y+6,assets,names)
    SVG.append(f'<a href="{esc(paper)}"><title>{esc(full_name)} · {esc(entry["date"])}</title>')
    text(c,x,y,value,size=size)
    SVG.append('</a>')
    c.linkURL(paper,(x-2,y+1,x+width+2,y+15),relative=0,thickness=0)
    if year:
        text(c,x+width+4,y+1,year,size=9.5,bold=False,color=MUTED)
    return {'name':full_name,'date':entry['date'],'track':entry['track'],
            'bbox':[x-27,y-4,x+width+date_width+3,y+16],
            'font_size':size,'logo':brand,'weights':bool(weights)}


def normalize_track(entry):
    # Backward compatibility lets the generator preview the old metadata while
    # the expanded, four-track source is being verified.
    result = dict(entry)
    if result['track'] == 'visual':
        result['track'] = 'retrieval' if result['name'] == 'ColPali' else 'understanding'
    assert result['track'] in TRACKS, result
    return result


def build():
    SVG.clear()
    metadata = json.loads(SOURCE.read_text())
    entries = [normalize_track(e) for e in metadata['entries']]
    assert entries and len({e['name'] for e in entries}) == len(entries)
    for entry in entries:
        assert entry.get('sources') and 2000 <= int(entry['date'][:4]) <= 2026, entry
    early = sorted([e for e in entries if int(e['date'][:4]) <= 2018],key=lambda e:(e['date'],e['name']))
    later = [e for e in entries if e not in early]
    assert len(early) <= 5, ('Early stem capacity exceeded', len(early))
    grouped = defaultdict(list)
    for entry in later:
        year = int(entry['date'][:4])
        band = next(i for i,(_,low,high,_) in enumerate(BANDS) if low<=year<=high)
        grouped[(entry['track'],band)].append(entry)
    for group in grouped.values(): group.sort(key=lambda e:(e['date'],e['name']))
    assets, names = asset_mapping()
    out = ROOT/'doc/figs/fig12.pdf'
    c = canvas.Canvas(str(out),pagesize=(W,H),pageCompression=1,invariant=1)
    c.setTitle('Document intelligence: four coexisting research directions, 2007–2026')
    c.setAuthor('Beyond OCR survey authors')
    c.setSubject('First-public-paper chronology; yellow highlights indicate verified official trained checkpoints')
    c.setFillColor(white); c.rect(0,0,W,H,stroke=0,fill=1)
    SVG.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc"><title id="title">Document intelligence: four coexisting research directions, 2007–2026</title><desc id="desc">{len(entries)} representative models and methods on branching OCR/layout, document understanding, structured reasoning and document retrieval streams. Dates are first public paper years. Pale yellow highlights mark verified official weights. Branches organize research directions and do not imply model ancestry.</desc><rect width="{W}" height="{H}" fill="white"/>')

    rect(c,25,695,161,21,YELLOW,3)
    text(c,105.5,701,'Publicly available weights',size=12.5,align='center')
    for label,low,high,x in BANDS:
        width = 102 if low!=high else 61
        center = x+55
        rect(c,center-width/2,695,width,21,YEAR,3)
        text(c,center,700.5,label,size=14.5,align='center')

    # A short early OCR stem fans into four genuinely separate research paths.
    root=(175,350)
    path(c,[('M',(18,449)),('L',(18,311)),
            ('C',(18,285,142,285,*root))],1.7,'#80909C')
    text(c,28,486,'EARLY OCR',size=13,bold=False,color=MUTED)
    rect(c,28,457,99,20,YEAR,3)
    text(c,77.5,462,'2007–2018',size=13.5,align='center')
    occupied=[]; leaders=[]
    first_early = 430
    for i,entry in enumerate(early):
        occupied.append(model(c,entry,53,first_early-i*24,assets,names,True,max_width=108))
    circle(c,*root,3.0,'#627686')
    for index,(track,spec) in enumerate(TRACKS.items(),1):
        y=spec['y']; color=spec['color']
        path(c,[('M',root),('C',(202,350,190,y,213,y)),
                ('C',(440,y-2,825,y+2,1074,y))],1.8,color)
        path(c,[('M',(1068,y+4)),('L',(1076,y)),('L',(1068,y-4))],1.5,color)
        text(c,217,y+137,spec['label'],size=19.5,color=color)
        for band_index,(label,low,high,x) in enumerate(BANDS):
            group=grouped.get((track,band_index),[])
            assert len(group)<=5,('Band capacity exceeded',track,label,len(group))
            if not group: continue
            first=y+113
            last=first-(len(group)-1)*LEADING
            stemx=x-32
            # Stems occupy the gutter left of every model/organization mark.
            leader=[('M',(stemx,y)),('L',(stemx,last+6)),
                    ('L',(stemx+4,last+6))]
            path(c,leader,.85,color)
            leaders.append({'track':track,'band':label,'points':[(stemx,y),(stemx,last+6),(stemx+4,last+6)]})
            circle(c,stemx,y,2.5,color)
            for j,entry in enumerate(group):
                occupied.append(model(c,entry,x,first-j*LEADING,assets,names,low!=high))
    text(c,217,20,'Coexisting research directions; branches do not imply ancestry.',size=11,bold=False,color=MUTED)
    text(c,1078,20,'† Component / adapter weights · Years grouped, not linearly spaced',size=10,bold=False,color=MUTED,align='right')
    assert {e['name'] for e in occupied} == {e['name'] for e in entries}
    for e in occupied:
        x0,y0,x1,y1=e['bbox']
        assert 3<x0<x1<W-5 and 35<y0<y1<692,e
    for i,a in enumerate(occupied):
        for b in occupied[i+1:]:
            ax0,ay0,ax1,ay1=a['bbox'];bx0,by0,bx1,by1=b['bbox']
            assert not(max(ax0,bx0)<min(ax1,bx1) and max(ay0,by0)<min(ay1,by1)),(a['name'],b['name'])
    for leader in leaders:
        for a,b in zip(leader['points'],leader['points'][1:]):
            steps=max(int(abs(a[0]-b[0])),int(abs(a[1]-b[1])),1)
            for i in range(steps+1):
                px=a[0]+(b[0]-a[0])*i/steps;py=a[1]+(b[1]-a[1])*i/steps
                for e in occupied:
                    x0,y0,x1,y1=e['bbox']
                    assert not (x0-1<px<x1+1 and y0-1<py<y1+1),('Leader crosses label',e['name'],px,py)
    c.showPage(); c.save()
    shutil.copyfile(out,ROOT/'figs_by_qixingyu/fig12.pdf')
    SVG.append('</svg>')
    (ROOT/'docs/images/document-timeline.svg').write_text('\n'.join(SVG)+'\n')
    qa=ROOT/'.build/timeline'; qa.mkdir(parents=True,exist_ok=True)
    (qa/'geometry.json').write_text(json.dumps({'page':[W,H],'base_font':FONT,'icon':ICON,'nodes':occupied,'leaders':leaders},indent=2)+'\n')
    try:
        import pypdfium2 as pdfium
        document=pdfium.PdfDocument(str(out))
        rendered=document[0].render(scale=2).to_pil()
        rendered.save(ROOT/'docs/images/document-timeline.png')
        rendered.save(qa/'figure.png')
    except ImportError:
        pass
    print(f'{len(entries)} entries; {sum(bool(e.get("weights_url")) for e in entries)} official checkpoints; native {W}x{H}; {out}')


if __name__=='__main__':
    build()
