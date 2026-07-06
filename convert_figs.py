import fitz
import os

pdf_dir = "/Users/jiashuyang/Downloads/Beyond_OCR__A_Survey_of_Document_Intelligence_from_Structured_Perception_to_Multimodal_Question_Answering/doc/figs"
img_dir = "/Users/jiashuyang/Downloads/Beyond_OCR__A_Survey_of_Document_Intelligence_from_Structured_Perception_to_Multimodal_Question_Answering/demo/images"

for i in range(1, 11):
    pdf_path = os.path.join(pdf_dir, f"fig{i:02d}.pdf")
    if os.path.exists(pdf_path):
        doc = fitz.open(pdf_path)
        page = doc[0]
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        img_path = os.path.join(img_dir, f"fig{i:02d}.png")
        pix.save(img_path)
        print(f"Converted {pdf_path} -> {img_path}")
        doc.close()

print("Done converting all figures!")
