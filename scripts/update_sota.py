#!/usr/bin/env python3
"""Refresh SOTA snapshot data for the static survey site.

The site is served as static files, so "live" means a scheduled workflow
refreshes docs/data/sota.json. Some leaderboards are easy to parse as static
HTML. Others render via custom scripts or require manual validation; for those
we keep the curated snapshot but still refresh the source-check timestamps.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import date, timedelta
from html import unescape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOTA_PATH = ROOT / "docs" / "data" / "sota.json"


def fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "document-intelligence-survey-bot/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read().decode("utf-8", "ignore")


def strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return unescape(value).strip().replace("🥇", "").replace("🥈", "").replace("🥉", "")


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


def row_to_entry(row: list[str], checked: str) -> dict:
    method = row[1]
    score = float(row[5])
    open_source = row[3].lower() == "yes"
    return {
        "year": int(checked[:4]),
        "model": method,
        "score": score,
        "type": "Open" if open_source else "API",
        "date": checked,
    }


def update_ocrbench_v2(data: dict, checked: str) -> list[str]:
    messages = []
    url = "https://99franklin.github.io/ocrbench_v2/"
    html = fetch(url)
    tables = parse_tables(html)
    targets = {
        "ocrbench-v2-full": 0,
        "ocrbench-v2-vqa": 1,
    }

    by_id = {bench["id"]: bench for bench in data.get("benchmarks", [])}
    for bench_id, table_index in targets.items():
        if bench_id not in by_id or table_index >= len(tables) or len(tables[table_index]) < 2:
            messages.append(f"skip {bench_id}: table not found")
            continue

        rows = tables[table_index][1:4]
        entries = [row_to_entry(row, checked) for row in rows]
        bench = by_id[bench_id]
        bench["leader"] = entries[0]
        bench["history"] = entries
        bench["lastChecked"] = checked
        bench["updateMode"] = "auto-scraped"
        messages.append(f"updated {bench_id}: {entries[0]['model']} {entries[0]['score']}")

    return messages


def touch_manual_sources(data: dict, checked: str) -> list[str]:
    messages = []
    for bench in data.get("benchmarks", []):
        if bench.get("updateMode") == "auto-scraped":
            continue

        url = bench.get("sourceUrl")
        if not url:
            continue

        try:
            fetch(url, timeout=20)
            bench["lastChecked"] = checked
            bench.pop("lastCheckError", None)
            messages.append(f"checked {bench['id']}: source reachable")
        except Exception as exc:  # noqa: BLE001 - keep scheduled refresh resilient.
            messages.append(f"warning {bench['id']}: {exc}")

    return messages


def main() -> int:
    data = json.loads(SOTA_PATH.read_text())
    checked = date.today().isoformat()
    cadence = data.get("updateCadence", "weekly")
    next_check = date.today() + (timedelta(days=30) if cadence == "monthly" else timedelta(days=7))

    messages = []
    messages.extend(update_ocrbench_v2(data, checked))
    messages.extend(touch_manual_sources(data, checked))

    data["lastChecked"] = checked
    data["nextScheduledCheck"] = next_check.isoformat()
    data["generatedBy"] = "scripts/update_sota.py"
    data["status"] = "source-backed snapshot"

    SOTA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print("\n".join(messages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
