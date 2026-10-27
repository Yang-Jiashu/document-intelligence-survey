"""Offline regression tests: no live sources, credentials, or paid APIs.

The small HTML fixtures reproduce the public RRC table/tab layout with synthetic
examples. Every test blocks urllib access unless an explicit fake response is set.
"""

import copy
import io
import json
import os
from pathlib import Path
import re
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_sota as sota


CHECKED = "2026-10-27"
FIXTURES = Path(__file__).parent / "fixtures"


def fixture(task=1):
    name = "rrc_docvqa.html" if task == 1 else "rrc_infographicvqa.html"
    return (FIXTURES / name).read_text(encoding="utf-8")


def snapshot():
    ids = ("docvqa", "infographicvqa", "ocrbench-v2-full", "ocrbench-v2-vqa", "mmlongbench-doc")
    return {
        "lastChecked": "2026-10-26",
        "updateCadence": "weekly",
        "benchmarks": [
            {
                "id": bench_id,
                "lastChecked": "2026-06-10",
                "leader": {"model": "Retained model", "score": 80.0},
                "history": [{"model": "Retained model", "score": 80.0}],
            }
            for bench_id in ids
        ],
    }


class FakeResponse:
    def __init__(self, url, body=b"<html>example</html>"):
        self.url = url
        self.body = body
        self.status = 200
        from email.message import Message
        self.headers = Message()
        self.headers["Content-Type"] = "text/html; charset=UTF-8"

    def read(self):
        return self.body

    def geturl(self):
        return self.url

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class OfflineCase(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(
            sota.urllib.request, "urlopen", side_effect=AssertionError("Live network is forbidden in offline tests")
        )
        self.network.start()
        self.addCleanup(self.network.stop)

    def fetch_error(self, url, error):
        """Build the real fetcher's classified error without coupling its constructor."""
        with patch.object(sota.urllib.request, "urlopen", side_effect=error), patch.object(sota.time, "sleep"):
            with self.assertRaises(sota.FetchError) as raised:
                sota.fetch(url, attempts=1)
        return raised.exception


class FetchTests(OfflineCase):
    url = "https://rrc.cvc.uab.es/?ch=17&com=evaluation&task=1"

    def test_success_records_final_response_url(self):
        final_url = "https://example.test/redirect-target"
        with patch.object(sota.urllib.request, "urlopen", return_value=FakeResponse(final_url)) as opened:
            result = sota.fetch(self.url, timeout=7)
        self.assertEqual(result.url, final_url)
        self.assertEqual(result.text, "<html>example</html>")
        self.assertEqual(opened.call_args.kwargs["timeout"], 7)

    def test_timeout_exhaustion_is_classified_and_bounded(self):
        with patch.object(sota.urllib.request, "urlopen", side_effect=urllib.error.URLError(TimeoutError("timeout"))) as opened, patch.object(sota.time, "sleep") as sleep:
            with self.assertRaises(sota.FetchError) as raised:
                sota.fetch(self.url, timeout=2, attempts=3)
        self.assertEqual(raised.exception.kind, "timeout")
        self.assertTrue(raised.exception.retryable)
        self.assertEqual(opened.call_count, 3)
        self.assertEqual([call.kwargs["timeout"] for call in opened.call_args_list], [2, 2, 2])
        delays = [call.args[0] for call in sleep.call_args_list]
        self.assertEqual(len(delays), 2)
        self.assertTrue(0 < delays[0] <= delays[1] <= 60)

    def test_timeout_then_success(self):
        with patch.object(sota.urllib.request, "urlopen", side_effect=[TimeoutError("timeout"), FakeResponse(self.url)]) as opened, patch.object(sota.time, "sleep"):
            result = sota.fetch(self.url)
        self.assertEqual(opened.call_count, 2)
        self.assertEqual(result.url, self.url)

    def test_transient_http_statuses_retry(self):
        for status in (408, 429, 500, 502, 503, 504):
            with self.subTest(status=status):
                error = urllib.error.HTTPError(self.url, status, "transient", {}, io.BytesIO())
                with patch.object(sota.urllib.request, "urlopen", side_effect=[error, FakeResponse(self.url)]) as opened, patch.object(sota.time, "sleep"):
                    self.assertEqual(sota.fetch(self.url).url, self.url)
                self.assertEqual(opened.call_count, 2)

    def test_permanent_http_status_is_not_retried(self):
        for status in (401, 403, 404):
            with self.subTest(status=status):
                error = urllib.error.HTTPError(self.url, status, "permanent", {}, io.BytesIO())
                with patch.object(sota.urllib.request, "urlopen", side_effect=error) as opened, patch.object(sota.time, "sleep") as sleep:
                    with self.assertRaises(sota.FetchError) as raised:
                        sota.fetch(self.url)
                self.assertEqual(raised.exception.kind, "http")
                self.assertFalse(raised.exception.retryable)
                self.assertEqual(opened.call_count, 1)
                sleep.assert_not_called()

    def test_certificate_failure_is_not_retried(self):
        error = urllib.error.URLError(ssl.SSLCertVerificationError("certificate verification failed"))
        with patch.object(sota.urllib.request, "urlopen", side_effect=error) as opened, patch.object(sota.time, "sleep") as sleep:
            with self.assertRaises(sota.FetchError) as raised:
                sota.fetch(self.url)
        self.assertEqual(raised.exception.kind, "tls")
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(opened.call_count, 1)
        sleep.assert_not_called()


class RRCAdapterTests(OfflineCase):
    def apply(self, html, task=1, response_url=None):
        data = snapshot()
        bench_id = "docvqa" if task == 1 else "infographicvqa"
        adapter = sota.RRCDocVQAAdapter(bench_id, task)
        with patch.object(sota, "fetch", return_value=sota.FetchResult(response_url or adapter.url, html)):
            adapter.update(data, CHECKED)
        return sota.by_id(data)[bench_id]

    def assert_rejected_without_mutation(self, html, task=1, response_url=None):
        data = snapshot()
        original = copy.deepcopy(data)
        bench_id = "docvqa" if task == 1 else "infographicvqa"
        adapter = sota.RRCDocVQAAdapter(bench_id, task)
        with patch.object(sota, "fetch", return_value=sota.FetchResult(response_url or adapter.url, html)) as fetched:
            with self.assertRaises(sota.AdapterError):
                adapter.update(data, CHECKED)
        self.assertEqual(data, original)
        self.assertEqual(fetched.call_count, 1, "A parsed invalid page must not trigger a transport fallback")

    def test_docvqa_normalizes_sorts_and_excludes_human(self):
        bench = self.apply(fixture())
        self.assertEqual(bench["leader"]["model"], "Example C")
        self.assertEqual(bench["leader"]["score"], 97.28)
        self.assertEqual(len(bench["history"]), 5)
        self.assertEqual([row["score"] for row in bench["history"]], [97.28, 97.25, 96.91, 96.71, 96.7])
        self.assertEqual(bench["history"][1]["model"], "Qwen3-VL")
        self.assertEqual(bench["history"][2]["type"], "API")
        self.assertEqual(bench["lastChecked"], CHECKED)
        self.assertEqual(bench["checkStatus"], "fresh")
        self.assertEqual(bench["lastCheckAttempt"], CHECKED)
        self.assertTrue(bench["lastCheckSourceUrl"].startswith("https://rrc.cvc.uab.es/"))

    def test_infographic_group_header_and_aliases(self):
        bench = self.apply(fixture(3), task=3)
        self.assertEqual(bench["leader"]["model"], "Seed-demo")
        self.assertEqual(bench["leader"]["score"], 91.2)
        self.assertEqual([row["model"] for row in bench["history"]][-2:], ["Qwen2.5-VL", "Qwen2-VL"])

    def test_verified_https_success_clears_previous_stale_error_and_warning(self):
        data = snapshot()
        bench = sota.by_id(data)["docvqa"]
        bench.update(checkStatus="stale", lastCheckError="previous timeout", lastCheckWarning="previous HTTP fallback")
        adapter = sota.RRCDocVQAAdapter("docvqa", 1)
        with patch.object(sota, "fetch", return_value=sota.FetchResult(adapter.url, fixture())):
            adapter.update(data, CHECKED)
        self.assertEqual(bench["checkStatus"], "fresh")
        self.assertNotIn("lastCheckError", bench)
        self.assertNotIn("lastCheckWarning", bench)
        self.assertEqual(bench["lastCheckSourceUrl"], adapter.url)

    def test_unrelated_first_table_and_reordered_columns(self):
        html = fixture()
        # Preserve empty icon columns while moving all columns in every row.
        def reorder(match):
            row = match.group(0)
            cells = re.findall(r"<t[dh]\b[^>]*>.*?</t[dh]>", row, flags=re.S)
            return "<tr>" + "".join(cells[index] for index in (5, 4, 0, 1, 2, 3, 6)) + "</tr>"
        html = re.sub(r"<tr>.*?</tr>", reorder, html, flags=re.S)
        html = html.replace('<table id="table-1-1">', '<table><tr><th>Notice</th></tr><tr><td>Maintenance note</td></tr></table><table id="table-1-1">')
        bench = self.apply(html)
        self.assertEqual(bench["leader"]["model"], "Example C")
        self.assertEqual(bench["leader"]["date"], "2026-01-02")

    def test_html_entities_are_decoded(self):
        html = fixture().replace("0.9000", "0.9900")
        self.assertEqual(self.apply(html)["leader"]["model"], "Example A & B")

    def test_missing_ambiguous_or_changed_structure_is_rejected(self):
        table = re.search(r"<table\b.*?</table>", fixture(), flags=re.S).group(0)
        cases = {
            "error-page": "<html><h1>Service unavailable</h1></html>",
            "missing-score": fixture().replace("<th>Score</th>", "<th>ANLS changed</th>"),
            "missing-date": fixture().replace("<th>Date</th>", "<th>Submitted</th>"),
            "ambiguous-table": fixture().replace("</body>", table + "</body>"),
            "wrong-active-task": fixture().replace('class="pill active" data-ref="t1"', 'class="pill active" data-ref="t3"'),
            "truncated-table": fixture().replace("</table>", ""),
        }
        for name, html in cases.items():
            with self.subTest(case=name):
                self.assert_rejected_without_mutation(html)

    def test_malformed_model_rows_are_rejected_even_below_top_five(self):
        for raw in ("nan", "inf", "-0.1", "1.1", "unavailable"):
            with self.subTest(score=raw):
                self.assert_rejected_without_mutation(fixture().replace("0.9000", raw))
        for raw in ("2026-02-30", "2027-01-01", "unknown", "2026-3-10"):
            with self.subTest(date=raw):
                self.assert_rejected_without_mutation(fixture().replace("2026-03-10", raw))
        self.assert_rejected_without_mutation(fixture().replace('<td>0.9000</td>', ''))
        self.assert_rejected_without_mutation(fixture().replace('Example A &amp; B', ''))

    def test_incomplete_or_unbalanced_table_markup_cannot_drop_rows_silently(self):
        html = fixture()
        cases = {
            "omitted-final-row-close": "".join(html.rsplit("</tr>", 1)),
            "omitted-final-cell-close": "".join(html.rsplit("</td>", 1)),
            "nested-row": html.replace("<tr><td>2026-03-10", "<tr><tr><td>2026-03-10", 1),
            "nested-table": html.replace("<td>2020-06-13", "<td><table><tr><td>nested</td></tr></table>2020-06-13", 1),
            "mismatched-cell-tag": html.replace("<td>2026-03-10</td>", "<td>2026-03-10</th>", 1),
        }
        for name, malformed in cases.items():
            with self.subTest(case=name):
                self.assert_rejected_without_mutation(malformed)

    def test_wrong_host_challenge_task_or_redirect_is_rejected(self):
        for url in (
            "https://example.test/?ch=17&com=evaluation&task=1",
            "https://rrc.cvc.uab.es/?ch=34&com=evaluation&task=1",
            "https://rrc.cvc.uab.es/?ch=17&com=evaluation&task=3",
            "https://rrc.cvc.uab.es/?ch=17&com=login&task=1",
        ):
            with self.subTest(url=url):
                self.assert_rejected_without_mutation(fixture(), response_url=url)

    def test_https_timeout_falls_back_only_to_same_official_http_endpoint(self):
        adapter = sota.RRCDocVQAAdapter("docvqa", 1)
        error = self.fetch_error(adapter.url, TimeoutError("timeout"))
        http_url = adapter.url.replace("https://", "http://", 1)
        data = snapshot()
        with patch.object(sota, "fetch", side_effect=[error, sota.FetchResult(http_url, fixture())]) as fetched:
            adapter.update(data, CHECKED)
        urls = [call.args[0] for call in fetched.call_args_list]
        self.assertEqual(urls, [adapter.url, http_url])
        bench = sota.by_id(data)["docvqa"]
        self.assertEqual(bench["lastCheckSourceUrl"], http_url)
        self.assertTrue(bench["lastCheckWarning"])
        self.assertEqual(bench["lastChecked"], CHECKED)

    def test_permanent_http_or_tls_failures_never_downgrade(self):
        adapter = sota.RRCDocVQAAdapter("docvqa", 1)
        errors = [
            urllib.error.HTTPError(adapter.url, 403, "Forbidden", {}, io.BytesIO()),
            urllib.error.URLError(ssl.SSLCertVerificationError("invalid cert")),
        ]
        for error in errors:
            classified = self.fetch_error(adapter.url, error)
            data = snapshot()
            original = copy.deepcopy(data)
            with patch.object(sota, "fetch", side_effect=classified) as fetched:
                with self.assertRaises(sota.AdapterError):
                    adapter.update(data, CHECKED)
            self.assertEqual(data, original)
            self.assertEqual(fetched.call_count, 1)

    def test_both_transports_fail_without_changing_rankings_or_dates(self):
        adapter = sota.RRCDocVQAAdapter("docvqa", 1)
        error = self.fetch_error(adapter.url, TimeoutError("timeout"))
        data = snapshot()
        original = copy.deepcopy(data)
        with patch.object(sota, "fetch", side_effect=error) as fetched:
            with self.assertRaises(sota.AdapterError):
                adapter.update(data, CHECKED)
        self.assertEqual(fetched.call_count, 2)
        self.assertEqual(data, original)

    def test_reachable_but_invalid_http_fallback_does_not_advance_date(self):
        adapter = sota.RRCDocVQAAdapter("docvqa", 1)
        error = self.fetch_error(adapter.url, TimeoutError("timeout"))
        http_url = adapter.url.replace("https://", "http://", 1)
        data = snapshot()
        original = copy.deepcopy(data)
        with patch.object(sota, "fetch", side_effect=[error, sota.FetchResult(http_url, "<html>Please log in</html>")]) as fetched:
            with self.assertRaises(sota.AdapterError):
                adapter.update(data, CHECKED)
        self.assertEqual(fetched.call_count, 2)
        self.assertEqual(data, original)


class PartialRefreshTests(OfflineCase):
    def test_run_adapters_marks_failure_stale_and_keeps_other_successes(self):
        data = snapshot()
        original = copy.deepcopy(data)

        def update_rrc(adapter, working, checked):
            if adapter.task == 1:
                raise sota.AdapterError("synthetic changed RRC header")
            entry = {"model": "Verified example", "score": 90.0}
            return [sota.update_benchmark(sota.by_id(working)[adapter.bench_id], [entry], checked, adapter.mode)]

        with patch.object(sota.RRCDocVQAAdapter, "update", update_rrc), patch.object(sota.OCRBenchV2Adapter, "update", return_value=[]), patch.object(sota.LLMStatsMMLongBenchDocAdapter, "update", return_value=[]):
            messages, pending = sota.run_adapters(data, CHECKED)
        doc = sota.by_id(data)["docvqa"]
        retained = sota.by_id(original)["docvqa"]
        for field in ("leader", "history", "lastChecked"):
            self.assertEqual(doc[field], retained[field])
        self.assertEqual(doc["checkStatus"], "stale")
        self.assertEqual(doc["lastCheckAttempt"], CHECKED)
        self.assertIn("header", doc["lastCheckError"])
        self.assertEqual(len(pending), 1)
        self.assertIn("docvqa", pending[0]["benchmarkIds"])
        self.assertEqual(sota.by_id(data)["infographicvqa"]["lastChecked"], CHECKED)
        self.assertTrue(messages)

    def test_multi_benchmark_adapter_rolls_back_partial_mutation(self):
        data = snapshot()
        original = copy.deepcopy(data)

        def partial_ocr(adapter, working, checked):
            bench = sota.by_id(working)["ocrbench-v2-full"]
            sota.update_benchmark(bench, [{"model": "Should be rolled back", "score": 99.0}], checked, adapter.mode)
            raise sota.AdapterError("synthetic second table missing")

        with patch.object(sota.RRCDocVQAAdapter, "update", return_value=[]), patch.object(sota.OCRBenchV2Adapter, "update", partial_ocr), patch.object(sota.LLMStatsMMLongBenchDocAdapter, "update", return_value=[]):
            _, pending = sota.run_adapters(data, CHECKED)
        for bench_id in ("ocrbench-v2-full", "ocrbench-v2-vqa"):
            bench = sota.by_id(data)[bench_id]
            for field in ("leader", "history", "lastChecked"):
                self.assertEqual(bench[field], sota.by_id(original)[bench_id][field])
            self.assertEqual(bench["checkStatus"], "stale")
        self.assertEqual(len(pending), 1)

    def test_main_writes_partial_results_and_returns_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sota_path = root / "sota.json"
            pending_path = root / "pending_updates.json"
            summary_path = root / "summary.md"
            sota_path.write_text(json.dumps(snapshot()), encoding="utf-8")

            def failed_adapter(data, checked):
                bench = sota.by_id(data)["docvqa"]
                bench.update(checkStatus="stale", lastCheckAttempt=checked, lastCheckError="synthetic source timeout")
                return ["pending docvqa: synthetic source timeout"], [{
                    "adapter": "RRCDocVQAAdapter", "status": "needs-review",
                    "benchmarkIds": ["docvqa"], "sourceUrl": "https://rrc.cvc.uab.es/?ch=17&com=evaluation&task=1",
                    "errorKind": "timeout", "message": "synthetic source timeout", "date": checked,
                }]

            with patch.object(sota, "SOTA_PATH", sota_path), patch.object(sota, "PENDING_PATH", pending_path), patch.object(sota, "run_adapters", side_effect=failed_adapter), patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary_path), "GITHUB_ACTIONS": "true"}), patch("sys.stdout", new_callable=io.StringIO):
                code = sota.main()
            self.assertNotEqual(code, 0)
            written = json.loads(sota_path.read_text())
            self.assertEqual(written["status"], "partially refreshed snapshot")
            doc = sota.by_id(written)["docvqa"]
            self.assertEqual(doc["lastChecked"], "2026-06-10")
            self.assertEqual(doc["leader"]["model"], "Retained model")
            self.assertEqual(json.loads(pending_path.read_text())["items"][0]["errorKind"], "timeout")
            summary = summary_path.read_text()
            self.assertIn("docvqa", summary)
            self.assertIn("synthetic source timeout", summary)

    def test_main_returns_success_only_without_pending_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sota_path = root / "sota.json"
            pending_path = root / "pending_updates.json"
            sota_path.write_text(json.dumps(snapshot()), encoding="utf-8")
            with patch.object(sota, "SOTA_PATH", sota_path), patch.object(sota, "PENDING_PATH", pending_path), patch.object(sota, "run_adapters", return_value=(["verified synthetic success"], [])), patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""}), patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(sota.main(), 0)
            self.assertEqual(json.loads(pending_path.read_text())["items"], [])


if __name__ == "__main__":
    unittest.main()
