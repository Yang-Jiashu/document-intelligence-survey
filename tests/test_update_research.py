"""Offline arXiv research-stream regressions. No network or API key is used."""

import copy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_research as research

NOW = datetime(2026, 10, 28, 4, 0, tzinfo=timezone.utc)
ATOM = "{http://www.w3.org/2005/Atom}"
OPEN = "{http://a9.com/-/spec/opensearch/1.1/}"
FIXTURE = Path(__file__).parent / "fixtures" / "research_atom.xml"


def xml_text():
    return FIXTURE.read_text(encoding="utf-8")


def empty_feed():
    root = ET.fromstring(xml_text())
    for item in root.findall(ATOM + "entry"):
        root.remove(item)
    root.find(OPEN + "totalResults").text = "0"
    root.find(OPEN + "itemsPerPage").text = "0"
    return ET.tostring(root, encoding="unicode")


def config():
    return {
        "lookbackDays": 30, "retentionDays": 90, "maxPapers": 1000,
        "maxResultsPerTopic": 100,
        "topics": [
            {"id": "search", "title": "搜索", "terms": ["neural retrieval"], "categories": ["cs.IR"]},
            {"id": "ads", "title": "广告", "terms": ["CTR prediction", "click-through rate"], "categories": ["cs.IR"]},
            {"id": "recommendation", "title": "推荐", "terms": ["recommender systems"], "categories": ["cs.IR"]},
        ],
    }


def snapshot():
    return {
        "schemaVersion": 1, "lastAttempt": "2026-10-01T00:00:00Z",
        "lastSuccessfulCheck": "2026-10-01T00:00:00Z", "status": "refreshed",
        "topics": [
            {"id": item["id"], "title": item["title"], "status": "fresh", "lastChecked": "2026-10-01T00:00:00Z"}
            for item in config()["topics"]
        ],
        "papers": [{
            "id": "arxiv:2609.00001", "arxiv": "2609.00001", "version": 1,
            "title": "Retained advertising example", "abstract": "A prior CTR prediction paper.",
            "authors": ["Retained Author"], "published": "2026-09-20T10:00:00Z",
            "updated": "2026-09-20T10:00:00Z", "url": "https://arxiv.org/abs/2609.00001",
            "pdfUrl": "https://arxiv.org/pdf/2609.00001", "topics": ["ads"],
            "matchedTerms": {"ads": ["CTR prediction"]}, "arxivCategories": ["cs.IR"],
            "firstSeen": "2026-10-01T00:00:00Z", "lastSeen": "2026-10-01T00:00:00Z",
            "sourceName": "arXiv",
        }],
    }


class FakeResponse:
    def __init__(self, url, body=None):
        self.url = url
        self.body = xml_text().encode() if body is None else body
        self.status = 200
        self.headers = {"Content-Type": "application/atom+xml; charset=utf-8"}

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class OfflineCase(unittest.TestCase):
    def setUp(self):
        for mocked in [
            patch.object(research.urllib.request, "urlopen", side_effect=AssertionError("No live network in offline tests")),
            patch.object(research.time, "sleep"),
            patch.dict(os.environ, {"GITHUB_OUTPUT": "", "GITHUB_STEP_SUMMARY": ""}),
        ]:
            mocked.start()
            self.addCleanup(mocked.stop)


class AtomParsingTests(OfflineCase):
    def test_normal_atom_normalizes_versions_authors_and_dates(self):
        papers, total = research.parse_feed(xml_text(), NOW)
        self.assertEqual(total, 2)
        self.assertEqual(len(papers), 2)
        paper = next(item for item in papers if item["arxiv"] == "2610.12345")
        self.assertEqual(paper["id"], "arxiv:2610.12345")
        self.assertEqual(paper["version"], 2)
        self.assertEqual(paper["authors"], ["Alice Example", "Bob Example"])
        self.assertEqual(paper["published"], "2026-10-20T10:00:00Z")
        self.assertEqual(paper["updated"], "2026-10-27T10:00:00Z")
        self.assertTrue(paper["url"].startswith("https://arxiv.org/abs/2610.12345"))
        self.assertIn("cs.IR", paper["arxivCategories"])

    def test_legacy_identifier_is_preserved_without_version_suffix(self):
        papers, _ = research.parse_feed(xml_text().replace("2610.12345v2", "cs/9901001v2"), NOW)
        self.assertIn("cs/9901001", [item["arxiv"] for item in papers])

    def test_genuine_zero_results_is_valid(self):
        self.assertEqual(research.parse_feed(empty_feed(), NOW), ([], 0))

    def test_error_or_unexpected_pages_are_not_empty_success(self):
        variants = [
            "<html><h1>Service unavailable</h1></html>",
            empty_feed().replace("http://www.w3.org/2005/Atom", "https://invalid.test/atom"),
            xml_text().replace("<opensearch:totalResults>2</opensearch:totalResults>", ""),
            xml_text().replace("http://arxiv.org/abs/2610.12345v2", "http://arxiv.org/api/errors"),
            xml_text().replace("</feed>", ""),
        ]
        for variant in variants:
            with self.subTest(variant=variant[:80]), self.assertRaises(research.ResearchError):
                research.parse_feed(variant, NOW)

    def test_incomplete_or_invalid_metadata_rejects_entire_response(self):
        replacements = [
            ("<title>Neural retrieval for recommender systems</title>", "<title></title>"),
            ("<author><name>Alice Example</name></author>", "<author><name></name></author>"),
            ("2026-10-20T10:00:00Z", "2026-02-30T10:00:00Z"),
            ("2026-10-27T10:00:00Z", "2027-10-27T10:00:00Z"),
            ("2026-10-27T10:00:00Z", "2026-01-01T10:00:00Z"),
            ("http://arxiv.org/abs/2610.12345v2", "https://evil.test/2610.12345v2"),
        ]
        for old, new in replacements:
            with self.subTest(replacement=new), self.assertRaises(research.ResearchError):
                research.parse_feed(xml_text().replace(old, new), NOW)


class TopicMatchingTests(OfflineCase):
    def test_overlap_is_explicit_and_categories_gate_irrelevant_fields(self):
        paper = research.parse_feed(xml_text(), NOW)[0][0]
        matches = research.classify(paper, config()["topics"])
        self.assertEqual(set(matches), {"search", "recommendation"})
        paper["arxivCategories"] = ["quant-ph"]
        self.assertFalse(research.classify(paper, config()["topics"]))

    def test_phrase_boundaries_prevent_substring_matches(self):
        paper = {"title": "preneural retrievals", "abstract": "not about advertising", "arxivCategories": ["cs.IR"]}
        self.assertFalse(research.classify(paper, config()["topics"]))

    def test_query_uses_title_abstract_categories_and_recent_sort(self):
        topic = config()["topics"][0]
        query = research.build_query(topic)
        self.assertIn('ti:"neural retrieval"', query)
        self.assertIn('abs:"neural retrieval"', query)
        self.assertIn("cat:cs.IR", query)
        parsed = urlsplit(research.query_url(topic, 100))
        args = parse_qs(parsed.query)
        self.assertEqual(parsed.scheme, "https")
        self.assertIn(parsed.hostname, {"arxiv.org", "export.arxiv.org"})
        self.assertEqual(args["sortBy"], ["lastUpdatedDate"])
        self.assertEqual(args["sortOrder"], ["descending"])


class FetchTests(OfflineCase):
    def test_successive_requests_keep_the_official_minimum_interval(self):
        url = research.query_url(config()["topics"][0], 100)
        clock = [0.0]
        opened_at = []
        def sleep(delay):
            clock[0] += delay
        def opened(*args, **kwargs):
            opened_at.append(clock[0])
            return FakeResponse(url)
        with patch.object(research, "NEXT_REQUEST_AT", 0), patch.object(research.time, "monotonic", side_effect=lambda: clock[0]), patch.object(research.time, "sleep", side_effect=sleep), patch.object(research.urllib.request, "urlopen", side_effect=opened):
            research.fetch(url, attempts=1)
            research.fetch(url, attempts=1)
        self.assertEqual(len(opened_at), 2)
        self.assertGreaterEqual(opened_at[1] - opened_at[0], 3)

    def test_timeout_retries_are_bounded(self):
        url = research.query_url(config()["topics"][0], 100)
        with patch.object(research.urllib.request, "urlopen", side_effect=TimeoutError("synthetic timeout")) as opened:
            with self.assertRaises(research.ResearchError):
                research.fetch(url, timeout=2, attempts=3)
        self.assertEqual(opened.call_count, 3)
        self.assertEqual([call.kwargs["timeout"] for call in opened.call_args_list], [2, 2, 2])

    def test_changed_host_or_query_cannot_be_accepted(self):
        url = research.query_url(config()["topics"][0], 100)
        for final in ["https://evil.test/api/query", "https://arxiv.org/api/query?search_query=other"]:
            with self.subTest(final=final), patch.object(research.urllib.request, "urlopen", return_value=FakeResponse(final)):
                with self.assertRaises(research.ResearchError):
                    research.fetch(url, attempts=1)

    def test_success_returns_verified_final_url_and_text(self):
        url = research.query_url(config()["topics"][0], 100)
        with patch.object(research.urllib.request, "urlopen", return_value=FakeResponse(url)):
            result = research.fetch(url, attempts=1)
        self.assertEqual(result.url, url)
        self.assertEqual(result.text, xml_text())

    def test_permanent_http_and_certificate_errors_are_not_retried(self):
        url = research.query_url(config()["topics"][0], 100)
        errors = [
            urllib.error.HTTPError(url, 401, "Unauthorized", {}, io.BytesIO()),
            urllib.error.URLError(ssl.SSLCertVerificationError("invalid certificate")),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__), patch.object(research.urllib.request, "urlopen", side_effect=error) as opened:
                with self.assertRaises(research.ResearchError):
                    research.fetch(url)
                self.assertEqual(opened.call_count, 1)


class MergeTests(OfflineCase):
    def fetch_all(self, url, *args, **kwargs):
        return research.FetchResult(url, xml_text())

    def test_verified_overlap_is_deduplicated_and_first_seen_is_stable(self):
        original = snapshot()
        before = copy.deepcopy(original)
        with patch.object(research, "fetch", side_effect=self.fetch_all):
            result, _ = research.run(original, config(), NOW)
        self.assertEqual(original, before, "run must not mutate the input before successful serialization")
        ids = [item["id"] for item in result["papers"]]
        self.assertEqual(len(ids), len(set(ids)))
        paper = next(item for item in result["papers"] if item["arxiv"] == "2610.12345")
        self.assertEqual(set(paper["topics"]), {"search", "recommendation"})
        with patch.object(research, "fetch", side_effect=self.fetch_all):
            second, _ = research.run(result, config(), NOW)
        self.assertEqual(next(item for item in second["papers"] if item["id"] == paper["id"])["firstSeen"], paper["firstSeen"])

    def test_partial_failure_retains_affected_data_and_last_success(self):
        original = snapshot()
        def fetch_topic(url, *args, **kwargs):
            if 'CTR+prediction' in url or 'CTR%20prediction' in url:
                raise research.ResearchError("synthetic timeout")
            return research.FetchResult(url, xml_text())
        with patch.object(research, "fetch", side_effect=fetch_topic):
            result, _ = research.run(original, config(), NOW)
        topics = {item["id"]: item for item in result["topics"]}
        self.assertEqual(result["status"], "partial")
        self.assertEqual(topics["ads"]["status"], "stale")
        self.assertEqual(topics["ads"]["lastChecked"], original["topics"][1]["lastChecked"])
        self.assertEqual(result["lastSuccessfulCheck"], original["lastSuccessfulCheck"])
        self.assertIn(original["papers"][0], result["papers"])

    def test_all_failures_retain_old_data(self):
        original = snapshot()
        with patch.object(research, "fetch", side_effect=research.ResearchError("synthetic outage")):
            result, _ = research.run(original, config(), NOW)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["papers"], original["papers"])
        self.assertTrue(all(item["status"] == "stale" for item in result["topics"]))

    def test_failed_source_keeps_old_records_even_beyond_retention_or_cap(self):
        original = snapshot()
        original["papers"][0].update(published="2020-01-01T00:00:00Z", updated="2020-01-01T00:00:00Z")
        second = copy.deepcopy(original["papers"][0])
        second.update(id="arxiv:2001.00002", arxiv="2001.00002")
        original["papers"].append(second)
        settings = config()
        settings["maxPapers"] = 1
        with patch.object(research, "fetch", side_effect=research.ResearchError("synthetic outage")):
            result, _ = research.run(original, settings, NOW)
        self.assertEqual({item["id"] for item in result["papers"]}, {item["id"] for item in original["papers"]})
        self.assertEqual(len(result["papers"]), 2)

    def test_empty_success_advances_checks_without_fabricating_papers(self):
        with patch.object(research, "fetch", side_effect=lambda url, **kwargs: research.FetchResult(url, empty_feed())):
            result, _ = research.run({"papers": [], "topics": []}, config(), NOW)
        self.assertEqual(result["status"], "refreshed")
        self.assertEqual(result["papers"], [])
        self.assertTrue(result["lastSuccessfulCheck"])

    def test_recent_revision_does_not_change_old_publication_date(self):
        xml = xml_text().replace("2610.12345v2", "2001.12345v2").replace("2026-10-20T10:00:00Z", "2020-01-01T10:00:00Z")
        with patch.object(research, "fetch", side_effect=lambda url, **kwargs: research.FetchResult(url, xml)):
            result, _ = research.run({"papers": [], "topics": []}, config(), NOW)
        paper = next(item for item in result["papers"] if item["arxiv"] == "2001.12345")
        self.assertEqual(paper["published"], "2020-01-01T10:00:00Z")
        self.assertEqual(paper["updated"], "2026-10-27T10:00:00Z")

    def test_older_feed_version_cannot_roll_back_metadata(self):
        with patch.object(research, "fetch", side_effect=self.fetch_all):
            first, _ = research.run({"papers": [], "topics": []}, config(), NOW)
        previous = next(item for item in first["papers"] if item["arxiv"] == "2610.12345")
        xml = xml_text().replace("2610.12345v2", "2610.12345v1").replace("2026-10-27T10:00:00Z", "2026-10-20T10:00:00Z")
        with patch.object(research, "fetch", side_effect=lambda url, **kwargs: research.FetchResult(url, xml)):
            second, _ = research.run(first, config(), NOW)
        current = next(item for item in second["papers"] if item["id"] == previous["id"])
        self.assertEqual(current["version"], 2)
        self.assertEqual(current["updated"], previous["updated"])

    def test_malformed_later_row_cannot_partially_publish_earlier_row(self):
        xml = xml_text().replace("<summary>A synthetic advertising model for click-through rate prediction.</summary>", "<summary></summary>")
        original = snapshot()
        with patch.object(research, "fetch", side_effect=lambda url, **kwargs: research.FetchResult(url, xml)):
            result, _ = research.run(original, config(), NOW)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["papers"], original["papers"])

    def test_next_schedule_matches_daily_0316_utc_boundary(self):
        for hour, minute, expected in [(3, 15, "2026-10-28"), (3, 17, "2026-10-29")]:
            now = NOW.replace(hour=hour, minute=minute)
            with self.subTest(now=now), patch.object(research, "fetch", side_effect=lambda url, **kwargs: research.FetchResult(url, empty_feed())):
                result, _ = research.run({"papers": [], "topics": []}, config(), now)
            self.assertEqual(result["nextScheduledCheck"], expected)


class ConfigurationTests(OfflineCase):
    def test_invalid_configuration_cannot_advance_success(self):
        variants = []
        for key, value in [("topics", []), ("topics", None), ("maxResultsPerTopic", 0), ("maxResultsPerTopic", 501), ("maxResultsPerTopic", 1.5), ("maxResultsPerTopic", True), ("lookbackDays", 366), ("lookbackDays", 0), ("retentionDays", 20), ("retentionDays", 731), ("maxPapers", 0), ("maxPapers", 10001), ("maxPapers", "100")]:
            settings = config()
            settings[key] = value
            variants.append(settings)
        duplicate = config()
        duplicate["topics"][1]["id"] = "search"
        variants.append(duplicate)
        for key, value in [("id", "other"), ("terms", []), ("terms", [42]), ("terms", ['unsafe"term']), ("terms", ["unsafe\nterm"]), ("categories", []), ("categories", [None]), ("categories", ['cs.IR OR all:"x"'])]:
            settings = config()
            settings["topics"][0][key] = value
            variants.append(settings)
        for settings in variants:
            original = snapshot()
            before = copy.deepcopy(original)
            with self.subTest(settings=settings), patch.object(research, "fetch") as fetched:
                with self.assertRaises(research.ResearchError):
                    research.run(original, settings, NOW)
                fetched.assert_not_called()
                self.assertEqual(original, before)


class MainTests(OfflineCase):
    def run_main(self, root, failed=False, bad_log_path=False):
        config_path, data_path = root / "config.json", root / "data.json"
        log_path = root / ("missing/log.json" if bad_log_path else "log.json")
        output_path, summary_path = root / "outputs.txt", root / "summary.md"
        config_path.write_text(json.dumps(config()))
        data_path.write_text(json.dumps(snapshot()))
        mocked_fetch = patch.object(research, "fetch", side_effect=research.ResearchError("synthetic outage") if failed else lambda url, **kwargs: research.FetchResult(url, xml_text()))
        with patch.object(research, "CONFIG_PATH", config_path), patch.object(research, "DATA_PATH", data_path), patch.object(research, "LOG_PATH", log_path), patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path), "GITHUB_STEP_SUMMARY": str(summary_path)}), mocked_fetch, patch("sys.stdout", new_callable=io.StringIO):
            code = research.main()
        return code, data_path, log_path, output_path, summary_path

    def test_complete_failure_is_nonzero_but_preserved_snapshot_can_publish(self):
        with tempfile.TemporaryDirectory() as folder:
            code, data, log, output, summary = self.run_main(Path(folder), failed=True)
            self.assertNotEqual(code, 0)
            self.assertEqual(json.loads(data.read_text())["status"], "unavailable")
            self.assertEqual(json.loads(data.read_text())["papers"], snapshot()["papers"])
            self.assertIn("snapshot_written=true", output.read_text())
            self.assertTrue(log.exists())
            self.assertTrue(summary.exists())

    def test_success_writes_snapshot_and_publication_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            code, data, _, output, _ = self.run_main(Path(folder))
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(data.read_text())["status"], "refreshed")
            self.assertIn("snapshot_written=true", output.read_text())

    def test_failed_second_write_does_not_authorize_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config_path, data_path, log_path, output_path = (root / name for name in ("config.json", "data.json", "blocked-log", "outputs.txt"))
            config_path.write_text(json.dumps(config()))
            data_path.write_text(json.dumps(snapshot()))
            log_path.mkdir()
            with patch.object(research, "CONFIG_PATH", config_path), patch.object(research, "DATA_PATH", data_path), patch.object(research, "LOG_PATH", log_path), patch.object(research, "fetch", side_effect=research.ResearchError("synthetic outage")), patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}):
                with self.assertRaises(OSError):
                    research.main()
            self.assertFalse(output_path.exists())

    def test_invalid_config_cannot_write_a_success_or_publication_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config_path, data_path, log_path, output_path = (root / name for name in ("config.json", "data.json", "log.json", "outputs.txt"))
            config_path.write_text(json.dumps({**config(), "topics": []}))
            original = json.dumps(snapshot())
            data_path.write_text(original)
            with patch.object(research, "CONFIG_PATH", config_path), patch.object(research, "DATA_PATH", data_path), patch.object(research, "LOG_PATH", log_path), patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}):
                with self.assertRaises(research.ResearchError):
                    research.main()
            self.assertEqual(data_path.read_text(), original)
            self.assertFalse(log_path.exists())
            self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
