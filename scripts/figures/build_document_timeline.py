#!/usr/bin/env python3
"""Render a sparse overview and a complete two-page linked chronology.

The adjacent 62-entry metadata is the only source of dates, research direction
assignments, paper links and weight availability. A fixed editorial selection
provides the 32-entry paper overview. Two 31-entry companion pages retain the
complete source coverage, with no duplicate or omitted records. Every page has
one black descending S-curve, sparse category dots and verified organization
marks; placeholder task icons are never drawn. Native page size: 1100 x 500 pt.
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
W, H = 1100, 500
FONT, MIN_FONT, LEADING, ICON = 17.5, 15.0, 24, 19
LABEL_WIDTH = 134
INK, MUTED, YELLOW, YEAR = '#202B35', '#65717B', '#FFF0B8', '#E2EDF5'
TRACKS = {
    'perception': {'label': 'OCR / layout perception', 'color': '#437C9A'},
    'understanding': {'label': 'Document models / VQA', 'color': '#96704D'},
    'structured': {'label': 'Tables / structured reasoning', 'color': '#3E8270'},
    'retrieval': {'label': 'Document retrieval / agents', 'color': '#826B9D'},
}
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


def model(c, entry, x, y, assets, names, show_year=False, max_width=LABEL_WIDTH, clean=False, seen_brands=None, seen_tracks=None):
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
    if clean:
        asset=entry_brand(entry,assets,names)
        if asset and asset['id'] not in seen_brands:
            brand=logo(c,entry,x-16,y+6,assets,names);seen_brands.add(asset['id'])
        else:brand=None
        if entry['track'] not in seen_tracks:
            circle(c,x-29,y+6,1.7,TRACKS[entry['track']]['color']);seen_tracks.add(entry['track'])
    else:brand=logo(c,entry,x-16,y+6,assets,names)
    SVG.append(f'<a href="{esc(paper)}"><title>{esc(full_name)} · {esc(entry["date"])}</title>')
    text(c,x,y,value,size=size)
    SVG.append('</a>')
    c.linkURL(paper,(x-2,y+1,x+width+2,y+15),relative=0,thickness=0)
    if year:
        text(c,x+width+4,y+1,year,size=9.5,bold=False,color=MUTED)
    return {'name':full_name,'date':entry['date'],'track':entry['track'],
            'bbox':[x-32 if clean else x-27,y-4,x+width+date_width+3,y+16],
            'font_size':size,'logo':brand,'weights':bool(weights)}


def normalize_track(entry):
    # Backward compatibility lets the generator preview the old metadata while
    # the expanded, four-track source is being verified.
    result = dict(entry)
    if result['track'] == 'visual':
        result['track'] = 'retrieval' if result['name'] == 'ColPali' else 'understanding'
    assert result['track'] in TRACKS, result
    return result



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


MAIN_NAMES = 'Tesseract|CRNN|DBNet|LayoutLM|TAPAS|RAG|DocVQA|Donut|LayoutLMv3|Pix2Struct|Hi-VT5 / MP-DocVQA|Qwen-VL|Chain-of-Table|GraphRAG|ColPali|Qwen2-VL|VisRAG|DocLayout-YOLO|TableGPT2|M3DocRAG|ViDoRAG|olmOCR|TableRAG|DeepSeek-OCR|Qwen3-VL|DeepSeek-OCR 2|PaddleOCR-VL-1.5|AutoThinkRAG|Qianfan-OCR|PreciseDoc|DocPilot|Unlimited OCR 2'.split('|')


def paper_key(e):return (e['date'],e['name'])


def legend(c):
    x=28
    for track,label in [('perception','OCR / layout'),('understanding','Document / VQA'),('structured','Tables'),('retrieval','Retrieval / agents')]:
        circle(c,x,16,1.9,TRACKS[track]['color']);text(c,x+7,12.5,label,size=10.5,bold=False,color=MUTED)
        x+=stringWidth(label,'Times-Roman',10.5)+28
    text(c,1075,12.5,'† Partial / component weights',size=10.5,bold=False,color=MUTED,align='right')


def draw_clean(c,entries,groups,curve,stations,title=None,description=None):
    assets,names=asset_mapping();occupied=[];nodegroups=[]
    c.setFillColor(white);c.rect(0,0,W,H,stroke=0,fill=1)
    SVG.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    if title:
        text(c,28,477,title,size=20)
        text(c,28,459,description or '',size=10.5,bold=False,color=MUTED)
    else:
        rect(c,835,474,238,20,YELLOW,3);text(c,954,480,'Publicly available weights',size=12.5,align='center')
    path(c,curve,2.1,'#17212B');endpoint=curve[-1][1][-2:]
    path(c,[('M',(endpoint[0]-8,endpoint[1]+4)),('L',(endpoint[0]+2,endpoint[1])),('L',(endpoint[0]-8,endpoint[1]-4))],1.8,'#17212B')
    for group in groups:
        selected=group['entries'];x,y=group['position'];seen_brands=set();seen_tracks=set();members=[]
        for i,e in enumerate(selected):
            item=model(c,e,x,y-i*LEADING,assets,names,group.get('show_year',False),clean=True,seen_brands=seen_brands,seen_tracks=seen_tracks)
            occupied.append(item);members.append(item)
        nodegroups.append((group,members))
    boxes=[n['bbox'] for n in occupied];pills=[];leaders=[]
    for key,(x,y,label) in stations.items():
        pw=stringWidth(label,'Times-Bold',13)+14;rect(c,x-pw/2,y-9,pw,20,YEAR,3);text(c,x,y-3,label,size=13,align='center')
        pills.append({'label':label,'bbox':[x-pw/2,y-9,x+pw/2,y+11]})
    for group,nodes in nodegroups:
        x,y,label=stations[group['station']];pw=stringWidth(label,'Times-Bold',13)+14
        points=link_cluster(c,(x,y,pw),union_box(nodes),boxes,'#69757F')
        leaders.append({'station':label,'points':points,'names':[e['name'] for e in nodes]})
    legend(c);issues=[]
    assert len(occupied)==len(entries) and {n['name'] for n in occupied}=={e['name'] for e in entries}
    for n in occupied:
        x0,y0,x1,y1=n['bbox']
        if not(3<x0<x1<W-4 and 30<y0<y1<H-2):issues.append(['bounds',n['name']])
    for i,a in enumerate(occupied):
        ax0,ay0,ax1,ay1=a['bbox']
        for b in occupied[i+1:]:
            bx0,by0,bx1,by1=b['bbox']
            if max(ax0,bx0)<min(ax1,bx1) and max(ay0,by0)<min(ay1,by1):issues.append(['node pair',a['name'],b['name']])
    for i,a in enumerate(pills):
        ax0,ay0,ax1,ay1=a['bbox']
        for b in pills[i+1:]:
            bx0,by0,bx1,by1=b['bbox']
            if max(ax0,bx0)<min(ax1,bx1) and max(ay0,by0)<min(ay1,by1):issues.append(['pill pair',a['label'],b['label']])
        for n in occupied:
            bx0,by0,bx1,by1=n['bbox']
            if max(ax0,bx0)<min(ax1,bx1) and max(ay0,by0)<min(ay1,by1):issues.append(['pill node',a['label'],n['name']])
    points=sample_curve(curve)
    for n in occupied:
        x0,y0,x1,y1=n['bbox']
        if any(x0-.5<x<x1+.5 and y0-.5<y<y1+.5 for x,y in points):issues.append(['curve node',n['name']])
    for leader in leaders:
        if not all(segment_clear(a,b,boxes) for a,b in zip(leader['points'],leader['points'][1:])):issues.append(['leader',leader['names']])
    for _,members in nodegroups:
        brands=[n['logo'] for n in members if n['logo']]
        assert len(brands)==len(set(brands)),brands
    max_leader=max(sum(((b[0]-a[0])**2+(b[1]-a[1])**2)**.5 for a,b in zip(leader['points'],leader['points'][1:])) for leader in leaders)
    assert max_leader<=60,(max_leader,title)
    assert not issues,issues
    return {'page':[W,H],'nodes':occupied,'curve':curve,'pills':pills,'leaders':leaders,'max_leader_length':max_leader,'base_font':FONT,'icon_size':ICON,'issues':issues}


def main_groups(entries):
    periods=[(2007,2019),(2020,2021),(2022,2023),(2024,2024),(2025,2025),(2026,2026)]
    chunks=[(4,),(4,),(4,),(4,4),(3,2),(4,3)]
    positions=[[(40,480)],[(150,305)],[(330,425)],[(510,310),(555,125)],[(710,260),(750,95)],[(900,295),(930,115)]]
    stations={0:(120,360,'2007–2019'),1:(260,345,'2020–2021'),2:(415,280,'2022–2023'),3:(590,175,'2024'),4:(800,140,'2025'),5:(1010,160,'2026')}
    groups=[]
    for k,((lo,hi),sizes,places) in enumerate(zip(periods,chunks,positions)):
        selected=sorted([e for e in entries if lo<=int(e['date'][:4])<=hi],key=paper_key)
        assert len(selected)==sum(sizes),(k,len(selected),sizes);offset=0
        for size,place in zip(sizes,places):
            groups.append({'entries':selected[offset:offset+size],'position':place,'station':k,'show_year':lo!=hi});offset+=size
    curve=[('M',(25,360)),('C',(130,362,210,357,260,345)),('C',(330,330,370,315,415,280)),('C',(480,230,510,185,590,175)),('C',(670,147,725,137,800,140)),('C',(900,141,970,150,1010,160)),('C',(1040,166,1055,167,1075,165))]
    return groups,curve,stations



def build_atlas(all_entries):
    foundation=[e for e in all_entries if e['track']=='perception' or (e['track']=='understanding' and int(e['date'][:4])<=2023)]
    systems=[e for e in all_entries if e not in foundation]
    assert len(foundation)==len(systems)==31
    ordered=sorted(systems,key=paper_key)
    first=[]
    for lo,hi in [(2007,2018),(2019,2020),(2021,2021),(2022,2022),(2023,2023),(2024,2024),(2025,2025),(2026,2026)]:
        first.append(sorted([e for e in foundation if lo<=int(e['date'][:4])<=hi],key=paper_key))
    second=[ordered[i:i+4] for i in range(0,len(ordered),4)]
    assert [len(es) for es in first]==[5,5,3,5,4,1,5,3]
    assert len(second)==8 and all(1<=len(es)<=4 for es in second)
    atlas=ROOT/'docs/chronology-atlas.pdf';c=canvas.Canvas(str(atlas),pagesize=(W,H),pageCompression=1,invariant=1)
    c.setTitle('Complete document-intelligence chronology: 62 entries, 2007–2026');c.setAuthor('Beyond OCR survey authors')
    centers=[(90,310),(250,305),(390,280),(510,230),(650,180),(785,160),(940,165),(1040,170)]
    xs=[40,170,325,440,575,710,845,945]
    curve=[('M',(25,310)),('C',(130,312,210,317,250,305)),('C',(320,300,365,295,390,280)),('C',(455,260,480,242,510,230)),('C',(570,205,610,188,650,180)),('C',(700,160,750,160,785,160)),('C',(850,160,900,162,940,165)),('C',(980,170,1015,172,1040,170)),('C',(1060,170,1075,173,1080,172))]
    reports=[]
    for index,(sets,title) in enumerate([(first,'A. Perception and document-model foundations'),(second,'B. Reasoning and document-evidence access')],1):
        groups=[];stations={}
        for i,es in enumerate(sets):
            years=sorted({e['date'][:4] for e in es});label=years[0] if len(years)==1 else years[0]+'–'+years[-1]
            cx,cy=centers[i]
            first_baseline=cy+26+(15 if i else 0)+(len(es)-1)*LEADING if i%2==0 else cy-40
            groups.append({'entries':es,'position':(xs[i],first_baseline),'station':i,'show_year':len(years)>1})
            stations[i]=(cx,cy,label)
        entries=[e for es in sets for e in es]
        qa=draw_clean(c,entries,groups,curve,stations,title,'Complete companion chronology · 31 entries · Yellow: verified official weights · Names link to original sources')
        qa['title']=title;qa['entry_count']=len(entries);reports.append(qa);c.showPage()
    c.save()
    union=[n['name'] for page in reports for n in page['nodes']]
    assert len(union)==len(set(union))==62 and set(union)=={e['name'] for e in all_entries}
    import pypdfium2 as pdfium
    from pypdf import PdfReader
    reader=PdfReader(atlas);assert len(reader.pages)==2
    for i,(page,qa) in enumerate(zip(reader.pages,reports),1):
        qa['uri_links']=len(page.get('/Annots',[]));assert qa['uri_links']==31+sum(n['weights'] for n in qa['nodes'])
        for ref in page.get('/Annots',[]):
            assert urlparse(str(ref.get_object()['/A']['/URI'])).scheme in {'http','https'}
    folder=ROOT/'.build/timeline';document=pdfium.PdfDocument(str(atlas))
    for i in range(2):document[i].render(scale=2).to_pil().save(folder/f'atlas-page-{i+1}.png')
    (folder/'atlas-geometry.json').write_text(json.dumps({'coverage':{'unique_entries':62,'metadata_entries':len(all_entries),'missing':[],'duplicates':[]},'pages':reports},indent=2)+'\n')
    print('ATLAS',[(page['entry_count'],page['issues']) for page in reports])


def build(main_only=False):
    SVG.clear();metadata=json.loads(SOURCE.read_text());all_entries=[normalize_track(e) for e in metadata['entries']]
    lookup={e['name']:e for e in all_entries};assert len(lookup)==len(all_entries)==62
    assert len(MAIN_NAMES)==len(set(MAIN_NAMES))==32;selected=[lookup[name] for name in MAIN_NAMES]
    groups,curve,stations=main_groups(selected);out=ROOT/'doc/figs/fig12.pdf'
    c=canvas.Canvas(str(out),pagesize=(W,H),pageCompression=1,invariant=1)
    c.setTitle('Selected milestones in document intelligence, 2007–2026');c.setAuthor('Beyond OCR survey authors')
    SVG.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc"><title id="title">Selected milestones in document intelligence, 2007–2026</title><desc id="desc">32 selected models, methods and benchmarks on one descending curved chronology. Yellow labels indicate verified official trained weights. A complete 62-entry chronology is provided separately.</desc>')
    qa=draw_clean(c,selected,groups,curve,stations);c.showPage();c.save();shutil.copyfile(out,ROOT/'figs_by_qixingyu/fig12.pdf')
    from pypdf import PdfReader
    linked=PdfReader(out).pages[0];qa['uri_links']=len(linked.get('/Annots',[]))
    qa['selection_names']=MAIN_NAMES
    qa['coverage']={'selected':32,'source_metadata':62,'missing_selected':[],'duplicates':[]}
    assert qa['uri_links']==32+sum(n['weights'] for n in qa['nodes'])
    assert set(qa['selection_names'])=={n['name'] for n in qa['nodes']}
    for ref in linked.get('/Annots',[]):
        assert urlparse(str(ref.get_object()['/A']['/URI'])).scheme in {'http','https'}
    SVG.append('</svg>');(ROOT/'docs/images/document-timeline.svg').write_text('\n'.join(SVG)+'\n')
    import pypdfium2 as pdfium
    pdf=pdfium.PdfDocument(str(out));im=pdf[0].render(scale=2).to_pil();im.save(ROOT/'docs/images/document-timeline.png')
    folder=ROOT/'.build/timeline';folder.mkdir(parents=True,exist_ok=True);im.save(folder/'figure.png');(folder/'geometry.json').write_text(json.dumps(qa,indent=2)+'\n')
    print('MAIN',len(selected),'nodes; issues:',qa['issues'])
    if not main_only:build_atlas(all_entries)


if __name__=='__main__':
    import sys
    build(main_only='--main-only' in sys.argv)
