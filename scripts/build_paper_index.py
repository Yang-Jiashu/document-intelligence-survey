from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BIB_PATH = ROOT / "paper_latex" / "latex" / "custom.bib"
SECTIONS_DIR = ROOT / "paper_latex" / "latex" / "sections"
OUT_PATH = ROOT / "docs" / "data" / "paper_index.json"


CATEGORY_CONFIG = {
    "ocr": {
        "file": "ocr.tex",
        "icon": "OCR",
        "title": "OCR & Text Recognition",
        "desc": "Optical Character Recognition, scene text, handwritten text",
        "children": ["Traditional OCR", "Deep Learning OCR", "OCR-VLM", "OCR Evaluation"],
    },
    "layout": {
        "file": "layout.tex",
        "icon": "LAY",
        "title": "Layout Analysis",
        "desc": "Document structure detection, region segmentation, reading order",
        "children": ["Geometric Detection", "Layout-Aware Learning", "Layout Reasoning", "Layout Evaluation"],
    },
    "table": {
        "file": "table.tex",
        "icon": "TAB",
        "title": "Table Understanding",
        "desc": "Table detection, structure recognition, table QA",
        "children": ["Structure-Aware Modeling", "Generation Enhancement", "Verifiable Reasoning", "Multimodal Tables"],
    },
    "rag": {
        "file": "text.tex",
        "icon": "RAG",
        "title": "Retrieval-Augmented Generation",
        "desc": "Document RAG, long-context understanding, multi-hop reasoning",
        "children": ["Unimodal RAG", "Long Document QA", "Graph Reasoning", "End-to-end QA"],
    },
    "vlm": {
        "file": "multi.tex",
        "icon": "VLM",
        "title": "Vision-Language Models",
        "desc": "VLM for document understanding, OCR-free methods, multimodal reasoning",
        "children": ["Document VLM", "OCR-free Models", "High-resolution VLM", "Multimodal RAG"],
    },
    "eval": {
        "file": "eval.tex",
        "icon": "EVAL",
        "title": "Evaluation & Benchmarks",
        "desc": "Datasets, metrics, benchmark suites for document intelligence",
        "children": ["Visual Document QA", "Document QA Evaluation", "RAG Evaluation", "Real-world Benchmarks"],
    },
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def clean_latex(value: str) -> str:
    value = value.replace("\n", " ")
    value = value.replace("\\&", "&").replace("\\_", "_").replace("\\%", "%")
    value = value.replace("---", "-").replace("--", "-").replace("~", " ")
    value = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", value)
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ,")


def split_bib_entries(text: str) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    i = 0
    while i < len(text):
        at = text.find("@", i)
        if at == -1:
            break
        brace = text.find("{", at)
        if brace == -1:
            break
        entry_type = text[at + 1 : brace].strip().lower()
        depth = 0
        end = brace
        while end < len(text):
            ch = text[end]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            end += 1
        raw = text[brace + 1 : end]
        comma = raw.find(",")
        if comma != -1:
            key = raw[:comma].strip()
            body = raw[comma + 1 :]
            entries.append((entry_type, key, body))
        i = end + 1
    return entries


def parse_field_value(body: str, start: int) -> tuple[str, int]:
    i = start
    while i < len(body) and body[i].isspace():
        i += 1
    if i >= len(body):
        return "", i

    if body[i] == "{":
        depth = 0
        j = i
        while j < len(body):
            if body[j] == "{":
                depth += 1
            elif body[j] == "}":
                depth -= 1
                if depth == 0:
                    return body[i + 1 : j], j + 1
            j += 1
        return body[i + 1 :], len(body)

    if body[i] == '"':
        j = i + 1
        escaped = False
        while j < len(body):
            if body[j] == '"' and not escaped:
                return body[i + 1 : j], j + 1
            escaped = body[j] == "\\" and not escaped
            if body[j] != "\\":
                escaped = False
            j += 1
        return body[i + 1 :], len(body)

    j = i
    while j < len(body) and body[j] not in ",\n":
        j += 1
    return body[i:j], j


def parse_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    pattern = re.compile(r"([A-Za-z][A-Za-z0-9_-]*)\s*=\s*")
    pos = 0
    while True:
        match = pattern.search(body, pos)
        if not match:
            break
        name = match.group(1).lower()
        raw_value, end = parse_field_value(body, match.end())
        fields[name] = clean_latex(raw_value)
        pos = end + 1
    return fields


def parse_bib(path: Path) -> dict[str, dict[str, str]]:
    text = read_text(path)
    parsed: dict[str, dict[str, str]] = {}
    for entry_type, key, body in split_bib_entries(text):
        fields = parse_fields(body)
        fields["entryType"] = entry_type
        fields["bibKey"] = key
        fields["_raw"] = body
        parsed[key] = fields
    return parsed


def extract_arxiv(fields: dict[str, str]) -> str:
    for candidate in (fields.get("eprint", ""), fields.get("url", ""), fields.get("journal", ""), fields.get("_raw", "")):
        match = re.search(r"(?:arxiv:|arxiv\.org/(?:abs|pdf)/)([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)", candidate, re.I)
        if match:
            return match.group(1)
    return ""


def normalize_authors(authors: str) -> str:
    authors = re.sub(r"\s+and\s+", ", ", authors)
    return re.sub(r"\s+", " ", authors).strip()


def venue_from_fields(fields: dict[str, str]) -> str:
    venue = fields.get("booktitle") or fields.get("journal") or fields.get("publisher") or fields.get("entryType", "")
    if re.search(r"arxiv preprint", venue, re.I):
        return f"arXiv {fields.get('year', '').strip()}".strip()
    return venue


def find_section_citations() -> dict[str, list[dict[str, str]]]:
    cite_pattern = re.compile(r"\\cite[a-zA-Z]*\s*(?:\[[^\]]*\]){0,2}\s*\{([^}]+)\}")
    heading_pattern = re.compile(r"\\(subsection|subsubsection|paragraph)\*?\{([^}]+)\}")
    occurrences: dict[str, list[dict[str, str]]] = defaultdict(list)

    for category, config in CATEGORY_CONFIG.items():
        path = SECTIONS_DIR / config["file"]
        current_subsection = config["title"]
        current_subsubsection = config["title"]
        current_paragraph = ""

        for line_no, line in enumerate(read_text(path).splitlines(), start=1):
            for heading in heading_pattern.finditer(line):
                level, title = heading.groups()
                title = clean_latex(title)
                if level == "subsection":
                    current_subsection = title
                    current_subsubsection = title
                    current_paragraph = ""
                elif level == "subsubsection":
                    current_subsubsection = title
                    current_paragraph = ""
                elif level == "paragraph":
                    current_paragraph = title

            for cite in cite_pattern.finditer(line):
                keys = [key.strip() for key in cite.group(1).split(",") if key.strip()]
                for key in keys:
                    occurrences[key].append(
                        {
                            "category": category,
                            "section": current_subsection,
                            "subcategory": current_subsubsection,
                            "topic": current_paragraph,
                            "sourceFile": config["file"],
                            "line": line_no,
                        }
                    )
    return occurrences


def unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def build_index() -> dict[str, object]:
    bib = parse_bib(BIB_PATH)
    occurrences = find_section_citations()
    papers = []

    for idx, key in enumerate(sorted(occurrences.keys()), start=1):
        fields = bib.get(key)
        if not fields:
            continue

        refs = occurrences[key]
        categories = unique([ref["category"] for ref in refs])
        subcategories = unique([ref["subcategory"] for ref in refs])
        topics = unique([ref["topic"] for ref in refs])
        primary_category = categories[0] if categories else "uncategorized"
        title = fields.get("title") or key
        year_text = fields.get("year") or "0"
        year_match = re.search(r"\d{4}", year_text)
        year = int(year_match.group(0)) if year_match else 0
        arxiv = extract_arxiv(fields)
        url = fields.get("url", "")

        tags = unique(categories + subcategories + topics)
        papers.append(
            {
                "id": idx,
                "bibKey": key,
                "title": title,
                "authors": normalize_authors(fields.get("author", "")),
                "venue": venue_from_fields(fields),
                "year": year,
                "category": primary_category,
                "categories": categories,
                "subcategory": subcategories[0] if subcategories else "",
                "subcategories": subcategories,
                "topics": topics,
                "tags": tags,
                "arxiv": arxiv,
                "url": url,
                "github": "",
                "stars": 0,
            }
        )

    papers.sort(key=lambda paper: (-paper["year"], paper["title"].lower()))
    for idx, paper in enumerate(papers, start=1):
        paper["id"] = idx

    taxonomy = []
    for category, config in CATEGORY_CONFIG.items():
        count = sum(1 for paper in papers if category in paper["categories"])
        taxonomy.append(
            {
                "id": category,
                "icon": config["icon"],
                "title": config["title"],
                "desc": config["desc"],
                "children": config["children"],
                "count": count,
            }
        )

    return {
        "source": {
            "bib": str(BIB_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sections": str(SECTIONS_DIR.relative_to(ROOT)).replace("\\", "/"),
            "bibEntries": len(bib),
            "citedPapers": len(papers),
        },
        "taxonomy": taxonomy,
        "papers": papers,
    }


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(build_index(), ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
