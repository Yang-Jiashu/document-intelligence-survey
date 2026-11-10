# Curved chronology layout - 10 November 2026

- Retained all 62 selected works, including 12 from 2026, the four research directions and the smaller model labels/icons.
- Replaced aligned year columns and parallel horizontal rails with an asymmetric curved composition, staggered branch origins and angled leaders. Year labels follow the local curves; the layout does not assert a linear time scale or model genealogy.
- Recompiled the complete manuscript to 65 pages with resolved references and no overfull boxes. Preserved the full bibliography and all 102 paper/checkpoint links in the chronology; updated the paper download after rendering the figure in context.

# Branched chronology through 2026 - 10 November 2026

- Expanded the paper chronology from 27 to 62 representative works and evaluation resources, including 12 first published in 2026 and a historically dated Tesseract 2007 paper anchor.
- Replaced the single curve with four coexisting directions: OCR/layout, document models/VQA, structured/table reasoning, and document retrieval/agents. Grouped year bands and a caption distinguish this reading map from model genealogy.
- Reduced native model labels from about 20.7pt to 17.5pt and logos from 22pt to 19pt. Kept official checkpoint qualification separate from code availability; benchmarks and unverified releases stay unhighlighted.
- Added primary-paper bibliography entries for the new 2026 examples and corrected DocLayNet's arXiv identifier to 2206.01062.
- Kept the full literature body and the homepage layout/traffic statistics. Updated the manuscript download only.

# Full-coverage restoration - 10 November 2026

- Restored the detailed literature discussions to the main manuscript across all six shared chapters, retaining all 412 distinct works cited by the pre-condensation full manuscript. The earlier 22-page condensation removed too much substantive coverage; the supplementary reading catalog is no longer used as a substitute for the main survey.
- Restored the fuller abstract, review scope, selection principles, evidence-centered comparison framework and research outlook. Preserved the corrected author order and factual qualifications from the pre-condensation revision.
- Kept the revised curved chronology, representation examples, table computation, retrieval structures, visual-budget diagram, adaptive document-access loop and evaluation cases. Figure captions continue to describe their actual content, with constructed examples distinguished from empirical results.
- Recompiled the restored manuscript to 64 pages with pdfLaTeX and BibTeX. The final build resolves all citations and references, with no overfull boxes or multiply defined labels.
- Kept the website layout and bottom traffic statistics. Updated only the manuscript download and its revision label.

The sections below describe earlier revisions and are retained as history.

# Visual and editorial revision - 10 November 2026

- Replaced the paper-by-paper narrative with a mechanism-led synthesis. Main-source word count (including captions/tables) falls from 21,696 to 6,371, approximately 71%; the validated report is 22 pages (16 main-text pages and 6 reference pages), down from 65 pages.
- Redrew every figure used by the main manuscript as a shape-led vector illustration: page regions, OCR tokens, cells, document trees, evidence graphs, crops, tool loops and worked source-to-answer traces. Short captions carry qualifications formerly placed in text cards.
- Removed the redundant taxonomy and date-by-focus matrices from the main manuscript; retained one compact representative chronology with linked primary metadata.
- Preserved the complete broader reading catalog in supplementary/literature/ and kept all 410 website records and category assignments unchanged. The main reference list now contains only works actually used in its synthesis.
- Preserved JiaShu Yang's first-author position, the larger homepage type, the color scholar portraits and the free update/search workflow.

# Manuscript revision - 9 November 2026

This revision preserves the full literature chapters and uses one set of section sources for the report and ACL entry points.

## Substantive changes

- Rewrote the abstract, introduction and conclusion around evidence preservation, retrieval, composition and verification.
- Defined five complementary comparison axes: input representation, context span, evidence granularity, inference control and validation. Chapter topics remain a reading order and permit overlapping membership.
- Added qualitative comparisons of perception routes, table reasoning methods and multimodal document systems, together with a benchmark capability matrix and comparison protocol.
- Distinguished answer accuracy, evidence localization, evidence support and executable computation. Explicitly stated that this survey reports literature results and introduces no newly run model benchmark.
- Replaced linear replacement narratives with conditional comparisons of OCR, direct-visual, hybrid, retrieval and agent-controlled approaches. Restricted the MMLongBench-Doc comparison to the original 2024 experimental setting.
- Corrected VISTA-OCR, Ocean-OCR, DocParseNet and DocLLM descriptions; corrected OCRBench's 29 datasets; repaired Table-GPT author names and distinguished InfographicVQA's 2021 preprint from WACV 2022 publication.
- Rebuilt affected vector diagrams to align routes, dates and capability labels with the revised text. Removed the unprovenanced performance flower plot from the manuscript; its historical source asset is retained.
- Added three original vector figures: a curved representative document-AI chronology, a worked cross-page financial-report example and four concrete evaluation traces. Chronology uses first-public-paper dates; public-checkpoint availability is verified separately against official project/model pages and stored in `scripts/figures/document_timeline_sources.json`. The worked examples contain explicitly constructed documents and numbers, not empirical predictions.
- Restored the project page's three official scholar portraits to their original color by removing the grayscale/sepia CSS filter, preserving the larger reading typography.
- Set the manuscript author order to JiaShu Yang, Chi Zhang, Xingyu Qi, Ning Zhang, Jie Wu, Lingxu Chen and Jiani Guo, matching the current project page and source instruction.

## Evidence for key corrections

| Work | Source | Correction |
| --- | --- | --- |
| VISTA-OCR | https://arxiv.org/html/2504.03621v1, Section 3.3 | CNN encoder and autoregressive Transformer decoder; not a diffusion model |
| Ocean-OCR | https://arxiv.org/html/2501.15558v1, Section 3.1 | NaViT, MLP projector and Qwen2.5-3B; remove unsupported 100-language evaluation claim |
| DocParseNet | https://arxiv.org/abs/2406.17591 | Document annotation/segmentation with OCR text features; not merely table recognition |
| DocLLM | https://aclanthology.org/2024.acl-long.463/ | Text and bounding boxes, without an image encoder |
| OCRBench | https://arxiv.org/abs/2305.07895 | 29 datasets, not 29 task types |
| MMLongBench-Doc | https://arxiv.org/abs/2407.01523 | Conditional comparison tied to original models and protocol |
| InfographicVQA | https://arxiv.org/abs/2104.12756 | Correct paper identifier; preprint 2021, WACV 2022 |
| Table-GPT | https://arxiv.org/abs/2310.09263 | Correct author name ordering and preprint/venue distinction |

These are focused checks of representative mechanisms and metadata. The revision does not claim independent reproduction of every cited result or exhaustive verification of the bibliography.

## Source and publication status

The build helpers synchronize the complete section corpus into the report and ACL formats before compilation. The revised downloadable manuscript is a separate revision; an archived Zenodo record requires its own version update.
