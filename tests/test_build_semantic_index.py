"""Offline index contracts, numerical validity, and cross-language identity."""
import importlib.util
import json
import math
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("semantic_index", ROOT / "scripts/build_semantic_index.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class SemanticIndexTests(unittest.TestCase):
    def setUp(self):
        self.papers = [
            {"title": "Donut: OCR-free Document Understanding", "arxiv": "2111.15664", "topics": ["vlm"], "tags": ["OCR-free"]},
            {"title": "Cross-page Evidence Retrieval", "arxiv": "2401.00001", "topics": ["docrag"], "abstract": "Grounded multi-page document retrieval with evidence localization."},
            {"title": "Faithfulness Evaluation Benchmark", "bibKey": "faith", "topics": ["eval"], "abstract": "Evaluation of answers, evidence and unanswerable questions."},
            {"title": "Table Structure Recognition", "bibKey": "table", "topics": ["table"]},
        ]

    def test_fingerprints_match_javascript_utf16(self):
        item = {"title": "跨页 Evidence 📚", "abstract": "Grounded answers with citation.", "updated": "2026-11-09", "tags": ["RAG", "中文"], "topics": ["docrag"], "category": "Retrieval", "categories": ["RAG", "Evaluation"]}
        self.assertEqual(builder.fingerprint(item), "4fd5ec55")
        self.assertEqual(builder.source_key({"arxiv": "2401.00001v3"}), "arxiv:2401.00001")
        self.assertEqual(builder.source_key({"url": "https://arxiv.org/pdf/2401.00001v3.pdf"}), "arxiv:2401.00001")
        self.assertEqual(builder.source_key({"id": "github:ORG/Repo:123"}), "github:org/repo:123")

    def test_deterministic_deduplicated_finite_and_bounded(self):
        update = {**self.papers[0], "id": "arxiv:2111.15664", "abstract": "A purely visual language understanding model without OCR."}
        result = builder.build_index(self.papers, [update], dimensions=4, max_terms=64)
        self.assertEqual(result, builder.build_index(list(reversed(self.papers)), [update], dimensions=4, max_terms=64))
        self.assertEqual(len(result["documents"]), 4)
        self.assertEqual(len(result["documents"]["arxiv:2111.15664"]["fingerprints"]), 2)
        self.assertLessEqual(len(result["terms"]), 64)
        self.assertIn("__concept_ocr_free", result["terms"])
        self.assertEqual(len(result["inputFingerprint"]), 64)
        for entry in result["documents"].values():
            self.assertTrue(all(math.isfinite(value) for value in entry["vector"]))
            self.assertAlmostEqual(sum(value * value for value in entry["vector"]), 1, places=5)
        self.assertTrue(all(len(row) == result["dimensions"] for row in result["projection"]))
        # Right singular vectors must be orthonormal, so TF-IDF projection is
        # a genuine low-dimensional SVD instead of arbitrary random features.
        projection = result["projection"]
        for i in range(result["dimensions"]):
            for j in range(result["dimensions"]):
                dot = sum(row[i] * row[j] for row in projection)
                self.assertAlmostEqual(dot, float(i == j), places=5)

    def test_changed_text_invalidates_only_matching_fingerprint(self):
        old = builder.build_index(self.papers, [], dimensions=3, max_terms=64)
        changed = [{**item} for item in self.papers]
        changed[0]["abstract"] = "Updated OCR-free model with an added evaluation."
        new = builder.build_index(changed, [], dimensions=3, max_terms=64)
        self.assertNotEqual(old["inputFingerprint"], new["inputFingerprint"])
        key = builder.source_key(changed[0])
        self.assertNotIn(builder.fingerprint(changed[0]), old["documents"][key]["fingerprints"])

    def test_cli_builds_from_local_files(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            papers, updates, output = (folder / name for name in ("papers.json", "updates.json", "index.json"))
            papers.write_text(json.dumps({"papers": self.papers}), encoding="utf-8")
            updates.write_text('{"papers":[]}', encoding="utf-8")
            command = ["python", str(ROOT / "scripts/build_semantic_index.py"), "--papers", str(papers), "--updates", str(updates), "--output", str(output), "--dimensions", "3", "--max-terms", "64"]
            subprocess.run(command, check=True, capture_output=True, text=True)
            first = output.read_bytes()
            subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(first, output.read_bytes())
            self.assertEqual(json.loads(first)["algorithm"], "tfidf-lsa+domain-concepts")

    def test_empty_corpus_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "empty corpus"):
            builder.build_index([], [])


if __name__ == "__main__":
    unittest.main()
