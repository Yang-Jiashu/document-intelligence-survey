#!/usr/bin/env python3
"""Compact vector evidence-join example; every value is constructed.

The document fragments are the data, not text explanations of a pipeline.
Caption prose supplies context. Both manuscript asset directories are updated.
"""
from pathlib import Path
from math import atan2, cos, sin, pi
import shutil
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
W, H = 900, 385
INK = HexColor('#243746')
NAVY = HexColor('#255C7B')
TEAL = HexColor('#2D8B7B')
AMBER = HexColor('#E8AD44')
CORAL = HexColor('#D57060')
GRAY = HexColor('#CBD3DA')
MUTED = HexColor('#6F7F8C')
WHITE = HexColor('#FFFFFF')


def text(c, x, y, value, size=17, bold=False, color=INK, align='left'):
    c.setFillColor(color)
    c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
    getattr(c, {'left':'drawString','center':'drawCentredString','right':'drawRightString'}[align])(x, y, value)


def line(c, x1, y1, x2, y2, color=GRAY, width=1):
    c.setStrokeColor(color); c.setLineWidth(width); c.line(x1,y1,x2,y2)


def arrow(c, points, color=TEAL, width=2):
    c.setStrokeColor(color); c.setFillColor(color); c.setLineWidth(width)
    p=c.beginPath();p.moveTo(*points[0])
    for pt in points[1:]:p.lineTo(*pt)
    c.drawPath(p)
    (x1,y1),(x2,y2)=points[-2:];a=atan2(y2-y1,x2-x1)
    p=c.beginPath();p.moveTo(x2,y2)
    p.lineTo(x2-7*cos(a-pi/6),y2-7*sin(a-pi/6));p.lineTo(x2-7*cos(a+pi/6),y2-7*sin(a+pi/6));p.close()
    c.drawPath(p,stroke=0,fill=1)


def page(c,x,y,w,h,number):
    # A folded corner and offset hard shadow give the fragments a page identity.
    c.setFillColor(HexColor('#EDF0F2'));c.rect(x+4,y-4,w,h,fill=1,stroke=0)
    c.setFillColor(WHITE);c.setStrokeColor(GRAY);c.setLineWidth(1)
    p=c.beginPath();p.moveTo(x,y);p.lineTo(x+w,y);p.lineTo(x+w,y+h-16);p.lineTo(x+w-16,y+h);p.lineTo(x,y+h);p.close()
    c.drawPath(p,fill=1,stroke=1)
    line(c,x+w-16,y+h,x+w-16,y+h-16);line(c,x+w-16,y+h-16,x+w,y+h-16)
    text(c,x+w-16,y+12,str(number),11,color=MUTED,align='right')


def badge(c,x,y,label,color):
    c.setFillColor(color);c.circle(x,y,12,fill=1,stroke=0)
    text(c,x,y-6,label,17,True,WHITE,'center')


def draw():
    out=ROOT/'doc/figs/fig13.pdf';out.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(out),pagesize=(W,H),invariant=1,pageCompression=1)
    c.setTitle('Joining a financial table with its restatement note')
    c.setAuthor('Beyond OCR survey authors')
    c.setSubject('Constructed cross-page evidence example; not empirical results')
    text(c,20,355,'Operating margin change, after restatement?',20,True)
    line(c,20,341,880,341,width=.8)

    page(c,20,48,286,272,12)
    badge(c,41,300,'A',NAVY)
    text(c,61,294,'Operating performance',18,True)
    text(c,37,270,'USD million',14,color=MUTED)
    # The actual table, with the superseded comparison-year cells picked out.
    text(c,222,245,'2024',16,True,align='center')
    text(c,278,245,'2023',16,True,align='center')
    line(c,36,235,292,235,INK)
    for y,label,a,b in [(211,'Revenue','1,000','800'),(181,'Operating profit','150','96'),(151,'Margin','15.0%','12.0%')]:
        text(c,37,y,label,16)
        text(c,222,y,a,17,align='center')
        if label=='Operating profit':
            c.setFillColor(HexColor('#FFF0CC'));c.rect(251,y-5,41,25,fill=1,stroke=0)
        text(c,278,y,b,17,label=='Operating profit',CORAL if label=='Margin' else INK,'center')
    line(c,36,138,292,138,INK)
    for y,w in [(116,233),(103,202),(90,222)]:line(c,37,y,37+w,y,GRAY,2)

    page(c,347,82,243,238,13)
    badge(c,369,300,'B',TEAL)
    text(c,389,294,'Note 7',18,True)
    text(c,365,265,'2023 operating profit',16)
    # Supersession is drawn, rather than narrated in a box.
    text(c,378,226,'96',27,True,CORAL)
    line(c,374,237,413,237,CORAL,2)
    arrow(c,[(425,235),(459,235)],TEAL)
    text(c,470,226,'104',29,True,TEAL)
    c.setFillColor(HexColor('#E4F2ED'));c.rect(362,178,211,28,fill=1,stroke=0)
    text(c,371,185,'Revenue unchanged: 800',16,True,TEAL)
    for y,w in [(158,207),(145,174),(132,197),(119,153)]:line(c,365,y,365+w,y,GRAY,2)

    # The two differently colored sources meet at the calculation, visibly.
    arrow(c,[(306,65),(625,65),(625,137),(656,137)],NAVY,2)
    arrow(c,[(590,194),(625,194),(625,235),(656,235)],TEAL,2)
    text(c,676,290,'2024',16,True,color=NAVY)
    text(c,676,264,'150 / 1,000',21,color=NAVY)
    text(c,870,264,'15%',27,True,NAVY,'right')
    line(c,675,249,878,249,GRAY)
    text(c,676,219,'2023',16,True,color=TEAL)
    text(c,676,193,'104 / 800',21,color=TEAL)
    text(c,870,193,'13%',27,True,TEAL,'right')
    line(c,675,175,878,175,INK,1.2)
    text(c,776,145,'15% - 13%',22,align='center')
    text(c,776,94,'+2 pp',43,True,TEAL,'center')
    c.setFillColor(TEAL);c.rect(712,81,128,3,fill=1,stroke=0)
    c.showPage();c.save()
    alt=ROOT/'figs_by_qixingyu/fig13.pdf';shutil.copyfile(out,alt)
    print(f'{out.relative_to(ROOT)} -> {alt.relative_to(ROOT)}; {W}x{H} pt')


if __name__=='__main__':draw()
