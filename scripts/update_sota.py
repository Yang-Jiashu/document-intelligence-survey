#!/usr/bin/env python3
"""Refresh SOTA snapshot data for the static survey site.

GitHub Pages is static, so the tracker becomes "live" through a scheduled
workflow that refreshes JSON. The script uses small source adapters: each
adapter knows how to fetch one public leaderboard, normalize model rows, and
write the result to the matching benchmark card.
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
from dataclasses import dataclass
from datetime import date, timedelta
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SOTA_PATH = ROOT / "docs" / "data" / "sota.json"
PENDING_PATH = ROOT / "docs" / "data" / "pending_updates.json"


class AdapterError(RuntimeError):
    """Raised when a source is reachable but cannot be normalized safely."""


class FetchError(AdapterError):
    """A transport failure, kept separate from an unexpected source page."""

    def __init__(self, url: str, kind: str, message: str, retryable: bool = False):
        super().__init__(f"{kind}: fetch failed for {url}: {message}")
        self.url = url
        self.kind = kind
        self.retryable = retryable


@dataclass(frozen=True)
class FetchResult:
    url: str
    text: str


def fetch(url: str, timeout: int = 30, attempts: int = 3, context: ssl.SSLContext | None = None) -> FetchResult:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    last_error: FetchError | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "document-intelligence-survey-bot/1.0 (+https://github.com/Yang-Jiashu/document-intelligence-survey)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout, context=context) as res:
                return FetchResult(url=res.geturl(), text=res.read().decode("utf-8", "strict"))
        except urllib.error.HTTPError as exc:
            last_error = FetchError(url, "http", f"HTTP {exc.code}",
                                    exc.code in {408, 429, 500, 502, 503, 504})
            exc.close()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, ssl.SSLError):
                last_error = FetchError(url, "tls", str(reason))
            elif isinstance(reason, TimeoutError):
                last_error = FetchError(url, "timeout", str(reason), True)
            else:
                last_error = FetchError(url, "network", str(reason), True)
        except UnicodeDecodeError as exc:
            raise AdapterError(f"{url}: response is not UTF-8") from exc
        if not last_error.retryable:
            break
        if attempt < attempts - 1:
            time.sleep(min(2 ** (attempt + 1), 8))
    raise last_error


def strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    value = unescape(value).strip()
    return value.replace("🥇", "").replace("🥈", "").replace("🥉", "")


def parse_tables(html: str) -> list[list[list[str]]]:
    tables = []
    for table in re.findall(r"<table\b.*?</table>", html, flags=re.I | re.S):
        parsed_rows = []
        for row in re.findall(r"<tr\b.*?</tr>", table, flags=re.I | re.S):
            cells = re.findall(r"<t[dh]\b.*?>(.*?)</t[dh]>", row, flags=re.I | re.S)
            if cells:
                parsed_rows.append([strip_html(cell) for cell in cells])
        if parsed_rows:
            tables.append(parsed_rows)
    return tables


def score_to_percent(raw: str) -> float:
    value = float(raw)
    return round(value * 100, 2) if value <= 1.0 else round(value, 2)


def infer_model_type(model: str, open_source: str | None = None) -> str:
    if open_source is not None:
        return "Open" if open_source.lower() == "yes" else "API"
    api_markers = ("gpt", "gemini", "claude", "seed", "kdl", "telemm")
    return "API" if any(marker in model.lower() for marker in api_markers) else "Open"


def by_id(data: dict) -> dict[str, dict]:
    return {bench["id"]: bench for bench in data.get("benchmarks", [])}


def update_benchmark(bench: dict, entries: list[dict], checked: str, mode: str, limit: int = 5) -> str:
    if not entries:
        raise AdapterError(f"{bench['id']}: no normalized entries")
    bench["leader"] = entries[0]
    bench["history"] = entries[:limit]
    bench["lastChecked"] = checked
    bench["updateMode"] = mode
    bench["lastCheckAttempt"] = checked
    bench["checkStatus"] = "fresh"
    bench.pop("lastCheckError", None)
    bench.pop("lastCheckWarning", None)
    return f"updated {bench['id']}: {entries[0]['model']} {entries[0]['score']}"


class SourceAdapter:
    mode = "auto-scraped"
    benchmark_ids: tuple[str, ...] = ()

    def update(self, data: dict, checked: str) -> list[str]:
        raise NotImplementedError


class OCRBenchV2Adapter(SourceAdapter):
    url = "https://99franklin.github.io/ocrbench_v2/"
    targets = {
        "ocrbench-v2-full": 0,
        "ocrbench-v2-vqa": 1,
    }
    benchmark_ids = tuple(targets)

    def update(self, data: dict, checked: str) -> list[str]:
        tables = parse_tables(fetch(self.url).text)
        benches = by_id(data)
        messages = []
        for bench_id, table_index in self.targets.items():
            if bench_id not in benches:
                raise AdapterError(f"{bench_id}: missing benchmark in sota.json")
            if table_index >= len(tables) or len(tables[table_index]) < 2:
                raise AdapterError(f"{bench_id}: OCRBench table {table_index} not found")
            entries = [self._row_to_entry(row, checked) for row in tables[table_index][1:6]]
            messages.append(update_benchmark(benches[bench_id], entries, checked, self.mode))
        return messages

    @staticmethod
    def _row_to_entry(row: list[str], checked: str) -> dict:
        return {
            "year": int(checked[:4]),
            "model": row[1],
            "score": float(row[5]),
            "type": infer_model_type(row[1], row[3]),
            "date": checked,
        }


class RRCPageContext(HTMLParser):
    """Validate the selected task and parse complete, balanced ranking tables."""

    def __init__(self):
        super().__init__()
        self.active_tasks: list[str] = []
        self.tables: list[list[list[str]]] = []
        self.table: list[list[str]] | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.cell_tag: str | None = None
        self.invalid_table = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "li" and "pill" in classes and "active" in classes:
            self.active_tasks.append(values.get("data-ref") or "")
        if tag == "table":
            if self.table is not None:
                self.invalid_table = True
            self.table = []
        elif tag == "tr" and self.table is not None:
            if self.row is not None:
                self.invalid_table = True
            self.row = []
        elif tag in {"td", "th"} and self.table is not None:
            if self.row is None or self.cell is not None:
                self.invalid_table = True
            self.cell = []
            self.cell_tag = tag

    def handle_data(self, value: str) -> None:
        if self.cell is not None:
            self.cell.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.table is not None:
            if self.cell is None or self.row is None or self.cell_tag != tag:
                self.invalid_table = True
            else:
                self.row.append(strip_html(" ".join(self.cell)))
            self.cell = None
            self.cell_tag = None
        elif tag == "tr" and self.table is not None:
            if self.row is None or self.cell is not None:
                self.invalid_table = True
            else:
                self.table.append(self.row)
            self.row = None
        elif tag == "table":
            if self.table is None or self.row is not None or self.cell is not None:
                self.invalid_table = True
            else:
                self.tables.append(self.table)
            self.table = None


class RRCDocVQAAdapter(SourceAdapter):
    mode = "auto-scraped"

    @staticmethod
    def _ssl_context() -> ssl.SSLContext:
        # RRC omits this issuer from its TLS handshake (verified on hosted
        # Actions runners). Supply the public intermediate, keeping the OS
        # roots and full certificate/hostname verification in place.
        context = ssl.create_default_context()
        context.load_verify_locations(cafile=str(ROOT / "scripts" / "certs" / "harica-geant-tls-r1.pem"))
        context.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
        return context

    def __init__(self, bench_id: str, task: int):
        if (bench_id, task) not in {("docvqa", 1), ("infographicvqa", 3)}:
            raise ValueError("RRC adapter only supports the verified DocVQA tasks 1 and 3")
        self.bench_id = bench_id
        self.benchmark_ids = (bench_id,)
        self.task = task
        self.url = f"https://rrc.cvc.uab.es/?ch=17&com=evaluation&task={task}"

    def update(self, data: dict, checked: str) -> list[str]:
        benches = by_id(data)
        if self.bench_id not in benches:
            raise AdapterError(f"{self.bench_id}: missing benchmark in sota.json")
        warning = None
        try:
            result = fetch(self.url, context=self._ssl_context())
        except FetchError as exc:
            if not exc.retryable:
                raise
            # RRC's own public navigation uses HTTP. Verified on 2026-10-27;
            # this exception is restricted to these two exact official pages.
            try:
                result = fetch(self.url.replace("https://", "http://", 1))
            except AdapterError as fallback_error:
                message = f"HTTPS failed ({exc}); official HTTP fallback failed ({fallback_error})"
                if isinstance(fallback_error, FetchError):
                    raise FetchError(self.url, fallback_error.kind, message) from fallback_error
                raise AdapterError(f"{self.bench_id}: {message}") from fallback_error
            warning = f"HTTPS failed ({exc}); official RRC HTTP fallback used (unencrypted transport)"
        self._validate_response_url(result.url)
        if urlsplit(result.url).scheme == "http" and warning is None:
            warning = "Official RRC redirected to HTTP (unencrypted transport)"
        entries = self._parse_entries(result.text, checked)
        bench = benches[self.bench_id]
        message = update_benchmark(bench, entries[:5], checked, self.mode)
        bench["lastCheckSourceUrl"] = result.url
        if warning:
            bench["lastCheckWarning"] = warning
            message += f"; warning: {warning}"
        return [message]

    def _validate_response_url(self, url: str) -> None:
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or parsed.netloc != "rrc.cvc.uab.es"
                or parsed.path not in {"", "/"} or parsed.fragment
                or parse_qs(parsed.query) != {"ch": ["17"], "com": ["evaluation"], "task": [str(self.task)]}):
            raise AdapterError(f"{self.bench_id}: unexpected RRC response URL: {url}")

    def _parse_entries(self, html: str, checked: str) -> list[dict]:
        context = RRCPageContext()
        context.feed(html)
        context.close()
        if context.active_tasks != [f"t{self.task}"]:
            raise AdapterError(f"{self.bench_id}: wrong or missing active RRC task")
        if context.invalid_table or context.table is not None:
            raise AdapterError(f"{self.bench_id}: incomplete or malformed RRC table markup")
        candidates = []
        for table in context.tables:
            for idx, row in enumerate(table):
                lower = [cell.strip().lower() for cell in row]
                if all(lower.count(name) == 1 for name in ("date", "method", "score")):
                    candidates.append((table, idx, lower))
        if len(candidates) != 1:
            raise AdapterError(f"{self.bench_id}: expected one RRC Date/Method/Score ranking header, found {len(candidates)}")
        table, header_idx, header = candidates[0]
        columns = {name: header.index(name) for name in ("date", "method", "score")}
        entries = []
        for row in table[header_idx + 1 :]:
            if len(row) != len(header):
                raise AdapterError(f"{self.bench_id}: RRC ranking row has unexpected column count")
            model = row[columns["method"]].strip()
            try:
                raw_date = row[columns["date"]]
                submitted = date.fromisoformat(raw_date)
                score = float(row[columns["score"]])
                if (not model or submitted.isoformat() != raw_date or submitted > date.fromisoformat(checked)
                        or not math.isfinite(score) or not 0 <= score <= 1):
                    raise ValueError("invalid method, date or ANLS fraction")
                if model.lower() == "human performance":
                    continue
                entries.append(
                    {
                        "year": submitted.year,
                        "model": self._normalize_model_name(model),
                        "score": round(score * 100, 2),
                        "type": infer_model_type(model),
                        "date": raw_date,
                    }
                )
            except (ValueError, IndexError) as exc:
                raise AdapterError(f"{self.bench_id}: invalid RRC ranking row for {model!r}: {exc}") from exc

        entries.sort(key=lambda item: item["score"], reverse=True)
        if not entries:
            raise AdapterError(f"{self.bench_id}: no RRC model entries found")
        return entries

    @staticmethod
    def _normalize_model_name(model: str) -> str:
        aliases = {
            "qwen3vl": "Qwen3-VL",
            "qwen2.5vl": "Qwen2.5-VL",
            "qwen2-vl": "Qwen2-VL",
        }
        return aliases.get(model.lower(), model)


class SourceReachabilityAdapter(SourceAdapter):
    mode = "manual-with-source-check"

    def __init__(self, bench_ids: Iterable[str]):
        self.bench_ids = set(bench_ids)
        self.benchmark_ids = tuple(self.bench_ids)

    def update(self, data: dict, checked: str) -> list[str]:
        benches = by_id(data)
        messages = []
        for bench_id in self.bench_ids:
            bench = benches.get(bench_id)
            if not bench:
                continue
            fetch(bench["sourceUrl"], timeout=20)
            bench["lastChecked"] = checked
            bench.pop("lastCheckError", None)
            messages.append(f"checked {bench_id}: source reachable")
        return messages


class LLMStatsMMLongBenchDocAdapter(SourceAdapter):
    mode = "auto-scraped"
    benchmark_ids = ("mmlongbench-doc",)
    url = "https://llm-stats.com/benchmarks/mmlongbench-doc"
    api_url = "https://api.zeroeval.com/leaderboard/benchmarks/mmlongbench-doc/details"

    def update(self, data: dict, checked: str) -> list[str]:
        benches = by_id(data)
        bench = benches.get("mmlongbench-doc")
        if not bench:
            raise AdapterError("mmlongbench-doc: missing benchmark in sota.json")

        payload = self._fetch_payload()
        models = payload.get("models") or []
        if not models:
            raise AdapterError("mmlongbench-doc: no LLM Stats models found")

        entries = []
        for model in models[:5]:
            score = model.get("score")
            if score is None:
                continue
            entries.append(
                {
                    "year": int((model.get("announcement_date") or checked)[:4]),
                    "model": model["model_name"],
                    "score": round(float(score) * 100, 2),
                    "type": "Open" if model.get("is_open_source") else "API",
                    "date": model.get("announcement_date") or checked,
                    "evidence": model.get("self_reported_source") or self.url,
                    "confidence": "self-reported" if model.get("self_reported") else "verified",
                }
            )
        entries.extend(self._local_evidence_entries(checked))
        entries = sorted(
            {entry["model"]: entry for entry in entries}.values(),
            key=lambda entry: entry["score"],
            reverse=True,
        )

        messages = [update_benchmark(bench, entries, checked, self.mode, limit=6)]
        bench["sourceName"] = "LLM Stats MMLongBench-Doc"
        bench["sourceUrl"] = self.url
        bench["metric"] = "Score"
        bench["task"] = "Long-document multimodal QA"
        return messages

    def _fetch_payload(self) -> dict:
        try:
            return json.loads(fetch(self.api_url).text)
        except Exception:
            return self._extract_initial_benchmark_data(fetch(self.url).text)

    @staticmethod
    def _local_evidence_entries(checked: str) -> list[dict]:
        return [
            {
                "year": 2025,
                "model": "Qwen3-VL 235B-A22B Instruct",
                "score": 57.0,
                "type": "Open",
                "date": checked,
                "evidence": "images/evidence/qwen3-vl-nonthinking-benchmarks.jpg",
                "confidence": "image-evidence",
            },
            {
                "year": 2025,
                "model": "Qwen3 VL 235B A22B Thinking",
                "score": 56.2,
                "type": "Open",
                "date": checked,
                "evidence": "images/evidence/qwen3-vl-thinking-benchmarks.jpg",
                "confidence": "image-evidence",
            },
        ]

    @staticmethod
    def _extract_initial_benchmark_data(html: str) -> dict:
        marker_idx = -1
        for marker in ('initialBenchmarkData\\\\":', 'initialBenchmarkData":', '"initialBenchmarkData":'):
            marker_idx = html.find(marker)
            if marker_idx != -1:
                break
        if marker_idx == -1:
            raise AdapterError("mmlongbench-doc: initialBenchmarkData marker not found")

        start = html.find("{", marker_idx)
        if start == -1:
            raise AdapterError("mmlongbench-doc: initialBenchmarkData object not found")

        depth = 0
        in_string = False
        escaped = False
        end = None
        for idx in range(start, len(html)):
            char = html[idx]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = idx + 1
                    break

        if end is None:
            raise AdapterError("mmlongbench-doc: initialBenchmarkData object is incomplete")

        raw = html[start:end]
        if raw.startswith(r"{\""):
            raw = raw.encode("utf-8").decode("unicode_escape")
        return json.loads(raw)


def run_adapters(data: dict, checked: str) -> tuple[list[str], list[dict]]:
    adapters: list[SourceAdapter] = [
        RRCDocVQAAdapter("docvqa", task=1),
        RRCDocVQAAdapter("infographicvqa", task=3),
        OCRBenchV2Adapter(),
        LLMStatsMMLongBenchDocAdapter(),
    ]
    messages: list[str] = []
    pending: list[dict] = []

    for adapter in adapters:
        # Do not retain half an adapter's mutations if a later row/target fails.
        candidate = copy.deepcopy(data)
        try:
            updated_messages = adapter.update(candidate, checked)
        except Exception as exc:
            benches = by_id(data)
            for bench_id in adapter.benchmark_ids:
                if bench_id in benches:
                    benches[bench_id]["lastCheckAttempt"] = checked
                    benches[bench_id]["checkStatus"] = "stale"
                    benches[bench_id]["lastCheckError"] = str(exc)
                    benches[bench_id].pop("lastCheckWarning", None)
            pending.append(
                {
                    "adapter": adapter.__class__.__name__,
                    "benchmarkIds": list(adapter.benchmark_ids),
                    "sourceUrl": getattr(adapter, "url", None),
                    "errorKind": exc.kind if isinstance(exc, FetchError) else
                                 "structure" if isinstance(exc, AdapterError) else "unexpected",
                    "status": "needs-review",
                    "message": str(exc),
                    "date": checked,
                }
            )
            messages.append(f"pending {adapter.__class__.__name__}: {exc}")
        else:
            data.clear()
            data.update(candidate)
            messages.extend(updated_messages)
    return messages, pending


def report_refresh(data: dict, pending: list[dict]) -> None:
    """Surface partial refreshes both in local exit status and Actions checks."""
    lines = [f"## SOTA refresh: {data['status']}", ""]
    for bench in data.get("benchmarks", []):
        state = bench.get("checkStatus", "unchanged")
        lines.append(f"- {bench['id']}: {state}; last verified {bench.get('lastChecked', 'unknown')}")
        if bench.get("lastCheckWarning"):
            lines.append(f"  - {bench['lastCheckWarning']}")
    for item in pending:
        lines.extend(["", f"- FAILED {', '.join(item['benchmarkIds'])}: {item['message']}"])
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as summary:
            summary.write("\n".join(lines) + "\n")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        def escape(message: str) -> str:
            return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        for item in pending:
            print(f"::error::{escape(item['message'])}")
        for bench in data.get("benchmarks", []):
            if bench.get("lastCheckWarning"):
                print(f"::warning::{escape(bench['id'] + ': ' + bench['lastCheckWarning'])}")


def main() -> int:
    data = json.loads(SOTA_PATH.read_text())
    checked = date.today().isoformat()
    cadence = data.get("updateCadence", "daily")
    next_check = date.today() + timedelta(days={"daily": 1, "weekly": 7, "monthly": 30}[cadence])

    messages, pending = run_adapters(data, checked)
    data["lastChecked"] = checked
    data["nextScheduledCheck"] = next_check.isoformat()
    data["generatedBy"] = "scripts/update_sota.py"
    data["status"] = "auto-refreshed snapshot" if not pending else "partially refreshed snapshot"

    SOTA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    PENDING_PATH.write_text(json.dumps({"lastChecked": checked, "items": pending}, indent=2, ensure_ascii=False) + "\n")
    print("\n".join(messages))
    report_refresh(data, pending)
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        # A nonzero source-health result can still produce a valid snapshot.
        # Publish it only after both files and diagnostics were written.
        with Path(output_path).open("a", encoding="utf-8") as output:
            output.write("snapshot_written=true\n")
    return 1 if pending else 0


if __name__ == "__main__":
    sys.exit(main())
