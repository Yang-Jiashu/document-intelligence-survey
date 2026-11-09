#!/usr/bin/env python3
"""Rebuild the survey's vector overview and composable-RAG diagrams.

Figures are author synthesis, not a measured ranking. Text remains selectable.
Run from any directory: python scripts/figures/build_evidence_diagrams.py
"""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color
import shutil

ROOT = Path(__file__).resolve().parents[2]
INK = HexColor('#26313A')
MUTED = HexColor('#55636E')
RED = HexColor('#8C1515')
BORDER = HexColor('#B9C4CA')
BLUE = HexColor('#EDF3F7')
GREEN = HexColor('#EDF4EE')
WARM = HexColor('#FAF1E8')
WHITE = HexColor('#FFFFFF')


def text(c, x, y, value, size=10, bold=False, color=INK, align='left'):
    c.setFillColor(color)
    c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
    getattr(c, {'left':'drawString','center':'drawCentredString','right':'drawRightString'}[align])(x,y,value)


def panel(c, x, y, w, h, fill=WHITE, stroke=BORDER, radius=5):
    c.setFillColor(fill);c.setStrokeColor(stroke);c.setLineWidth(.75)
    c.roundRect(x,y,w,h,radius,fill=1,stroke=1)


def arrow(c, x1,y1,x2,y2,color=MUTED):
    from math import atan2,cos,sin,pi
    c.setStrokeColor(color);c.setFillColor(color);c.setLineWidth(.9)
    c.line(x1,y1,x2,y2)
    angle=atan2(y2-y1,x2-x1);length=5
    p=c.beginPath();p.moveTo(x2,y2)
    p.lineTo(x2-length*cos(angle-pi/6),y2-length*sin(angle-pi/6))
    p.lineTo(x2-length*cos(angle+pi/6),y2-length*sin(angle+pi/6));p.close()
    c.drawPath(p,fill=1,stroke=0)


def save_and_copy(c, path):
    c.showPage();c.save()
    destination=ROOT/'doc/figs'/path.name
    shutil.copyfile(path,destination)
    print(path.relative_to(ROOT), '->', destination.relative_to(ROOT))


def overview():
    path=ROOT/'figs_by_qixingyu/fig01.pdf'
    c=canvas.Canvas(str(path),pagesize=(600,306),pageCompression=1,invariant=1)
    c.setTitle('Document intelligence: representations, evidence and verification')
    text(c,16,286,'Document intelligence as evidence preservation and use',14,True,color=RED)
    text(c,16,269,'Perception and reasoning organize the review; the routes below are not exclusive model classes.',9.3,color=MUTED)

    panel(c,16,101,96,142,WARM)
    text(c,64,222,'Document inputs',10.5,True,align='center')
    for i,line in enumerate(['PDF / scan / photo','Text, tables, charts','and page layout']):
        text(c,64,201-i*14,line,9.5,align='center')
    text(c,64,137,'Native PDF text',9.1,align='center')
    text(c,64,124,'may also be used.',9.1,align='center')

    text(c,130,248,'PERCEPTION / REPRESENTATION',8.6,True,color=RED)
    panel(c,130,101,156,142,BLUE)
    text(c,208,225,'Choose or combine inputs',10.4,True,align='center')
    rows=[('OCR + layout','text + coordinates'),('Direct visual encoding','page / region visual tokens'),('Hybrid encoding','text + layout + images')]
    for i,(title,detail) in enumerate(rows):
        y=183-i*35
        panel(c,139,y-7,138,31,WHITE)
        text(c,208,y+12,title,9.4,True,align='center')
        text(c,208,y-1,detail,8.8,align='center')

    text(c,304,248,'REASONING / EVIDENCE USE',8.6,True,color=RED)
    panel(c,304,101,142,142,GREEN)
    text(c,375,222,'Shared mechanisms',10.4,True,align='center')
    for i,line in enumerate(['Select or retrieve evidence','Compose text, cells,','regions and pages']):
        text(c,375,202-i*14,line,9.4,align='center')
    c.setStrokeColor(BORDER);c.line(316,158,434,158)
    text(c,375,143,'Optional iterative tools',9.4,True,align='center')
    text(c,375,129,'and agent control',9.4,align='center')
    text(c,375,113,'Fixed context is also valid.',8.7,color=MUTED,align='center')

    panel(c,464,101,120,142,WARM)
    text(c,524,222,'Answer + evidence',10.4,True,align='center')
    text(c,524,201,'Evaluate separately:',9.3,align='center')
    for i,line in enumerate(['Answer correctness','Evidence localization','Support / faithfulness','Program execution','Abstention behavior']):
        text(c,524,183-i*14,line,9.1,align='center')
    for x1,x2 in [(112,130),(286,304),(446,464)]: arrow(c,x1,173,x2,173)

    panel(c,16,22,568,61,HexColor('#F5F6F7'))
    text(c,28,65,'Cross-cutting comparison axes',10.2,True,color=RED)
    labels=[('Representation','text / boxes / images'),('Context span','page / document / collection'),('Evidence granularity','token / cell / region / page'),('Control','fixed / iterative'),('Validation','answer / evidence / process')]
    widths=[100,123,127,92,110]
    x=28
    for (label,detail),width in zip(labels,widths):
        text(c,x,48,label,9.1,True)
        text(c,x,34,detail,8.2,color=MUTED)
        x+=width
    save_and_copy(c,path)


def rag_mechanisms():
    path=ROOT/'figs_by_qixingyu/fig06.pdf'
    c=canvas.Canvas(str(path),pagesize=(540,272),pageCompression=1,invariant=1)
    c.setTitle('Composable retrieval and reasoning mechanisms for document QA')
    text(c,14,252,'Composable retrieval and reasoning mechanisms',13.5,True,color=RED)
    text(c,14,236,'Mechanisms can be combined. Panel order does not imply replacement or a performance ranking.',8.8,color=MUTED)
    cards=[
      ('Retrieve then generate',['Retrieve passages, then','condition answer generation.'],['RAG (Lewis et al., 2020)','Triple-Fact Retriever; DR-RAG'],BLUE),
      ('Structure-aware retrieval',['Preserve sections and','document relationships.'],['PdfTriage; HiQA','DocReLM'],GREEN),
      ('Graph-based retrieval',['Connect entities or evidence','within and across documents.'],['GraphRAG; LightRAG','HyperGraphRAG'],WARM),
      ('Visual retrieval',['Index page or region','image representations.'],['ColPali; VisRAG','M3DocRAG'],GREEN),
      ('Agent control',['Choose retrieval / tool actions;','revise the evidence context.'],['MA-RAG; CogDoc','AutoThinkRAG'],WARM),
      ('Combine, then evaluate',['Example: visual index + graph','+ iterative retrieval control.'],['Report answer / evidence quality','and token, latency, tool costs.'],BLUE),
    ]
    for i,(title,body,examples,color) in enumerate(cards):
        col=i%3;row=i//3;x=14+col*174;y=124-row*108
        panel(c,x,y,164,100,color)
        text(c,x+10,y+80,title,10.5,True)
        for j,line in enumerate(body):text(c,x+10,y+60-j*13,line,9.4)
        c.setStrokeColor(BORDER);c.line(x+10,y+37,x+154,y+37)
        for j,line in enumerate(examples):text(c,x+10,y+23-j*12,line,8.6,color=MUTED)
    save_and_copy(c,path)


def capability_grid(filename, title, subtitle, cards, columns=2, footer=None):
    path=ROOT/'figs_by_qixingyu'/filename
    rows=(len(cards)+columns-1)//columns
    width=540; card_w=(width-28-(columns-1)*10)/columns
    card_h=108; height=58+rows*card_h+(rows-1)*10+(31 if footer else 12)
    c=canvas.Canvas(str(path),pagesize=(width,height),pageCompression=1,invariant=1)
    c.setTitle(title)
    text(c,14,height-22,title,13,True,color=RED)
    text(c,14,height-39,subtitle,8.7,color=MUTED)
    for i,(heading,body,examples,color) in enumerate(cards):
        col=i%columns;row=i//columns
        x=14+col*(card_w+10);y=height-54-(row+1)*card_h-row*10
        panel(c,x,y,card_w,card_h,color)
        text(c,x+10,y+87,heading,10.2,True)
        for j,line in enumerate(body):text(c,x+10,y+66-j*13,line,9.1)
        c.setStrokeColor(BORDER);c.line(x+10,y+34,x+card_w-10,y+34)
        for j,line in enumerate(examples):text(c,x+10,y+20-j*12,line,8.6,color=MUTED)
    if footer:text(c,14,15,footer,8.5,color=MUTED)
    save_and_copy(c,path)


def ocr_designs():
    capability_grid('fig02.pdf','OCR design choices: complementary mechanisms',
      'Examples illustrate overlapping design choices, not exclusive eras or a performance ranking.',[
      ('Detection and recognition pipelines',
       ['Locate text and recognize selected regions.','Expose intermediate boxes and transcriptions.','Segmentation or recognition errors can propagate.'],
       ['OCRopus; Tesseract','PP-OCR also uses neural sequence models.'],BLUE),
      ('Neural sequence recognition',
       ['Learn image-to-sequence mappings.','CTC or autoregressive decoding predicts text.','Output and supervision depend on the task.'],
       ['CRNN; Calamari; PP-OCR','Can be used inside a modular pipeline.'],GREEN),
      ('Joint text and layout generation',
       ['Generate text with locations or formatted content.','Preserve structure in the output representation.','Serialization alone does not establish correctness.'],
       ['VISTA-OCR; GOT-OCR','Text and structure require separate evaluation.'],WARM),
      ('Vision-language OCR and parsing',
       ['Condition generation on visual tokens.','Resolution and compression affect retained detail.','External OCR can still be used during training.'],
       ['Ocean-OCR; PaddleOCR-VL','TextHawk2; DeepSeek-OCR; Qwen3-VL'],BLUE),
    ])


def table_capabilities():
    capability_grid('fig05.pdf','Complementary capabilities for table question answering',
      'A system can combine representation learning, context selection, generation and program execution.',[
      ('Structure representations',
       ['Encode row / column relations','and table-text associations.','Known structure is assumed.'],
       ['OmniTab; FORTAP; ReasTAP','AIT-QA; FeTaQA (benchmarks)'],BLUE),
      ('Generation and selection',
       ['Tune, decompose or select','question-relevant table context.','May omit relevant cells.'],
       ['Table-GPT; TableGPT2; CABINET','Chain-of-Table; TabSQLify'],GREEN),
      ('Execution and feedback',
       ['Use SQL, code or tool feedback','to evaluate an explicit plan.','Valid code can use wrong data.'],
       ['OpenTab; Weaver; TaPERA','Plan-of-SQLs reasoning'],WARM),
    ],columns=3,footer='Report answer correctness, evidence grounding and execution validity separately; none implies the others.')


def agentic_evidence_flow():
    path=ROOT/'figs_by_qixingyu/fig08.pdf'
    c=canvas.Canvas(str(path),pagesize=(600,224),pageCompression=1,invariant=1)
    c.setTitle('Illustrative document QA control loop with evidence-linked output')
    text(c,14,204,'Illustrative document QA control and evidence flow',13.3,True,color=RED)
    text(c,14,187,'Tools and iterative retrieval are optional system choices, not a guarantee of reliable reasoning.',9.1,color=MUTED)
    cards=[
      (14,88,'Question',['Natural-language','question with a','document or corpus'],WARM),
      (117,98,'Query planning',['Interpret the query;','decompose only','when useful.'],BLUE),
      (230,111,'Evidence access',['Text / visual retrieval','and reranking, or','provided context.'],GREEN),
      (356,111,'Reasoning / tools',['Compose evidence;','use SQL, code or','other tools if needed.'],BLUE),
      (482,104,'Answer + evidence',['Link supporting regions.','Uncertainty signal','when available.'],WARM),
    ]
    for x,w,title,lines,fill in cards:
        panel(c,x,71,w,98,fill)
        text(c,x+w/2,148,title,9.8,True,align='center')
        for i,line in enumerate(lines):text(c,x+w/2,128-i*14,line,8.7,align='center')
    for x1,x2 in [(102,117),(215,230),(341,356),(467,482)]:arrow(c,x1,118,x2,118)
    c.setStrokeColor(MUTED);c.setLineWidth(.8);c.setDash(3,2)
    c.line(411.5,71,411.5,47);c.line(411.5,47,285.5,47)
    c.setDash();arrow(c,285.5,47,285.5,71)
    text(c,348.5,32,'Optional retrieval / tool iteration',9.0,color=MUTED,align='center')
    text(c,14,12,'Located evidence, successful execution and an uncertainty signal must be evaluated separately.',8.5,color=MUTED)
    save_and_copy(c,path)


if __name__=='__main__':
    overview();ocr_designs();table_capabilities();rag_mechanisms();agentic_evidence_flow()
