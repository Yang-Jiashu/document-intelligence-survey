"""Free compatibility maintenance must preserve evidence without paid requests."""

import copy
from contextlib import ExitStack, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_dynamic_papers as dynamic


class FreeDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config_path = self.root / "config.json"
        self.dynamic_path = self.root / "dynamic.json"
        self.pending_path = self.root / "pending.json"
        self.log_path = self.root / "log.json"
        self.snapshot_path = self.root / "research.json"
        self.config = {
            "freeOnly": True,
            # Even accidentally enabled provider flags and present keys cannot
            # defeat the top-level free policy.
            "enabledProviders": ["tavily"],
            "llmClassification": {"enabled": True, "apiKeyEnv": "DMX_API_KEY"},
            "verifiedSeedArticles": [{"url": f"https://mp.weixin.qq.com/s/seed-{i}"} for i in range(5)],
            "taxonomy": [{"id": "ocr", "title": "OCR", "keywords": ["OCR"]}],
        }
        self.historical = {
            "lastUpdated": "2026-01-02T00:00:00Z",
            "sourceStatus": {"wechat": {"lastVerified": "2026-01-01T12:00:00Z"}},
            "verifiedWechatArticles": [
                {"url": f"https://mp.weixin.qq.com/s/history-{i}", "foundAt": "2026-01-01", "verifiedAt": "2026-01-01T12:00:00Z", "provider": "verified-seed"}
                for i in range(5)
            ],
            "papers": [{
                "arxiv": "2601.00001", "title": "Old OCR title", "abstract": "Old document abstract",
                "authors": "An Author", "updated": "2026-01-01", "firstSeen": "2026-01-02",
                "lastSeen": "2026-01-02", "sourceMentions": [{"foundAt": "2026-01-01"}],
            }],
        }
        self.pending = {"lastUpdated": "2026-01-02T00:00:00Z", "items": [{"reason": "untrusted_source", "candidateTitle": "Keep for review"}]}
        self.snapshot = {
            "schemaVersion": 2, "scope": "document-intelligence", "status": "refreshed",
            "lastSuccessfulCheck": "2026-02-11T00:00:00Z",
            "papers": [{
                "kind": "paper", "sourceName": "arXiv", "arxiv": "2601.00001",
                "title": "Revised OCR title", "abstract": "New public document abstract", "authors": ["An Author", "B Author"],
                "updated": "2026-02-10T10:00:00Z", "published": "2026-01-01T10:00:00Z",
                "lastSeen": "2026-02-11T00:00:00Z", "url": "https://arxiv.org/abs/2601.00001",
                "pdfUrl": "https://arxiv.org/pdf/2601.00001", "arxivCategories": ["cs.CV"],
            }],
        }
        self.write_inputs()

    def write_inputs(self):
        for path, value in ((self.config_path, self.config), (self.dynamic_path, self.historical), (self.pending_path, self.pending), (self.snapshot_path, self.snapshot)):
            path.write_text(json.dumps(value), encoding="utf-8")

    def run_free(self, flags=()):
        with ExitStack() as stack:
            for name, value in {
                "DYNAMIC_PAPERS_PATH": self.dynamic_path, "PENDING_DYNAMIC_PATH": self.pending_path,
                "UPDATE_LOG_PATH": self.log_path, "RESEARCH_UPDATES_PATH": self.snapshot_path,
                "CURATED_INDEX_PATH": self.root / "curated.json",
            }.items():
                stack.enter_context(patch.object(dynamic, name, value))
            stack.enter_context(patch.dict(os.environ, {"TAVILY_API_KEY": "valid-key-present", "DMX_API_KEY": "valid-key-present"}))
            # A free run must not even read local credentials or enter a paid
            # helper, not merely recover after a request has failed.
            blocked = [stack.enter_context(patch.object(dynamic, name, side_effect=AssertionError(f"unexpected {name}")))
                       for name in ("read_local_api_key", "read_local_env_value", "get_env_or_local", "post_json", "tavily_search", "tavily_extract")]
            opened = stack.enter_context(patch.object(dynamic.urllib.request, "urlopen", side_effect=AssertionError("unexpected network")))
            stack.enter_context(redirect_stdout(io.StringIO()))
            self.assertEqual(dynamic.main(["--config", str(self.config_path), *flags]), 0)
            opened.assert_not_called()
            for mocked in blocked:
                mocked.assert_not_called()

    def test_enabled_provider_and_valid_credentials_cannot_bypass_free_only(self):
        self.run_free(["--provider", "tavily"])
        result = json.loads(self.dynamic_path.read_text())
        self.assertEqual(result["verifiedWechatArticles"], self.historical["verifiedWechatArticles"])
        self.assertEqual(result["lastUpdated"], self.historical["lastUpdated"])
        self.assertEqual(json.loads(self.pending_path.read_text()), self.pending)
        self.assertEqual(result["sourceStatus"]["wechat"]["status"], "retained_not_rechecked")
        self.assertEqual(result["sourceStatus"]["wechat"]["lastVerified"], self.historical["sourceStatus"]["wechat"]["lastVerified"])
        self.assertEqual(json.loads(self.config_path.read_text())["verifiedSeedArticles"], self.config["verifiedSeedArticles"])
        self.assertEqual(result["papers"][0]["title"], "Revised OCR title")
        self.assertEqual(result["papers"][0]["authors"], "An Author, B Author")
        for key in ("firstSeen", "lastSeen", "sourceMentions"):
            self.assertEqual(result["papers"][0][key], self.historical["papers"][0][key])
        self.assertEqual(result["papers"][0]["metadataSnapshotLastSeen"], self.snapshot["lastSuccessfulCheck"])
        log = json.loads(self.log_path.read_text())
        self.assertEqual((log["paidApiCalls"], log["externalRequests"], log["llmClassificationAttempted"]), (0, 0, 0))
        self.assertEqual(log["verifiedSeedArticles"], 0)
        self.assertEqual(log["retainedWechatArticles"], 5)

    def test_missing_free_only_is_also_free(self):
        del self.config["freeOnly"]
        self.write_inputs()
        self.run_free(["--provider", "tavily"])

    def test_cli_free_only_overrides_explicit_legacy_configuration(self):
        self.config["freeOnly"] = False
        self.write_inputs()
        self.run_free(["--provider", "tavily", "--free-only"])

    def test_dry_run_never_writes_data_or_verification_dates(self):
        before = self.dynamic_path.read_bytes()
        self.run_free(["--dry-run"])
        self.assertEqual(self.dynamic_path.read_bytes(), before)
        self.assertFalse(self.log_path.exists())

    def test_missing_or_invalid_snapshot_retains_all_history(self):
        self.snapshot_path.unlink()
        self.run_free()
        result = json.loads(self.dynamic_path.read_text())
        self.assertEqual(result["papers"], self.historical["papers"])
        self.assertEqual(result["verifiedWechatArticles"], self.historical["verifiedWechatArticles"])
        self.assertEqual(result["sourceStatus"]["arxiv"]["status"], "snapshot_unavailable")

    def test_metadata_sync_rejects_non_arxiv_sources_and_older_revisions(self):
        for mutation in ({"url": "https://example.com/2601.00001"}, {"updated": "2025-01-01"}, {"sourceName": "Unverified"}):
            snapshot = copy.deepcopy(self.snapshot)
            snapshot["papers"][0].update(mutation)
            existing = copy.deepcopy(self.historical)
            self.assertEqual(dynamic.sync_existing_free_metadata(existing, snapshot), 0)
            self.assertEqual(existing, self.historical)

    def test_paid_post_and_direct_llm_calls_are_closed_without_opt_in_context(self):
        with patch.object(dynamic.urllib.request, "urlopen") as opened, patch.object(dynamic, "get_env_or_local") as secret:
            with self.assertRaises(dynamic.PaidApiDisabledError):
                dynamic.post_json(dynamic.TAVILY_SEARCH_URL, {}, "valid-key-present")
            result, status = dynamic.classify_with_llm({}, {}, [], {"enabled": True}, [], free_only_mode=False)
            self.assertIsNone(result)
            self.assertEqual(status, "free_only")
            opened.assert_not_called()
            secret.assert_not_called()

    def test_free_classifier_cannot_use_paid_context_from_another_legacy_operation(self):
        token = dynamic._PAID_API_ALLOWED.set(True)
        try:
            with patch.object(dynamic, "get_env_or_local") as secret, patch.object(dynamic, "post_json") as post:
                log = {"errors": [], "llmClassificationSkipped": 0}
                result = dynamic.classify_candidate({"title": "OCR for documents"}, {}, self.config["taxonomy"], self.config, log)
                self.assertEqual(result["provider"], "keywords")
                secret.assert_not_called()
                post.assert_not_called()
        finally:
            dynamic._PAID_API_ALLOWED.reset(token)

    def test_repository_configuration_and_workflow_select_free_path(self):
        settings = json.loads(dynamic.DEFAULT_CONFIG_PATH.read_text())
        self.assertTrue(dynamic.free_only(settings))
        self.assertNotIn("tavily", settings["enabledProviders"])
        self.assertFalse(settings["llmClassification"]["enabled"])
        self.assertFalse(settings["extractArticleContent"])
        self.assertTrue(settings["verifiedSeedArticles"])
        workflow = (dynamic.ROOT / ".github/workflows/update-papers.yml").read_text()
        self.assertIn("--free-only", workflow)
        for paid_secret in ("TAVILY_API_KEY", "DMX_API_KEY", "DMX_BASE_URL", "DMX_MODEL"):
            self.assertNotIn(paid_secret, workflow)

    def test_policy_requires_literal_false_to_opt_out(self):
        for value in (None, True, 0, "false", "true", [], {}):
            self.assertTrue(dynamic.free_only({"freeOnly": value}))
        self.assertFalse(dynamic.free_only({"freeOnly": False}))


if __name__ == "__main__":
    unittest.main()
