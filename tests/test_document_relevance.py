"""Regressions for document-only discovery, ranking, migration and releases."""

import copy
from datetime import timedelta
import io
import os
import unittest
from unittest.mock import patch
import urllib.error

from test_update_research import FakeResponse, OfflineCase, NOW, config, snapshot, empty_feed, xml_text
import update_research as research


def paper(identifier, title, abstract, days=1, topics=None):
    return {
        "id": "arxiv:" + identifier, "arxiv": identifier, "kind": "paper", "version": 1,
        "title": title, "abstract": abstract, "authors": ["Example Author"],
        "published": research.iso(NOW - timedelta(days=days)),
        "updated": research.iso(NOW - timedelta(days=days)),
        "url": "https://arxiv.org/abs/" + identifier,
        "pdfUrl": "https://arxiv.org/pdf/" + identifier,
        "arxivCategories": ["cs.IR"], "topics": topics or ["ocr"],
        "sourceName": "arXiv", "firstSeen": "2026-10-01T00:00:00Z",
        "lastSeen": "2026-10-01T00:00:00Z",
    }


def release_payload():
    return [{
        "id": 123, "tag_name": "v1.2", "name": None,
        "html_url": "https://github.com/PaddlePaddle/PaddleOCR/releases/tag/v1.2",
        "published_at": "2026-10-26T10:00:00Z", "created_at": "2026-09-01T10:00:00Z",
        "updated_at": "2026-10-27T10:00:00Z", "draft": False, "prerelease": False,
        "body": "Official document parsing and optical character recognition improvements.",
        "author": {"login": "PaddlePaddle"},
    }]


class DocumentRelevanceTests(OfflineCase):
    def test_general_ctr_recommendation_quantum_and_rag_are_excluded(self):
        cases = [
            ("CTR prediction for advertising", "A new click-through rate advertising model."),
            ("Sequential recommendation", "A recommender system improves product ranking."),
            ("Quantum information retrieval", "Quantum memories for information retrieval."),
            ("Retrieval augmented generation", "A general language-model RAG benchmark for open-domain QA."),
            ("A table of retrieval results", "The document describes a generic ranking algorithm."),
        ]
        for title, abstract in cases:
            item = paper("2610.00001", title, abstract)
            with self.subTest(title=title):
                self.assertEqual(research.document_relevance(item), 0)
                self.assertFalse(research.classify(item, config()["topics"]))

    def test_specific_document_anchors_admit_document_research(self):
        for title in ["Optical character recognition for document parsing", "Document question answering over visually rich documents", "Document layout analysis for scanned documents"]:
            item = paper("2610.00002", title, "A synthetic document understanding evaluation.")
            with self.subTest(title=title):
                self.assertGreater(research.document_relevance(item), 0)

    def test_on_topic_phrase_still_needs_independent_document_anchor(self):
        item = paper("2610.00003", "Document retrieval for generic web search", "A dense retrieval experiment ranks ordinary web pages.")
        settings = [{"id": "docrag", "title": "文档检索", "terms": ["document retrieval"], "categories": ["cs.IR"]}]
        self.assertFalse(research.classify(item, settings))

    def test_explicit_document_titles_rank_above_incidental_abstract_mentions(self):
        strong = paper("2610.00004", "Optical character recognition for document parsing", "Document layout analysis and document question answering.")
        weak = paper("2610.00005", "A broadly applicable machine learning method", "One experiment includes optical character recognition.")
        ranked = research.rank_documents([weak, strong], NOW)
        self.assertEqual(ranked[0]["id"], strong["id"])
        self.assertGreater(ranked[0]["relevanceScore"], ranked[1]["relevanceScore"])
        self.assertTrue(ranked[0]["rankReasons"])
        self.assertTrue(all("rankScore" in row for row in ranked))
        explanations = " ".join(str(reason) for row in ranked for reason in row["rankReasons"]).lower()
        self.assertNotIn("state of the art", explanations)
        self.assertNotIn("peer reviewed", explanations)

    def test_recency_orders_equally_relevant_items(self):
        old = paper("2610.00006", "Optical character recognition for document parsing", "A document understanding study.", days=20)
        recent = paper("2610.00007", old["title"], old["abstract"], days=1)
        ranked = research.rank_documents([old, recent], NOW)
        self.assertEqual(ranked[0]["id"], recent["id"])
        self.assertGreater(ranked[0]["rankScore"], ranked[1]["rankScore"])

    def test_comparable_items_do_not_allow_one_topic_to_dominate_first_results(self):
        shared_title = "Optical character recognition and document layout analysis"
        shared_abstract = "A synthetic document understanding study."
        repeated = [paper(f"2610.00{index:03d}", shared_title, shared_abstract, topics=["ocr"]) for index in range(10, 15)]
        other = paper("2610.00009", shared_title, shared_abstract, topics=["layout"])
        ranked = research.rank_documents(repeated + [other], NOW)
        self.assertIn(other["id"], [row["id"] for row in ranked[:3]])
        self.assertEqual(len(ranked), len(repeated) + 1)
        self.assertEqual(repeated[0].get("rankScore"), None, "Ranking must not mutate stored source metadata")

    def test_comparable_items_also_diversify_sources(self):
        shared_title = "Optical character recognition for document parsing"
        shared_abstract = "A synthetic document understanding study."
        repeated = [paper(f"2610.00{index:03d}", shared_title, shared_abstract) for index in range(20, 25)]
        other = paper("2610.00019", shared_title, shared_abstract)
        other.update(sourceName="GitHub", repo="PaddlePaddle/PaddleOCR")
        ranked = research.rank_documents(repeated + [other], NOW)
        self.assertIn(other["id"], [row["id"] for row in ranked[:3]])

    def test_scope_migration_drops_irrelevant_history_even_when_requests_fail(self):
        old = snapshot()
        old.update(schemaVersion=1, scope="search-advertising-recommendation")
        old["topics"] = [{"id": "ads", "title": "广告", "status": "fresh", "lastChecked": "2026-10-01T00:00:00Z"}]
        irrelevant = paper("2610.00008", "CTR prediction for advertising", "A click-through rate model.", topics=["ads"])
        old["papers"].append(irrelevant)
        with patch.object(research, "fetch", side_effect=research.ResearchError("synthetic outage")):
            result, _ = research.run(old, config(), NOW)
        self.assertEqual(result["schemaVersion"], 2)
        self.assertEqual(result["scope"], "document-intelligence")
        self.assertNotIn(irrelevant["id"], [row["id"] for row in result["papers"]])
        self.assertIn(old["papers"][0]["id"], [row["id"] for row in result["papers"]])
        self.assertFalse(result.get("lastSuccessfulCheck"))
        self.assertTrue(all(not topic.get("lastChecked") for topic in result["topics"]))

    def test_old_schema_check_dates_are_not_reused_even_if_scope_label_matches(self):
        old = snapshot()
        old["schemaVersion"] = 1
        with patch.object(research, "fetch", side_effect=research.ResearchError("synthetic outage")):
            result, _ = research.run(old, config(), NOW)
        self.assertFalse(result.get("lastSuccessfulCheck"))
        self.assertTrue(all(not topic.get("lastChecked") for topic in result["topics"]))


class GitHubReleaseTests(OfflineCase):
    repo = "PaddlePaddle/PaddleOCR"

    def test_release_uses_publication_not_creation_date_and_falls_back_to_tag(self):
        entries = research.parse_releases(release_payload(), self.repo, NOW)
        self.assertEqual(len(entries), 1)
        row = entries[0]
        self.assertEqual(row["id"], "github:PaddlePaddle/PaddleOCR:123")
        self.assertEqual(row["kind"], "release")
        self.assertEqual(row["published"], "2026-10-26T10:00:00Z")
        self.assertEqual(row["updated"], "2026-10-27T10:00:00Z")
        self.assertIn("v1.2", row["title"])
        self.assertFalse(row.get("pdfUrl"))
        self.assertEqual(row["url"], release_payload()[0]["html_url"])

    def test_drafts_prereleases_and_unpublished_entries_are_skipped(self):
        for changes in [{"draft": True}, {"prerelease": True}, {"published_at": None}]:
            payload = release_payload()
            payload[0].update(changes)
            with self.subTest(changes=changes):
                self.assertEqual(research.parse_releases(payload, self.repo, NOW), [])

    def test_rate_limit_failure_does_not_expose_tokens_or_retry_unboundedly(self):
        url = f"https://api.github.com/repos/{self.repo}/releases?per_page=20"
        error = urllib.error.HTTPError(url, 403, "Rate limited", {"X-RateLimit-Remaining": "0"}, io.BytesIO(b"private-token-value"))
        with patch.dict(os.environ, {"GITHUB_TOKEN": "private-token-value"}), patch.object(research.urllib.request, "urlopen", side_effect=error) as opened:
            with self.assertRaises(research.ResearchError) as raised:
                research.fetch_releases(self.repo, NOW)
        self.assertEqual(opened.call_count, 1)
        self.assertIn("rate limit", str(raised.exception).lower())
        self.assertNotIn("private-token-value", str(raised.exception))

    def test_unverified_project_or_redirect_is_rejected(self):
        with self.assertRaises(research.ResearchError):
            research.fetch_releases("Unverified/Project", NOW)
        with patch.object(research.urllib.request, "urlopen", return_value=FakeResponse("https://evil.test/releases", b"[]")):
            with self.assertRaises(research.ResearchError):
                research.fetch_releases(self.repo, NOW)

    def test_invalid_release_json_is_not_a_valid_empty_feed(self):
        url = f"https://api.github.com/repos/{self.repo}/releases?per_page=20"
        with patch.object(research.urllib.request, "urlopen", return_value=FakeResponse(url, b"<html>Service unavailable</html>")):
            with self.assertRaises(research.ResearchError):
                research.fetch_releases(self.repo, NOW)

    def test_api_errors_invalid_dates_and_wrong_urls_are_not_empty_success(self):
        for payload in [{"message": "rate limit exceeded"}, None, ["not a release"]]:
            with self.subTest(payload=payload), self.assertRaises(research.ResearchError):
                research.parse_releases(payload, self.repo, NOW)
        for changes in [
            {"published_at": "2026-02-30T00:00:00Z"},
            {"published_at": "2027-10-26T10:00:00Z"},
            {"updated_at": "2026-01-01T00:00:00Z"},
            {"html_url": "javascript:alert(1)"},
            {"html_url": "https://evil.test/PaddlePaddle/PaddleOCR/releases/tag/v1.2"},
            {"html_url": "https://github.com/Other/Repository/releases/tag/v1.2"},
        ]:
            payload = release_payload()
            payload[0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(research.ResearchError):
                research.parse_releases(payload, self.repo, NOW)

    def test_failed_release_source_retains_verified_entry_and_check_date(self):
        settings = config()
        settings["githubRepos"] = [self.repo]
        old = snapshot()
        release = {
            **release_payload()[0], "id": "github:PaddlePaddle/PaddleOCR:123", "kind": "release",
            "title": "Official OCR release", "abstract": "Document parsing improvements.",
            "published": "2026-10-26T10:00:00Z", "updated": "2026-10-27T10:00:00Z",
            "url": release_payload()[0]["html_url"], "repo": self.repo, "topics": ["ocr"],
            "sourceName": "GitHub", "firstSeen": "2026-10-26T10:00:00Z", "lastSeen": "2026-10-27T10:00:00Z",
        }
        old["papers"].append(release)
        old["sources"] = [{"id": "github:" + self.repo, "repo": self.repo, "title": self.repo, "status": "fresh", "lastChecked": "2026-10-27T10:00:00Z"}]
        with patch.object(research, "fetch", side_effect=lambda url, **kwargs: research.FetchResult(url, empty_feed())), patch.object(research, "fetch_releases", side_effect=research.ResearchError("synthetic GitHub timeout")):
            result, _ = research.run(old, settings, NOW)
        self.assertEqual(result["status"], "partial")
        self.assertIn(release["id"], [row["id"] for row in result["papers"]])
        source = next(row for row in result["sources"] if row["id"] == "github:" + self.repo)
        self.assertEqual(source["status"], "stale")
        self.assertEqual(source["lastChecked"], old["sources"][0]["lastChecked"])


if __name__ == "__main__":
    unittest.main()
