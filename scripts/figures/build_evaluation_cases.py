#!/usr/bin/env python3
"""Draw an illustrative diagnostic, not model results or measured scores.

The four constructed traces separate numeric agreement, relevant evidence,
document support and arithmetic conditional on the displayed operands.
They cannot establish whether a model causally relied on the cited evidence.
"""
from pathlib import Path
import shutil

from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[2]
W, H = 800, 824
INK = HexColor("#263C39")
MUTED = HexColor("#566C68")
GREEN = HexColor("#326A53")
RED = HexColor("#A84F3D")
BLUE = HexColor("#38698A")
BORDER = HexColor("#CCD6D0")
PALE_GREEN = HexColor("#EAF2EA")
PALE_RED = HexColor("#FAEDE6")
PALE_BLUE = HexColor("#EAF1F5")
PAPER = HexColor("#FBFBF6")
WHITE = HexColor("#FFFFFF")


def text(c, x, y, s, size=16, bold=False, color=INK, align="left"):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    getattr(c, {"left": "drawString", "center": "drawCentredString", "right": "drawRightString"}[align])(x, y, s)


def panel(c, x, y, w, h, fill=WHITE, stroke=BORDER, r=8):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, r, fill=1, stroke=1)


def badge(c, x, y, s, fill, color=INK, size=15.2):
    width = stringWidth(s, "Helvetica-Bold", size) + 18
    panel(c, x, y-5, width, 24, fill, fill, r=4)
    text(c, x+9, y+1, s, size, True, color)
    return width


def check(c, x, y, passed):
    # Vector marks remain recognizable without a special symbol font.
    color = GREEN if passed else RED
    c.setFillColor(PALE_GREEN if passed else PALE_RED)
    c.circle(x, y, 11, fill=1, stroke=0)
    c.setStrokeColor(color)
    c.setLineWidth(2.3)
    if passed:
        p=c.beginPath(); p.moveTo(x-5,y); p.lineTo(x-1,y-4); p.lineTo(x+6,y+5)
        c.drawPath(p)
    else:
        c.line(x-4,y-4,x+4,y+4); c.line(x-4,y+4,x+4,y-4)


def card(c, x, y, key, title, answer, citation, result, support_note, good_cite=True, extra=None):
    width, height = 372, 150
    panel(c,x,y,width,height,PAPER)
    badge(c,x+12,y+120,key,PALE_BLUE,BLUE)
    text(c,x+47,y+122,title,16.5,True)
    text(c,x+13,y+94,"Answer:",15.5,True,color=MUTED)
    text(c,x+78,y+94,answer,17,True)
    if extra:
        badge(c,x+13,y+66,extra,PALE_RED,RED,15.2)
    else:
        text(c,x+13,y+68,"Cites",15.5,color=MUTED)
        badge(c,x+57,y+67,citation,PALE_GREEN if good_cite else PALE_RED,GREEN if good_cite else RED,15.2)
    text(c,x+13,y+39,"Trace:",15.5,color=MUTED)
    text(c,x+68,y+39,result,16.5)
    text(c,x+13,y+13,support_note,15.2,color=MUTED)


def build():
    out=ROOT/"doc/figs/fig14.pdf"
    out.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(out),pagesize=(W,H),pageCompression=1,invariant=1)
    c.setTitle("Why an answer score alone cannot diagnose document QA")
    c.setAuthor("Beyond OCR survey authors")
    c.setSubject("Constructed staffing-table example; not experimental results")

    text(c,20,796,"Why an answer score alone cannot diagnose document QA",22,True)
    text(c,20,771,"Constructed example: four traces, one source document and one question",16.5,color=MUTED)

    panel(c,20,581,760,170,WHITE)
    text(c,36,723,"SOURCE: STAFFING REPORT",15.2,True,color=BLUE)
    # An actual table is shown instead of an abstract input box.
    colx=[37,201,287]
    text(c,colx[0],698,"Category",16,True)
    text(c,colx[1],698,"2023",16,True)
    text(c,colx[2],698,"2024",16,True)
    c.setFillColor(PALE_GREEN);c.rect(31,660,316,28,fill=1,stroke=0)
    text(c,colx[0],669,"Staff",16,True,color=GREEN)
    text(c,colx[1],669,"80",17,True,color=GREEN)
    text(c,colx[2],669,"100",17,True,color=GREEN)
    text(c,colx[0],639,"Contractors",16)
    text(c,colx[1],639,"40",17)
    text(c,colx[2],639,"50",17)
    c.setStrokeColor(BORDER);c.line(31,692,347,692);c.line(31,627,347,627)
    text(c,37,604,"Note: staff exclude contractors.",15.2,color=MUTED)
    c.setStrokeColor(BORDER);c.line(365,600,365,730)
    text(c,386,723,"QUESTION",15.2,True,color=BLUE)
    text(c,386,697,"How many staff were added in 2024?",17,True)
    text(c,386,666,"Reference: 100 - 80 = 20 staff",17,color=GREEN)
    text(c,386,637,"No reason for the change is stated.",16,color=MUTED)
    text(c,386,611,"A numeric match can miss other errors.",16,color=MUTED)

    card(c,20,410,"A","Correct number, wrong citation","20 staff","Contractors row","100 - 80 = 20","The cited row does not supply these inputs.",False)
    card(c,408,410,"B","Correct cells, unsupported claim","20 staff","Staff row","100 - 80 = 20","Staff row cited; cause absent from source.",True,extra='"due to automation"')
    card(c,20,244,"C","Correct cells, arithmetic error","30 staff","Staff row","100 - 80 = 30","Relevant evidence; incorrect calculation.")
    card(c,408,244,"D","All observed checks consistent","20 staff","Staff row","100 - 80 = 20","Correct number with relevant support.")

    # Four diagnostics are a matrix, not a single invented aggregate score.
    panel(c,20,49,760,179,WHITE)
    text(c,36,204,"DIAGNOSTIC",15.2,True,color=BLUE)
    xs=[371,483,598,714]
    labels=[("Numeric","match"),("Relevant","cells"),("Cited","support"),("Arithmetic","(given inputs)")]
    for x,lines in zip(xs,labels):
        text(c,x,211,lines[0],15.2,True,align="center")
        text(c,x,193,lines[1],15.2,align="center")
    c.setStrokeColor(BORDER);c.line(35,184,765,184)
    rows=[("A  Wrong citation",[True,False,False,True]),
          ("B  Unsupported claim",[True,True,False,True]),
          ("C  Arithmetic error",[False,True,False,False]),
          ("D  Consistent trace",[True,True,True,True])]
    for i,(name,values) in enumerate(rows):
        yy=165-i*30
        text(c,36,yy-5,name,16,True)
        for x,value in zip(xs,values): check(c,x,yy,value)
    text(c,20,25,"Causal faithfulness still needs evidence-removal or substitution controls.",16,True,color=MUTED)
    c.showPage();c.save()
    target=ROOT/"figs_by_qixingyu/fig14.pdf"
    shutil.copyfile(out,target)
    print(f"Created {out.relative_to(ROOT)} and {target.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
