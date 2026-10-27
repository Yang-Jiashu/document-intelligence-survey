#!/usr/bin/env python3
"""Discover recent search, advertising and recommendation preprints from arXiv.

No API key, LLM classifier or paid discovery service is required. Paper dates
come from the official query API, never from discovery time or RSS timestamps.
"""
from __future__ import annotations

import copy
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/research_sources.json"
DATA_PATH = ROOT / "docs/data/research_updates.json"
LOG_PATH = ROOT / "docs/data/research_update_log.json"
API_URL = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
OPEN = "{http://a9.com/-/spec/opensearch/1.1/}"
NEXT_REQUEST_AT = 0.0


class ResearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class FetchResult:
    url: str
    text: str


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("timezone is required")
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ResearchError(f"Invalid source timestamp: {value!r}") from exc


def validate_url(url: str, requested: str) -> None:
    target, original = urlsplit(url), urlsplit(requested)
    if (target.scheme != "https" or target.netloc not in {"arxiv.org", "export.arxiv.org"}
            or target.path != "/api/query" or target.fragment
            or parse_qs(target.query) != parse_qs(original.query)):
        raise ResearchError("Unexpected arXiv API response URL")


def fetch(url: str, timeout: int = 30, attempts: int = 3) -> FetchResult:
    global NEXT_REQUEST_AT
    validate_url(url, url)
    if attempts < 1:
        raise ValueError("attempts must be positive")
    last_error = None
    for attempt in range(attempts):
        # arXiv requires a single connection and at least three seconds
        # between requests. This applies to retries as well as topic queries.
        delay = NEXT_REQUEST_AT - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": "document-intelligence-survey-research-tracker/1.0 (+https://github.com/Yang-Jiashu/document-intelligence-survey)",
                "Accept": "application/atom+xml,application/xml;q=0.9",
            })
            with urllib.request.urlopen(request, timeout=timeout) as response:
                validate_url(response.geturl(), url)
                body = response.read(8 * 1024 * 1024 + 1)
                if len(body) > 8 * 1024 * 1024:
                    raise ResearchError("arXiv response exceeds size limit")
                return FetchResult(response.geturl(), body.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            retryable = exc.code in {408, 429, 500, 502, 503, 504}
            exc.close()
            if not retryable:
                break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
            if isinstance(getattr(exc, "reason", exc), ssl.SSLError):
                break
        except UnicodeDecodeError as exc:
            raise ResearchError("arXiv response is not UTF-8") from exc
        finally:
            NEXT_REQUEST_AT = time.monotonic() + max(3.1, 2 ** attempt)
    raise ResearchError(f"arXiv request failed after at most {attempts} attempts: {last_error}")


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_feed(xml: str, now: datetime) -> tuple[list[dict], int]:
    try:
        root = ET.fromstring(xml)
        if root.tag != ATOM + "feed":
            raise ResearchError("Expected an official arXiv Atom query feed")
        total = int(root.findtext(OPEN + "totalResults", ""))
        if total < 0:
            raise ValueError("negative total")
        entries = root.findall(ATOM + "entry")
        if total < len(entries) or (total > 0 and not entries):
            raise ResearchError("Incomplete arXiv query response")
        papers = []
        for entry in entries:
            raw_id = entry.findtext(ATOM + "id", "")
            parsed = urlsplit(raw_id)
            identifier = parsed.path.removeprefix("/abs/")
            match = re.fullmatch(r"(\d{4}\.\d{4,5}|[a-z][a-z.\-]+/\d{7})(?:v([1-9]\d*))?", identifier)
            if (parsed.scheme not in {"http", "https"} or parsed.netloc != "arxiv.org"
                    or not parsed.path.startswith("/abs/") or parsed.query or parsed.fragment or not match):
                raise ResearchError("Invalid arXiv paper identifier or API error entry")
            arxiv, version = match.group(1), int(match.group(2) or 1)
            title = clean(entry.findtext(ATOM + "title", ""))
            abstract = clean(entry.findtext(ATOM + "summary", ""))
            authors = [clean(author.findtext(ATOM + "name", "")) for author in entry.findall(ATOM + "author")]
            categories = sorted({node.get("term", "") for node in entry.findall(ATOM + "category") if node.get("term")})
            published = timestamp(entry.findtext(ATOM + "published", ""))
            updated = timestamp(entry.findtext(ATOM + "updated", ""))
            if not title or not abstract or not authors or not all(authors) or not categories:
                raise ResearchError(f"Missing arXiv paper metadata: {arxiv}")
            if published > updated or updated > now + timedelta(minutes=5):
                raise ResearchError(f"Inconsistent or future arXiv paper dates: {arxiv}")
            papers.append({
                "id": f"arxiv:{arxiv}", "arxiv": arxiv, "version": version,
                "title": title, "abstract": abstract, "authors": authors,
                "published": iso(published), "updated": iso(updated),
                "url": f"https://arxiv.org/abs/{arxiv}", "pdfUrl": f"https://arxiv.org/pdf/{arxiv}",
                "arxivCategories": categories, "sourceName": "arXiv",
            })
        return papers, total
    except (ET.ParseError, ValueError) as exc:
        raise ResearchError(f"Malformed arXiv query feed: {exc}") from exc


def normalized(value: str) -> str:
    return clean(re.sub(r"[^\w]+", " ", value.casefold()))


def classify(paper: dict, topics: list[dict]) -> dict[str, list[str]]:
    text = normalized(paper["title"] + " " + paper["abstract"])
    result = {}
    for topic in topics:
        if not set(paper["arxivCategories"]) & set(topic["categories"]):
            continue
        terms = [term for term in topic["terms"] if re.search(r"(?<!\w)" + re.escape(normalized(term)) + r"(?!\w)", text)]
        if terms:
            result[topic["id"]] = terms
    return result


def build_query(topic: dict) -> str:
    categories = " OR ".join(f"cat:{value}" for value in topic["categories"])
    # Both spellings cover the hyphenated expressions common in abstracts.
    phrases = dict.fromkeys(phrase for term in topic["terms"] for phrase in (term, term.replace(" ", "-")))
    terms = " OR ".join(f'{field}:"{term}"' for term in phrases for field in ("ti", "abs"))
    return f"({categories}) AND ({terms})"


def query_url(topic: dict, limit: int) -> str:
    return API_URL + "?" + urlencode({"search_query": build_query(topic), "sortBy": "lastUpdatedDate", "sortOrder": "descending", "start": 0, "max_results": limit})


def validate_config(config: dict) -> None:
    topics = config.get("topics")
    if not isinstance(topics, list) or not topics:
        raise ResearchError("At least one research topic is required")
    seen = set()
    for topic in topics:
        if not isinstance(topic, dict) or topic.get("id") not in {"search", "ads", "recommendation"} or topic["id"] in seen:
            raise ResearchError("Research topic IDs must be supported and unique")
        seen.add(topic["id"])
        if not isinstance(topic.get("title"), str) or not topic["title"].strip():
            raise ResearchError("Research topic title is required")
        for field in ("terms", "categories"):
            values = topic.get(field)
            if (not isinstance(values, list) or not values or any(not isinstance(value, str) or not value.strip() for value in values)):
                raise ResearchError(f"Topic {field} must be nonempty strings")
        if any(not re.fullmatch(r"[A-Za-z]+\.[A-Za-z]+", value) for value in topic["categories"]):
            raise ResearchError("Invalid arXiv category in research configuration")
        if any(len(value) > 120 or not normalized(value) or any(char in value for char in '\"\\\r\n') for value in topic["terms"]):
            raise ResearchError("Invalid research query phrase")
    limits = {"maxResultsPerTopic": (100, 1, 500), "lookbackDays": (30, 1, 365),
              "retentionDays": (90, 1, 730), "maxPapers": (1000, 1, 10000)}
    for key, (default, lower, upper) in limits.items():
        value = config.get(key, default)
        if type(value) is not int or not lower <= value <= upper:
            raise ResearchError(f"Invalid positive bounded research limit: {key}")
    if config.get("retentionDays", 90) < config.get("lookbackDays", 30):
        raise ResearchError("Retention must cover the discovery window")


def run(data: dict, config: dict, now: datetime) -> tuple[dict, dict]:
    validate_config(config)
    checked = iso(now)
    topics = config["topics"]
    limit = int(config.get("maxResultsPerTopic", 100))
    lookback = int(config.get("lookbackDays", 30))
    retention = int(config.get("retentionDays", 90))
    previous_topics = {item["id"]: item for item in data.get("topics", [])}
    papers = {item["id"]: copy.deepcopy(item) for item in data.get("papers", [])}
    statuses, errors, received = [], [], 0
    for topic in topics:
        url = query_url(topic, limit)
        state = copy.deepcopy(previous_topics.get(topic["id"], {}))
        state.update(id=topic["id"], title=topic["title"], sourceUrl=url)
        state.setdefault("lastChecked", None)
        try:
            response = fetch(url)
            validate_url(response.url, url)
            entries, total = parse_feed(response.text, now)
            accepted = []
            for paper in entries:
                matches = classify(paper, topics)
                if not matches or timestamp(paper["updated"]) < now - timedelta(days=lookback):
                    continue
                paper.update(topics=list(matches), matchedTerms=matches)
                accepted.append(paper)
            # All rows were parsed before any entries from this topic mutate data.
            for paper in accepted:
                old = papers.get(paper["id"])
                if old and timestamp(old["updated"]) > timestamp(paper["updated"]):
                    continue
                if old and old.get("version", 1) > paper["version"]:
                    continue
                paper.update(firstSeen=old.get("firstSeen", checked) if old else checked, lastSeen=checked)
                papers[paper["id"]] = paper
            received += len(accepted)
            state.update(status="fresh", lastChecked=checked, fetchedCount=len(entries), matchedCount=len(accepted),
                         totalResults=total, resultLimit=limit, truncated=total > len(entries))
            state.pop("error", None)
        except Exception as exc:
            state.update(status="stale", error=str(exc))
            errors.append({"topic": topic["id"], "message": str(exc), "sourceUrl": url})
        statuses.append(state)
    failed = {item["topic"] for item in errors}
    kept = [paper for paper in papers.values() if failed.intersection(paper.get("topics", [])) or timestamp(paper["updated"]) >= now - timedelta(days=retention)]
    kept.sort(key=lambda paper: (paper["updated"], paper["id"]), reverse=True)
    # Failed topics' retained records are never removed just to satisfy a cap.
    preserved = [paper for paper in kept if failed.intersection(paper.get("topics", []))]
    preserved_ids = {paper["id"] for paper in preserved}
    remaining = [paper for paper in kept if paper["id"] not in preserved_ids]
    kept = preserved + remaining[:max(0, int(config.get("maxPapers", 1000)) - len(preserved))]
    kept.sort(key=lambda paper: (paper["updated"], paper["id"]), reverse=True)
    status = "refreshed" if not errors else "unavailable" if len(errors) == len(topics) else "partial"
    next_check = now.astimezone(timezone.utc).replace(hour=3, minute=16, second=0, microsecond=0)
    if next_check <= now:
        next_check += timedelta(days=1)
    snapshot = {"schemaVersion": 1, "lastAttempt": checked,
                "lastSuccessfulCheck": checked if not errors else data.get("lastSuccessfulCheck"),
                "status": status, "nextScheduledCheck": next_check.date().isoformat(),
                "updateCadence": "daily", "lookbackDays": lookback, "retentionDays": retention,
                "topics": statuses, "papers": kept}
    log = {"lastAttempt": checked, "status": status, "errors": errors, "received": received,
           "paperCount": len(kept), "topics": statuses}
    return snapshot, log


def write_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    data = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.exists() else {}
    now = datetime.now(timezone.utc)
    snapshot, log = run(data, config, now)
    write_json(DATA_PATH, snapshot)
    write_json(LOG_PATH, log)
    lines = [f"## Research progress: {snapshot['status']}", ""]
    for topic in snapshot["topics"]:
        message = f"{topic['id']}: {topic['status']}; last verified {topic.get('lastChecked') or 'never'}"
        print(message)
        lines.append("- " + message)
    for error in log["errors"]:
        message = f"{error['topic']}: {error['message']}"
        lines.append("- FAILED " + message)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print("::error::" + escaped)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as output:
            output.write("\n".join(lines) + "\n")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as output:
            output.write("snapshot_written=true\n")
    return 1 if log["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
