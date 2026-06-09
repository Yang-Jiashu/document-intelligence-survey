# Beyond OCR: A Survey of Document Intelligence
## PKU Technical Report Version

This is the PKU Technical Report template version of the survey paper "Beyond OCR: A Survey of Document Intelligence from Structured Perception to Multimodal Question Answering".

### File Structure

```
PKU_Technical_Report/
├── main.tex              # Main document file
├── main.bib              # Complete bibliography (3248+ entries)
├── style.cls             # PKU style class (do not modify)
├── resources/            # Fonts and PKU logo
│   ├── packages.tex      # Package definitions
│   ├── pku.png           # PKU logo
│   └── *.ttf, *.tfm      # Custom fonts
├── figs/                 # Figures
│   ├── fig01.pdf - fig10.pdf  # Survey figures
│   └── icons/            # Project page icons
├── sec/                  # Section files
│   ├── 0_abstract.tex    # Abstract
│   ├── 1_intro.tex       # Introduction
│   ├── 2_layout_ocr.tex  # Document Layout Analysis and OCR
│   ├── 3_table.tex       # Table Understanding
│   ├── 4_text_rag.tex    # Text-based RAG
│   ├── 5_vlm.tex         # Vision-Language Models
│   ├── 6_eval.tex        # Evaluation
│   └── 7_conclusion.tex  # Conclusion and Future Directions
└── tabs/                 # Tables (empty, for future use)
```

### Compilation

**Important:** This template requires **pdfLaTeX** (not XeLaTeX or LuaLaTeX).

#### Using LaTeX Workshop (VSCode)
1. Open `main.tex` in VSCode
2. Use the default "latexmk" recipe (already configured for pdfLaTeX)
3. The `.latexmkrc` file pins the build to pdfLaTeX

#### Command Line
```bash
# Recommended (automatically runs bibtex and multiple passes)
latexmk -pdf main.tex

# Or manually:
pdflatex main
bibtex main
pdflatex main
pdflatex main
```

### Requirements

- **TeX Live 2024/2025** (full installation recommended)
- Required packages (included in full TeX Live):
  - `tcolorbox`, `titlesec`, `natbib`, `cleveref`, `nicematrix`
  - `booktabs`, `multirow`, `hyperref`
  - `mwe` (for placeholder images, though not used in this survey)

### Content Overview

This survey covers:

**Part I: Perception**
- Document Layout Analysis (geometric detection, layout-aware representation, reasoning)
- OCR (traditional methods, deep learning, VLM-based approaches)

**Part II: Understanding**
- Table Understanding (structure-aware modeling, modular reasoning, verifiable reasoning)
- Text-based Retrieval-Augmented Generation (RAG evolution, end-to-end QA)
- Vision-Language Models (foundational models, OCR-free approaches, agentic systems)

**Evaluation**
- Visual document understanding benchmarks
- RAG evaluation datasets
- Real-world deployment metrics

### Key Figures

1. **fig01.pdf** - Document Intelligence pipeline overview
2. **fig02.pdf** - OCR evolution (4 stages)
3. **fig03.pdf** - Layout Analysis and OCR methods hierarchy
4. **fig04.pdf** - Document Intelligence milestones timeline
5. **fig05.pdf** - Table understanding evolution (3 stages)
6. **fig06.pdf** - RAG paradigm evolution (5 stages)
7. **fig07.pdf** - VLM evolution for document understanding
8. **fig08.pdf** - Agentic Document QA pipeline
9. **fig09.pdf** - Evaluation datasets (imported from figs_by_qixingyu/fig09.tex)
10. **fig10.pdf** - Benchmark landscape

### Customization

To modify the document:

1. **Title/Authors**: Edit in `main.tex` (lines 25-40)
2. **Abstract**: Edit `sec/0_abstract.tex`
3. **Content**: Edit respective section files in `sec/`
4. **References**: Add new entries to `main.bib`

### Notes

- The `\cref{}` command is used for cross-referencing (requires `cleveref` package)
- The `\pkured{}` command applies PKU brand color (#8C1515) to text
- All figures use `figs/` directory path
- Bibliography uses `plainnat` style with numeric citations

### Troubleshooting

**Issue**: "File `example-image-duck` not found"
- **Solution**: Install `mwe` package: `tlmgr install mwe`
- Note: This survey uses actual PDF figures, not placeholders

**Issue**: Font-related errors
- **Solution**: Ensure you're using pdfLaTeX, not XeLaTeX/LuaLaTeX

**Issue**: Missing citations
- **Solution**: Run `bibtex main` or `latexmk -pdf main.tex` (handles all passes automatically)

### Contact

For questions about this survey, contact: jiashuyang@pku.edu.cn
