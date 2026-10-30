from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = "8f7ef6e5029dfb0bf9a05800f63e5e05043d39c74d5dd0df500a27484aecec6e"


class KentPhase2CandidateParserTests(unittest.TestCase):
    def test_parser_main_generates_candidate_index_without_context_name_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "structured").mkdir()
            (root / "chunks" / "mind").mkdir(parents=True)
            (root / "source-metadata.json").write_text(json.dumps({"source_sha256": SOURCE_SHA}), encoding="utf-8")
            (root / "section-index.json").write_text(json.dumps({
                "sections": [{
                    "id": "mind", "pdf_page_start": 66, "pdf_page_end": 66,
                    "internal_page_range": [1, 1],
                }],
                "chunks": [{
                    "section_id": "mind", "part": 1, "pdf_page_start": 66, "pdf_page_end": 66,
                    "page_count": 1, "file": "chunks/mind/mind-001.jsonl",
                }],
            }), encoding="utf-8")
            (root / "structured" / "remedy-abbreviations.json").write_text(json.dumps({
                "dataset_id": "kent-pdf-remedy-abbreviation-index",
                "duplicate_abbreviation_count": 0,
                "records": [{"abbreviation_as_printed": "Nat-m.", "full_name_as_printed": "Natrum Muriaticum"}],
            }), encoding="utf-8")
            page = {
                "pdf_page": 66, "section_id": "mind", "text": "ABRUPT : Nat-m.",
                "text_items": [
                    {"text": "ABRUPT", "top": 100, "left": 108, "font_family": "Arial", "font_size": "18", "color": "#000080", "bold": True, "italic": False},
                    {"text": " : Nat-m.", "top": 100, "left": 180, "font_family": "TimesNewRomanPSMT", "font_size": "18", "color": "#000000", "bold": False, "italic": False},
                ],
            }
            (root / "chunks" / "mind" / "mind-001.jsonl").write_text(json.dumps(page) + "\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "parse-kent-grade-candidates.py"), "--source", str(root)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            index = json.loads((root / "structured" / "grade-candidates-index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["candidate_count"], 1)
            self.assertFalse(index["rubric_hierarchy_assigned"])
            self.assertEqual(index["review_status_counts"]["pending"], 1)


class KentPhase2VerifiedDatabaseTests(unittest.TestCase):
    def make_inputs(self, root: Path):
        structured = root / "structured"
        structured.mkdir()
        (structured / "grade-candidates").mkdir()
        abbreviations = {
            "dataset_id": "kent-pdf-remedy-abbreviation-index",
            "duplicate_abbreviation_count": 0,
            "source_file_sha256": SOURCE_SHA,
            "proofreading": {
                "status": "complete",
                "source_record_count": 1,
                "verified_record_count": 1,
                "uncertain_record_count": 0,
                "rejected_record_count": 0,
                "pending_record_count": 0,
            },
            "records": [{
                "id": "abbrev-1",
                "abbreviation_as_printed": "Nat-m.",
                "full_name_as_printed": "Natrum Muriaticum",
                "verification_status": "verified",
            }],
        }
        abbreviation_path = structured / "verified-remedy-abbreviations.json"
        abbreviation_path.write_text(json.dumps(abbreviations), encoding="utf-8")
        candidates = [
            {"id": "sample-001-p0066-y010000-x010800-i001-t00", "source_pdf_page": 66, "source_section_id": "mind", "matched_abbreviation_as_printed_in_index": "Nat-m.", "token_as_printed_in_rubric": "Nat-m.", "candidate_grade_from_source_key": 1, "grade_evidence": "ordinary_black_layout_span"},
            {"id": "sample-001-p0067-y010000-x010800-i001-t00", "source_pdf_page": 67, "source_section_id": "mind", "matched_abbreviation_as_printed_in_index": "Nat-m.", "token_as_printed_in_rubric": "Nat-m.", "candidate_grade_from_source_key": 2, "grade_evidence": "italic_layout_span"},
            {"id": "sample-001-p0068-y010000-x010800-i001-t00", "source_pdf_page": 68, "source_section_id": "mind", "matched_abbreviation_as_printed_in_index": "Nat-m.", "token_as_printed_in_rubric": "Nat-m.", "candidate_grade_from_source_key": 3, "grade_evidence": "red_uppercase_token_as_printed"},
            {"id": "sample-001-p0069-y010000-x010800-i001-t00", "source_pdf_page": 69, "source_section_id": "mind", "matched_abbreviation_as_printed_in_index": "Nat-m.", "token_as_printed_in_rubric": "Nat-m.", "candidate_grade_from_source_key": None, "grade_evidence": "unrecognised_color_or_style_review"},
            {"id": "sample-001-p0070-y010000-x010800-i001-t00", "source_pdf_page": 70, "source_section_id": "mind", "matched_abbreviation_as_printed_in_index": "Nat-m.", "token_as_printed_in_rubric": "Nat-m.", "candidate_grade_from_source_key": 1, "grade_evidence": "ordinary_black_layout_span"},
            {"id": "sample-001-p0071-y010000-x010800-i001-t00", "source_pdf_page": 71, "source_section_id": "mind", "matched_abbreviation_as_printed_in_index": "Nat-m.", "token_as_printed_in_rubric": "Nat-m.", "candidate_grade_from_source_key": 1, "grade_evidence": "ordinary_black_layout_span"},
        ]
        (structured / "grade-candidates" / "sample.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in candidates), encoding="utf-8"
        )
        (structured / "grade-candidates-index.json").write_text(json.dumps({
            "dataset_id": "kent-pdf-rubric-grade-candidate-index",
            "source_file_sha256": SOURCE_SHA,
            "abbreviation_index_sha256": hashlib.sha256(abbreviation_path.read_bytes()).hexdigest(),
            "abbreviation_index_verified": True,
            "candidate_count": len(candidates),
            "chunks": [{
                "chunk_id": "sample-001",
                "section_id": "mind",
                "pdf_page_start": 66,
                "pdf_page_end": 71,
                "page_count": 6,
                "file": "grade-candidates/sample.jsonl",
                "candidate_count": len(candidates),
            }],
        }), encoding="utf-8")
        decisions = [
            {"candidateId": "sample-001-p0066-y010000-x010800-i001-t00", "remedyAbbreviation": "Nat-m.", "rubricPath": ["MIND", "ABRUPT"], "approvedGrade": 1, "sourcePdfPage": 66, "sourceChecked": True, "reviewStatus": "verified", "savedAt": "2026-10-31T00:00:00Z"},
            {"candidateId": "sample-001-p0067-y010000-x010800-i001-t00", "remedyAbbreviation": "Nat-m.", "rubricPath": ["MIND", "ABRUPT"], "approvedGrade": 2, "sourcePdfPage": 67, "sourceChecked": True, "reviewStatus": "verified", "savedAt": "2026-10-31T00:01:00Z"},
            {"candidateId": "sample-001-p0068-y010000-x010800-i001-t00", "remedyAbbreviation": "Nat-m.", "rubricPath": ["MIND", "ABSENT-MINDED"], "approvedGrade": 3, "sourcePdfPage": 68, "sourceChecked": True, "reviewStatus": "verified", "savedAt": "2026-10-31T00:02:00Z"},
            {"candidateId": "sample-001-p0069-y010000-x010800-i001-t00", "remedyAbbreviation": "Nat-m.", "sourcePdfPage": 69, "sourceChecked": True, "reviewStatus": "uncertain", "reviewNote": "Style not clear."},
            {"candidateId": "sample-001-p0070-y010000-x010800-i001-t00", "remedyAbbreviation": "Nat-m.", "sourcePdfPage": 70, "sourceChecked": True, "reviewStatus": "rejected", "reviewNote": "Not a rubric remedy occurrence."},
            {"candidateId": "sample-001-p0071-y010000-x010800-i001-t00", "remedyAbbreviation": "Nat-m.", "sourcePdfPage": 71, "sourceChecked": True, "reviewStatus": "duplicate", "duplicateOfCandidateId": "sample-001-p0068-y010000-x010800-i001-t00", "reviewNote": "Same printed occurrence duplicated in extraction."},
        ]
        reviews = {
            "dataset_id": "curiva-kent-user-verified-review-decisions",
            "source_file_sha256": SOURCE_SHA,
            "records": decisions,
        }
        (root / "reviews.json").write_text(json.dumps(reviews), encoding="utf-8")
        return root / "reviews.json", abbreviation_path, structured / "grade-candidates-index.json"

    def test_builder_validates_candidate_provenance_and_builds_hierarchy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reviews, abbreviations, candidate_index = self.make_inputs(root)
            output = root / "verified.json"
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "build-verified-kent-database.py"),
                "--reviews", str(reviews), "--abbreviations", str(abbreviations),
                "--candidate-index", str(candidate_index), "--out", str(output),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            database = json.loads(output.read_text(encoding="utf-8"))
            qc = json.loads(output.with_name("verified-qc.json").read_text(encoding="utf-8"))
        self.assertEqual(database["rubric_count"], 2)
        self.assertEqual(database["verified_grade_pair_count"], 1)
        self.assertEqual(qc["grade_pairs_withheld_for_conflict"], 1)
        self.assertEqual(qc["rejected_decisions"], 1)
        self.assertEqual(qc["uncertain_decisions"], 1)
        self.assertEqual(qc["confirmed_duplicate_decisions"], 1)
        self.assertEqual(qc["duplicate_decisions"][0]["duplicate_of_candidate_id"], "sample-001-p0068-y010000-x010800-i001-t00")
        leaf = next(item for item in database["rubrics"] if item["text_as_entered_from_pdf"] == "ABSENT-MINDED")
        self.assertEqual(leaf["parent_rubric_id"], next(item["id"] for item in database["rubrics"] if item["text_as_entered_from_pdf"] == "MIND"))
        self.assertEqual(leaf["grades"][0]["grade"], 3)

    def test_builder_rejects_candidate_id_not_in_candidate_dataset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reviews, abbreviations, candidate_index = self.make_inputs(root)
            payload = json.loads(reviews.read_text(encoding="utf-8"))
            payload["records"][0]["candidateId"] = "invented-candidate-id"
            reviews.write_text(json.dumps(payload), encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "build-verified-kent-database.py"),
                "--reviews", str(reviews), "--abbreviations", str(abbreviations),
                "--candidate-index", str(candidate_index), "--out", str(root / "bad.json"),
            ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no source chunk", result.stderr)

    def test_builder_rejects_wrong_page_for_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reviews, abbreviations, candidate_index = self.make_inputs(root)
            payload = json.loads(reviews.read_text(encoding="utf-8"))
            payload["records"][0]["sourcePdfPage"] = 99
            reviews.write_text(json.dumps(payload), encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "build-verified-kent-database.py"),
                "--reviews", str(reviews), "--abbreviations", str(abbreviations),
                "--candidate-index", str(candidate_index), "--out", str(root / "bad.json"),
            ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        qc = json.loads((root / "bad-qc.json").read_text(encoding="utf-8"))
        self.assertEqual(qc["invalid_decisions"][0]["reason"], "source_page_does_not_match_candidate")


if __name__ == "__main__":
    unittest.main()
