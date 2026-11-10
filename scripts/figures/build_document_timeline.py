#!/usr/bin/env python3
"""Draw a linked, four-branch chronology of document intelligence.

All dates, track assignments and checkpoint qualifications come from the
adjacent metadata file. Branches describe coexisting research directions, not
model ancestry. Year bands intentionally group early, sparse years. The PDF is
native 1100 x 780 pt: it must not be squeezed into the former 1100 x 480 box.
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
W, H = 1100, 780
FONT, MIN_FONT, LEADING, ICON = 17.5, 15.0, 24, 19
LABEL_WIDTH = 134
INK, MUTED, YELLOW, YEAR = '#202B35', '#65717B', '#FFF0B8', '#E2EDF5'
TRACKS = {
    'perception': {'label': 'OCR / layout perception', 'color': '#437C9A'},
    'understanding': {'label': 'Document models / VQA', 'color': '#96704D'},
    'structured': {'label': 'Tables / structured reasoning', 'color': '#3E8270'},
    'retrieval': {'label': 'Document retrieval / agents', 'color': '#826B9D'},
}
# Logical date buckets only: each track has separately curated positions.
# Pooled clusters also show each entry's actual first-public-paper year.
BANDS = [('2019–2021', 2019, 2021), ('2022–2023', 2022, 2023),
         ('2024', 2024, 2024), ('2025', 2025, 2025), ('2026', 2026, 2026)]
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



def italic_text(c,x,y,value,color):
    c.setFont('Times-Italic',13.5);c.setFillColor(HexColor(color))
    c.drawString(x,y,value)
    SVG.append(f'<text x="{x}" y="{sy(y)}" font-family="Times New Roman,Times,serif" font-size="13.5" font-style="italic" fill="{color}">{esc(value)}</text>')


def union_box(nodes):
    return [min(n['bbox'][0] for n in nodes),min(n['bbox'][1] for n in nodes),
            max(n['bbox'][2] for n in nodes),max(n['bbox'][3] for n in nodes)]


def segment_clear(a,b,boxes):
    steps=max(int(abs(a[0]-b[0])),int(abs(a[1]-b[1])),1)
    for i in range(steps+1):
        x=a[0]+(b[0]-a[0])*i/steps;y=a[1]+(b[1]-a[1])*i/steps
        for x0,y0,x1,y1 in boxes:
            if x0-.6<x<x1+.6 and y0-.6<y<y1+.6:return False
    return True


def link_cluster(c,pill,bounds,boxes,color):
    px,py,pw=pill;x0,y0,x1,y1=bounds
    # Connect nearest perimeter points; never drop a repeated full-height stem.
    target=(min(max(px,x0),x1),min(max(py,y0),y1))
    if py<y0:target=(target[0],y0-2);start=(px,py+10)
    elif py>y1:target=(target[0],y1+2);start=(px,py-10)
    elif px<x0:target=(x0-2,target[1]);start=(px+pw/2,py)
    else:target=(x1+2,target[1]);start=(px-pw/2,py)
    candidates=[[start,target],[start,(start[0],target[1]),target],
                [start,(target[0],start[1]),target]]
    for delta in (-25,25,-50,50):
        candidates += [[start,(start[0]+delta,start[1]),(start[0]+delta,target[1]),target],
                       [start,(start[0],start[1]+delta),(target[0],start[1]+delta),target]]
    for points in candidates:
        if all(segment_clear(a,b,boxes) for a,b in zip(points,points[1:])):
            path(c,[('M',points[0])]+[('L',v) for v in points[1:]],.8,color)
            return points
    # Preview should remain inspectable while routing is polished; diagnostics
    # name any residual leader collision in the geometry audit.
    path(c,[('M',start),('L',target)],.8,color)
    return [start,target]



def sample_curve(points):
    sampled=[];current=None
    for op,args in points:
        if op=='M':current=args;sampled.append(current)
        elif op=='L':
            target=args
            for i in range(1,101):
                t=i/100;sampled.append((current[0]+(target[0]-current[0])*t,current[1]+(target[1]-current[1])*t))
            current=target
        else:
            a=current;b=args[:2];d=args[2:4];e=args[4:6]
            for i in range(1,301):
                t=i/300;u=1-t
                sampled.append((u**3*a[0]+3*u*u*t*b[0]+3*u*t*t*d[0]+t**3*e[0],u**3*a[1]+3*u*u*t*b[1]+3*u*t*t*d[1]+t**3*e[1]))
            current=e
    return sampled


def build():
    SVG.clear()
    metadata=json.loads(SOURCE.read_text())
    entries=[normalize_track(e) for e in metadata['entries']]
    assert entries and len({e['name'] for e in entries})==len(entries)
    early=sorted([e for e in entries if int(e['date'][:4])<=2018],key=lambda e:(e['date'],e['name']))
    later=[e for e in entries if e not in early]
    grouped=defaultdict(list)
    for entry in later:
        year=int(entry['date'][:4]);band=next(i for i,(_,lo,hi) in enumerate(BANDS) if lo<=year<=hi)
        grouped[(entry['track'],band)].append(entry)
    for group in grouped.values():group.sort(key=lambda e:(e['date'],e['name']))
    assets,names=asset_mapping()
    out=ROOT/'doc/figs/fig12.pdf'
    c=canvas.Canvas(str(out),pagesize=(W,H),pageCompression=1,invariant=1)
    c.setTitle('Document intelligence: a branching chronology, 2007–2026')
    c.setAuthor('Beyond OCR survey authors')
    c.setSubject('First-public-paper chronology; coexisting research directions, not model ancestry')
    c.setFillColor(white);c.rect(0,0,W,H,stroke=0,fill=1)
    SVG.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc"><title id="title">Document intelligence: a branching chronology, 2007–2026</title><desc id="desc">{len(entries)} representative models and methods, arranged around a descending S-shaped OCR/layout spine and three winding branches for document understanding, structured reasoning and retrieval. Yellow highlights indicate verified official weights. Branches organize coexisting research directions, not model ancestry.</desc><rect width="{W}" height="{H}" fill="white"/>')
    # Curated, deliberately asymmetric cluster positions. Values are name x,
    # first baseline, and a nearby year pill on the curve or its short leader.
    layout={
      ('perception',0):(45,570,(215,623)),
      ('perception',1):(235,745,(457,428)),
      ('perception',2):(535,410,(565,340)),
      ('perception',3):(710,475,(800,308)),
      ('perception',4):(930,300,(1010,352)),
      ('understanding',0):(188,580,(320,624)),
      ('understanding',1):(450,716,(535,600)),
      ('understanding',2):(660,748,(740,650)),
      ('understanding',3):(880,728,(895,689)),
      ('understanding',4):(940,590,(1040,630)),
      ('structured',0):(245,430,(410,460)),
      ('structured',1):(430,330,(510,250)),
      ('structured',2):(650,210,(710,242)),
      ('structured',3):(775,270,(820,244)),
      ('structured',4):(900,205,(960,234)),
      ('retrieval',0):(255,310,(360,340)),
      ('retrieval',2):(430,205,(480,50)),
      ('retrieval',3):(720,100,(780,37)),
      ('retrieval',4):(935,160,(1000,37)),
    }
    main=[('M',(22,622)),('C',(140,626,220,626,285,610)),
          ('C',(306,605,322,600,335,590)),('C',(370,570,392,545,410,520)),
          ('C',(455,455,450,380,565,340)),('C',(740,258,850,320,1070,365))]
    understanding=[('M',(285,610)),('C',(350,650,450,575,535,600)),
                   ('C',(620,615,680,625,740,650)),('C',(810,680,865,705,930,675)),
                   ('C',(1000,650,1040,635,1080,610))]
    structured=[('M',(410,520)),('C',(395,455,370,410,370,350)),
                ('C',(370,275,430,225,510,250)),
                ('C',(590,215,710,255,800,245)),('C',(870,240,950,250,1020,235))]
    retrieval=[('M',(335,590)),('C',(305,490,375,350,375,250)),
               ('C',(372,150,375,65,430,65)),('C',(500,35,610,40,700,38)),
               ('C',(820,22,950,50,1070,30))]
    curves={'perception':main,'understanding':understanding,'structured':structured,'retrieval':retrieval}
    for track,points in curves.items():path(c,points,1.9,TRACKS[track]['color'])
    # Different branch birth points and endings keep the silhouette a tree,
    # rather than four rails hidden behind cosmetic curves.
    for track,x,y in [('understanding',285,610),('structured',410,520),('retrieval',335,590)]:
        circle(c,x,y,2.5,TRACKS[track]['color'])
    for track,x,y,dx,dy in [('perception',1070,365,7,3),('understanding',1080,610,7,-4),
                           ('structured',1020,235,7,-1),('retrieval',1070,30,7,-1)]:
        path(c,[('M',(x-dx,y+dy+3)),('L',(x+1,y)),('L',(x-dx,y+dy-3))],1.4,TRACKS[track]['color'])
    occupied=[];groups=[]
    for i,entry in enumerate(early):occupied.append(model(c,entry,45,744-i*24,assets,names,True,max_width=108))
    groups.append({'track':'perception','label':'2007–2018','pill':(80,623),'nodes':occupied[:len(early)]})
    for key,group in grouped.items():
        assert key in layout,('No curated placement',key)
        x,first,pill=layout[key];nodegroup=[]
        for i,entry in enumerate(group):
            item=model(c,entry,x,first-i*LEADING,assets,names,BANDS[key[1]][1]!=BANDS[key[1]][2])
            occupied.append(item);nodegroup.append(item)
        years=sorted({e['date'][:4] for e in group})
        label=years[0] if len(years)==1 else years[0]+'–'+years[-1]
        groups.append({'track':key[0],'label':label,'pill':pill,'nodes':nodegroup})
    rect(c,810,755,258,19,YELLOW,3)
    text(c,939,760,'Publicly available weights',size=12.5,align='center')
    italic_text(c,450,505,'OCR / layout',TRACKS['perception']['color'])
    italic_text(c,620,610,'Document understanding / VQA',TRACKS['understanding']['color'])
    italic_text(c,560,255,'Tables / structured reasoning',TRACKS['structured']['color'])
    italic_text(c,625,75,'Retrieval / agents',TRACKS['retrieval']['color'])
    boxes=[n['bbox'] for n in occupied]
    leaders=[];pillboxes=[]
    for group in groups:
        label=group['label'];px,py=group['pill']
        pw=stringWidth(label,'Times-Bold',13)+14
        rect(c,px-pw/2,py-9,pw,20,YEAR,3)
        text(c,px,py-3,label,size=13,align='center')
        if group['track']=='perception' and label=='2019–2021':
            points=[(px-pw/2,py),(155,py-13),(155,564)]
            path(c,[('M',points[0])]+[('L',point) for point in points[1:]],.8,TRACKS[group['track']]['color'])
        else:
            points=link_cluster(c,(px,py,pw),union_box(group['nodes']),boxes,TRACKS[group['track']]['color'])
        leaders.append({'track':group['track'],'label':label,'points':points})
        pillboxes.append({'label':label,'bbox':[px-pw/2,py-9,px+pw/2,py+11]})
    text(c,30,17,'Coexisting research directions; branches do not imply ancestry.',size=10.5,bold=False,color=MUTED)
    text(c,1070,17,'† Component / adapter weights · First-public-paper years',size=10.5,bold=False,color=MUTED,align='right')
    issues=[]
    assert {e['name'] for e in occupied}=={e['name'] for e in entries}
    for e in occupied:
        x0,y0,x1,y1=e['bbox']
        if not(3<x0<x1<W-5 and 35<y0<y1<H-4):issues.append(['bounds',e['name'],e['bbox']])
    for i,a in enumerate(occupied):
        for b in occupied[i+1:]:
            ax0,ay0,ax1,ay1=a['bbox'];bx0,by0,bx1,by1=b['bbox']
            if max(ax0,bx0)<min(ax1,bx1) and max(ay0,by0)<min(ay1,by1):issues.append(['label overlap',a['name'],b['name']])
    for pill in pillboxes:
        x0,y0,x1,y1=pill['bbox']
        for e in occupied:
            bx0,by0,bx1,by1=e['bbox']
            if max(x0,bx0)<min(x1,bx1) and max(y0,by0)<min(y1,by1):issues.append(['pill overlap',pill['label'],e['name']])
    for i,a in enumerate(pillboxes):
        ax0,ay0,ax1,ay1=a['bbox']
        for b in pillboxes[i+1:]:
            bx0,by0,bx1,by1=b['bbox']
            if max(ax0,bx0)<min(ax1,bx1) and max(ay0,by0)<min(ay1,by1):issues.append(['pill pair',a['label'],b['label']])
    for track,curve in curves.items():
        points=sample_curve(curve)
        for e in occupied:
            x0,y0,x1,y1=e['bbox']
            if any(x0-.5<x<x1+.5 and y0-.5<y<y1+.5 for x,y in points):issues.append(['curve collision',track,e['name']])
    for leader in leaders:
        if not all(segment_clear(a,b,boxes) for a,b in zip(leader['points'],leader['points'][1:])):
            issues.append(['leader collision',leader['track'],leader['label']])
    assert not issues, issues
    c.showPage();c.save();shutil.copyfile(out,ROOT/'figs_by_qixingyu/fig12.pdf')
    SVG.append('</svg>');(ROOT/'docs/images/document-timeline.svg').write_text('\n'.join(SVG)+'\n')
    qa=ROOT/'.build/timeline';qa.mkdir(parents=True,exist_ok=True)
    (qa/'geometry.json').write_text(json.dumps({'page':[W,H],'base_font':FONT,'icon':ICON,'nodes':occupied,'leaders':leaders,'pills':pillboxes,'curves':curves,'issues':issues},indent=2)+'\n')
    import pypdfium2 as pdfium
    document=pdfium.PdfDocument(str(out));rendered=document[0].render(scale=2).to_pil()
    rendered.save(ROOT/'docs/images/document-timeline.png');rendered.save(qa/'figure.png')
    print(f'{len(entries)} entries; native {W}x{H}; issues: {json.dumps(issues)}; {out}')


if __name__=='__main__':build()
