#!/usr/bin/env bash
# Build the full technical report with only checkout-local runtime state.
set -euo pipefail
paper_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
paper_output="${1:-$paper_root/.build/paper}"
mkdir -p -- "$paper_output"
paper_output="$(cd -- "$paper_output" && pwd)"

python3 "$paper_root/scripts/sync_paper_sources.py"

# Complete TeX Live installations need no environment overrides. Some minimal
# images contain all sources/fonts but omit format files and the filename DB.
# In that case prepare only local formats/maps; never modify the system tree.
if ! kpsewhich -engine=pdftex pdflatex.fmt >/dev/null 2>&1 || ! kpsewhich latex.ltx >/dev/null 2>&1; then
    paper_cache="$paper_output/tex-cache"
    mkdir -p -- "$paper_cache"
    export TEXMF="{/usr/share/texlive/texmf-dist,/usr/share/texmf}"
    export TEXMFVAR="$paper_cache"
    export TEXMFCONFIG="$paper_cache"
    export TEXFORMATS="$paper_cache:"
    if [[ ! -s "$paper_cache/pdflatex.fmt" ]]; then
        (cd -- "$paper_cache" && pdftex -ini -etex -jobname=pdflatex -interaction=nonstopmode -halt-on-error pdflatex.ini > format.log 2>&1)
    fi
    if ! kpsewhich pdftex.map >/dev/null 2>&1; then
        python3 - "$paper_cache/pdftex.map" <<'PY'
from pathlib import Path
import sys
paths = [Path('/usr/share/texmf/fonts/map/dvips/lm/lm.map')]
for directory in ('amsfonts', 'zapfding', 'symbol'):
    paths.extend(Path('/usr/share/texlive/texmf-dist/fonts/map/dvips', directory).glob('*.map'))
entries = {}
for path in paths:
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('%'):
                entries.setdefault(line.split()[0], line)
Path(sys.argv[1]).write_text('\n'.join(entries.values()) + '\n')
PY
        export TEXFONTMAPS="$paper_cache:"
    fi
fi

cd -- "$paper_root/doc"
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir="$paper_output" main.tex > "$paper_output/build.log" 2>&1 || {
    tail -80 "$paper_output/build.log" >&2
    exit 1
}
python3 - "$paper_output/main.log" <<'PY'
from pathlib import Path
import re
import sys
text = Path(sys.argv[1]).read_text(errors='replace')
errors = re.findall(r'(?:There were undefined (?:references|citations)|Citation [^\n]* undefined|Reference [^\n]* undefined|[^\n]*multiply defined[^\n]*)', text)
if errors:
    print('\n'.join(errors), file=sys.stderr)
    raise SystemExit(1)
print('References and citations resolved; overfull boxes:', len(re.findall(r'Overfull \\[hv]box', text)))
PY
printf 'Built %s\n' "$paper_output/main.pdf"
