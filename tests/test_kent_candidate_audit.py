from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = "8f7ef6e5029dfb0bf9a05800f63e5e05043d39c74d5dd0df500a27484aecec6e"


class KentCandidateAuditTests(unittest.TestCase):
    def make_source(self, root: Path):
        source = root / "source"
        structured = source / "structured"
        (structured / "grade-candidates").mkdir(parents=True)
        (source / "source-metadata.json").write_text(json.dumps({"source_sha256": SOURCE_SHA}), encoding="utf-8")
        abbreviations = {
            "dataset_id": "kent-pdf-remedy-abbreviation-index",
            "records": [{"abbreviation_as_printed": "Nat-m."}],
        }
        abbreviation_path = structured / "remedy-abbreviations.json"
        abbreviation_path.write_text(json.dumps(abbreviations), encoding="utf-8")
        candidates = [
            {
                "id": "candidate-one",
                "source_pdf_page": 66,
                "source_section_id": "mind",
                "matched_abbreviation_as_printed_in_index": "Nat-m.",
                "candidate_grade_from_source_key": 1,
                "grade_evidence": "ordinary_black_layout_span",
                "verification_status": "needs_review",
                "rubric_assignment": "unassigned",
                "suggested_context_method": "source_heading_font_and_color",
                "line_text_as_extracted": "ABRUPT : Nat-m.",
            },
            {
                "id": "candidate-two",
                "source_pdf_page": 66,
                "source_section_id": "mind",
                "matched_abbreviation_as_printed_in_index": "Nat-m.",
                "candidate_grade_from_source_key": 1,
                "grade_evidence": "ordinary_black_layout_span",
                "verification_status": "needs_review",
                "rubric_assignment": "unassigned",
                "suggested_context_method": "source_heading_font_and_color",
                "line_text_as_extracted": "ABRUPT : Nat-m.",
            },
        ]
        (structured / "grade-candidates" / "mind-001.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in candidates), encoding="utf-8"
        )
        (structured / "grade-candidates-index.json").write_text(json.dumps({
            "dataset_id": "kent-pdf-rubric-grade-candidate-index",
            "source_file_sha256": SOURCE_SHA,
            "candidate_count": 2,
            "chunks": [{
                "chunk_id": "mind-001",
                "file": "grade-candidates/mind-001.jsonl",
                "candidate_count": 2,
            }],
        }), encoding="utf-8")
        return source, structured

    def test_audit_flags_possible_duplicates_without_deleting_candidates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, structured = self.make_source(root)
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "audit-kent-candidate-data.py"),
                "--source", str(source),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((structured / "candidate-data-audit.json").read_text(encoding="utf-8"))
            duplicates = json.loads((structured / "possible-duplicate-candidates.json").read_text(encoding="utf-8"))
        self.assertEqual(report["candidate_count"], 2)
        self.assertEqual(report["unique_candidate_ids"], 2)
        self.assertEqual(report["validation_error_count"], 0)
        self.assertEqual(report["possible_exact_occurrence_duplicate_groups"], 1)
        self.assertEqual(duplicates[0]["candidate_ids"], ["candidate-one", "candidate-two"])

    def test_audit_rejects_candidate_index_with_wrong_abbreviation_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, structured = self.make_source(root)
            index_path = structured / "grade-candidates-index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["abbreviation_index_sha256"] = "wrong"
            index_path.write_text(json.dumps(index), encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "audit-kent-candidate-data.py"),
                "--source", str(source),
            ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fingerprint", result.stderr)


if __name__ == "__main__":
    unittest.main()
