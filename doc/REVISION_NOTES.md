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
