#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "dynamic_sources.json"
LOCAL_ENV_PATH = ROOT / ".env.local"
CURATED_INDEX_PATH = ROOT / "docs" / "data" / "paper_index.json"
DYNAMIC_PAPERS_PATH = ROOT / "docs" / "data" / "dynamic_papers.json"
PENDING_DYNAMIC_PATH = ROOT / "docs" / "data" / "pending_dynamic_papers.json"
UPDATE_LOG_PATH = ROOT / "docs" / "data" / "update_log.json"

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"
ARXIV_QUERY_URL = "https://export.arxiv.org/api/query"

ARXIV_ID_RE = re.compile(
    r"(?:arxiv(?:\.org)?/(?:abs|pdf)/|arxiv\s*:\s*|arxiv\s+)?"
    r"([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)",
    re.IGNORECASE,
)

WECHAT_ARTICLE_RE = re.compile(r"^https?://mp\.weixin\.qq\.com/(?:s/[^/?#]+|s\?.*(?:__biz=|mid=))", re.IGNORECASE)
GITHUB_REPO_RE = re.compile(
    r"https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def normalize_publication_date(value: str) -> str:
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?", value or "")
    if not match:
        return ""
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date().isoformat()
    except ValueError:
        return ""


def detect_publication_date(article: dict[str, Any]) -> str:
    explicit = normalize_publication_date(str(article.get("publishedDate") or ""))
    if explicit:
        return explicit
    text = " ".join(
        str(article.get(key) or "") for key in ("title", "snippet", "contentText")
    )
    marker_match = re.search(
        r"(?:发布时间|发布于|发表于|发布日期|date published|published(?:\s+on)?)\s*[:：]?\s*"
        r"(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?)",
        text,
        re.IGNORECASE,
    )
    return normalize_publication_date(marker_match.group(1)) if marker_match else ""


def read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def read_local_env_value(name: str) -> str:
    if not LOCAL_ENV_PATH.exists():
        return ""
    for line in LOCAL_ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        env_name, value = line.split("=", 1)
        if env_name.strip() != name:
            continue
        return value.strip().strip('"').strip("'")
    return ""


def read_local_api_key() -> str:
    return read_local_env_value("TAVILY_API_KEY")


def get_env_or_local(name: str) -> str:
    return os.environ.get(name, "").strip() or read_local_env_value(name)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def normalize_arxiv_id(value: str) -> str:
    return re.sub(r"v\d+$", "", value.strip(), flags=re.IGNORECASE)


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def extract_arxiv_ids(text: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for match in ARXIV_ID_RE.finditer(text or ""):
        arxiv_id = normalize_arxiv_id(match.group(1))
        if arxiv_id not in seen:
            seen.add(arxiv_id)
            result.append(arxiv_id)
    return result


def extract_github_urls(text: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    reserved = {
        "about", "apps", "collections", "events", "features", "marketplace",
        "orgs", "search", "settings", "sponsors", "topics",
    }
    for match in GITHUB_REPO_RE.finditer(text or ""):
        owner = match.group(1)
        repo = match.group(2).rstrip(".,);]}\"").removesuffix(".git")
        if owner.lower() in reserved or not repo:
            continue
        url = f"https://github.com/{owner}/{repo}"
        key = url.lower()
        if key not in seen:
            seen.add(key)
            result.append(url)
    return result


def is_wechat_article_url(url: str) -> bool:
    return bool(WECHAT_ARTICLE_RE.search((url or "").strip()))


def post_json(url: str, payload: dict[str, Any], api_key: str, timeout: int = 45) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "document-intelligence-survey-bot/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def get_text(url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "document-intelligence-survey-bot/1.0",
            "Accept": "application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read().decode("utf-8", "replace")


def tavily_search(
    query: str,
    api_key: str,
    max_results: int,
    search_depth: str,
    include_raw_content: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = {
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": include_raw_content,
    }
    data = post_json(TAVILY_SEARCH_URL, payload, api_key)
    normalized = []
    raw_results = data.get("results", [])
    filtered_examples = []
    for item in raw_results:
        url = str(item.get("url") or "")
        if not is_wechat_article_url(url):
            if url and len(filtered_examples) < 5:
                filtered_examples.append(url)
            continue
        normalized.append(
            {
                "provider": "tavily",
                "title": str(item.get("title") or "").strip(),
                "url": url,
                "snippet": str(item.get("content") or "").strip(),
                "contentText": str(item.get("raw_content") or "").strip(),
                "score": item.get("score"),
            }
        )
    return normalized, {
        "rawResults": len(raw_results),
        "wechatResults": len(normalized),
        "filteredExamples": filtered_examples,
    }


def tavily_extract(
    urls: list[str],
    api_key: str,
    extract_depth: str,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    if not urls:
        return {}, []

    payload = {
        "urls": urls,
        "extract_depth": extract_depth,
        "include_images": False,
        "include_favicon": False,
        "format": "markdown",
    }
    data = post_json(TAVILY_EXTRACT_URL, payload, api_key)
    extracted: dict[str, str] = {}
    for item in data.get("results", []):
        url = str(item.get("url") or "")
        raw_content = str(item.get("raw_content") or "").strip()
        if url and raw_content:
            extracted[url] = raw_content
    return extracted, data.get("failed_results", [])


def enrich_articles_with_extracted_content(
    articles: list[dict[str, Any]],
    api_key: str,
    max_urls: int,
    extract_depth: str,
    errors: list[str],
) -> dict[str, Any]:
    diagnostics = {
        "extractRequested": 0,
        "extractSucceeded": 0,
        "extractFailed": 0,
    }
    if max_urls <= 0:
        return diagnostics

    urls = []
    for article in articles:
        if len(str(article.get("contentText") or "").strip()) >= 200:
            continue
        for key in ("url", "mirrorUrl"):
            url = str(article.get(key) or "")
            if url and url not in urls and len(urls) < max_urls:
                urls.append(url)
        if len(urls) >= max_urls:
            break

    diagnostics["extractRequested"] = len(urls)
    for start in range(0, len(urls), 20):
        batch = urls[start : start + 20]
        try:
            extracted, failed = tavily_extract(batch, api_key, extract_depth)
        except urllib.error.HTTPError as exc:
            errors.append(f"tavily extract failed: {format_http_error(exc)}")
            diagnostics["extractFailed"] += len(batch)
            continue
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            errors.append(f"tavily extract failed: {exc}")
            diagnostics["extractFailed"] += len(batch)
            continue

        diagnostics["extractSucceeded"] += len(extracted)
        diagnostics["extractFailed"] += len(failed)
        for article in articles:
            content = extracted.get(str(article.get("url") or ""))
            extraction_source = "wechat"
            if not content:
                content = extracted.get(str(article.get("mirrorUrl") or ""))
                extraction_source = "verified_mirror"
            if content:
                article["contentText"] = content
                article["contentExtractionSource"] = extraction_source
        time.sleep(0.2)

    return diagnostics


def format_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", "replace").strip()
    except Exception:
        body = ""
    detail = f"HTTP {exc.code}: {exc.reason}"
    if body:
        detail = f"{detail}: {body[:500]}"
    return detail


def fetch_arxiv_metadata(arxiv_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not arxiv_ids:
        return {}

    query = urllib.parse.urlencode({"id_list": ",".join(arxiv_ids)})
    xml_text = get_text(f"{ARXIV_QUERY_URL}?{query}")
    root = ET.fromstring(xml_text)
    atom = "{http://www.w3.org/2005/Atom}"
    arxiv_ns = "{http://arxiv.org/schemas/atom}"
    result: dict[str, dict[str, Any]] = {}

    for entry in root.findall(f"{atom}entry"):
        id_text = entry.findtext(f"{atom}id", default="")
        arxiv_id = normalize_arxiv_id(id_text.rsplit("/", 1)[-1])
        if not arxiv_id:
            continue
        title = " ".join(entry.findtext(f"{atom}title", default="").split())
        summary = " ".join(entry.findtext(f"{atom}summary", default="").split())
        authors = []
        for author in entry.findall(f"{atom}author"):
            name = author.findtext(f"{atom}name", default="").strip()
            if name:
                authors.append(name)
        published = entry.findtext(f"{atom}published", default="")[:10]
        updated = entry.findtext(f"{atom}updated", default="")[:10]
        primary = ""
        primary_node = entry.find(f"{arxiv_ns}primary_category")
        if primary_node is not None:
            primary = primary_node.attrib.get("term", "")
        if not primary:
            category_node = entry.find(f"{atom}category")
            if category_node is not None:
                primary = category_node.attrib.get("term", "")

        result[arxiv_id] = {
            "arxiv": arxiv_id,
            "title": title,
            "authors": ", ".join(authors),
            "abstract": summary,
            "published": published,
            "updated": updated,
            "year": int(published[:4]) if re.match(r"\d{4}", published) else 0,
            "venue": f"arXiv {published[:4]}" if re.match(r"\d{4}", published) else "arXiv",
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdfUrl": f"https://arxiv.org/pdf/{arxiv_id}",
            "primaryArxivCategory": primary,
        }

    return result


def detect_trusted_source(
    article: dict[str, Any],
    hints: list[str],
    trusted_biz_ids: dict[str, list[str]] | None = None,
) -> str:
    # The account name must be visible in the result metadata or near the top of
    # the extracted page. Searching the whole article can mistake a cited
    # account for the publisher, and trusting the query alone is not sufficient.
    parsed_url = urllib.parse.urlparse(str(article.get("url") or ""))
    biz_id = urllib.parse.parse_qs(parsed_url.query).get("__biz", [""])[0]
    if biz_id:
        for source, ids in (trusted_biz_ids or {}).items():
            if biz_id in ids:
                return source
    haystack = " ".join(
        [
            str(article.get("title") or ""),
            str(article.get("snippet") or ""),
            str(article.get("contentText") or "")[:1200],
        ]
    ).lower()
    for hint in hints:
        if hint.lower() in haystack:
            return hint
    return ""


def detect_query_source(query: str, hints: list[str]) -> str:
    query_lower = query.lower()
    for hint in hints:
        if hint.lower() in query_lower:
            return hint
    return ""


def build_search_queries(config: dict[str, Any], trusted_hints: list[str]) -> list[dict[str, str]]:
    expansion = config.get("queryExpansion") or {}
    if expansion.get("enabled"):
        domain = str(config.get("searchDomain") or "mp.weixin.qq.com/s")
        template = str(expansion.get("template") or "site:{domain} {source} {term}")
        sources = [str(item).strip() for item in expansion.get("sources", trusted_hints) if str(item).strip()]
        terms = [str(item).strip() for item in expansion.get("terms", []) if str(item).strip()]
        max_per_source = int(expansion.get("maxQueriesPerSource") or 0)
        if expansion.get("rotateTerms") and max_per_source > 0 and len(terms) > max_per_source:
            window_count = (len(terms) + max_per_source - 1) // max_per_source
            window_index = (datetime.now(timezone.utc).isocalendar().week - 1) % window_count
            start = window_index * max_per_source
            active_terms = terms[start : start + max_per_source]
            if len(active_terms) < max_per_source:
                active_terms.extend(terms[: max_per_source - len(active_terms)])
            terms = active_terms
        entries: list[dict[str, str]] = []
        seen: set[str] = set()
        source_terms_config = expansion.get("sourceTerms") or {}
        terms_by_source = {
            source: [
                str(item).strip()
                for item in source_terms_config.get(source, terms)
                if str(item).strip()
            ]
            for source in sources
        }

        # Interleave sources so a provider quota cannot be consumed entirely by
        # the first account before the other allowlisted accounts are searched.
        source_counts = {source: 0 for source in sources}
        max_term_count = max((len(items) for items in terms_by_source.values()), default=0)
        for term_index in range(max_term_count):
            for source in sources:
                if max_per_source > 0 and source_counts[source] >= max_per_source:
                    continue
                source_terms = terms_by_source[source]
                if term_index >= len(source_terms):
                    continue
                term = source_terms[term_index]
                query = template.format(domain=domain, source=source, term=term)
                query = " ".join(query.split())
                if not query or query in seen:
                    continue
                seen.add(query)
                entries.append({"query": query, "source": source})
                source_counts[source] += 1
        return entries

    entries = []
    for query in config.get("queries", []):
        query_text = str(query)
        entries.append({"query": query_text, "source": detect_query_source(query_text, trusted_hints)})
    return entries


def classify_paper(metadata: dict[str, Any], article: dict[str, Any], taxonomy: list[dict[str, Any]]) -> dict[str, Any]:
    text = " ".join(
        [
            str(metadata.get("title") or ""),
            str(metadata.get("abstract") or ""),
            str(metadata.get("primaryArxivCategory") or ""),
            str(article.get("title") or ""),
            str(article.get("snippet") or ""),
            str(article.get("contentText") or ""),
        ]
    ).lower()
    scores: dict[str, int] = {}
    for node in taxonomy:
        score = 0
        for keyword in node.get("keywords", []):
            needle = str(keyword).lower().strip()
            if not needle:
                continue
            score += text.count(needle)
        scores[str(node["id"])] = score

    total = sum(scores.values())
    if total <= 0:
        return {
            "category": "",
            "subcategory": "",
            "tags": [],
            "confidence": 0.0,
            "scores": scores,
        }

    category = max(scores, key=scores.get)
    confidence = scores[category] / total
    selected = next(node for node in taxonomy if node["id"] == category)
    return {
        "category": category,
        "subcategory": selected.get("subcategory") or selected.get("title") or category,
        "tags": selected.get("tags") or [selected.get("title") or category],
        "confidence": round(confidence, 4),
        "scores": scores,
    }


def clamp_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0.0, min(1.0, parsed))


def paper_context_text(
    metadata: dict[str, Any],
    article: dict[str, Any],
    max_chars: int = 0,
    include_article: bool = True,
) -> str:
    parts = [
        str(metadata.get("title") or ""),
        str(metadata.get("abstract") or ""),
        str(metadata.get("primaryArxivCategory") or ""),
    ]
    if include_article:
        parts.extend(
            [
                str(article.get("title") or ""),
                str(article.get("snippet") or ""),
                str(article.get("contentText") or ""),
            ]
        )
    text = " ".join(parts)
    text = " ".join(text.split())
    if max_chars > 0:
        return text[:max_chars]
    return text


def count_keyword_occurrences(text: str, keyword: str) -> int:
    needle = keyword.lower().strip()
    if not needle:
        return 0
    if any(ord(char) > 127 for char in needle):
        return text.count(needle)
    pattern = re.escape(needle).replace(r"\ ", r"\s+")
    return len(re.findall(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text))


def keyword_document_relevance(
    metadata: dict[str, Any],
    article: dict[str, Any],
    relevance_config: dict[str, Any],
) -> dict[str, Any]:
    keywords = [str(item).strip() for item in relevance_config.get("keywords", []) if str(item).strip()]
    min_matches = int(relevance_config.get("minKeywordMatches") or 1)
    required = bool(relevance_config.get("required", False))
    use_source_context = bool(relevance_config.get("useSourceContext", False))
    text = paper_context_text(metadata, article, include_article=use_source_context).lower()
    matched_keywords = []
    total_occurrences = 0

    for keyword in keywords:
        occurrences = count_keyword_occurrences(text, keyword)
        if occurrences <= 0:
            continue
        matched_keywords.append(keyword)
        total_occurrences += occurrences

    is_relevant = len(matched_keywords) >= min_matches
    if not required:
        is_relevant = True

    return {
        "isDocumentIntelligence": is_relevant,
        "matchedKeywords": matched_keywords[:24],
        "matchCount": len(matched_keywords),
        "occurrences": total_occurrences,
        "confidence": round(min(0.95, 0.45 + 0.08 * len(matched_keywords)), 4) if matched_keywords else 0.0,
    }


def taxonomy_ids(taxonomy: list[dict[str, Any]]) -> set[str]:
    return {str(node.get("id") or "") for node in taxonomy if node.get("id")}


def taxonomy_node(taxonomy: list[dict[str, Any]], category: str) -> dict[str, Any] | None:
    for node in taxonomy:
        if str(node.get("id") or "") == category:
            return node
    return None


def classification_from_category(
    category: str,
    taxonomy: list[dict[str, Any]],
    confidence: float,
    scores: dict[str, int] | None = None,
) -> dict[str, Any]:
    selected = taxonomy_node(taxonomy, category)
    if not selected:
        return {
            "category": "",
            "subcategory": "",
            "tags": [],
            "confidence": 0.0,
            "scores": scores or {},
        }
    return {
        "category": category,
        "subcategory": selected.get("subcategory") or selected.get("title") or category,
        "tags": selected.get("tags") or [selected.get("title") or category],
        "confidence": round(clamp_float(confidence), 4),
        "scores": scores or {},
    }


def parse_llm_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    return str(value).strip().lower() in {"true", "yes", "y", "1", "是", "相关"}


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("LLM response did not contain a JSON object")
    return json.loads(cleaned[start : end + 1])


def llm_message_content(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    first = choices[0] or {}
    message = first.get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        return "\n".join(str(part.get("text") or part) for part in content)
    if content is not None:
        return str(content)
    return str(first.get("text") or "")


def classify_with_llm(
    metadata: dict[str, Any],
    article: dict[str, Any],
    taxonomy: list[dict[str, Any]],
    llm_config: dict[str, Any],
    errors: list[str],
) -> tuple[dict[str, Any] | None, str]:
    if not llm_config.get("enabled"):
        return None, "disabled"

    api_key_env = str(llm_config.get("apiKeyEnv") or "OPENAI_API_KEY")
    api_key = get_env_or_local(api_key_env)
    if not api_key:
        return None, "missing_key"

    base_url_env = str(llm_config.get("baseUrlEnv") or "")
    base_url = (get_env_or_local(base_url_env) if base_url_env else "") or str(llm_config.get("baseUrl") or "")
    model_env = str(llm_config.get("modelEnv") or "")
    model = (get_env_or_local(model_env) if model_env else "") or str(llm_config.get("model") or "")
    if not base_url or not model:
        return None, "missing_config"

    max_prompt_chars = int(llm_config.get("maxPromptChars") or 7000)
    categories = "\n".join(
        f"- {node.get('id')}: {node.get('title')} ({', '.join(str(tag) for tag in node.get('tags', []))})"
        for node in taxonomy
    )
    user_context = {
        "arxiv": metadata.get("arxiv", ""),
        "title": metadata.get("title", ""),
        "abstract": metadata.get("abstract", ""),
        "primaryArxivCategory": metadata.get("primaryArxivCategory", ""),
        "sourceArticleTitle": article.get("title", ""),
        "sourceArticleSnippet": article.get("snippet", ""),
        "sourceArticleText": str(article.get("contentText") or "")[:max_prompt_chars],
    }
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You classify arXiv papers for a document intelligence survey. "
                    "Return strict JSON only. Mark isDocumentIntelligence true only when the paper directly studies "
                    "document AI, OCR, layout analysis, table/chart/form understanding, document VQA/QA/RAG, "
                    "document vision-language models, or document-specific datasets/evaluation. "
                    "Generic LLM reasoning, RL, agents, or general multimodal papers are false unless documents are central."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Available categories:\n"
                    f"{categories}\n\n"
                    "Return exactly this JSON shape:\n"
                    '{"isDocumentIntelligence": boolean, "category": "ocr|layout|table|rag|vlm|eval|", '
                    '"confidence": 0.0, "reason": "short reason"}\n\n'
                    f"Paper context:\n{json.dumps(user_context, ensure_ascii=False)}"
                ),
            },
        ],
        "temperature": float(llm_config.get("temperature") or 0),
        "max_tokens": 300,
    }

    try:
        data = post_json(base_url, payload, api_key, timeout=int(llm_config.get("timeoutSeconds") or 45))
        parsed = extract_json_object(llm_message_content(data))
    except urllib.error.HTTPError as exc:
        errors.append(f"llm classification failed: {format_http_error(exc)}")
        return None, "failed"
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"llm classification failed: {exc}")
        return None, "failed"

    valid_categories = taxonomy_ids(taxonomy)
    category = str(parsed.get("category") or "").strip().lower()
    if category not in valid_categories:
        category = ""

    return {
        "isDocumentIntelligence": parse_llm_bool(parsed.get("isDocumentIntelligence")),
        "category": category,
        "confidence": clamp_float(parsed.get("confidence"), 0.0),
        "reason": str(parsed.get("reason") or "")[:400],
        "model": model,
    }, "succeeded"


def classify_candidate(
    metadata: dict[str, Any],
    article: dict[str, Any],
    taxonomy: list[dict[str, Any]],
    config: dict[str, Any],
    log: dict[str, Any],
) -> dict[str, Any]:
    rule_classification = classify_paper(metadata, article, taxonomy)
    relevance = keyword_document_relevance(metadata, article, config.get("documentRelevance") or {})
    llm_result, llm_status = classify_with_llm(
        metadata,
        article,
        taxonomy,
        config.get("llmClassification") or {},
        log.setdefault("errors", []),
    )

    if llm_status in {"succeeded", "failed"}:
        log["llmClassificationAttempted"] += 1
    elif llm_status not in {"disabled"}:
        log["llmClassificationSkipped"] += 1

    if llm_status == "succeeded" and llm_result:
        log["llmClassificationSucceeded"] += 1
        category = llm_result["category"] or rule_classification.get("category", "")
        confidence = llm_result["confidence"] or rule_classification.get("confidence", 0.0)
        classification = classification_from_category(
            category,
            taxonomy,
            confidence,
            rule_classification.get("scores", {}),
        )
        classification["provider"] = "llm"
        classification["llmReason"] = llm_result.get("reason", "")
        classification["llmModel"] = llm_result.get("model", "")
        llm_is_relevant = bool(llm_result.get("isDocumentIntelligence"))
        keyword_gate_required = bool((config.get("documentRelevance") or {}).get("required"))
        keyword_is_relevant = bool(relevance.get("isDocumentIntelligence"))
        classification["isDocumentIntelligence"] = (
            llm_is_relevant and (keyword_is_relevant if keyword_gate_required else True)
        )
        if llm_is_relevant and keyword_gate_required and not keyword_is_relevant:
            classification["llmReason"] = (
                f"{classification['llmReason']} Rejected by the required metadata keyword relevance gate."
            ).strip()
    else:
        if llm_status == "failed":
            log["llmClassificationFailed"] += 1
        classification = dict(rule_classification)
        classification["provider"] = "keywords"
        classification["isDocumentIntelligence"] = bool(relevance.get("isDocumentIntelligence"))

    classification["keywordRelevance"] = relevance
    classification["documentRelevanceConfidence"] = relevance.get("confidence", 0.0)
    return classification


def track_document_relevance(log: dict[str, Any], classification: dict[str, Any]) -> None:
    if classification.get("isDocumentIntelligence"):
        log["documentRelevant"] += 1
    else:
        log["documentIrrelevant"] += 1


def build_existing_sets(curated_index: dict[str, Any], dynamic_data: dict[str, Any]) -> dict[str, set[str]]:
    curated_arxiv: set[str] = set()
    curated_titles: set[str] = set()
    dynamic_arxiv: set[str] = set()

    for paper in curated_index.get("papers", []):
        arxiv_id = str(paper.get("arxiv") or "").strip()
        if arxiv_id:
            curated_arxiv.add(normalize_arxiv_id(arxiv_id))
        title = normalize_title(str(paper.get("title") or ""))
        if title:
            curated_titles.add(title)

    for paper in dynamic_data.get("papers", []):
        arxiv_id = str(paper.get("arxiv") or "").strip()
        if arxiv_id:
            dynamic_arxiv.add(normalize_arxiv_id(arxiv_id))

    return {
        "curated_arxiv": curated_arxiv,
        "curated_titles": curated_titles,
        "dynamic_arxiv": dynamic_arxiv,
    }


def pending_key(item: dict[str, Any]) -> str:
    arxiv_id = str(item.get("arxiv") or "")
    if arxiv_id:
        return "|".join([str(item.get("reason") or ""), normalize_arxiv_id(arxiv_id)])
    return "|".join(
        [
            str(item.get("reason") or ""),
            normalize_title(str(item.get("candidateTitle") or "")),
            str(item.get("sourceUrl") or ""),
        ]
    )


def add_pending(pending_data: dict[str, Any], item: dict[str, Any]) -> bool:
    existing = {pending_key(existing_item) for existing_item in pending_data.get("items", [])}
    key = pending_key(item)
    if key in existing:
        return False
    pending_data.setdefault("items", []).append(item)
    return True


def remove_pending_for_arxiv(pending_data: dict[str, Any], arxiv_id: str) -> None:
    normalized = normalize_arxiv_id(arxiv_id)
    pending_data["items"] = [
        item
        for item in pending_data.get("items", [])
        if normalize_arxiv_id(str(item.get("arxiv") or "")) != normalized
    ]


def classification_pending_fields(classification: dict[str, Any]) -> dict[str, Any]:
    relevance = classification.get("keywordRelevance") or {}
    return {
        "classificationProvider": classification.get("provider", "keywords"),
        "classificationConfidence": classification.get("confidence", 0.0),
        "classificationScores": classification.get("scores", {}),
        "documentRelevanceConfidence": classification.get("documentRelevanceConfidence", 0.0),
        "documentRelevanceKeywords": relevance.get("matchedKeywords", []),
        "llmReason": classification.get("llmReason", ""),
        "llmModel": classification.get("llmModel", ""),
    }


def metadata_is_complete(metadata: dict[str, Any]) -> bool:
    return bool(metadata.get("title") and metadata.get("authors") and metadata.get("abstract"))


def create_source_mention(article: dict[str, Any], found_at: str) -> dict[str, Any]:
    mention = {
        "platform": "wechat",
        "provider": str(article.get("provider") or "tavily"),
        "account": str(article.get("trustedSource") or article.get("queryTrustedSource") or "Unknown"),
        "articleTitle": str(article.get("title") or "WeChat article"),
        "url": str(article.get("url") or ""),
        "foundAt": found_at,
    }
    if article.get("publishedDate"):
        mention["publishedDate"] = str(article["publishedDate"])
    if article.get("publicationDateEvidenceUrl"):
        mention["publicationDateEvidenceUrl"] = str(article["publicationDateEvidenceUrl"])
    if article.get("sourceTrustMethod"):
        mention["sourceTrustMethod"] = str(article["sourceTrustMethod"])
    return mention


def merge_source_mentions(
    existing_mentions: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    found_at: str,
) -> list[dict[str, Any]]:
    merged = [dict(mention) for mention in existing_mentions if is_wechat_article_url(str(mention.get("url") or ""))]
    urls = {str(mention.get("url") or "") for mention in merged}
    for article in articles:
        url = str(article.get("url") or "")
        if not is_wechat_article_url(url) or url in urls:
            continue
        merged.append(create_source_mention(article, found_at))
        urls.add(url)
    return merged


def create_dynamic_paper(
    metadata: dict[str, Any],
    classification: dict[str, Any],
    first_seen: str,
    source_articles: list[dict[str, Any]],
) -> dict[str, Any]:
    arxiv_id = metadata["arxiv"]
    is_document_intelligence = bool(classification.get("isDocumentIntelligence", True))
    return {
        "id": f"arxiv:{arxiv_id}",
        "arxiv": arxiv_id,
        "title": metadata["title"],
        "authors": metadata["authors"],
        "abstract": metadata["abstract"],
        "year": metadata["year"],
        "published": metadata["published"],
        "updated": metadata["updated"],
        "venue": metadata["venue"],
        "category": classification["category"],
        "categories": [classification["category"]],
        "subcategory": classification["subcategory"],
        "tags": classification["tags"],
        "classificationConfidence": classification["confidence"],
        "classificationProvider": classification.get("provider", "keywords"),
        "documentRelevanceConfidence": classification.get("documentRelevanceConfidence", 0.0),
        "isDocumentIntelligence": is_document_intelligence,
        "status": "auto" if is_document_intelligence else "source-only",
        "firstSeen": first_seen,
        "lastSeen": first_seen,
        "url": metadata["url"],
        "pdfUrl": metadata["pdfUrl"],
        "primaryArxivCategory": metadata.get("primaryArxivCategory", ""),
        "sourceMentions": merge_source_mentions([], source_articles, first_seen),
    }


def merge_curated_source_mentions(
    dynamic: dict[str, Any],
    arxiv_id: str,
    articles: list[dict[str, Any]],
    found_at: str,
) -> None:
    mention_map = dynamic.setdefault("curatedSourceMentions", {})
    mention_map[arxiv_id] = merge_source_mentions(mention_map.get(arxiv_id, []), articles, found_at)


def merge_dynamic_paper_mentions(
    dynamic: dict[str, Any],
    arxiv_id: str,
    articles: list[dict[str, Any]],
    found_at: str,
) -> None:
    for paper in dynamic.get("papers", []):
        if normalize_arxiv_id(str(paper.get("arxiv") or "")) != arxiv_id:
            continue
        paper["sourceMentions"] = merge_source_mentions(paper.get("sourceMentions", []), articles, found_at)
        paper["lastSeen"] = found_at
        return


def merge_verified_wechat_articles(
    dynamic: dict[str, Any],
    articles: list[dict[str, Any]],
    found_at: str,
) -> None:
    existing = dynamic.setdefault("verifiedWechatArticles", [])
    by_url = {str(item.get("url") or ""): item for item in existing}
    for article in articles:
        if not article.get("trustedSource"):
            continue
        arxiv_ids = extract_arxiv_ids(
            " ".join(
                [
                    str(article.get("title") or ""),
                    str(article.get("snippet") or ""),
                    str(article.get("contentText") or ""),
                ]
            )
        )
        if not arxiv_ids:
            continue
        mention = create_source_mention(article, found_at)
        url = mention["url"]
        if not is_wechat_article_url(url):
            continue
        mention["arxivIds"] = arxiv_ids
        if url in by_url:
            by_url[url].update({key: value for key, value in mention.items() if value})
        else:
            existing.append(mention)
            by_url[url] = mention


def add_verified_github_article(
    dynamic: dict[str, Any],
    article: dict[str, Any],
    github_urls: list[str],
    classification: dict[str, Any],
    found_at: str,
) -> None:
    mention = create_source_mention(article, found_at)
    if str(mention.get("articleTitle") or "").startswith(("http://", "https://")):
        mention["articleTitle"] = github_urls[0].rstrip("/").rsplit("/", 1)[-1]
    mention.update(
        {
            "arxivIds": [],
            "githubUrls": github_urls,
            "category": classification.get("category", ""),
            "categories": [classification["category"]] if classification.get("category") else [],
            "tags": classification.get("tags", []),
            "classificationConfidence": classification.get("confidence", 0.0),
            "classificationProvider": classification.get("provider", "keywords"),
            "documentRelevanceConfidence": classification.get("documentRelevanceConfidence", 0.0),
            "isDocumentIntelligence": True,
            "status": "github-only",
        }
    )
    existing = dynamic.setdefault("verifiedWechatArticles", [])
    for current in existing:
        if str(current.get("url") or "") == mention["url"]:
            current.update(mention)
            return
    existing.append(mention)


def review_existing_dynamic_papers(
    dynamic: dict[str, Any],
    pending: dict[str, Any],
    taxonomy: list[dict[str, Any]],
    config: dict[str, Any],
    log: dict[str, Any],
    today: str,
) -> None:
    relevance_config = config.get("documentRelevance") or {}
    if not relevance_config.get("required"):
        return

    kept_papers = []
    for paper in dynamic.get("papers", []):
        metadata = {
            "arxiv": paper.get("arxiv", ""),
            "title": paper.get("title", ""),
            "authors": paper.get("authors", ""),
            "abstract": paper.get("abstract", ""),
            "published": paper.get("published", ""),
            "updated": paper.get("updated", ""),
            "year": paper.get("year", 0),
            "venue": paper.get("venue", "arXiv"),
            "url": paper.get("url", ""),
            "pdfUrl": paper.get("pdfUrl", ""),
            "primaryArxivCategory": paper.get("primaryArxivCategory", ""),
        }
        classification = classify_candidate(metadata, {}, taxonomy, config, log)
        track_document_relevance(log, classification)
        if (
            classification.get("isDocumentIntelligence")
            and classification.get("category")
            and classification.get("confidence", 0.0) >= float(config.get("autoPublishConfidence") or 0.9)
        ):
            paper["isDocumentIntelligence"] = True
            kept_papers.append(paper)
            continue

        log["existingRemovedAsIrrelevant"] += 1

    dynamic["papers"] = kept_papers


def group_articles_by_arxiv(articles: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    no_arxiv_articles: list[dict[str, Any]] = []
    for article in articles:
        if article.get("preferGithubOnly") and article.get("seedGithubUrls"):
            no_arxiv_articles.append(article)
            continue
        text = " ".join(
            [
                article.get("title", ""),
                article.get("snippet", ""),
                article.get("url", ""),
                article.get("contentText", ""),
            ]
        )
        arxiv_ids = extract_arxiv_ids(text)
        if not arxiv_ids:
            no_arxiv_articles.append(article)
            continue
        for arxiv_id in arxiv_ids:
            grouped.setdefault(arxiv_id, []).append(article)
    return grouped, no_arxiv_articles


def load_runtime_data(config_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    config = read_json(config_path, {})
    curated = read_json(CURATED_INDEX_PATH, {"papers": []})
    dynamic = read_json(
        DYNAMIC_PAPERS_PATH,
        {"lastUpdated": None, "source": "scheduled-wechat-arxiv-pipeline", "papers": []},
    )
    pending = read_json(PENDING_DYNAMIC_PATH, {"lastUpdated": None, "items": []})
    return config, curated, dynamic, pending


def search_articles(
    query_entries: list[dict[str, str]],
    api_key: str,
    max_results: int,
    search_depth: str,
    concurrency: int,
    max_candidates: int,
    include_raw_content: bool,
    errors: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    articles_by_url: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, Any] = {
        "rawSearchResults": 0,
        "wechatSearchResults": 0,
        "filteredNonWechat": 0,
        "filteredExamples": [],
        "sourceSearchSummary": {},
        "searchConcurrency": concurrency,
        "searchQueriesAttempted": 0,
        "searchStoppedForExtraction": False,
        "searchRawContentResults": 0,
    }

    def search_one(entry: dict[str, str]) -> tuple[dict[str, str], list[dict[str, Any]], dict[str, Any], str, bool]:
        query_text = entry["query"]
        try:
            query_articles, query_diagnostics = tavily_search(
                query_text, api_key, max_results, search_depth, include_raw_content
            )
            return entry, query_articles, query_diagnostics, "", False
        except urllib.error.HTTPError as exc:
            is_quota_error = exc.code == 432
            return entry, [], {}, f"tavily query failed: {query_text}: {format_http_error(exc)}", is_quota_error
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            return entry, [], {}, f"tavily query failed: {query_text}: {exc}", False

    batch_size = max(1, concurrency)
    for start in range(0, len(query_entries), batch_size):
        batch = query_entries[start : start + batch_size]
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
            outcomes = list(executor.map(search_one, batch))
        diagnostics["searchQueriesAttempted"] += len(batch)

        quota_exceeded = False
        for entry, query_articles, query_diagnostics, error, is_quota_error in outcomes:
            query_text = entry["query"]
            query_source = entry.get("source", "")
            source_key = query_source or "unknown"
            source_summary = diagnostics["sourceSearchSummary"].setdefault(
                source_key,
                {
                    "queries": 0,
                    "rawResults": 0,
                    "wechatResults": 0,
                    "queriesWithWechatResults": 0,
                    "errors": 0,
                },
            )
            source_summary["queries"] += 1
            if error:
                source_summary["errors"] += 1
                errors.append(error)
                quota_exceeded = quota_exceeded or is_quota_error
                continue

            source_summary["rawResults"] += query_diagnostics["rawResults"]
            source_summary["wechatResults"] += query_diagnostics["wechatResults"]
            if query_diagnostics["wechatResults"]:
                source_summary["queriesWithWechatResults"] += 1
            diagnostics["rawSearchResults"] += query_diagnostics["rawResults"]
            diagnostics["wechatSearchResults"] += query_diagnostics["wechatResults"]
            diagnostics["filteredNonWechat"] += query_diagnostics["rawResults"] - query_diagnostics["wechatResults"]
            for url in query_diagnostics["filteredExamples"]:
                if len(diagnostics["filteredExamples"]) < 8 and url not in diagnostics["filteredExamples"]:
                    diagnostics["filteredExamples"].append(url)

            for article in query_articles:
                article["matchedQuery"] = query_text
                article["queryTrustedSource"] = query_source
                article["matchedQueries"] = [query_text]
                article["queryTrustedSources"] = [query_source] if query_source else []
                url = article["url"]
                if url in seen_urls:
                    existing_article = articles_by_url[url]
                    if query_text not in existing_article.setdefault("matchedQueries", []):
                        existing_article["matchedQueries"].append(query_text)
                    if query_source and query_source not in existing_article.setdefault("queryTrustedSources", []):
                        existing_article["queryTrustedSources"].append(query_source)
                    if not existing_article.get("contentText") and article.get("contentText"):
                        existing_article["contentText"] = article["contentText"]
                    continue
                seen_urls.add(url)
                articles.append(article)
                articles_by_url[url] = article
                if article.get("contentText"):
                    diagnostics["searchRawContentResults"] += 1

        if quota_exceeded:
            diagnostics["quotaExceeded"] = True
            return articles, diagnostics
        if max_candidates > 0 and len(articles) >= max_candidates:
            diagnostics["searchStoppedForExtraction"] = True
            return articles[:max_candidates], diagnostics
        time.sleep(0.2)
    return articles, diagnostics


def run(args: argparse.Namespace) -> int:
    config_path = Path(args.config).resolve() if args.config else DEFAULT_CONFIG_PATH
    config, curated, dynamic, pending = load_runtime_data(config_path)
    now = utc_now()
    today = utc_today()
    max_results = args.max_results or int(config.get("maxResultsPerQuery") or 10)
    search_depth = str(config.get("searchDepth") or "basic")
    search_concurrency = max(1, int(config.get("searchConcurrency") or 1))
    extract_depth = str(config.get("extractDepth") or "basic")
    max_extract_urls = int(config.get("maxExtractUrlsPerRun") or 0)
    max_candidate_articles = int(config.get("maxCandidateArticlesPerRun") or 0)
    search_include_raw_content = bool(config.get("searchIncludeRawContent", False))
    threshold = float(config.get("autoPublishConfidence") or 0.75)
    allow_query_source_trust = bool(config.get("allowQuerySourceTrust", False))
    allow_github_only = bool(config.get("allowGithubOnly", False))
    trusted_hints = [str(item) for item in config.get("trustedSourceHints", [])]
    trusted_biz_ids = {
        str(source): [str(item) for item in ids]
        for source, ids in (config.get("trustedSourceBizIds") or {}).items()
    }
    trusted_github_owners = {
        str(source): {str(item).lower() for item in owners}
        for source, owners in (config.get("trustedGithubOwners") or {}).items()
    }
    taxonomy = config.get("taxonomy") or []
    search_query_entries = build_search_queries(config, trusted_hints)

    log: dict[str, Any] = {
        "lastRun": now,
        "provider": "tavily",
        "searchDepth": search_depth,
        "searchedQueries": len(search_query_entries),
        "rawSearchResults": 0,
        "wechatSearchResults": 0,
        "filteredNonWechat": 0,
        "filteredExamples": [],
        "sourceSearchSummary": {},
        "extractRequested": 0,
        "extractSucceeded": 0,
        "extractFailed": 0,
        "candidateArticles": 0,
        "arxivIdsFound": 0,
        "githubProjectsFound": 0,
        "githubProjectsPublished": 0,
        "verifiedSeedArticles": 0,
        "publicationYearRejected": 0,
        "publicationEvidenceRejected": 0,
        "documentRelevant": 0,
        "documentIrrelevant": 0,
        "llmClassificationEnabled": bool((config.get("llmClassification") or {}).get("enabled")),
        "llmClassificationAttempted": 0,
        "llmClassificationSucceeded": 0,
        "llmClassificationFailed": 0,
        "llmClassificationSkipped": 0,
        "autoPublished": 0,
        "pendingReview": 0,
        "pendingPreview": [],
        "duplicates": 0,
        "ignoredExistingCurated": 0,
        "existingRemovedAsIrrelevant": 0,
        "errors": [],
    }

    if args.provider != "tavily":
        log["errors"].append(f"unsupported provider: {args.provider}")
    if "tavily" not in config.get("enabledProviders", []):
        log["errors"].append("tavily is not enabled in config")
    if not taxonomy:
        log["errors"].append("taxonomy is empty")

    api_key = os.environ.get("TAVILY_API_KEY", "").strip() or read_local_api_key()
    if not api_key:
        log["errors"].append("missing TAVILY_API_KEY; Tavily search skipped")

    if log["errors"]:
        print_summary(log, args.dry_run)
        if not args.dry_run:
            write_json(UPDATE_LOG_PATH, log)
        return 0

    review_existing_dynamic_papers(dynamic, pending, taxonomy, config, log, today)
    dynamic["verifiedWechatArticles"] = []
    transient_pending_reasons = {"no_arxiv_id", "no_arxiv_or_github", "untrusted_source"}
    pending["items"] = [
        item for item in pending.get("items", [])
        if item.get("reason") not in transient_pending_reasons
    ]

    articles, search_diagnostics = search_articles(
        search_query_entries,
        api_key,
        max_results,
        search_depth,
        search_concurrency,
        max_candidate_articles,
        search_include_raw_content,
        log["errors"],
    )
    log.update(search_diagnostics)
    articles_by_url = {str(article.get("url") or ""): article for article in articles}
    for seed in config.get("verifiedSeedArticles") or []:
        url = str(seed.get("url") or "")
        account = str(seed.get("account") or "")
        published_date = normalize_publication_date(str(seed.get("publishedDate") or ""))
        publication_evidence_url = str(seed.get("publicationDateEvidenceUrl") or "")
        if not is_wechat_article_url(url) or not account or account not in trusted_hints:
            continue
        if int(config.get("requiredPublicationYear") or 0) and (
            not published_date or not publication_evidence_url.startswith(("http://", "https://"))
        ):
            log["publicationEvidenceRejected"] += 1
            continue
        seed_github_urls = [str(item) for item in seed.get("githubUrls", []) if str(item)]
        if url in articles_by_url:
            article = articles_by_url[url]
            article["trustedSource"] = account
            article["seedGithubUrls"] = seed_github_urls
            article["publishedDate"] = published_date
            article["publicationDateEvidenceUrl"] = publication_evidence_url
            article["mirrorUrl"] = str(seed.get("mirrorUrl") or "")
            article["preferGithubOnly"] = bool(seed.get("preferGithubOnly"))
            article["sourceTrustMethod"] = str(seed.get("verification") or "verified_seed")
            article["seedVerified"] = True
            article["title"] = str(seed.get("title") or article.get("title") or "WeChat article")
        else:
            article = {
                "provider": "verified-seed",
                "title": str(seed.get("title") or "WeChat article"),
                "url": url,
                "snippet": "",
                "contentText": "",
                "score": None,
                "trustedSource": account,
                "queryTrustedSource": account,
                "queryTrustedSources": [account],
                "matchedQuery": "verified seed article",
                "matchedQueries": ["verified seed article"],
                "seedGithubUrls": seed_github_urls,
                "publishedDate": published_date,
                "publicationDateEvidenceUrl": publication_evidence_url,
                "mirrorUrl": str(seed.get("mirrorUrl") or ""),
                "preferGithubOnly": bool(seed.get("preferGithubOnly")),
                "sourceTrustMethod": str(seed.get("verification") or "verified_seed"),
                "seedVerified": True,
            }
            articles.append(article)
            articles_by_url[url] = article
        log["verifiedSeedArticles"] += 1
    if config.get("extractArticleContent", True) and articles:
        extract_diagnostics = enrich_articles_with_extracted_content(
            articles,
            api_key,
            max_extract_urls,
            extract_depth,
            log["errors"],
        )
        log.update(extract_diagnostics)
    log["contentAvailable"] = sum(
        1 for article in articles if len(str(article.get("contentText") or "").strip()) >= 200
    )
    for article in articles:
        if not article.get("seedVerified"):
            article["trustedSource"] = detect_trusted_source(article, trusted_hints, trusted_biz_ids)
        if not article["trustedSource"] and allow_query_source_trust:
            article["trustedSource"] = article.get("queryTrustedSource", "")

    required_publication_year = int(config.get("requiredPublicationYear") or 0)
    if required_publication_year:
        eligible_articles = []
        for article in articles:
            article["publishedDate"] = detect_publication_date(article)
            if article["publishedDate"].startswith(f"{required_publication_year:04d}-"):
                eligible_articles.append(article)
            else:
                log["publicationYearRejected"] += 1
        articles = eligible_articles

    log["candidateArticles"] = len(articles)

    grouped, no_arxiv_articles = group_articles_by_arxiv(articles)
    log["arxivIdsFound"] = len(grouped)

    for article in no_arxiv_articles:
        article_text = " ".join(
            str(article.get(key) or "") for key in ("title", "snippet", "url", "contentText")
        )
        article_text = " ".join([article_text, *[str(url) for url in article.get("seedGithubUrls", [])]])
        github_urls = extract_github_urls(article_text) if allow_github_only else []
        log["githubProjectsFound"] += len(github_urls)

        github_owners = {
            urllib.parse.urlparse(url).path.strip("/").split("/", 1)[0].lower()
            for url in github_urls
        }
        if not article.get("trustedSource"):
            query_sources = article.get("queryTrustedSources") or [article.get("queryTrustedSource", "")]
            for query_source in query_sources:
                allowed_owners = trusted_github_owners.get(str(query_source), set())
                if allowed_owners.intersection(github_owners):
                    article["trustedSource"] = str(query_source)
                    article["queryTrustedSource"] = str(query_source)
                    article["sourceTrustMethod"] = "official_github_owner"
                    break

        if article.get("trustedSource") and github_urls:
            project_name = github_urls[0].rstrip("/").rsplit("/", 1)[-1]
            synthetic_metadata = {
                "arxiv": "",
                "title": article.get("title") or project_name,
                "authors": article.get("trustedSource", ""),
                "abstract": " ".join(
                    [str(article.get("snippet") or ""), str(article.get("contentText") or "")]
                )[:12000],
                "primaryArxivCategory": "",
            }
            classification = classify_candidate(synthetic_metadata, article, taxonomy, config, log)
            track_document_relevance(log, classification)
            if (
                classification.get("isDocumentIntelligence")
                and classification.get("category")
                and classification.get("confidence", 0.0) >= threshold
            ):
                add_verified_github_article(dynamic, article, github_urls, classification, today)
                log["githubProjectsPublished"] += 1
                continue
            reason = (
                "not_document_relevant"
                if not classification.get("isDocumentIntelligence")
                else "low_confidence"
            )
        else:
            reason = "no_arxiv_or_github" if article.get("trustedSource") else "untrusted_source"
        append_pending_preview(
            log,
            reason,
            article.get("title", ""),
            "",
            article.get("trustedSource", ""),
            article.get("url", ""),
            article.get("queryTrustedSource", ""),
            article.get("matchedQuery", ""),
            github_urls,
        )
    metadata_by_id: dict[str, dict[str, Any]] = {}
    try:
        metadata_by_id = fetch_arxiv_metadata(list(grouped.keys()))
    except (urllib.error.URLError, TimeoutError, OSError, ET.ParseError) as exc:
        log["errors"].append(f"arXiv metadata fetch failed: {exc}")

    existing = build_existing_sets(curated, dynamic)

    for arxiv_id, related_articles in grouped.items():
        trusted_articles = [article for article in related_articles if article.get("trustedSource")]
        representative = trusted_articles[0] if trusted_articles else related_articles[0]

        if not trusted_articles:
            reason = "query_source_unverified" if representative.get("queryTrustedSource") else "untrusted_source"
            append_pending_preview(
                log,
                reason,
                representative.get("title", ""),
                arxiv_id,
                "",
                representative.get("url", ""),
                representative.get("queryTrustedSource", ""),
                representative.get("matchedQuery", ""),
            )
            if add_pending(
                pending,
                {
                    "reason": reason,
                    "arxiv": arxiv_id,
                    "candidateTitle": representative.get("title", ""),
                    "sourceUrl": representative.get("url", ""),
                    "sourceTitle": representative.get("title", ""),
                    "queryTrustedSource": representative.get("queryTrustedSource", ""),
                    "matchedQuery": representative.get("matchedQuery", ""),
                    "foundAt": today,
                },
            ):
                log["pendingReview"] += 1
            continue

        if arxiv_id in existing["curated_arxiv"]:
            merge_curated_source_mentions(dynamic, arxiv_id, trusted_articles, today)
            remove_pending_for_arxiv(pending, arxiv_id)
            log["ignoredExistingCurated"] += 1
            continue

        if arxiv_id in existing["dynamic_arxiv"]:
            merge_dynamic_paper_mentions(dynamic, arxiv_id, trusted_articles, today)
            remove_pending_for_arxiv(pending, arxiv_id)
            log["duplicates"] += 1
            continue

        metadata = metadata_by_id.get(arxiv_id)
        if not metadata or not metadata_is_complete(metadata):
            append_pending_preview(
                log,
                "metadata_failed",
                representative.get("title", ""),
                arxiv_id,
                representative.get("trustedSource", ""),
                representative.get("url", ""),
                representative.get("queryTrustedSource", ""),
                representative.get("matchedQuery", ""),
            )
            if add_pending(
                pending,
                {
                    "reason": "metadata_failed",
                    "arxiv": arxiv_id,
                    "candidateTitle": representative.get("title", ""),
                    "sourceUrl": representative.get("url", ""),
                    "sourceTitle": representative.get("title", ""),
                    "trustedSource": representative.get("trustedSource", ""),
                    "foundAt": today,
                },
            ):
                log["pendingReview"] += 1
            continue

        title_key = normalize_title(metadata["title"])
        if title_key and title_key in existing["curated_titles"]:
            log["ignoredExistingCurated"] += 1
            continue

        classification = classify_candidate(metadata, representative, taxonomy, config, log)
        track_document_relevance(log, classification)
        is_document_intelligence = bool(classification.get("isDocumentIntelligence"))
        if not is_document_intelligence:
            append_pending_preview(
                log,
                "not_document_relevant",
                metadata.get("title") or representative.get("title", ""),
                arxiv_id,
                representative.get("trustedSource", ""),
                representative.get("url", ""),
                representative.get("queryTrustedSource", ""),
                representative.get("matchedQuery", ""),
            )
            continue

        if not classification["category"] or classification["confidence"] < threshold:
            append_pending_preview(
                log,
                "low_confidence" if classification["category"] else "no_classification",
                metadata.get("title") or representative.get("title", ""),
                arxiv_id,
                representative.get("trustedSource", ""),
                representative.get("url", ""),
                representative.get("queryTrustedSource", ""),
                representative.get("matchedQuery", ""),
            )
            item = {
                "reason": "low_confidence" if classification["category"] else "no_classification",
                "arxiv": arxiv_id,
                "candidateTitle": metadata.get("title") or representative.get("title", ""),
                "sourceUrl": representative.get("url", ""),
                "sourceTitle": representative.get("title", ""),
                "trustedSource": representative.get("trustedSource", ""),
                "foundAt": today,
            }
            item.update(classification_pending_fields(classification))
            if add_pending(pending, item):
                log["pendingReview"] += 1
            continue

        dynamic.setdefault("papers", []).append(
            create_dynamic_paper(metadata, classification, today, trusted_articles)
        )
        remove_pending_for_arxiv(pending, arxiv_id)
        existing["dynamic_arxiv"].add(arxiv_id)
        log["autoPublished"] += 1

    dynamic["lastUpdated"] = now
    pending["lastUpdated"] = now
    dynamic["papers"] = sorted(dynamic.get("papers", []), key=lambda item: item.get("firstSeen") or "", reverse=True)

    print_summary(log, args.dry_run)
    if args.dry_run:
        return 0

    write_json(DYNAMIC_PAPERS_PATH, dynamic)
    write_json(PENDING_DYNAMIC_PATH, pending)
    write_json(UPDATE_LOG_PATH, log)
    return 0


def print_summary(log: dict[str, Any], dry_run: bool) -> None:
    prefix = "Dry run" if dry_run else "Update"
    print(f"{prefix}: searched {log['searchedQueries']} queries")
    if "searchQueriesAttempted" in log:
        print(f"{prefix}: search queries attempted {log['searchQueriesAttempted']}")
    if log.get("searchStoppedForExtraction"):
        print(f"{prefix}: search stopped early to preserve extraction budget")
    if log.get("searchDepth"):
        print(f"{prefix}: search depth {log['searchDepth']}")
    if "rawSearchResults" in log:
        print(f"{prefix}: raw Tavily results {log['rawSearchResults']}")
        print(f"{prefix}: WeChat URL results {log['wechatSearchResults']}")
        print(f"{prefix}: filtered non-WeChat results {log['filteredNonWechat']}")
    if log.get("sourceSearchSummary"):
        print(f"{prefix}: source search summary:")
        for source, item in log["sourceSearchSummary"].items():
            print(
                f"{prefix}:   {source}: queries {item.get('queries', 0)}, "
                f"raw {item.get('rawResults', 0)}, "
                f"WeChat {item.get('wechatResults', 0)}, "
                f"queries with WeChat {item.get('queriesWithWechatResults', 0)}, "
                f"errors {item.get('errors', 0)}"
            )
    if "extractRequested" in log:
        print(f"{prefix}: extract requested {log['extractRequested']}")
        print(f"{prefix}: extract succeeded {log['extractSucceeded']}")
        print(f"{prefix}: extract failed {log['extractFailed']}")
        print(f"{prefix}: candidate content available {log.get('contentAvailable', 0)}")
    print(f"{prefix}: candidate articles {log['candidateArticles']}")
    print(f"{prefix}: verified seed articles {log.get('verifiedSeedArticles', 0)}")
    print(f"{prefix}: publication year rejected {log.get('publicationYearRejected', 0)}")
    print(f"{prefix}: publication evidence rejected {log.get('publicationEvidenceRejected', 0)}")
    print(f"{prefix}: arXiv IDs found {log['arxivIdsFound']}")
    print(f"{prefix}: GitHub repositories found {log.get('githubProjectsFound', 0)}")
    print(f"{prefix}: GitHub-only articles published {log.get('githubProjectsPublished', 0)}")
    print(f"{prefix}: document relevant {log.get('documentRelevant', 0)}")
    print(f"{prefix}: document irrelevant {log.get('documentIrrelevant', 0)}")
    if log.get("llmClassificationEnabled"):
        print(f"{prefix}: LLM classification attempted {log.get('llmClassificationAttempted', 0)}")
        print(f"{prefix}: LLM classification succeeded {log.get('llmClassificationSucceeded', 0)}")
        print(f"{prefix}: LLM classification failed {log.get('llmClassificationFailed', 0)}")
        print(f"{prefix}: LLM classification skipped {log.get('llmClassificationSkipped', 0)}")
    print(f"{prefix}: auto-published {log['autoPublished']}")
    print(f"{prefix}: pending review {log['pendingReview']}")
    print(f"{prefix}: duplicates {log['duplicates']}")
    print(f"{prefix}: ignored curated {log['ignoredExistingCurated']}")
    print(f"{prefix}: existing removed as irrelevant {log.get('existingRemovedAsIrrelevant', 0)}")
    for error in log.get("errors", []):
        print(f"{prefix}: error: {error}")
    if dry_run and log.get("candidateArticles") == 0 and log.get("filteredExamples"):
        print(f"{prefix}: sample filtered URLs:")
        for url in log["filteredExamples"][:5]:
            print(f"{prefix}:   {url}")
    if dry_run and log.get("pendingPreview"):
        print(f"{prefix}: pending preview:")
        for item in log["pendingPreview"][:8]:
            arxiv_part = f" arxiv={item['arxiv']}" if item.get("arxiv") else ""
            source_part = f" source={item['trustedSource']}" if item.get("trustedSource") else ""
            query_source_part = f" querySource={item['queryTrustedSource']}" if item.get("queryTrustedSource") else ""
            print(f"{prefix}:   [{item['reason']}]{arxiv_part}{source_part}{query_source_part} {item['title']}")
            if item.get("url"):
                print(f"{prefix}:      {item['url']}")
            if item.get("matchedQuery"):
                print(f"{prefix}:      query: {item['matchedQuery']}")


def append_pending_preview(
    log: dict[str, Any],
    reason: str,
    title: str,
    arxiv_id: str = "",
    trusted_source: str = "",
    url: str = "",
    query_trusted_source: str = "",
    matched_query: str = "",
    github_urls: list[str] | None = None,
) -> None:
    preview = log.setdefault("pendingPreview", [])
    if len(preview) >= 12:
        return
    preview.append(
        {
            "reason": reason,
            "title": title,
            "arxiv": arxiv_id,
            "trustedSource": trusted_source,
            "url": url,
            "queryTrustedSource": query_trusted_source,
            "matchedQuery": matched_query,
            "githubUrls": github_urls or [],
        }
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update dynamic arXiv paper data from public WeChat search results.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned updates without writing JSON files.")
    parser.add_argument("--provider", default="tavily", choices=["tavily"], help="Search provider to use.")
    parser.add_argument("--max-results", type=int, default=None, help="Override max results per query.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to dynamic source configuration JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv or sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
