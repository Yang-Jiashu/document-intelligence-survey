#!/usr/bin/env python3
"""Refresh SOTA snapshot data for the static survey site.

GitHub Pages is static, so the tracker becomes "live" through a scheduled
workflow that refreshes JSON. The script uses small source adapters: each
adapter knows how to fetch one public leaderboard, normalize model rows, and
write the result to the matching benchmark card.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from html import unescape
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SOTA_PATH = ROOT / "docs" / "data" / "sota.json"
PENDING_PATH = ROOT / "docs" / "data" / "pending_updates.json"


class AdapterError(RuntimeError):
    """Raised when a source is reachable but cannot be normalized safely."""


@dataclass(frozen=True)
class FetchResult:
    url: str
    text: str


def fetch(url: str, timeout: int = 30, attempts: int = 3) -> FetchResult:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "document-intelligence-survey-bot/1.0 (+https://github.com/Yang-Jiashu/document-intelligence-survey)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return FetchResult(url=url, text=res.read().decode("utf-8", "ignore"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
    raise AdapterError(f"fetch failed for {url}: {last_error}")


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


def update_benchmark(bench: dict, entries: list[dict], checked: str, mode: str) -> str:
    if not entries:
        raise AdapterError(f"{bench['id']}: no normalized entries")
    bench["leader"] = entries[0]
    bench["history"] = entries[:5]
    bench["lastChecked"] = checked
    bench["updateMode"] = mode
    bench.pop("lastCheckError", None)
    return f"updated {bench['id']}: {entries[0]['model']} {entries[0]['score']}"


class SourceAdapter:
    mode = "auto-scraped"

    def update(self, data: dict, checked: str) -> list[str]:
        raise NotImplementedError


class OCRBenchV2Adapter(SourceAdapter):
    url = "https://99franklin.github.io/ocrbench_v2/"
    targets = {
        "ocrbench-v2-full": 0,
        "ocrbench-v2-vqa": 1,
    }

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


class RRCDocVQAAdapter(SourceAdapter):
    mode = "auto-scraped"

    def __init__(self, bench_id: str, task: int):
        self.bench_id = bench_id
        self.task = task
        self.url = f"https://rrc.cvc.uab.es/?ch=17&com=evaluation&task={task}"

    def update(self, data: dict, checked: str) -> list[str]:
        benches = by_id(data)
        if self.bench_id not in benches:
            raise AdapterError(f"{self.bench_id}: missing benchmark in sota.json")
        tables = parse_tables(fetch(self.url).text)
        if not tables:
            raise AdapterError(f"{self.bench_id}: no RRC ranking table found")

        header_idx = self._find_header(tables[0])
        if header_idx is None:
            raise AdapterError(f"{self.bench_id}: no RRC ranking header found")

        entries = []
        for row in tables[0][header_idx + 1 :]:
            if len(row) < 6:
                continue
            model = row[4].strip()
            if not model or model.lower() == "human performance":
                continue
            try:
                entries.append(
                    {
                        "year": int(row[0][:4]),
                        "model": self._normalize_model_name(model),
                        "score": score_to_percent(row[5]),
                        "type": infer_model_type(model),
                        "date": row[0],
                    }
                )
            except (ValueError, IndexError):
                continue

        entries.sort(key=lambda item: item["score"], reverse=True)
        return [update_benchmark(benches[self.bench_id], entries[:5], checked, self.mode)]

    @staticmethod
    def _find_header(rows: list[list[str]]) -> int | None:
        for idx, row in enumerate(rows):
            lower = [cell.lower() for cell in row]
            if "method" in lower and "score" in lower:
                return idx
        return None

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


def run_adapters(data: dict, checked: str) -> tuple[list[str], list[dict]]:
    adapters: list[SourceAdapter] = [
        RRCDocVQAAdapter("docvqa", task=1),
        RRCDocVQAAdapter("infographicvqa", task=3),
        OCRBenchV2Adapter(),
        SourceReachabilityAdapter(["mmlongbench-doc"]),
    ]
    messages: list[str] = []
    pending: list[dict] = []

    for adapter in adapters:
        try:
            messages.extend(adapter.update(data, checked))
        except AdapterError as exc:
            pending.append(
                {
                    "adapter": adapter.__class__.__name__,
                    "status": "needs-review",
                    "message": str(exc),
                    "date": checked,
                }
            )
            messages.append(f"pending {adapter.__class__.__name__}: {exc}")
    return messages, pending


def main() -> int:
    data = json.loads(SOTA_PATH.read_text())
    checked = date.today().isoformat()
    cadence = data.get("updateCadence", "weekly")
    next_check = date.today() + (timedelta(days=30) if cadence == "monthly" else timedelta(days=7))

    messages, pending = run_adapters(data, checked)
    data["lastChecked"] = checked
    data["nextScheduledCheck"] = next_check.isoformat()
    data["generatedBy"] = "scripts/update_sota.py"
    data["status"] = "auto-refreshed snapshot" if not pending else "partially refreshed snapshot"

    SOTA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    PENDING_PATH.write_text(json.dumps({"lastChecked": checked, "items": pending}, indent=2, ensure_ascii=False) + "\n")
    print("\n".join(messages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
