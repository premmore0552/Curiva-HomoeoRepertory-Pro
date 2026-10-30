from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREPARE = load_script("prepare_kent_pdf", "prepare-kent-pdf.py")
ABBREVIATIONS = load_script("parse_kent_abbreviations", "parse-kent-abbreviations.py")
GRADE_CANDIDATES = load_script("parse_kent_grade_candidates", "parse-kent-grade-candidates.py")
VERIFIED_BUILDER = load_script("build_verified_kent_database", "build-verified-kent-database.py")


class SectionMapTests(unittest.TestCase):
    def test_pdf_section_map_covers_every_page_once(self):
        page_map = {}
        for section_id, _title, start, end, _internal in PREPARE.SECTIONS:
            self.assertGreaterEqual(start, 1, section_id)
            self.assertLessEqual(end, PREPARE.EXPECTED_PAGES, section_id)
            self.assertLessEqual(start, end, section_id)
            for page in range(start, end + 1):
                self.assertNotIn(page, page_map, f"overlap at PDF page {page}")
                page_map[page] = section_id
        self.assertEqual(set(page_map), set(range(1, PREPARE.EXPECTED_PAGES + 1)))
        self.assertEqual(sum(1 for item in PREPARE.SECTIONS if item[4] is not None), 34)

    def test_chunk_plan_never_exceeds_25_pages(self):
        count = 0
        for _section_id, _title, start, end, _internal in PREPARE.SECTIONS:
            for first in range(start, end + 1, PREPARE.CHUNK_PAGES):
                last = min(first + PREPARE.CHUNK_PAGES - 1, end)
                self.assertLessEqual(last - first + 1, 25)
                count += 1
        self.assertEqual(count, 134)

    def test_every_repertory_section_has_a_matching_app_chapter_id(self):
        import re
        catalog = (ROOT / "src" / "data" / "kent-source-catalog.ts").read_text(encoding="utf-8")
        catalog_ids = set(re.findall(r'id: "([^"]+)"', catalog))
        importer_ids = {section_id for section_id, _title, _start, _end, internal in PREPARE.SECTIONS if internal is not None}
        self.assertEqual(importer_ids - catalog_ids, set())


class AbbreviationParserTests(unittest.TestCase):
    def make_source(self, root: Path, missing_page: int | None = None) -> None:
        folder = root / "chunks" / "remedy-abbreviations"
        folder.mkdir(parents=True)
        for page_number in range(10, 19):
            if page_number == missing_page:
                continue
            items = []
            if page_number == 10:
                items = [
                    {"text": "Abies-c.------- Abies Canadensis", "top": 130, "left": 108},
                    {"text": "Anag.--------- Anagallis Arvensis", "top": 130, "left": 452},
                ]
            elif page_number == 11:
                items = [
                    {"text": "Aur-m-n.--------- Aurum Muriaticum", "top": 371, "left": 108},
                    {"text": "Natronatum", "top": 392, "left": 108},
                    {"text": "Calc-f.--------- Calcarea Fluorata", "top": 392, "left": 466},
                ]
            elif page_number == 12:
                items = [
                    {"text": "Chen-an.--------- Chenopodium", "top": 373, "left": 108},
                    {"text": "Anthelminticum", "top": 395, "left": 108},
                ]
            record = {"pdf_page": page_number, "text_items": items}
            with (folder / "part.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def test_parses_columns_and_preserves_source_continuations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_source(root)
            records, continuations, flagged = ABBREVIATIONS.parse(root)
        by_abbreviation = {item["abbreviation_as_printed"]: item for item in records}
        self.assertEqual(by_abbreviation["Abies-c."]["full_name_as_printed"], "Abies Canadensis")
        self.assertEqual(by_abbreviation["Anag."]["source_column"], "right")
        self.assertEqual(by_abbreviation["Aur-m-n."]["full_name_as_printed"], "Aurum Muriaticum Natronatum")
        self.assertEqual(by_abbreviation["Chen-an."]["full_name_as_printed"], "Chenopodium Anthelminticum")
        self.assertEqual(len(continuations), 2)
        self.assertEqual(by_abbreviation["Aur-m-n."]["source_pdf_pages"], [11])
        self.assertTrue(all(item["verification_status"] == "transcribed_not_manually_proofread" for item in records))
        self.assertEqual(flagged, [])

    def test_missing_abbreviation_page_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_source(root, missing_page=14)
            with self.assertRaisesRegex(ValueError, "Missing abbreviation source pages"):
                ABBREVIATIONS.load_pages(root)

    def test_grade_candidates_keep_pdf_style_and_remain_unverified(self):
        abbreviation_map = {"nat-m.": "Nat-m.", "tarent.": "Tarent.", "apis.": "Apis."}
        page = {
            "pdf_page": 66,
            "section_id": "mind",
            "text_items": [
                {"text": "ABRUPT", "top": 100, "left": 108, "font_family": "Arial", "bold": True, "color": "#000080", "italic": False},
                {"text": " : Nat-m., ", "top": 100, "left": 175, "font_family": "TimesNewRomanPSMT", "bold": False, "color": "#000000", "italic": False},
                {"text": "tarent. ", "top": 100, "left": 256, "font_family": "TimesNewRomanPS", "bold": True, "color": "#0070c0", "italic": True},
                {"text": "APIS.", "top": 100, "left": 322, "font_family": "TimesNewRomanPS", "bold": True, "color": "#ff0000", "italic": False},
                {"text": "morning : Nat-m.", "top": 130, "left": 162, "font_family": "TimesNewRomanPSMT", "bold": False, "color": "#000000", "italic": False},
            ],
        }
        candidates, wrapped = GRADE_CANDIDATES.candidate_records(page, abbreviation_map, "mind-001", {})
        self.assertEqual([item["candidate_grade_from_source_key"] for item in candidates], [1, 2, 3, 1])
        self.assertEqual([item["verification_status"] for item in candidates], ["needs_review"] * 4)
        self.assertTrue(all(item["rubric_assignment"] == "unassigned" for item in candidates))
        self.assertEqual(candidates[0]["suggested_rubric_context"], "ABRUPT")
        self.assertEqual(candidates[3]["suggested_rubric_context"], "ABRUPT / morning")
        self.assertEqual(len(wrapped), 0)

    def test_black_uppercase_does_not_get_an_automatic_grade_three(self):
        grade, evidence = GRADE_CANDIDATES.grade_evidence("PULS.", {"italic": False, "color": "#000000"})
        self.assertIsNone(grade)
        self.assertEqual(evidence, "uppercase_token_without_red_grade_style_review")

    def test_verified_database_builder_refuses_unproofread_abbreviations(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            abbreviation_file = root / "abbreviations.json"
            review_file = root / "reviews.json"
            output_file = root / "verified.json"
            abbreviation_file.write_text(json.dumps({
                "dataset_id": "kent-pdf-remedy-abbreviation-index",
                "source_file_sha256": VERIFIED_BUILDER.SOURCE_SHA256,
                "duplicate_abbreviation_count": 0,
                "proofreading": {"status": "partial"},
                "records": [{
                    "abbreviation_as_printed": "Nat-m.",
                    "full_name_as_printed": "Natrum Muriaticum",
                    "verification_status": "transcribed_not_manually_proofread"
                }]
            }), encoding="utf-8")
            review_file.write_text(json.dumps({
                "dataset_id": "curiva-kent-user-verified-review-decisions",
                "source_file_sha256": VERIFIED_BUILDER.SOURCE_SHA256,
                "records": [{
                    "candidateId": "not-yet-indexed",
                    "remedyAbbreviation": "Nat-m.",
                    "rubricText": "ABRUPT",
                    "approvedGrade": 1,
                    "sourcePdfPage": 66,
                    "sourceChecked": True,
                    "savedAt": "2026-10-30T00:00:00Z"
                }]
            }), encoding="utf-8")
            script = ROOT / "scripts" / "build-verified-kent-database.py"
            result = subprocess.run([
                sys.executable, str(script), "--reviews", str(review_file),
                "--abbreviations", str(abbreviation_file), "--out", str(output_file)
            ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("consistent, source-proofread index", result.stderr)



if __name__ == "__main__":
    unittest.main()
