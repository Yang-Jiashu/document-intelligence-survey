#!/usr/bin/env python3
"""Author-drawn retrieval schematics with visual objects instead of text cards.

All highlighted regions, graph links and token matches are illustrative. They
are not measurements from a model. Main labels stay >=16 pt on a 900 pt canvas.
"""
from __future__ import annotations

from math import atan2, cos, sin, pi
from pathlib import Path
import shutil

from reportlab.lib.colors import Color, HexColor, white
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
INK = HexColor('#243746')
NAVY = HexColor('#255C7B')
TEAL = HexColor('#2D8B7B')
AMBER = HexColor('#E8AD44')
CORAL = HexColor('#D57060')
GRAY = HexColor('#CBD3DA')
MUTED = HexColor('#6C7B85')
PALE = HexColor('#F3F6F7')
TINT = HexColor('#E6F3EF')


def text(c, x, y, value, size=19, bold=False, color=INK, align='left'):
    c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
    c.setFillColor(color)
    getattr(c, {'left':'drawString', 'center':'drawCentredString',
                'right':'drawRightString'}[align])(x, y, value)


def line(c, x1, y1, x2, y2, color=GRAY, width=1.4, dash=None):
    c.setLineWidth(width); c.setStrokeColor(color)
    c.setDash(dash or [])
    c.line(x1,y1,x2,y2); c.setDash([])


def arrow(c, x1, y1, x2, y2, color=MUTED, width=1.6, head=7, dash=None):
    line(c,x1,y1,x2,y2,color,width,dash)
    theta=atan2(y2-y1,x2-x1)
    p=c.beginPath();p.moveTo(x2,y2)
    for a in (-pi/6,pi/6):
        p.lineTo(x2-head*cos(theta+a),y2-head*sin(theta+a))
    p.close();c.setFillColor(color);c.drawPath(p,stroke=0,fill=1)


def curve_arrow(c, points, color=MUTED, width=1.6, dash=None):
    x0,y0,x1,y1,x2,y2,x3,y3=points
    p=c.beginPath();p.moveTo(x0,y0);p.curveTo(x1,y1,x2,y2,x3,y3)
    c.setStrokeColor(color);c.setLineWidth(width);c.setDash(dash or [])
    c.drawPath(p,stroke=1,fill=0);c.setDash([])
    theta=atan2(y3-y2,x3-x2)
    q=c.beginPath();q.moveTo(x3,y3)
    for a in (-pi/6,pi/6):q.lineTo(x3-7*cos(theta+a),y3-7*sin(theta+a))
    q.close();c.setFillColor(color);c.drawPath(q,stroke=0,fill=1)


def rect(c,x,y,w,h,fill=white,stroke=GRAY,width=1.3,radius=0):
    c.setFillColor(fill);c.setStrokeColor(stroke);c.setLineWidth(width)
    if radius:c.roundRect(x,y,w,h,radius,stroke=1,fill=1)
    else:c.rect(x,y,w,h,stroke=1,fill=1)


def circle(c,x,y,r=10,fill=white,stroke=GRAY,width=1.6):
    c.setFillColor(fill);c.setStrokeColor(stroke);c.setLineWidth(width)
    c.circle(x,y,r,stroke=1,fill=1)


def tag(c,x,y,value,color=TEAL,r=12):
    circle(c,x,y,r,color,color)
    text(c,x,y-5,value,16,True,white,'center')


def page(c,x,y,w=75,h=100,highlight=None,table=False,patches=False,
         border=GRAY,fold=True):
    """A genuine miniature page object; bars represent untranscribed body text."""
    rect(c,x,y,w,h,white,border,1.25)
    if fold:
        p=c.beginPath();p.moveTo(x+w-14,y+h);p.lineTo(x+w-14,y+h-14);p.lineTo(x+w,y+h-14)
        c.setStrokeColor(border);c.drawPath(p,stroke=1,fill=0)
    line(c,x+w*.13,y+h*.85,x+w*.65,y+h*.85,NAVY,2.2)
    if patches:
        for i in range(3):
            for j in range(2):
                colors=[TINT,PALE,HexColor('#FFF3D9'),PALE,HexColor('#ECF1F6'),TINT]
                rect(c,x+7+j*(w-14)/2,y+10+i*(h-33)/3,
                     (w-14)/2,(h-33)/3,colors[i*2+j],white,.9)
        return
    for i,frac in enumerate((.72,.61,.72,.66,.72)):
        yy=y+h*.73-i*h*.09
        line(c,x+w*.13,yy,x+w*(.13+frac),yy,GRAY,1.6)
    if table:
        tx=x+w*.13;ty=y+h*.18;tw=w*.74;th=h*.29
        rect(c,tx,ty,tw,th,PALE,GRAY,.8)
        for i in range(1,3):line(c,tx,ty+i*th/3,tx+tw,ty+i*th/3,GRAY,.75)
        for i in range(1,3):line(c,tx+i*tw/3,ty,tx+i*tw/3,ty+th,GRAY,.75)
    if highlight:
        a,b,d,e=highlight
        rect(c,x+a*w,y+b*h,d*w,e*h,TINT,TEAL,1.7)
        for k in range(2):
            yy=y+(b+.04)*h+k*e*h*.4
            line(c,x+(a+.03)*w,yy,x+(a+d-.03)*w,yy,TEAL,1.6)


def chunk(c,x,y,w=125,h=28,chosen=False):
    rect(c,x,y,w,h,TINT if chosen else white,TEAL if chosen else GRAY,1.7 if chosen else 1.2)
    for j,f in enumerate((.80,.57)):
        line(c,x+10,y+h-9-j*8,x+10+(w-20)*f,y+h-9-j*8,
             TEAL if chosen else GRAY,1.5)


def answer(c,x,y,w=190,h=39,label='Answer',citations='[A, B]'):
    rect(c,x,y,w,h,white,TEAL,1.8,5)
    text(c,x+14,y+12,label,20,True,INK)
    text(c,x+w-14,y+12,citations,18,False,TEAL,'right')


def save(c,number):
    c.showPage();c.save()
    a=ROOT/f'doc/figs/fig{number:02}.pdf'
    b=ROOT/f'figs_by_qixingyu/fig{number:02}.pdf'
    shutil.copyfile(a,b)
    print(f'Figure {number:02}: {a.stat().st_size} bytes; synchronized both asset directories')


def start(number,size,title):
    p=ROOT/f'doc/figs/fig{number:02}.pdf'
    c=canvas.Canvas(str(p),pagesize=size,pageCompression=1,invariant=1)
    c.setTitle(title);c.setAuthor('Beyond OCR survey authors')
    c.setSubject('Original schematic; highlighted evidence is illustrative, not measured model output')
    return c


def retrieval_patterns():
    c=start(6,(900,355),'Three document evidence index structures')
    # Shared question and answer make the different index geometries comparable.
    text(c,450,327,'Question',21,True,align='center')
    line(c,150,307,750,307,GRAY,1.3)
    line(c,450,319,450,307,GRAY,1.3)
    for x in (150,450,750):arrow(c,x,307,x,285,NAVY)
    for x,heading in ((150,'(a) Flat chunks'),(450,'(b) Document tree'),(750,'(c) Evidence graph')):
        text(c,x,257,heading,21,True,align='center')
    for x in (300,600):line(c,x,79,x,239,HexColor('#E5E9EC'),1)

    # Flat chunk index: the second chunk, rather than a text explanation, is selected.
    for i in range(4):chunk(c,85,199-i*35,133,27,chosen=i==1)
    tag(c,232,177,'A',TEAL)
    # Faint offset document edge identifies the chunks as serialized page content.
    line(c,73,224,73,95,GRAY,1)
    line(c,73,224,80,224,GRAY,1);line(c,73,95,80,95,GRAY,1)

    # A page -> sections -> leaves hierarchy. Colored links expose a chosen path.
    for a,b in [((450,210),(391,169)),((450,210),(509,169)),
                ((391,169),(354,116)),((391,169),(423,116)),
                ((509,169),(487,116)),((509,169),(556,116))]:
        line(c,*a,*b,TEAL if b in ((391,169),(423,116)) else GRAY,2.0 if b in ((391,169),(423,116)) else 1.3)
    page(c,438,202,24,30,border=NAVY,fold=False)
    for xx in (377,495):chunk(c,xx,154,28,28,chosen=xx==377)
    for xx in (338,407,471,540):chunk(c,xx,101,32,24,chosen=xx==407)
    tag(c,454,111,'B',TEAL)

    # Graph retains non-tree links between related regions or entities.
    nodes={'a':(656,193),'b':(729,221),'c':(811,190),
           'd':(684,122),'e':(765,105),'f':(844,129)}
    edges=[('a','b'),('a','d'),('b','c'),('b','d'),('b','e'),('c','f'),('d','e'),('e','f')]
    chosen={('b','e'),('d','e')}
    for a,b in edges:line(c,*nodes[a],*nodes[b],TEAL if (a,b) in chosen else GRAY,2.7 if (a,b) in chosen else 1.3)
    for key,(xx,yy) in nodes.items():
        circle(c,xx,yy,13,TINT if key in ('b','d','e') else white,TEAL if key in ('b','d','e') else GRAY,1.8)
        if key in ('b','d','e'):circle(c,xx,yy,3.1,TEAL,TEAL)
    tag(c,790,93,'C',TEAL)

    # Different index structures converge on the same downstream answer interface.
    for xx in (150,450,750):
        line(c,xx,80,xx,62,GRAY,1.2)
    line(c,150,62,750,62,GRAY,1.2)
    arrow(c,450,62,450,48,TEAL)
    answer(c,340,7,220,39,'Answer','[A / B / C]')
    save(c,6)


def magnifier(c,x,y,r=14,color=NAVY):
    circle(c,x,y,r,white,color,2)
    line(c,x+r*.72,y-r*.72,x+r*1.55,y-r*1.55,color,3)


def calculator(c,x,y,w=70,h=78,display='='):
    rect(c,x,y,w,h,white,NAVY,1.5,4)
    rect(c,x+8,y+h-25,w-16,16,PALE,GRAY,.8)
    for i in range(2):
        for j in range(3):
            rect(c,x+9+j*18,y+11+i*17,11,10,TINT if j==2 else PALE,GRAY,.6)
    text(c,x+w-10,y+h-22,display,15,False,NAVY,'right')


def agent_control():
    c=start(8,(900,330),'Document question answering with revisitable evidence and tools')
    # The page is a real visual object and the output retains its region identifiers.
    rect(c,20,127,136,68,white,NAVY,1.6,9)
    p=c.beginPath();p.moveTo(120,127);p.lineTo(113,112);p.lineTo(138,127)
    c.setFillColor(white);c.setStrokeColor(NAVY);c.drawPath(p,stroke=1,fill=1)
    text(c,88,166,'Margin',21,True,align='center')
    text(c,88,143,'change?',21,True,align='center')
    text(c,88,88,'Question',18,align='center')
    arrow(c,162,163,211,163,NAVY)

    # Planning symbol: one observed state can choose several actions.
    circle(c,260,164,43,white,NAVY,2)
    circle(c,248,164,4,NAVY,NAVY)
    for xx,yy in ((277,184),(282,164),(277,144)):
        line(c,252,164,xx,yy,NAVY,1.5);circle(c,xx,yy,3.5,NAVY,NAVY)
    text(c,260,92,'Plan',20,True,align='center')
    arrow(c,309,164,352,164,NAVY)

    page(c,365,127,55,90,(.14,.20,.72,.27),table=True,border=NAVY)
    page(c,430,127,55,90,(.14,.28,.72,.26),table=False,border=NAVY)
    tag(c,411,139,'A',TEAL,10)
    tag(c,476,139,'B',AMBER,10)
    magnifier(c,488,112,13,NAVY)
    text(c,420,236,'Retrieve',20,True,align='center')
    arrow(c,495,164,526,164,TEAL)

    # Document evidence is recorded before it supplies arithmetic operands.
    # A is the current-year ratio; B is the footnote-restated comparison ratio.
    rect(c,535,112,158,100,white,GRAY,1.3)
    text(c,614,237,'Source evidence',20,True,align='center')
    for i,(letter,color,ratio) in enumerate((('A',TEAL,'150 / 1000'),
                                             ('B',AMBER,'104 / 800'))):
        yy=183-i*39
        tag(c,553,yy,letter,color,10)
        text(c,572,yy-5,ratio,17,True,INK)

    # Arithmetic results follow a separate path from the document citations.
    arrow(c,614,106,614,91,NAVY)
    calculator(c,576,16,76,70,display='2.0')
    text(c,555,43,'Calculate',18,align='right')
    text(c,676,18,'100(A - B)',17,color=NAVY)
    curve_arrow(c,(660,51,719,51,722,148,755,148),NAVY,1.8)
    text(c,729,196,'Sources',16.5,False,TEAL,'center')
    arrow(c,701,174,755,174,TEAL,1.5,dash=[3,3])
    rect(c,764,139,118,51,white,TEAL,1.8,5)
    text(c,823,157,'+2 pp',24,True,NAVY,'center')
    text(c,823,213,'Answer',20,True,align='center')
    text(c,823,111,'[A, B]',20,True,TEAL,'center')

    # A high loop makes revisiting evidence visible without crossing page objects.
    line(c,693,212,695,220,MUTED,1.5,[4,4])
    curve_arrow(c,(695,220,760,314,255,314,260,214),MUTED,1.5,[4,4])
    text(c,460,300,'Revisit',18,color=MUTED,align='center')
    save(c,8)


def visual_budget():
    c=start(15,(900,390),'Visual resolution and patch-level retrieval decisions')
    text(c,24,355,'(a) Keep small text readable',22,True)
    text(c,480,355,'(b) Match query tokens to patches',22,True)
    line(c,450,24,450,335,HexColor('#E5E9EC'),1)

    # Same illustrative page is globally resized or cropped at native detail.
    page(c,42,128,117,177,table=True,border=NAVY)
    rect(c,56,171,88,36,HexColor('#FFF4DB'),AMBER,1.9)
    text(c,100,184,'13.0%',18,True,INK,'center')
    text(c,100,93,'Page',20,True,align='center')
    arrow(c,174,268,240,268,NAVY)
    page(c,255,225,56,85,table=True)
    # Raster-like lines convey the loss of legible character detail after resizing.
    for yy in (245,249,253):line(c,263,yy,302,yy,GRAY,.7)
    text(c,283,199,'Global resize',19,True,align='center')
    text(c,283,176,'Detail lost',17,color=CORAL,align='center')
    line(c,170,218,183,218,GRAY,1.2)
    curve_arrow(c,(179,189,218,189,203,106,237,106),AMBER,1.7)
    rect(c,243,53,159,93,white,AMBER,1.8)
    text(c,258,117,'2023',17,True,NAVY)
    line(c,254,105,391,105,GRAY,1)
    text(c,323,71,'13.0%',29,True,INK,'center')
    text(c,323,26,'Native-detail crop',19,True,align='center')

    # Page patches, query tokens and an intentionally schematic interaction matrix.
    page(c,740,240,78,95,patches=True,border=NAVY)
    text(c,680,279,'Page patches',18,True,NAVY,'right')
    arrow(c,822,260,848,224,GRAY,1.4)
    q=['margin','2023','restated']
    vals=[[.12,.18,.16,.92,.22,.10],
          [.16,.91,.22,.34,.10,.20],
          [.22,.12,.15,.30,.88,.14]]
    mx,my,cw,ch=622,96,30,35
    text(c,848,222,'Max',17,True,TEAL,'center')
    for row,word in enumerate(q):
        yy=my+(2-row)*ch
        text(c,604,yy+11,word,19,False,INK,'right')
        for col,v in enumerate(vals[row]):
            fill=Color(1-v*(1-TEAL.red),1-v*(1-TEAL.green),1-v*(1-TEAL.blue))
            rect(c,mx+col*cw,yy,cw,ch,fill,white,1.6)
        best=max(range(6),key=lambda j:vals[row][j])
        bx=mx+best*cw+cw/2
        # A small outlined diamond identifies each token's strongest patch match.
        p=c.beginPath();p.moveTo(bx,yy+27);p.lineTo(bx+6,yy+17.5)
        p.lineTo(bx,yy+8);p.lineTo(bx-6,yy+17.5);p.close()
        c.setStrokeColor(white);c.setLineWidth(1.5);c.drawPath(p,stroke=1,fill=0)
        arrow(c,807,yy+17,833,yy+17,TEAL,1.2,5)
        circle(c,848,yy+17,8,white,TEAL,1.6)
    text(c,720,71,'Token-patch matches',17,color=MUTED,align='center')
    # An aggregation glyph avoids fabricated numeric scores in the illustration.
    for yy in (113,148,183):line(c,859,yy,878,yy,TEAL,1.2)
    line(c,878,183,878,43,TEAL,1.2)
    arrow(c,878,43,850,43,TEAL,1.2,5)
    circle(c,835,43,13,white,TEAL,1.5)
    p=c.beginPath();p.moveTo(840,51);p.lineTo(830,51);p.lineTo(836,43)
    p.lineTo(830,35);p.lineTo(840,35)
    c.setStrokeColor(TEAL);c.setLineWidth(1.4);c.drawPath(p,stroke=1,fill=0)
    text(c,806,36,'Page score',19,True,TEAL,'right')
    save(c,15)


if __name__=='__main__':
    retrieval_patterns()
    agent_control()
    visual_budget()
