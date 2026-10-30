from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = "8f7ef6e5029dfb0bf9a05800f63e5e05043d39c74d5dd0df500a27484aecec6e"


class KentAbbreviationProofreadingTests(unittest.TestCase):
    def make_inputs(self, root: Path):
        source = root / "source-abbreviations.json"
        reviews = root / "reviews.json"
        output = root / "verified-remedy-abbreviations.json"
        source.write_text(json.dumps({
            "dataset_id": "kent-pdf-remedy-abbreviation-index",
            "source": {"pdf_page_start": 10, "pdf_page_end": 18},
            "record_count": 2,
            "duplicate_abbreviation_count": 0,
            "records": [
                {"id": "abbr-1", "abbreviation_as_printed": "Nat-m.", "full_name_as_printed": "Natrum Muriaticum", "source_pdf_page": 10, "source_column": "left", "source_pdf_pages": [10], "source_line_as_printed": "Nat-m. Natrum Muriaticum", "verification_status": "transcribed_not_manually_proofread"},
                {"id": "abbr-2", "abbreviation_as_printed": "Acon.", "full_name_as_printed": "Aconitum Napellus", "source_pdf_page": 10, "source_column": "right", "source_pdf_pages": [10], "source_line_as_printed": "Acon. Aconitum Napellus", "verification_status": "transcribed_not_manually_proofread"},
            ],
        }), encoding="utf-8")
        reviews.write_text(json.dumps({
            "dataset_id": "curiva-kent-abbreviation-review-decisions",
            "source_file_sha256": SOURCE_SHA,
            "records": [
                {"recordId": "abbr-1", "sourcePdfPage": 10, "confirmedAbbreviation": "Nat-m.", "confirmedFullName": "Natrum Muriaticum", "sourceChecked": True, "reviewStatus": "verified", "savedAt": "2026-10-31T00:00:00Z"},
                {"recordId": "abbr-2", "sourcePdfPage": 10, "confirmedAbbreviation": "Acon.", "confirmedFullName": "Aconitum Napellus", "sourceChecked": True, "reviewStatus": "uncertain", "savedAt": "2026-10-31T00:01:00Z"},
            ],
        }), encoding="utf-8")
        return source, reviews, output

    def test_only_source_checked_verified_entries_enter_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, reviews, output = self.make_inputs(root)
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "build-verified-kent-abbreviation-index.py"),
                "--source-index", str(source), "--reviews", str(reviews), "--out", str(output),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            index = json.loads(output.read_text(encoding="utf-8"))
            qc = json.loads(output.with_name("verified-remedy-abbreviations-qc.json").read_text(encoding="utf-8"))
        self.assertEqual(index["record_count"], 1)
        self.assertEqual(index["records"][0]["verification_status"], "verified")
        self.assertEqual(index["records"][0]["proofreading"]["original_parser_transcription"]["abbreviation_as_parsed"], "Nat-m.")
        self.assertEqual(index["proofreading"]["status"], "partial")
        self.assertEqual(qc["uncertain_records"], 1)
        self.assertEqual(qc["pending_records"], 0)

    def test_complete_option_blocks_unreviewed_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, reviews, output = self.make_inputs(root)
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "build-verified-kent-abbreviation-index.py"),
                "--source-index", str(source), "--reviews", str(reviews), "--out", str(output), "--require-complete",
            ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Complete proofreading required", result.stderr)

    def test_duplicate_corrections_are_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, reviews, output = self.make_inputs(root)
            payload = json.loads(reviews.read_text(encoding="utf-8"))
            payload["records"][1]["reviewStatus"] = "verified"
            payload["records"][1]["confirmedAbbreviation"] = "Nat-m."
            reviews.write_text(json.dumps(payload), encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts" / "build-verified-kent-abbreviation-index.py"),
                "--source-index", str(source), "--reviews", str(reviews), "--out", str(output),
            ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate abbreviations", result.stderr)


if __name__ == "__main__":
    unittest.main()
