#!/usr/bin/env python3
"""Restore URI links lost when LaTeX includes the two-page chronology atlas.

Usage (requires pypdf)::

    python scripts/figures/restore_timeline_links.py \
        .build/clean-paper/main.pdf doc/figs/fig12.pdf .build/paper-linked.pdf

The two source pages have the same MediaBox. A Form is identified by its
decoded content, or by its complete ordered text-show sequence when an importer
adds graphics-state wrappers or renames font resources. A bounding box alone is
never sufficient. Nested Form transforms are respected; existing annotations
are preserved, and rerunning the helper does not duplicate matching URI links.
Exactly one placement of each atlas page is required. Validation precedes an
atomic output write, so missing or ambiguous matches cannot publish a partial
restoration. --dry-run performs the matching without writing an output PDF.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import (
    ArrayObject,
    ByteStringObject,
    ContentStream,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)


def resolved(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def string_bytes(value: Any) -> bytes | None:
    if isinstance(value, ByteStringObject):
        return bytes(value)
    if isinstance(value, TextStringObject):
        try:
            return value.get_original_bytes()
        except Exception:
            return str(value).encode("utf-8")
    return None


def text_fingerprint(stream: ContentStream) -> str:
    """Hash all shown strings in order, independent of fonts and q/Q wrappers.

    Numbers inside a TJ array only adjust kerning and are deliberately omitted.
    Concatenating text runs also tolerates splitting a Tj into an equivalent TJ.
    A title or a few common model names alone cannot identify an atlas page.
    """
    runs: list[bytes] = []
    for operands, operator in stream.operations:
        values: list[Any] = []
        if operator in (b"Tj", b"'"):
            values = [operands[0]]
        elif operator == b'"':
            values = [operands[2]]
        elif operator == b"TJ":
            values = list(operands[0])
        for value in values:
            data = string_bytes(value)
            if data is not None:
                runs.append(data)
    return hashlib.sha256(b"".join(runs)).hexdigest() if runs else ""


@dataclass(frozen=True)
class SourceLink:
    uri: str
    rect: tuple[float, float, float, float]


@dataclass(frozen=True)
class AtlasPage:
    number: int
    bbox: tuple[float, float, float, float]
    content_hash: str
    text_hash: str
    links: tuple[SourceLink, ...]


def uri_links(page: Any) -> tuple[SourceLink, ...]:
    links: list[SourceLink] = []
    for reference in resolved(page.get("/Annots", [])):
        annotation = resolved(reference)
        action = resolved(annotation.get("/A", {}))
        if annotation.get("/Subtype") != "/Link" or action.get("/S") != "/URI":
            continue
        rect = tuple(float(value) for value in annotation["/Rect"])
        if len(rect) != 4 or rect[2] <= rect[0] or rect[3] <= rect[1]:
            raise ValueError("Source atlas contains an invalid URI rectangle")
        links.append(SourceLink(str(action["/URI"]), rect))
    return tuple(links)


def load_atlas(reader: PdfReader) -> tuple[AtlasPage, AtlasPage]:
    if len(reader.pages) != 2:
        raise ValueError(f"Expected a two-page source atlas, got {len(reader.pages)} pages")
    pages: list[AtlasPage] = []
    for number, page in enumerate(reader.pages, 1):
        if int(page.get("/Rotate", 0)) % 360:
            raise ValueError("Rotated atlas source pages are unsupported; normalize them first")
        stream = page.get_contents()
        if stream is None:
            raise ValueError(f"Atlas page {number} has no content")
        links = uri_links(page)
        if not links:
            raise ValueError(f"Atlas page {number} has no URI links to restore")
        pages.append(AtlasPage(
            number=number,
            bbox=tuple(float(value) for value in page.mediabox),
            content_hash=hashlib.sha256(stream.get_data()).hexdigest(),
            text_hash=text_fingerprint(stream),
            links=links,
        ))
    if not all(page.text_hash for page in pages) or pages[0].text_hash == pages[1].text_hash:
        raise ValueError("Source atlas pages lack distinct complete text fingerprints")
    return pages[0], pages[1]


def same_bbox(form: Any, page: AtlasPage) -> bool:
    box = tuple(float(value) for value in form.get("/BBox", []))
    return len(box) == 4 and all(abs(a - b) < 0.01 for a, b in zip(box, page.bbox))


def identify_form(form: Any, writer: PdfWriter, atlas: tuple[AtlasPage, AtlasPage]) -> tuple[AtlasPage, str] | None:
    compatible = [page for page in atlas if same_bbox(form, page)]
    if not compatible:
        return None
    stream = ContentStream(form, writer)
    content_hash = hashlib.sha256(stream.get_data()).hexdigest()
    exact = [page for page in compatible if page.content_hash == content_hash]
    if len(exact) == 1:
        return exact[0], "decoded-content"
    if len(exact) > 1:
        raise ValueError("Ambiguous decoded-content match between atlas pages")
    text_hash = text_fingerprint(stream)
    matches = [page for page in compatible if page.text_hash == text_hash]
    if len(matches) > 1:
        raise ValueError("Ambiguous complete-text match between atlas pages")
    return (matches[0], "complete-text-sequence") if matches else None


def transformed_rect(rect: tuple[float, float, float, float], transform: Transformation) -> tuple[float, float, float, float]:
    # All four corners are needed for rotated or sheared placements.
    left, bottom, right, top = rect
    corners = [transform.apply_on(point) for point in (
        (left, bottom), (left, top), (right, bottom), (right, top)
    )]
    xs, ys = zip(*corners)
    return min(xs), min(ys), max(xs), max(ys)


def link_key(uri: str, rect: tuple[float, float, float, float]) -> tuple[Any, ...]:
    return uri, *(round(value, 3) for value in rect)


def restore_links(paper: Path, source_atlas: Path, output: Path, *, dry_run: bool = False) -> dict[str, Any]:
    atlas_reader = PdfReader(source_atlas)
    atlas = load_atlas(atlas_reader)
    paper_reader = PdfReader(paper)
    writer = PdfWriter(clone_from=paper_reader)
    placements: list[dict[str, Any]] = []

    def walk(stream: ContentStream, resources: Any, initial: Transformation,
             paper_page: int, names: tuple[str, ...], ancestors: frozenset[int]) -> None:
        transform = initial
        stack: list[Transformation] = []
        resources = resolved(resources)
        xobjects = resolved(resources.get("/XObject", {}))
        for operands, operator in stream.operations:
            if operator == b"q":
                stack.append(transform)
            elif operator == b"Q":
                if not stack:
                    raise ValueError(f"Unbalanced graphics state on paper page {paper_page}")
                transform = stack.pop()
            elif operator == b"cm":
                if len(operands) != 6:
                    raise ValueError("Invalid cm transformation")
                transform = Transformation(tuple(float(value) for value in operands)).transform(transform)
            elif operator == b"Do":
                name = operands[0]
                form = resolved(xobjects.get(name))
                if not form or form.get("/Subtype") != "/Form":
                    continue
                object_id = id(form)
                if object_id in ancestors:
                    raise ValueError("Cyclic nested PDF Form resources")
                matrix = tuple(float(value) for value in form.get("/Matrix", [1, 0, 0, 1, 0, 0]))
                form_transform = Transformation(matrix).transform(transform)
                path = names + (str(name),)
                match = identify_form(form, writer, atlas)
                if match:
                    identity, method = match
                    placements.append({
                        "paper_page": paper_page,
                        "atlas_page": identity.number,
                        "xobject": "/".join(name.lstrip("/") for name in path),
                        "match": method,
                        "transform": list(form_transform.ctm),
                        "source_links": len(identity.links),
                        "identity": identity,
                        "ctm": form_transform,
                    })
                    # A matched source page owns its own annotations. Do not
                    # count any nested resources as a second placement.
                    continue
                walk(ContentStream(form, writer), form.get("/Resources", resources),
                     form_transform, paper_page, path, ancestors | {object_id})

    for index, page in enumerate(writer.pages, 1):
        stream = page.get_contents()
        if stream is not None:
            walk(stream, page.get("/Resources", {}), Transformation(), index, (), frozenset())

    counts = Counter(placement["atlas_page"] for placement in placements)
    if counts != Counter({1: 1, 2: 1}):
        public = [{key: value for key, value in placement.items() if key not in {"identity", "ctm"}}
                  for placement in placements]
        raise ValueError(f"Expected one distinct placement of each atlas page; got {dict(counts)}. Matches: {public}")

    for placement in placements:
        page = writer.pages[placement["paper_page"] - 1]
        annotations = resolved(page.get("/Annots", ArrayObject()))
        existing = {link_key(link.uri, link.rect) for link in uri_links(page)}
        identity = placement.pop("identity")
        transform = placement.pop("ctm")
        added = skipped = 0
        for link in identity.links:
            rect = transformed_rect(link.rect, transform)
            key = link_key(link.uri, rect)
            if key in existing:
                skipped += 1
                continue
            annotation = DictionaryObject({
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Link"),
                NameObject("/Rect"): ArrayObject([FloatObject(value) for value in rect]),
                NameObject("/Border"): ArrayObject([NumberObject(0), NumberObject(0), NumberObject(0)]),
                NameObject("/A"): DictionaryObject({
                    NameObject("/S"): NameObject("/URI"),
                    NameObject("/URI"): TextStringObject(link.uri),
                }),
            })
            annotations.append(writer._add_object(annotation))
            existing.add(key)
            added += 1
        page[NameObject("/Annots")] = annotations
        placement.update(added=added, already_present=skipped)

    summary = {
        "paper": str(paper), "atlas": str(source_atlas), "output": str(output),
        "dry_run": dry_run, "pages": len(writer.pages),
        "source_links": [len(page.links) for page in atlas],
        "placements": placements,
        "added": sum(placement["added"] for placement in placements),
        "already_present": sum(placement["already_present"] for placement in placements),
    }
    if not dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent, delete=False) as handle:
                temporary = handle.name
                writer.write(handle)
            os.replace(temporary, output)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paper", type=Path, help="Compiled LaTeX paper PDF")
    parser.add_argument("atlas", type=Path, help="The two-page source atlas PDF included by LaTeX")
    parser.add_argument("output", type=Path, help="Destination for the paper with restored URI annotations")
    parser.add_argument("--dry-run", action="store_true", help="Validate distinct matches without writing the destination")
    args = parser.parse_args()
    try:
        summary = restore_links(args.paper, args.atlas, args.output, dry_run=args.dry_run)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Timeline link restoration failed: {error}\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
