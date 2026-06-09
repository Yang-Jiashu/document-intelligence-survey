# Pin the build to pdfLaTeX, which this template requires (the custom TTF font
# setup in style.cls uses pdfTeX's \pdfmapline and will not work under
# xelatex / lualatex). latexmk will also run bibtex automatically.
$pdf_mode  = 1;   # 1 = pdflatex
$bibtex_use = 2;  # run bibtex when a .bib is present
$max_repeat = 5;  # allow enough passes to resolve refs/citations
