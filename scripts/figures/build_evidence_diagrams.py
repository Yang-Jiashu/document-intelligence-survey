#!/usr/bin/env python3
"""Rebuild the current shape-led survey figures (legacy command entry point).

Figures 01/02/05 use document and cell primitives; 06/08/15 use retrieval,
control and patch-interaction schematics. Long text-card generators were
replaced in the 10 November 2026 visual revision.
"""
from pathlib import Path
import runpy

if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    for script in ("build_visual_foundations.py", "build_visual_retrieval.py"):
        runpy.run_path(str(folder / script), run_name="__main__")
