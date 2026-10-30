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


if __name__ == "__main__":
    unittest.main()
