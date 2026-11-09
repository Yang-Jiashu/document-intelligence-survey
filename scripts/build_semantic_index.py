"""Build a deterministic, offline TF-IDF/LSA search index using only stdlib.

This is a small corpus-specific latent topic index, not pretrained embeddings or
an LLM.  The browser adds bilingual domain concepts and always requires a real
term or concept anchor before using the latent score. No network access occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAPERS = ROOT / "docs/data/paper_index.json"
DEFAULT_UPDATES = ROOT / "docs/data/research_updates.json"
DEFAULT_OUTPUT = ROOT / "docs/data/semantic_index.json"
MODULE_PATH = ROOT / "docs/js/semantic-search.js"
STOPWORDS = set("a an and are as at be been by can could did do does for from how i in into is it its may model models of on or our that the their these they this to using use used uses was we were what when where which who why will with without would you your document documents paper papers method methods approach approaches study studies understanding new based system systems research find search looking want need learn about tell me".split())


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"\s+", " ", re.sub(r"[‐‑‒–—−_-]+", " ", text)).strip()


def tokenize(value: object) -> list[str]:
    result = []
    for word in re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)*|[\u3400-\u9fff]+", normalize(value)):
        if "\u3400" <= word[0] <= "\u9fff":
            result.extend(word[i:i + 2] for i in range(max(1, len(word) - 1)))
        elif len(word) > 1 and word not in STOPWORDS:
            result.append(word)
    return result


def contains(text: str, phrase: str) -> bool:
    needle = normalize(phrase)
    if re.search(r"[\u3400-\u9fff]", needle):
        return needle in text
    return bool(re.search(r"(?:^|[^a-z0-9])" + re.escape(needle) + r"(?:$|[^a-z0-9])", text))


def source_key(item: dict) -> str:
    arxiv = re.sub(r"v\d+$", "", re.sub(r"^arxiv:", "", str(item.get("arxiv") or ""), flags=re.I), flags=re.I)
    if not arxiv and str(item.get("id", "")).startswith("arxiv:"):
        arxiv = re.sub(r"v\d+$", "", item["id"][6:], flags=re.I)
    if not arxiv:
        match = re.match(r"^https://(?:export\.)?arxiv\.org/(?:abs|pdf)/(.+?)(?:\.pdf)?$", str(item.get("url") or ""))
        if match:
            arxiv = re.sub(r"v\d+$", "", match[1], flags=re.I)
    if re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z.-]+/\d{7})", arxiv, re.I):
        return "arxiv:" + arxiv.lower()
    if str(item.get("id", "")).startswith("github:"):
        return item["id"].lower()
    if item.get("bibKey"):
        return "bib:" + str(item["bibKey"])
    return "title:" + normalize(item.get("title"))


def fingerprint(item: dict) -> str:
    def joined(field):
        return "|".join(str(value) for value in item[field]) if isinstance(item.get(field), list) else ""
    fields = [str(item.get("title") or ""), str(item.get("abstract") or "")[:7000],
              str(item.get("updated") or ""), joined("tags"), joined("topics"),
              str(item.get("category") or ""), joined("categories")]
    text = json.dumps(fields, ensure_ascii=False, separators=(",", ":")).encode("utf-16-le")
    value = 2166136261
    for position in range(0, len(text), 2):
        value = ((value ^ (text[position] + 256 * text[position + 1])) * 16777619) & 0xffffffff
    return f"{value:08x}"


def load_concepts(path: Path = MODULE_PATH) -> list[dict]:
    match = re.search(r"const CONCEPTS = (\[.*?\]);", path.read_text(encoding="utf-8"), re.S)
    if not match:
        raise ValueError("Domain concepts are missing from semantic-search.js")
    return json.loads(match[1])


def item_terms(item: dict, concepts: list[dict]) -> Counter:
    def values(field):
        value = item.get(field) or []
        return value if isinstance(value, list) else [str(value)]
    title = normalize(item.get("title"))
    tags = normalize(" ".join(str(value) for field in ("tags", "category", "categories", "subcategory", "subcategories", "topics") for value in values(field)))
    body = normalize(str(item.get("abstract") or "")[:7000])
    result = Counter(tokenize(title) * 3 + tokenize(tags) * 2 + tokenize(body))
    topics = set(values("category") + values("categories") + values("topics"))
    for concept in concepts:
        matches = any(contains(title + " " + tags + " " + body, term) for term in concept["document"])
        if matches or topics.intersection(concept["topics"]):
            result["__concept_" + concept["id"]] += 3 if matches else 1
    return result


def orthonormalize(matrix: list[list[float]]) -> list[list[float]]:
    """Modified Gram-Schmidt with reorthogonalization, columns in row storage."""
    if not matrix:
        return []
    columns = []
    for column in zip(*matrix):
        vector = list(column)
        for _ in range(2):
            for previous in columns:
                dot = sum(x * y for x, y in zip(vector, previous))
                vector = [x - dot * y for x, y in zip(vector, previous)]
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 1e-10:
            columns.append([x / norm for x in vector])
    return [list(row) for row in zip(*columns)] if columns else []


def symmetric_eigen(matrix: list[list[float]]) -> tuple[list[float], list[list[float]]]:
    """Jacobi rotation for the tiny symmetric (at most 32x32) covariance."""
    size = len(matrix)
    values = [row[:] for row in matrix]
    vectors = [[float(i == j) for j in range(size)] for i in range(size)]
    for _ in range(max(1, size * size * 40)):
        off = [(abs(values[i][j]), i, j) for i in range(size) for j in range(i + 1, size)]
        if not off:
            break
        largest, p, q = max(off)
        if largest < 1e-10:
            break
        angle = .5 * math.atan2(2 * values[p][q], values[q][q] - values[p][p])
        c, s = math.cos(angle), math.sin(angle)
        pp, qq, pq = values[p][p], values[q][q], values[p][q]
        for i in range(size):
            if i != p and i != q:
                ip, iq = values[i][p], values[i][q]
                values[i][p] = values[p][i] = c * ip - s * iq
                values[i][q] = values[q][i] = s * ip + c * iq
            vp, vq = vectors[i][p], vectors[i][q]
            vectors[i][p], vectors[i][q] = c * vp - s * vq, s * vp + c * vq
        values[p][p] = c * c * pp - 2 * s * c * pq + s * s * qq
        values[q][q] = s * s * pp + 2 * s * c * pq + c * c * qq
        values[p][q] = values[q][p] = 0
    order = sorted(range(size), key=lambda i: (-values[i][i], i))
    return [max(0, values[i][i]) for i in order], [[row[i] for i in order] for row in vectors]


def lsa_projection(rows: list[list[tuple[int, float]]], vocabulary_size: int, dimensions: int) -> list[list[float]]:
    """Deterministic randomized subspace SVD: A≈Q B, then a small eigensolve."""
    size = min(dimensions, len(rows), vocabulary_size)
    randomizer = random.Random(48271)
    q = orthonormalize([[randomizer.gauss(0, 1) for _ in range(size)] for _ in rows])
    for _ in range(3):
        size = len(q[0])
        atq = [[0.0] * size for _ in range(vocabulary_size)]
        for row, qrow in zip(rows, q):
            for term, weight in row:
                for j in range(size):
                    atq[term][j] += weight * qrow[j]
        q = orthonormalize([[sum(weight * atq[term][j] for term, weight in row) for j in range(size)] for row in rows])
    size = len(q[0])
    atq = [[0.0] * size for _ in range(vocabulary_size)]
    for row, qrow in zip(rows, q):
        for term, weight in row:
            for j in range(size):
                atq[term][j] += weight * qrow[j]
    covariance = [[sum(row[i] * row[j] for row in atq) for j in range(size)] for i in range(size)]
    eigenvalues, eigenvectors = symmetric_eigen(covariance)
    active = [j for j, value in enumerate(eigenvalues) if value > 1e-10]
    return [[sum(row[i] * eigenvectors[i][j] for i in range(size)) / math.sqrt(eigenvalues[j]) for j in active] for row in atq]


def build_index(papers: list[dict], updates: list[dict], *, dimensions: int = 16, max_terms: int = 1400) -> dict:
    concepts = load_concepts()
    groups = defaultdict(list)
    for item in papers + updates:
        if isinstance(item, dict) and item.get("title"):
            groups[source_key(item)].append(item)
    if not groups:
        raise ValueError("Cannot build an index from an empty corpus")
    keys = sorted(groups)
    counters = []
    for key in keys:
        # The same arXiv paper can occur in the bibliography and recent feed.
        # Take maximum counts rather than doubling repeated words.
        counts = Counter()
        for item in groups[key]:
            counts |= item_terms(item, concepts)
        counters.append(counts)
    frequency = Counter(term for counter in counters for term in counter)
    totals = sum(counters, Counter())
    # Domain features are always preserved. Remaining vocabulary prefers useful
    # corpus-wide words; one-off paper/model names still qualify for exact text.
    selected = sorted(frequency, key=lambda term: (not term.startswith("__concept_"), -frequency[term] * math.log(1 + totals[term]), term))[:max_terms]
    terms = sorted(selected)
    positions = {term: i for i, term in enumerate(terms)}
    idf = [1 + math.log((1 + len(keys)) / (1 + frequency[term])) for term in terms]
    rows = []
    for counter in counters:
        row = [(positions[term], (1 + math.log(count)) * idf[positions[term]]) for term, count in sorted(counter.items()) if term in positions]
        norm = math.sqrt(sum(weight * weight for _, weight in row)) or 1
        rows.append([(term, weight / norm) for term, weight in row])
    projection = lsa_projection(rows, len(terms), dimensions)
    actual_dimensions = len(projection[0])
    documents = {}
    for key, row in zip(keys, rows):
        vector = [sum(weight * projection[term][j] for term, weight in row) for j in range(actual_dimensions)]
        norm = math.sqrt(sum(value * value for value in vector)) or 1
        documents[key] = {"fingerprints": sorted({fingerprint(item) for item in groups[key]}), "vector": [round(value / norm, 7) for value in vector]}
    input_fingerprint = hashlib.sha256(json.dumps([[key, documents[key]["fingerprints"]] for key in keys], separators=(",", ":")).encode()).hexdigest()
    return {"schemaVersion": 1, "scope": "document-intelligence", "algorithm": "tfidf-lsa+domain-concepts", "dimensions": actual_dimensions,
            "terms": terms, "idf": [round(value, 7) for value in idf], "projection": [[round(value, 7) for value in row] for row in projection],
            "documents": documents, "inputFingerprint": input_fingerprint}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--papers", type=Path, default=DEFAULT_PAPERS)
    parser.add_argument("--updates", type=Path, default=DEFAULT_UPDATES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dimensions", type=int, default=16, choices=range(1, 33), metavar="1..32")
    parser.add_argument("--max-terms", type=int, default=1400)
    args = parser.parse_args()
    if not 32 <= args.max_terms <= 3000:
        parser.error("--max-terms must be between 32 and 3000")
    papers = json.loads(args.papers.read_text(encoding="utf-8")).get("papers", [])
    updates = json.loads(args.updates.read_text(encoding="utf-8")).get("papers", [])
    result = build_index(papers, updates, dimensions=args.dimensions, max_terms=args.max_terms)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Offline topic index: {len(result['documents'])} documents, {len(result['terms'])} terms, {result['dimensions']} dimensions → {args.output}")


if __name__ == "__main__":
    main()
