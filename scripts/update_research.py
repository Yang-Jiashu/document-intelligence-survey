#!/usr/bin/env python3
"""Discover, filter and rank new document-intelligence information.

No API key, LLM classifier or paid discovery service is required. Paper dates
come from the official query API, never from discovery time or RSS timestamps.
"""
from __future__ import annotations

import copy
import json
import math
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
from urllib.parse import parse_qs, quote, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/research_sources.json"
DATA_PATH = ROOT / "docs/data/research_updates.json"
LOG_PATH = ROOT / "docs/data/research_update_log.json"
API_URL = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
OPEN = "{http://a9.com/-/spec/opensearch/1.1/}"
NEXT_REQUEST_AT = 0.0
DOCUMENT_TOPIC_IDS = {"ocr", "layout", "table", "docqa", "docrag", "eval"}
OFFICIAL_REPOS = {"PaddlePaddle/PaddleOCR", "opendatalab/MinerU", "docling-project/docling"}
DOCUMENT_ANCHORS = (
    "optical character recognition", "ocr", "docvqa", "infographicvqa", "omnidocbench", "ocrbench",
    "document intelligence", "document understanding", "document parsing", "document extraction",
    "document digitization", "document layout", "document image", "document images",
    "document visual question answering", "document question answering", "multimodal document retrieval",
    "document rag", "visually rich document", "pdf parsing", "pdf question answering",
    "table structure recognition", "table extraction", "table question answering", "chart question answering",
    "chart understanding", "form understanding", "invoice processing", "receipt understanding", "colpali",
    "long document understanding", "multi page document",
)


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
                "kind": "paper",
            })
        return papers, total
    except (ET.ParseError, ValueError) as exc:
        raise ResearchError(f"Malformed arXiv query feed: {exc}") from exc


def normalized(value: str) -> str:
    return clean(re.sub(r"[^\w]+", " ", value.casefold()))


def contains(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(normalized(phrase)) + r"(?!\w)", normalized(text)))


def document_relevance(paper: dict) -> float:
    """Require actual document evidence, not generic retrieval/table/doc wording."""
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    title_matches = [term for term in DOCUMENT_ANCHORS if contains(title, term)]
    body_matches = [term for term in DOCUMENT_ANCHORS if contains(abstract, term)]
    if title_matches:
        return round(min(1.0, .82 + .04 * len(title_matches) + .01 * len(body_matches)), 3)
    strong = [term for term in body_matches if term != "ocr"]
    if strong:
        return round(min(.8, .52 + .05 * len(strong)), 3)
    # OCR alone in a general AI abstract is not enough to establish scope.
    return 0.0


def classify(paper: dict, topics: list[dict]) -> dict[str, list[str]]:
    if not document_relevance(paper):
        return {}
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
        if not isinstance(topic, dict) or topic.get("id") not in DOCUMENT_TOPIC_IDS or topic["id"] in seen:
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
    if config.get("scope") != "document-intelligence" or config.get("scopeVersion") != 2:
        raise ResearchError("Document-intelligence scope version 2 is required")
    repos = config.get("githubRepos", [])
    if not isinstance(repos, list) or any(not isinstance(repo, str) or repo not in OFFICIAL_REPOS for repo in repos) or len(repos) != len(set(repos)):
        raise ResearchError("GitHub sources must be distinct verified document projects")


def parse_releases(payload: object, repo: str, now: datetime) -> list[dict]:
    if repo not in OFFICIAL_REPOS or not isinstance(payload, list):
        raise ResearchError("Invalid official GitHub release response")
    result = []
    for item in payload:
        if not isinstance(item, dict) or type(item.get("draft")) is not bool or type(item.get("prerelease")) is not bool:
            raise ResearchError("Missing GitHub release visibility metadata")
        if item["draft"] or item["prerelease"]:
            continue
        if item.get("published_at") is None:
            continue
        published = timestamp(item["published_at"])
        updated = timestamp(item.get("updated_at") or item["published_at"])
        release_id, tag, url = item.get("id"), item.get("tag_name"), item.get("html_url", "")
        expected = f"https://github.com/{repo}/releases/tag/{quote(str(tag), safe='')}"
        # GitHub keeps slash-containing tag names unescaped in html_url too.
        allowed = {expected, f"https://github.com/{repo}/releases/tag/{quote(str(tag), safe='/')}"}
        if type(release_id) is not int or release_id <= 0 or not isinstance(tag, str) or not tag.strip() or url not in allowed:
            raise ResearchError("Invalid official GitHub release identity or URL")
        if published > updated or updated > now + timedelta(minutes=5):
            raise ResearchError("Inconsistent or future official release dates")
        body = clean(re.sub(r"<[^>]+>", " ", str(item.get("body") or "")))[:500]
        result.append({"id": f"github:{repo}:{release_id}", "kind": "release", "repo": repo,
                       "title": f"{repo.split('/')[-1]} · {item.get('name') or tag}",
                       "abstract": body or f"官方正式版本 {tag}；请查看原始发布说明。",
                       "authors": [], "published": iso(published), "updated": iso(updated),
                       "url": url, "tag": tag, "sourceName": f"GitHub · {repo}",
                       "topics": ["ocr", "layout", "table"],
                       "matchedTerms": {"ocr": ["官方文档解析项目"]}, "relevanceScore": 1.0})
    return result


def fetch_releases(repo: str, now: datetime) -> list[dict]:
    if repo not in OFFICIAL_REPOS:
        raise ResearchError("Unverified GitHub project")
    url = f"https://api.github.com/repos/{repo}/releases?per_page=20"
    headers = {"User-Agent": "document-intelligence-survey-research-tracker/2.0", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers=headers)
            if token:
                # The token is sent only to this exact API origin, never copied
                # by urllib's redirect handler to another destination.
                request.add_unredirected_header("Authorization", "Bearer " + token)
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.geturl() != url:
                    raise ResearchError("Unexpected GitHub API redirect")
                body = response.read(4 * 1024 * 1024 + 1)
                if len(body) > 4 * 1024 * 1024:
                    raise ResearchError("GitHub release response exceeds size limit")
                return parse_releases(json.loads(body.decode("utf-8")), repo, now)
        except urllib.error.HTTPError as exc:
            rate_limited = exc.code == 429 or (exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0")
            message = "GitHub API rate limit exceeded" if rate_limited else f"GitHub API HTTP {exc.code}"
            transient = exc.code in {408, 500, 502, 503, 504}
            exc.close()
            if not transient or attempt == 2:
                raise ResearchError(message) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 2:
                raise ResearchError("GitHub official release connection failed") from None
        except (ValueError, UnicodeDecodeError) as exc:
            raise ResearchError("Malformed GitHub official release JSON") from exc
        time.sleep(2 ** (attempt + 1))
    raise ResearchError("GitHub official release request failed")


def rank_documents(papers: list[dict], now: datetime) -> list[dict]:
    """Content-based reading order: document relevance, freshness and diversity."""
    candidates = []
    for original in papers:
        paper = copy.deepcopy(original)
        relevance = 1.0 if paper.get("kind") == "release" else document_relevance(paper)
        if not relevance:
            continue
        age = max(0, (now - timestamp(paper["updated"])).total_seconds() / 86400)
        freshness = math.exp(-age / 14)
        recent_discovery = (now - timestamp(paper.get("firstSeen", iso(now)))).days < 3
        paper["relevanceScore"] = relevance
        paper["rankReasons"] = ["官方文档工具发布" if paper.get("kind") == "release" else "文档主题匹配"]
        if age <= 7:
            paper["rankReasons"].append("近 7 天有更新")
        if recent_discovery:
            paper["rankReasons"].append("新收录")
        candidates.append((.6 * relevance + .32 * freshness + (.08 if recent_discovery else 0), paper))
    ranked, topic_counts, source_counts = [], {}, {}
    while candidates:
        def adjusted(candidate: tuple[float, dict]) -> float:
            base, paper = candidate
            same_topic = max((topic_counts.get(topic, 0) for topic in paper.get("topics", [])), default=0)
            source = paper.get("repo") or paper.get("sourceName", "arXiv")
            return base - .07 * min(same_topic, 3) - .04 * min(source_counts.get(source, 0), 3)
        chosen = max(range(len(candidates)), key=lambda index: (adjusted(candidates[index]), candidates[index][1]["updated"], candidates[index][1]["id"]))
        score = adjusted(candidates[chosen])
        _, paper = candidates.pop(chosen)
        paper["rankScore"] = round(max(0, score), 5)
        if ranked:
            paper["rankReasons"].append("兼顾主题与来源多样性")
        ranked.append(paper)
        for topic in paper.get("topics", []):
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        source = paper.get("repo") or paper.get("sourceName", "arXiv")
        source_counts[source] = source_counts.get(source, 0) + 1
    return ranked


def run(data: dict, config: dict, now: datetime) -> tuple[dict, dict]:
    validate_config(config)
    checked = iso(now)
    topics = config["topics"]
    limit = int(config.get("maxResultsPerTopic", 100))
    lookback = int(config.get("lookbackDays", 30))
    retention = int(config.get("retentionDays", 90))
    same_scope = data.get("schemaVersion") == 2 and data.get("scope") == "document-intelligence"
    previous_topics = {item["id"]: item for item in data.get("topics", [])} if same_scope else {}
    previous_sources = {item["id"]: item for item in data.get("sources", [])} if same_scope else {}
    repos = config.get("githubRepos", [])
    papers = {}
    removed = 0
    for original in data.get("papers", []):
        paper = copy.deepcopy(original)
        if paper.get("kind", "paper") == "release":
            if not same_scope or paper.get("repo") not in repos:
                removed += 1
                continue
        else:
            matches = classify(paper, topics)
            if not matches:
                removed += 1
                continue
            paper.update(kind="paper", topics=list(matches), matchedTerms=matches)
        papers[paper["id"]] = paper
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
    sources = []
    for repo in repos:
        source_id = "github:" + repo
        state = copy.deepcopy(previous_sources.get(source_id, {}))
        state.update(id=source_id, title=repo, repo=repo, sourceUrl=f"https://github.com/{repo}/releases")
        state.setdefault("lastChecked", None)
        try:
            releases = fetch_releases(repo, now)
            accepted = [item for item in releases if timestamp(item["published"]) >= now - timedelta(days=lookback)]
            for item in accepted:
                old = papers.get(item["id"])
                if old and timestamp(old["updated"]) > timestamp(item["updated"]):
                    continue
                item.update(firstSeen=old.get("firstSeen", checked) if old else checked, lastSeen=checked)
                papers[item["id"]] = item
            received += len(accepted)
            state.update(status="fresh", lastChecked=checked, fetchedCount=len(releases), matchedCount=len(accepted),
                         resultLimit=20, truncated=len(releases) >= 20)
            state.pop("error", None)
        except Exception as exc:
            state.update(status="stale", error=str(exc))
            errors.append({"topic": source_id, "message": str(exc), "sourceUrl": state["sourceUrl"]})
        sources.append(state)
    failed = {item["topic"] for item in errors}
    def affected(paper: dict) -> bool:
        if paper.get("kind") == "release":
            return "github:" + paper.get("repo", "") in failed
        return bool(failed.intersection(paper.get("topics", [])))
    kept = [paper for paper in papers.values() if affected(paper) or timestamp(paper["updated"]) >= now - timedelta(days=retention)]
    kept.sort(key=lambda paper: (paper["updated"], paper["id"]), reverse=True)
    # Failed topics' retained records are never removed just to satisfy a cap.
    preserved = [paper for paper in kept if affected(paper)]
    preserved_ids = {paper["id"] for paper in preserved}
    remaining = [paper for paper in kept if paper["id"] not in preserved_ids]
    kept = preserved + remaining[:max(0, int(config.get("maxPapers", 1000)) - len(preserved))]
    kept = rank_documents(kept, now)
    status = "refreshed" if not errors else "unavailable" if len(errors) == len(topics) + len(repos) else "partial"
    next_check = now.astimezone(timezone.utc).replace(hour=3, minute=16, second=0, microsecond=0)
    if next_check <= now:
        next_check += timedelta(days=1)
    snapshot = {"schemaVersion": 2, "scope": "document-intelligence", "lastAttempt": checked,
                "lastSuccessfulCheck": checked if not errors else data.get("lastSuccessfulCheck") if same_scope else None,
                "status": status, "nextScheduledCheck": next_check.date().isoformat(),
                "updateCadence": "daily", "lookbackDays": lookback, "retentionDays": retention,
                "topics": statuses, "sources": sources, "papers": kept,
                "ranking": {"method": "document-relevance-freshness-diversity", "personalized": False}}
    log = {"lastAttempt": checked, "status": status, "errors": errors, "received": received,
           "scope": "document-intelligence", "paperCount": len(kept), "topics": statuses, "sources": sources,
           "removedOutOfScope": removed}
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
    for topic in snapshot["topics"] + snapshot["sources"]:
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
