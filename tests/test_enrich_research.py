"""Offline regressions for free-only research enrichment; never call an API."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import enrich_research as intelligence

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
ABSTRACT = "We propose document OCR with layout evidence and compare 12 datasets."
ENV = {
    "CLOUDFLARE_ACCOUNT_ID": "a" * 32,
    "CLOUDFLARE_API_TOKEN": "offline-test-token-never-real",
    "FREE_AI_PLAN_CONFIRMED": "true",
}


def paper(number=1, **overrides):
    identifier = f"2611.{number:05d}"
    item = {
        "id": "arxiv:" + identifier,
        "arxiv": identifier,
        "version": 1,
        "kind": "paper",
        "title": f"Document OCR method {number}",
        "abstract": ABSTRACT,
        "authors": ["Example Author"],
        "url": "https://arxiv.org/abs/" + identifier,
        "pdfUrl": "https://arxiv.org/pdf/" + identifier,
        "published": "2026-11-08T03:00:00Z",
        "updated": "2026-11-08T03:00:00Z",
        "topics": ["ocr"],
        "sourceName": "arXiv",
        "rankScore": 1 - number / 100,
        "relevanceScore": .9,
    }
    return {**item, **overrides}


def snapshot(*items):
    return {
        "schemaVersion": 2,
        "scope": "document-intelligence",
        "status": "refreshed",
        "lastAttempt": "2026-11-09T03:16:00Z",
        "lastSuccessfulCheck": "2026-11-09T03:16:00Z",
        "topics": [{"id": "ocr", "title": "OCR", "status": "fresh", "lastChecked": "2026-11-09T03:16:00Z"}],
        "papers": list(items) or [paper()],
    }


def empty_cache():
    return {"schemaVersion": 1, "scope": "document-intelligence", "entries": {}, "budgetLedger": {}}


def config(**overrides):
    result = copy.deepcopy(intelligence.DEFAULT_CONFIG)
    result.setdefault("embedding", {})["enabled"] = False
    result["maxEmbeddingsPerDay"] = 0
    result.update(overrides)
    return result


def answer(**overrides):
    value = {
        "summary": "该研究提出结合版面证据的文档文字识别方法，并在12个数据集上比较。",
        "summaryEvidence": ABSTRACT,
        "contributions": [{"point": "结合版面证据进行文档文字识别。", "evidence": "document OCR with layout evidence"}],
        "topics": ["ocr"],
    }
    value.update(overrides)
    return {"response": json.dumps(value, ensure_ascii=False)}


class FakeClient:
    def __init__(self, response=None, error=None, before_call=None):
        self.response = answer() if response is None else response
        self.error = error
        self.before_call = before_call
        self.calls = []

    def call(self, model, payload):
        self.calls.append((model, copy.deepcopy(payload)))
        if self.before_call:
            self.before_call()
        if self.error:
            raise self.error
        if "embedding" in model:
            return {"data": [[.1, .2, .3]]}
        return copy.deepcopy(self.response)


class EnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.saved = []
        patcher = patch("urllib.request.urlopen", side_effect=AssertionError("No live network in offline tests"))
        patcher.start()
        self.addCleanup(patcher.stop)
        opener_patcher = patch("urllib.request.build_opener", side_effect=AssertionError("No live network in offline tests"))
        opener_patcher.start()
        self.addCleanup(opener_patcher.stop)

    def run_enrichment(self, source=None, cached=None, settings=None, now=NOW, env=None, client=None, persist_cache=None):
        persist = persist_cache or (lambda state: self.saved.append(copy.deepcopy(state)))
        return intelligence.enrich(
            snapshot(paper()) if source is None else source,
            empty_cache() if cached is None else cached,
            config() if settings is None else settings,
            now,
            env={} if env is None else env,
            client=FakeClient() if client is None else client,
            persist_cache=persist,
        )

    def test_missing_credentials_or_confirmation_never_calls_model(self):
        variants = [{}, {k: v for k, v in ENV.items() if k != "FREE_AI_PLAN_CONFIRMED"},
                    {k: v for k, v in ENV.items() if k != "CLOUDFLARE_API_TOKEN"},
                    {k: v for k, v in ENV.items() if k != "CLOUDFLARE_ACCOUNT_ID"},
                    {**ENV, "FREE_AI_PLAN_CONFIRMED": "false"}]
        for env in variants:
            with self.subTest(env_keys=list(env)):
                client = FakeClient()
                digest, _ = self.run_enrichment(env=env, client=client)
                self.assertEqual(client.calls, [])
                self.assertEqual(digest["status"], "unconfigured")
                self.assertGreater(digest["pendingCount"], 0)
                item = digest["items"][0]
                self.assertEqual(item["summaryKind"], "source-excerpt")
                self.assertIn(item["summary"], ABSTRACT)
                self.assertEqual(item["url"], paper()["url"])
                self.assertNotIn(ENV["CLOUDFLARE_API_TOKEN"], json.dumps(digest))

    def test_valid_source_enrichment_is_grounded_and_uses_only_source_link(self):
        client = FakeClient()
        digest, _ = self.run_enrichment(env=ENV, client=client)
        self.assertEqual(len(client.calls), 1)
        item = digest["items"][0]
        self.assertEqual(item["url"], paper()["url"])
        self.assertIn("文档", item["summary"])
        self.assertNotEqual(item["summaryKind"], "source-excerpt")
        self.assertTrue(item["contributions"])
        self.assertEqual(item["topics"], ["ocr"])
        self.assertEqual(item["sourceFingerprint"], intelligence.fingerprint(intelligence.valid_source(paper(), NOW)))
        self.assertEqual(digest["budget"]["modelRequests"], 1)
        self.assertNotIn(ENV["CLOUDFLARE_API_TOKEN"], json.dumps(digest))
        payload = client.calls[0][1]
        self.assertEqual(payload["max_completion_tokens"], config()["maxOutputTokens"])
        self.assertNotIn("max_tokens", payload)

    def test_disallowed_model_configuration_never_calls_provider(self):
        invalid_settings = [config(summaryModel="@cf/meta/llama-paid-alternative"), config()]
        invalid_settings[1]["embedding"]["model"] = "@cf/unverified/embedding-alternative"
        for settings in invalid_settings:
            with self.subTest(settings=settings):
                client = FakeClient()
                with self.assertRaises(intelligence.IntelligenceError):
                    self.run_enrichment(settings=settings, env=ENV, client=client)
                self.assertEqual(client.calls, [])

    def test_malformed_account_ids_never_enable_model_calls(self):
        for account in ("a" * 31, "a" * 33, "../other-account", "a" * 32 + "/../../", "https://evil.test", "z" * 32):
            with self.subTest(account=account):
                client = FakeClient()
                digest, _ = self.run_enrichment(env={**ENV, "CLOUDFLARE_ACCOUNT_ID": account}, client=client)
                self.assertEqual(client.calls, [])
                self.assertEqual(digest["status"], "unconfigured")

    def test_cloudflare_transport_uses_only_allowlisted_exact_endpoints(self):
        requests = []
        class Response:
            def __init__(self, url):
                self.url = url
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return self.url
            def read(self, limit):
                return b'{"success": true, "result": {"sentinel": "offline"}}'
        class Opener:
            def open(self, request, timeout):
                requests.append(request)
                return Response(request.full_url)
        with patch("urllib.request.build_opener", return_value=Opener()):
            client = intelligence.CloudflareClient(ENV)
            for model in (intelligence.SUMMARY_MODEL, intelligence.EMBEDDING_MODEL):
                self.assertEqual(client.call(model, {"test": "offline"}), {"sentinel": "offline"})
                self.assertEqual(requests[-1].full_url, f"https://api.cloudflare.com/client/v4/accounts/{ENV['CLOUDFLARE_ACCOUNT_ID']}/ai/run/{model}")
            with self.assertRaises(intelligence.ProviderUnavailable):
                client.call("@cf/unverified/paid-model", {})
        self.assertEqual(len(requests), 2)

    def test_transport_provider_errors_do_not_expose_tokens_or_raw_messages(self):
        class Opener:
            def open(self, request, timeout):
                raise urllib.error.URLError("Private provider detail: " + ENV["CLOUDFLARE_API_TOKEN"])
        with patch("urllib.request.build_opener", return_value=Opener()):
            with self.assertRaises(intelligence.ProviderUnavailable) as caught:
                intelligence.CloudflareClient(ENV).call(intelligence.SUMMARY_MODEL, {})
        self.assertEqual(str(caught.exception), "unavailable")
        self.assertNotIn(ENV["CLOUDFLARE_API_TOKEN"], str(caught.exception))

    def test_matching_cache_is_reused_even_without_credentials(self):
        first, cached = self.run_enrichment(env=ENV)
        client = FakeClient(error=AssertionError("Cache hit must not call provider"))
        second, _ = self.run_enrichment(cached=cached, client=client)
        self.assertEqual(client.calls, [])
        self.assertEqual(second["items"][0]["summary"], first["items"][0]["summary"])
        self.assertEqual(second["pendingCount"], 0)
        self.assertEqual(second["status"], "ready")

    def test_source_revision_invalidates_cached_generation(self):
        first, cached = self.run_enrichment(env=ENV)
        changed = paper(version=2, updated="2026-11-09T08:00:00Z", abstract=ABSTRACT + " We also discuss reading order.")
        client = FakeClient()
        second, _ = self.run_enrichment(source=snapshot(changed), cached=cached, env=ENV, client=client)
        self.assertEqual(len(client.calls), 1)
        self.assertNotEqual(first["items"][0]["sourceFingerprint"], second["items"][0]["sourceFingerprint"])
        self.assertFalse(second["items"][0].get("stale", False))
        self.assertEqual(second["budget"]["modelRequests"], 2)

    def test_digest_limits_release_noise_and_prefers_papers_for_remaining_slots(self):
        releases = []
        for repo_index, repo in enumerate(("docling-project/docling", "opendatalab/MinerU")):
            for number in range(3):
                tag = f"v3.0.{number}"
                releases.append({
                    "id": f"github:{repo}:{1000 + repo_index * 10 + number}",
                    "kind": "release", "repo": repo, "tag": tag,
                    "title": f"{repo} {tag}", "abstract": ABSTRACT,
                    "url": f"https://github.com/{repo}/releases/tag/{tag}",
                    "published": "2026-11-08T03:00:00Z", "updated": "2026-11-08T03:00:00Z",
                    "topics": ["ocr", "layout", "table"], "rankScore": 2 - number / 100,
                })
        papers = [paper(i, topics=["ocr", "layout", "table"]) for i in range(1, 9)]
        digest, _ = self.run_enrichment(snapshot(*releases, *papers))
        selected_releases = [item for item in digest["items"] if item["kind"] == "release"]
        self.assertEqual(len(digest["items"]), 10)
        self.assertEqual(len(selected_releases), 2)
        self.assertEqual(len({item["id"].rsplit(":", 1)[0] for item in selected_releases}), 2)
        self.assertEqual(sum(item["kind"] == "paper" for item in digest["items"]), 8)

    def test_summary_version_change_invalidates_matching_source_cache(self):
        first, cached = self.run_enrichment(env=ENV)
        revised_config = config(summaryVersion="abstract-zh-v2-offline-test")
        client = FakeClient()
        second, _ = self.run_enrichment(cached=cached, settings=revised_config, env=ENV, client=client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(second["items"][0]["sourceFingerprint"], first["items"][0]["sourceFingerprint"])
        self.assertEqual(second["budget"]["modelRequests"], 2)

    def test_embedding_opt_in_is_cached_and_bound_to_validated_source(self):
        settings = config(maxEmbeddingsPerDay=8, maxRequestsPerDay=16)
        settings["embedding"]["enabled"] = True
        client = FakeClient()
        first, cached = self.run_enrichment(settings=settings, env=ENV, client=client)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(sum("embedding" in model for model, _ in client.calls), 1)
        item = first["items"][0]
        embedding = item["embedding"]
        self.assertEqual(embedding["sourceFingerprint"], item["sourceFingerprint"])
        self.assertEqual(len(embedding["vector"]), 3)
        self.assertTrue(all(math.isfinite(value) for value in embedding["vector"]))
        self.assertAlmostEqual(sum(value * value for value in embedding["vector"]), 1.0, places=6)
        second_client = FakeClient(error=AssertionError("Cached embedding must not call provider"))
        second, _ = self.run_enrichment(cached=cached, settings=settings, client=second_client)
        self.assertEqual(second_client.calls, [])
        self.assertEqual(second["items"][0]["embedding"], embedding)

    def test_corrupt_embedding_keeps_previously_validated_summary(self):
        settings = config(maxEmbeddingsPerDay=8, maxRequestsPerDay=16)
        settings["embedding"]["enabled"] = True
        first, cached = self.run_enrichment(settings=settings, env=ENV)
        cached["entries"][paper()["id"]]["embedding"]["vector"] = [float("nan"), 0]
        client = FakeClient(error=AssertionError("Unconfigured cache load cannot call provider"))
        digest, _ = self.run_enrichment(cached=cached, settings=settings, client=client)
        self.assertEqual(client.calls, [])
        self.assertEqual(digest["items"][0]["summary"], first["items"][0]["summary"])
        self.assertEqual(digest["items"][0]["summaryStatus"], "ready")
        self.assertNotIn("embedding", digest["items"][0])

    def test_cache_with_disallowed_model_is_not_treated_as_verified(self):
        _, cached = self.run_enrichment(env=ENV)
        cached["entries"][paper()["id"]]["model"] = "@cf/unverified/summary-model"
        client = FakeClient()
        digest, _ = self.run_enrichment(cached=cached, env=ENV, client=client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(digest["budget"]["modelRequests"], 2)

    def test_disabled_embedding_never_calls_embedding_model(self):
        client = FakeClient()
        digest, _ = self.run_enrichment(env=ENV, client=client)
        self.assertFalse(any("embedding" in model for model, _ in client.calls))
        self.assertNotIn("embedding", digest["items"][0])

    def test_daily_budget_persists_across_runs_and_resets_next_day(self):
        source = snapshot(paper(1), paper(2), paper(3))
        settings = config(maxSummariesPerDay=1, maxRequestsPerDay=1)
        client = FakeClient()
        first, cached = self.run_enrichment(source, settings=settings, env=ENV, client=client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(first["budget"]["modelRequests"], 1)
        second_client = FakeClient()
        second, cached = self.run_enrichment(source, cached, settings, env=ENV, client=second_client)
        self.assertEqual(second_client.calls, [])
        self.assertEqual(second["budget"]["modelRequests"], 1)
        next_client = FakeClient()
        third, _ = self.run_enrichment(source, cached, settings, now=NOW + timedelta(days=1), env=ENV, client=next_client)
        self.assertEqual(len(next_client.calls), 1)
        self.assertEqual(third["budget"]["modelRequests"], 1)

    def test_pending_queue_eventually_processes_sources_beyond_display_limit(self):
        for count in (3, 12):
            with self.subTest(source_count=count):
                papers = [paper(number) for number in range(1, count + 1)]
                source = snapshot(*papers)
                settings = config(maxItems=2, maxSummariesPerDay=1, maxRequestsPerDay=1)
                cached = empty_cache()
                for day in range(count):
                    client = FakeClient()
                    digest, cached = self.run_enrichment(
                        source, cached, settings, now=NOW + timedelta(days=day), env=ENV, client=client,
                    )
                    self.assertEqual(len(client.calls), 1)
                    self.assertEqual(len(digest["items"]), 2)
                    self.assertEqual(digest["budget"]["modelRequests"], 1)
                    self.assertEqual(digest["pendingCount"], count - day - 1)
                self.assertIn(papers[-1]["id"], cached["entries"])
                self.assertEqual(len(cached["entries"]), count)

    def test_quota_keeps_prior_output_marks_it_stale_and_stops_same_day(self):
        first, cached = self.run_enrichment(env=ENV)
        changed = paper(version=2, updated="2026-11-09T08:00:00Z", abstract=ABSTRACT + " Revised document evidence.")
        client = FakeClient(error=intelligence.ProviderUnavailable("quota"))
        second, cached = self.run_enrichment(snapshot(changed), cached, env=ENV, client=client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(second["items"][0]["summary"], first["items"][0]["summary"])
        self.assertTrue(second["items"][0]["stale"])
        self.assertEqual(second["status"], "quota")
        retry = FakeClient()
        _, cached = self.run_enrichment(snapshot(changed), cached, env=ENV, client=retry)
        self.assertEqual(retry.calls, [])
        next_day = FakeClient()
        resumed, _ = self.run_enrichment(snapshot(changed), cached, now=NOW + timedelta(days=1), env=ENV, client=next_day)
        self.assertEqual(len(next_day.calls), 1)
        self.assertFalse(resumed["items"][0].get("stale", False))

    def test_provider_error_is_sanitized_and_does_not_erase_previous_cache(self):
        first, cached = self.run_enrichment(env=ENV)
        changed = paper(version=2, updated="2026-11-09T08:00:00Z", abstract=ABSTRACT + " A revised abstract.")
        client = FakeClient(error=intelligence.ProviderUnavailable("unavailable"))
        digest, retained = self.run_enrichment(snapshot(changed), cached, env=ENV, client=client)
        self.assertEqual(digest["items"][0]["summary"], first["items"][0]["summary"])
        self.assertTrue(retained["entries"])
        self.assertGreater(digest["pendingCount"], 0)

    def test_model_urls_html_ungrounded_numbers_and_invented_evidence_are_rejected(self):
        invalid = [
            answer(summary="请访问 https://evil.test 查看文档研究。"),
            answer(summary="<img src=x onerror=alert(1)>文档分析结果。"),
            answer(summary="该方法在999个数据集上超过所有方法。"),
            answer(summaryEvidence="This sentence does not occur in the abstract."),
            answer(contributions=[{"point": "该方法改善了文档识别。", "evidence": "invented supporting quote"}]),
            answer(topics=["advertising"]),
            answer(url="https://evil.test/model-supplied-link"),
            answer(contributions=[{"point": "结合版面证据进行识别。", "evidence": "document OCR with layout evidence", "url": "https://evil.test"}]),
        ]
        for response in invalid:
            with self.subTest(response=response):
                digest, _ = self.run_enrichment(env=ENV, client=FakeClient(response=response))
                item = digest["items"][0]
                self.assertEqual(item["summaryKind"], "source-excerpt")
                self.assertIn(item["summary"], ABSTRACT)
                self.assertNotIn("evil.test", json.dumps(digest))
                self.assertNotIn("onerror", json.dumps(digest))
                self.assertNotIn("999", item["summary"])

    def test_unsafe_sources_are_not_published_or_sent_to_the_model(self):
        unsafe = [
            paper(url="https://arxiv.org.evil.test/abs/2611.00001"),
            paper(url="http://arxiv.org/abs/2611.00001"),
            paper(url="https://evil@arxiv.org/abs/2611.00001"),
            paper(url="javascript:alert(1)"),
            paper(url="https://arxiv.org/abs/2611.00002"),
            paper(updated="2026-11-10T03:00:00Z"),
            paper(updated="2026-11-07T03:00:00Z"),
            paper(updated="2026-11-08T03:00:00"),
            paper(topics=["advertising"]),
        ]
        client = FakeClient()
        digest, _ = self.run_enrichment(snapshot(*unsafe), env=ENV, client=client)
        self.assertEqual(digest["items"], [])
        self.assertEqual(client.calls, [])

    def test_corrupt_source_scope_is_not_treated_as_empty_success(self):
        wrong = {**snapshot(paper()), "scope": "ads"}
        with self.assertRaises(intelligence.IntelligenceError):
            self.run_enrichment(wrong)

    def test_only_official_matching_release_identity_is_accepted(self):
        release = {
            "id": "github:PaddlePaddle/PaddleOCR:123456",
            "kind": "release",
            "repo": "PaddlePaddle/PaddleOCR",
            "title": "PaddleOCR · v3.0.0",
            "abstract": "Official document OCR release with layout evidence.",
            "authors": [],
            "published": "2026-11-08T03:00:00Z",
            "updated": "2026-11-08T03:00:00Z",
            "url": "https://github.com/PaddlePaddle/PaddleOCR/releases/tag/v3.0.0",
            "tag": "v3.0.0",
            "sourceName": "GitHub · PaddlePaddle/PaddleOCR",
            "topics": ["ocr"],
        }
        digest, _ = self.run_enrichment(snapshot(release))
        self.assertEqual(len(digest["items"]), 1)
        self.assertEqual(digest["items"][0]["kind"], "release")
        self.assertEqual(digest["items"][0]["url"], release["url"])
        bad_variants = [
            {**release, "repo": "untrusted/PaddleOCR", "id": "github:untrusted/PaddleOCR:123456",
             "url": "https://github.com/untrusted/PaddleOCR/releases/tag/v3.0.0"},
            {**release, "url": "https://github.com/PaddlePaddle/PaddleOCR/releases/tag/v4.0.0"},
            {**release, "id": "github:opendatalab/MinerU:123456"},
            {**release, "url": "https://github.com/PaddlePaddle/PaddleOCR/issues/123456"},
        ]
        for bad in bad_variants:
            with self.subTest(source=bad):
                client = FakeClient()
                digest, _ = self.run_enrichment(snapshot(bad), env=ENV, client=client)
                self.assertEqual(digest["items"], [])
                self.assertEqual(client.calls, [])

    def test_request_budget_is_persisted_before_network_call(self):
        def find_counters(value):
            if isinstance(value, dict):
                return ([value["modelRequests"]] if "modelRequests" in value else []) + [x for v in value.values() for x in find_counters(v)]
            if isinstance(value, list):
                return [x for v in value for x in find_counters(v)]
            return []

        def check_reservation():
            self.assertTrue(self.saved, "No durable budget reservation occurred")
            self.assertTrue(any(value > 0 for value in find_counters(self.saved[-1])))

        self.run_enrichment(env=ENV, client=FakeClient(before_call=check_reservation))

    def test_failed_budget_persistence_prevents_model_call(self):
        client = FakeClient()
        def fail(_):
            raise OSError("Offline disk-full simulation")
        with self.assertRaises((OSError, intelligence.IntelligenceError)):
            self.run_enrichment(env=ENV, client=client, persist_cache=fail)
        self.assertEqual(client.calls, [])

    def test_atomic_write_failure_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "cache.json"
            previous = b'{"sentinel":"previous verified cache"}\n'
            target.write_bytes(previous)
            with patch.object(intelligence.os, "replace", side_effect=OSError("Offline rename failure")):
                with self.assertRaises((OSError, intelligence.IntelligenceError)):
                    intelligence.atomic_write_json(target, {"sentinel": "new value"})
            self.assertEqual(target.read_bytes(), previous)


if __name__ == "__main__":
    unittest.main()
