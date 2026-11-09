#!/usr/bin/env python3
"""Shape-led publication figures for perception, evidence and table operations.

All source documents and values are constructed illustrations. These diagrams
make no measured accuracy or causal-faithfulness claim. Geometry is original;
all outputs are vector PDFs, copied to both manuscript asset directories.
"""
from pathlib import Path
from math import atan2, cos, sin, pi
import shutil

from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color, white
from reportlab.pdfbase.pdfmetrics import stringWidth

ROOT = Path(__file__).resolve().parents[2]
INK = HexColor('#243746')
NAVY = HexColor('#255C7B')
TEAL = HexColor('#2D8B7B')
AMBER = HexColor('#E8AD44')
CORAL = HexColor('#D57060')
GRAY = HexColor('#CBD3DA')
MUTED = HexColor('#667681')
LIGHT = HexColor('#EDF1F3')
PALE_BLUE = HexColor('#EAF2F6')
PALE_TEAL = HexColor('#EAF5F1')
PALE_AMBER = HexColor('#FFF5DB')
LABELS = []


def text(c, x, y, s, size=18, bold=False, color=INK, align='left', micro=False):
    if not micro:
        assert size >= 16, (s, size)
    LABELS.append(s)
    c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
    c.setFillColor(color)
    getattr(c, {'left':'drawString', 'center':'drawCentredString', 'right':'drawRightString'}[align])(x,y,s)


def line(c, x1, y1, x2, y2, color=GRAY, width=1):
    c.setStrokeColor(color); c.setLineWidth(width); c.line(x1,y1,x2,y2)


def arrow(c, x1,y1,x2,y2, color=MUTED, width=1.4, dashed=False):
    c.setStrokeColor(color); c.setFillColor(color); c.setLineWidth(width)
    if dashed: c.setDash(3,3)
    c.line(x1,y1,x2,y2); c.setDash()
    a=atan2(y2-y1,x2-x1); p=c.beginPath(); p.moveTo(x2,y2)
    p.lineTo(x2-7*cos(a-pi/6),y2-7*sin(a-pi/6));p.lineTo(x2-7*cos(a+pi/6),y2-7*sin(a+pi/6));p.close()
    c.drawPath(p,fill=1,stroke=0)


def page(c,x,y,w,h,fill=white,fold=True,shadow=True):
    if shadow:
        c.setFillColor(LIGHT);c.rect(x+4,y-4,w,h,fill=1,stroke=0)
    c.setFillColor(fill);c.setStrokeColor(GRAY);c.setLineWidth(1)
    if fold:
        p=c.beginPath();p.moveTo(x,y);p.lineTo(x+w,y);p.lineTo(x+w,y+h-14);p.lineTo(x+w-14,y+h);p.lineTo(x,y+h);p.close()
        c.drawPath(p,fill=1,stroke=1)
        line(c,x+w-14,y+h,x+w-14,y+h-14);line(c,x+w-14,y+h-14,x+w,y+h-14)
    else:c.rect(x,y,w,h,fill=1,stroke=1)


def paragraph(c,x,y,width,rows=4,color=GRAY,gap=7):
    for i in range(rows):
        line(c,x,y-i*gap,x+width*(1 if i<rows-1 else .72),y-i*gap,color,2)


def document(c,x,y,w=145,h=212,highlight=False,patches=False):
    page(c,x,y,w,h)
    text(c,x+12,y+h-30,'ANNUAL REPORT',11,True,NAVY,micro=True)
    line(c,x+12,y+h-39,x+w-18,y+h-39,GRAY)
    text(c,x+12,y+h-55,'USD million',9.5,color=MUTED,micro=True)
    paragraph(c,x+12,y+h-67,w-30,2)
    tx=x+12;ty=y+h-113;tw=w-28;rh=18
    c.setFillColor(PALE_BLUE);c.rect(tx,ty+rh,tw,rh,fill=1,stroke=0)
    if highlight:
        c.setFillColor(PALE_AMBER);c.rect(tx,ty-rh,tw,rh*2,fill=1,stroke=0)
    for yy in (ty-rh,ty,ty+rh,ty+2*rh):line(c,tx,yy,tx+tw,yy,GRAY,.7)
    cols=(tx,tx+tw*.48,tx+tw*.74,tx+tw)
    for xx in cols:line(c,xx,ty-rh,xx,ty+2*rh,GRAY,.7)
    for s,xx,yy,b in [('Year',tx+5,ty+24,True),('2023',cols[1]+3,ty+24,True),('2024',cols[2]+3,ty+24,True),('Sales',tx+5,ty+6,False),('100',cols[1]+5,ty+6,False),('120',cols[2]+5,ty+6,False),('Costs',tx+5,ty-12,False),('70',cols[1]+8,ty-12,False),('84',cols[2]+8,ty-12,False)]:
        text(c,xx,yy,s,9.5,b,micro=True)
    if highlight:
        c.setStrokeColor(AMBER);c.setLineWidth(1.5);c.rect(tx,ty,tw,rh,stroke=1,fill=0)
    # A small chart is a visual part of the source document, not a score plot.
    bx=x+19;by=y+20
    line(c,bx,by,bx+w-44,by,GRAY)
    for j,val in enumerate((16,22,28,37)):
        c.setFillColor(NAVY if j<3 else TEAL);c.rect(bx+8+j*20,by,12,val,fill=1,stroke=0)
    if patches:
        c.setStrokeColor(NAVY);c.setLineWidth(.7)
        for i in range(1,6):c.line(x+i*w/6,y,x+i*w/6,y+h)
        for j in range(1,9):c.line(x,y+j*h/9,x+w,y+j*h/9)


def token(c,x,y,s,color=NAVY,fill=PALE_BLUE,size=17,w=None):
    tw=w or stringWidth(s,'Helvetica',size)+18
    c.setFillColor(fill);c.roundRect(x,y-5,tw,25,3,fill=1,stroke=0)
    text(c,x+9,y+2,s,size,color=color)
    return tw


def selected_cells(c,x,y,w=152,h=71):
    c.setFillColor(white);c.setStrokeColor(GRAY);c.setLineWidth(1);c.rect(x,y,w,h,fill=1,stroke=1)
    c.setFillColor(PALE_AMBER);c.rect(x,y+1,w,h/2-1,fill=1,stroke=0)
    line(c,x,y+h/2,x+w,y+h/2,GRAY);line(c,x+w/2,y,x+w/2,y+h,GRAY)
    for xx,s in ((x+w*.25,'2023'),(x+w*.75,'2024')):text(c,xx,y+h*.72,s,16,True,NAVY,'center')
    for xx,s in ((x+w*.25,'100'),(x+w*.75,'120')):text(c,xx,y+h*.20,s,21,True,INK,'center')


def make(number,width,height,subject,draw):
    global LABELS
    LABELS=[]
    dst=ROOT/f'doc/figs/fig{number:02}.pdf'
    c=canvas.Canvas(str(dst),pagesize=(width,height),invariant=1,pageCompression=1)
    c.setTitle(subject);c.setAuthor('Beyond OCR survey authors');c.setSubject('Constructed document illustration; no experimental results')
    draw(c)
    c.showPage();c.save()
    shutil.copyfile(dst,ROOT/f'figs_by_qixingyu/fig{number:02}.pdf')
    print(f'Figure {number}: {width}x{height}; {sum(len(s.split()) for s in LABELS)} visible words (including source-page facsimile).')


def overview(c):
    # The source page is the dominant object, not a box labelled "document".
    document(c,22,70,153,237,highlight=True)
    text(c,98,37,'Document',20,True,align='center')
    # Three evidence representations, drawn rather than described in prose.
    text(c,284,326,'Text + layout',19,True,NAVY,align='center')
    token(c,218,282,'Sales',NAVY);token(c,286,282,'120',NAVY)
    c.setStrokeColor(NAVY);c.setLineWidth(1.2);c.rect(214,270,128,40,fill=0,stroke=1)
    for bx,by in ((214,270),(342,270),(214,310),(342,310)):
        c.setFillColor(NAVY);c.circle(bx,by,2.4,fill=1,stroke=0)
    text(c,284,209,'Visual tokens',19,True,TEAL,align='center')
    # Each visual tile keeps its relative page location.
    for i in range(8):
        for j in range(3):
            c.setFillColor(TEAL if (i+j)%5==0 else HexColor('#BFDCD5'))
            c.roundRect(224+i*14,154+j*14,11,11,1,fill=1,stroke=0)
    text(c,284,94,'Hybrid',19,True,HexColor('#B07925'),align='center')
    token(c,217,50,'Sales',HexColor('#A26F20'),PALE_AMBER)
    for i in range(4):
        for j in range(2):
            c.setFillColor(AMBER if j else HexColor('#F3D99D'));c.rect(293+i*10,46+j*12,8,9,fill=1,stroke=0)
    for yy in (286,179,65):arrow(c,178,189,205,yy,GRAY,1.3)
    # A shared source selection interface, not an extra method class.
    for yy in (286,179,65):arrow(c,354,yy,416,181,GRAY,1.3)
    text(c,488,326,'Evidence selection',20,True,align='center')
    for dx,dy in ((10,10),(5,5),(0,0)):
        page(c,430+dx,96+dy,113,164,shadow=False)
    paragraph(c,443,239,81,3,gap=8)
    c.setFillColor(PALE_AMBER);c.rect(441,175,91,35,fill=1,stroke=0)
    line(c,441,192,532,192,AMBER);line(c,485,175,485,210,AMBER)
    text(c,463,180,'100',16,False,INK,'center');text(c,508,180,'120',16,False,INK,'center')
    paragraph(c,443,159,81,4,gap=8)
    text(c,489,65,'page / region / cell',16,color=MUTED,align='center')
    arrow(c,561,181,620,181,NAVY)
    # The result is visually tied to a source, not just an unsupported answer.
    text(c,739,326,'Answer + source',20,True,align='center')
    text(c,738,215,'+20',51,True,TEAL,align='center')
    text(c,738,181,'Sales change',19,align='center')
    line(c,646,163,832,163,GRAY)
    selected_cells(c,666,68,144,70)
    c.setFillColor(TEAL);c.circle(829,104,10,fill=1,stroke=0)
    line(c,824,104,828,100,white,2);line(c,828,100,835,109,white,2)
    arrow(c,738,147,738,139,TEAL)


def perception(c):
    document(c,23,88,153,234,highlight=True)
    text(c,99,55,'Same source page',18,True,align='center')
    # One fork leads to three materially different representations.
    line(c,182,205,211,205,NAVY,1.4)
    line(c,211,205,211,345,GRAY,1.2)
    line(c,211,345,788,345,GRAY,1.2)
    for x in (316,535,756):arrow(c,x,345,x,312,GRAY)
    text(c,316,286,'Flat OCR',21,True,NAVY,'center')
    text(c,535,286,'Visual patches',21,True,TEAL,'center')
    text(c,756,286,'Structured cells',21,True,HexColor('#A26F20'),'center')
    # Text stream preserves the glyph values, but the year association can vanish.
    for yy,vals in ((232,['Sales','100','120']),(191,['Costs','70','84'])):
        xx=230
        for val in vals:xx+=token(c,xx,yy,val,NAVY,PALE_BLUE,16)+5
    text(c,316,134,'2023     2024',18,True,CORAL,'center')
    line(c,249,141,383,141,CORAL,1.7)
    text(c,316,101,'Header link lost',17,True,CORAL,'center')
    # A page is explicitly partitioned into positioned tiles.
    document(c,473,97,125,165,patches=True)
    c.setFillColor(white);c.setStrokeColor(TEAL);c.setLineWidth(2)
    c.rect(513,162,20.8,18.3,fill=0,stroke=1)
    # Selected cells retain the label -> unit -> values relation.
    c.setFillColor(PALE_AMBER);c.rect(663,228,187,32,fill=1,stroke=0)
    text(c,756,238,'Sales / USD million',16,True,HexColor('#A26F20'),'center')
    selected_cells(c,669,127,175,85)
    line(c,756,228,756,212,AMBER,1.6)
    text(c,756,92,'row + column + unit',17,color=MUTED,align='center')


def table_operations(c):
    # A table is the starting visual, not a list of model names.
    text(c,113,310,'Source table',21,True,align='center')
    text(c,113,266,'USD million',16,color=MUTED,align='center')
    tx,ty,tw,rh=20,117,195,36
    c.setFillColor(PALE_BLUE);c.rect(tx,ty+2*rh,tw,rh,fill=1,stroke=0)
    c.setFillColor(PALE_AMBER);c.rect(tx,ty+rh,tw,rh,fill=1,stroke=0)
    widths=[93,51,51];xx=[tx,tx+93,tx+144,tx+195]
    for x in xx:line(c,x,ty,x,ty+3*rh,GRAY)
    for i in range(4):line(c,tx,ty+i*rh,tx+tw,ty+i*rh,GRAY)
    for i,row in enumerate((('Item','2023','2024'),('Sales','100','120'),('Costs','70','84'))):
        yy=ty+(2-i)*rh+12
        for j,s in enumerate(row):text(c,(xx[j]+xx[j+1])/2,yy,s,16,i==0,INK,'center')
    text(c,113,84,'Structure-aware',16,color=MUTED,align='center')
    text(c,113,62,'TAPAS / TableGPT2',16,color=NAVY,align='center')
    arrow(c,227,189,265,189,NAVY)
    text(c,355,310,'Select evidence',21,True,align='center')
    selected_cells(c,276,151,154,77)
    text(c,353,244,'Sales',18,True,TEAL,'center')
    text(c,353,84,'Relevance / operations',16,color=MUTED,align='center')
    text(c,353,62,'CABINET / Chain-of-Table',16,color=TEAL,align='center')
    arrow(c,442,189,476,189,NAVY)
    text(c,587,310,'Execute',21,True,align='center')
    # Code has a simple left-hand execution guide, not a rounded explainer card.
    line(c,486,128,486,251,NAVY,2.1)
    for yy,s,col in ((226,'previous = 100',INK),(192,'current = 120',INK),(158,'current - previous',NAVY)):
        text(c,501,yy,s,18,False,col)
    text(c,587,84,'Program / interpreter',16,color=MUTED,align='center')
    text(c,587,62,'OpenTab / TaPERA',16,color=NAVY,align='center')
    arrow(c,697,189,728,189,NAVY)
    text(c,806,310,'Answer',21,True,align='center')
    text(c,807,204,'+20',46,True,TEAL,'center')
    text(c,807,172,'USD million',17,False,INK,'center')
    # Trace-back path is the defining source-check boundary.
    c.setStrokeColor(AMBER);c.setLineWidth(1.5);c.setDash(4,4)
    p=c.beginPath();p.moveTo(808,137);p.lineTo(808,30);p.lineTo(8,30);p.lineTo(8,189);c.drawPath(p)
    c.setDash();arrow(c,8,189,17,189,AMBER,1.6)
    text(c,476,13,'Check source cells and units',17,True,HexColor('#A26F20'),'center')


def main():
    make(1,900,360,'Representations, selected evidence and a source-linked answer',overview)
    make(2,900,375,'What survives OCR, visual tokenization and structured extraction',perception)
    make(5,900,340,'Table question answering through selection and execution',table_operations)


if __name__=='__main__':main()
