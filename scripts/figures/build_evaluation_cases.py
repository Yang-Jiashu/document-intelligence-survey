#!/usr/bin/env python3
"""Four constructed traces and four independent checks, as a compact visual.

Numbers and traces illustrate diagnostics; they are not model measurements.
The caption explains source support and causal-faithfulness limitations.
"""
from pathlib import Path
import shutil
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

ROOT=Path(__file__).resolve().parents[2]
W,H=900,355
INK=HexColor('#243746');NAVY=HexColor('#255C7B');TEAL=HexColor('#2D8B7B')
CORAL=HexColor('#D57060');GRAY=HexColor('#CBD3DA');WHITE=HexColor('#FFFFFF')
MUTED=HexColor('#6F7F8C')


def text(c,x,y,s,size=17,bold=False,color=INK,align='left'):
    c.setFillColor(color);c.setFont('Helvetica-Bold' if bold else 'Helvetica',size)
    getattr(c,{'left':'drawString','center':'drawCentredString','right':'drawRightString'}[align])(x,y,s)


def line(c,x1,y1,x2,y2,color=GRAY,width=1):
    c.setStrokeColor(color);c.setLineWidth(width);c.line(x1,y1,x2,y2)


def wire(c,points,color):
    c.setStrokeColor(color);c.setLineWidth(1.8)
    p=c.beginPath();p.moveTo(*points[0])
    for pt in points[1:]:p.lineTo(*pt)
    c.drawPath(p)
    c.setFillColor(color)
    for x,y in (points[0],points[-1]):c.circle(x,y,3.5,fill=1,stroke=0)


def mark(c,x,y,passed):
    color=TEAL if passed else CORAL
    c.setFillColor(HexColor('#E4F2ED') if passed else HexColor('#FBEAE5'))
    c.circle(x,y,13,fill=1,stroke=0)
    c.setStrokeColor(color);c.setLineWidth(2.6)
    if passed:
        p=c.beginPath();p.moveTo(x-6,y);p.lineTo(x-1,y-5);p.lineTo(x+7,y+6);c.drawPath(p)
    else:
        c.line(x-5,y-5,x+5,y+5);c.line(x-5,y+5,x+5,y-5)


def build():
    out=ROOT/'doc/figs/fig14.pdf';out.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(out),pagesize=(W,H),invariant=1,pageCompression=1)
    c.setTitle('Four document-QA traces with independent diagnostic outcomes')
    c.setAuthor('Beyond OCR survey authors')
    c.setSubject('Constructed staffing-table example; not experimental results')
    text(c,20,330,'How many staff were added?',20,True)
    line(c,20,317,883,317,width=.8)

    # Left: the document is the anchor for every citation link.
    c.setFillColor(HexColor('#EDF0F2'));c.rect(24,39,264,263,fill=1,stroke=0)
    c.setFillColor(WHITE);c.setStrokeColor(GRAY);c.rect(20,43,264,263,fill=1,stroke=1)
    text(c,36,279,'Staffing report',19,True)
    text(c,200,244,'2023',16,True,align='center');text(c,253,244,'2024',16,True,align='center')
    line(c,35,235,270,235,INK)
    c.setFillColor(HexColor('#E4F2ED'));c.rect(34,197,236,30,fill=1,stroke=0)
    text(c,40,205,'Staff',17,True,TEAL);text(c,200,205,'80',19,True,TEAL,'center');text(c,253,205,'100',19,True,TEAL,'center')
    text(c,40,173,'Contractors',17);text(c,200,173,'40',19,align='center');text(c,253,173,'50',19,align='center')
    line(c,35,160,270,160,INK)
    text(c,36,138,'Staff exclude contractors.',15,color=MUTED)
    for yy,ww in [(112,228),(98,197),(84,219),(70,167)]:line(c,36,yy,36+ww,yy,GRAY,2)

    # A: a wrong row is cited even though the visible arithmetic is correct.
    wire(c,[(274,179),(301,179),(301,269),(348,269)],CORAL)
    # B/C/D: the same correct row supports three different outcomes.
    wire(c,[(274,210),(320,210),(320,89)],TEAL)
    for yy in (209,149,89):wire(c,[(320,yy),(348,yy)],TEAL)
    text(c,393,294,'Added staff',16,True,color=NAVY)
    ys=[269,209,149,89]
    for key,number,y,expression in zip('ABCD',['20','20','30','20'],ys,['100 - 80 = 20','100 - 80 = 20','100 - 80 = 30','100 - 80 = 20']):
        text(c,363,y-6,key,17,True)
        text(c,397,y-8,number,28,True,CORAL if key=='C' else INK)
        text(c,397,y-30,expression,16,color=MUTED)
    # The unsupported addition is a visible speech annotation, not prose.
    text(c,452,201,'+ automation',16,True,CORAL)
    line(c,450,194,555,194,CORAL,1.2)

    # Right: one diagnostic per column, one trace per row.
    xs=[621,698,776,852]
    labels=['Number','Cells','Support','Math']
    for x,label in zip(xs,labels):text(c,x,294,label,16,True,align='center')
    line(c,582,282,884,282,INK)
    matrix=[[1,0,0,1],[1,1,0,1],[0,1,0,0],[1,1,1,1]]
    for y,values in zip(ys,matrix):
        for x,value in zip(xs,values):mark(c,x,y,bool(value))
    for yy in (239,179,119,59):line(c,583,yy,884,yy,GRAY,.7)
    c.showPage();c.save();alt=ROOT/'figs_by_qixingyu/fig14.pdf';shutil.copyfile(out,alt)
    print(f'{out.relative_to(ROOT)} -> {alt.relative_to(ROOT)}; {W}x{H} pt')


if __name__=='__main__':build()
