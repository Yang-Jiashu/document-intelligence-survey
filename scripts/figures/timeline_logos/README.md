# Timeline visual assets

These are unmodified official GitHub organization avatars fetched on 10 November 2026. `sources.json` records each exact source URL and the papers associated with that organization or project. The marks provide visual attribution and do not imply an endorsement or that an individual model has its own logo.

Papers without a verified brand asset use original task glyphs drawn by the renderer. Dates and trained-weight qualifications remain in `../document_timeline_sources.json`; this visual update does not advance their verification date.

Regenerate the linked PDF and standalone SVG with:

```sh
python3 scripts/figures/build_document_timeline.py
```

The script requires ReportLab, uses cached assets, keeps the existing 1100 by 480 PDF page size, verifies all 27 entries are represented once, checks label separation, and checks leaders against every label and logo envelope. The optional PNG is a 2x rendering of that PDF.
