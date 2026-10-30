from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate-kent-source-package.py"
SPEC = importlib.util.spec_from_file_location("validate_kent_source_package", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Could not load Kent source package validator.")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class KentSourcePackageValidationTests(unittest.TestCase):
    def make_package(self, root: Path) -> Path:
        (root / "chunks" / "sample").mkdir(parents=True)
        pdf_bytes = b"local test pdf fingerprint"
        source_hash = hashlib.sha256(pdf_bytes).hexdigest()
        metadata = {
            "dataset_id": "kent-repertory-uploaded-pdf",
            "source_file_name": "test.pdf",
            "source_sha256": source_hash,
            "pdf_page_count": 2,
            "text_extraction": {
                "xml_pages_processed": 2,
                "pages_with_replacement_characters": [],
            },
            "rights_and_provenance": {
                "redistribution_status": "unknown_from_file_alone",
            },
            "data_integrity": {
                "fabricated_records": 0,
                "grade_inference_applied": False,
            },
        }
        index = {
            "chunk_pages_max": 25,
            "section_count": 1,
            "chapter_count": 1,
            "sections": [{
                "id": "sample",
                "title": "Sample",
                "pdf_page_start": 1,
                "pdf_page_end": 2,
                "internal_page_range": [1, 2],
            }],
            "chunks": [{
                "section_id": "sample",
                "part": 1,
                "pdf_page_start": 1,
                "pdf_page_end": 2,
                "page_count": 2,
                "file": "chunks/sample/sample-001.jsonl",
            }],
        }
        (root / "source-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        (root / "section-index.json").write_text(json.dumps(index), encoding="utf-8")
        records = []
        for page in (1, 2):
            records.append(json.dumps({
                "pdf_page": page,
                "section_id": "sample",
                "section_title": "Sample",
                "boundary_page_review": page == 1 or page == 2,
                "text": "Source page " + str(page),
                "text_items": [],
            }))
        (root / "chunks" / "sample" / "sample-001.jsonl").write_text(
            "\n".join(records) + "\n", encoding="utf-8"
        )
        (root / "QC_REPORT.md").write_text("Local test report\n", encoding="utf-8")
        return root

    def test_valid_folder_passes_and_reports_unconfirmed_rights(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_package(Path(temp) / "package")
            result = VALIDATOR.validate_package(root)
        self.assertTrue(result["valid"])
        self.assertEqual(result["page_records_validated"], 2)
        self.assertFalse(result["manifest_verified"])
        self.assertFalse(result["publication_ready"])

    def test_missing_page_record_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_package(Path(temp) / "package")
            chunk = root / "chunks" / "sample" / "sample-001.jsonl"
            chunk.write_text(chunk.read_text(encoding="utf-8").splitlines()[0] + "\n", encoding="utf-8")
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "record count mismatch"):
                VALIDATOR.validate_package(root)

    def test_pdf_fingerprint_must_match(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_package(Path(temp) / "package")
            pdf = Path(temp) / "test.pdf"
            pdf.write_bytes(b"not the source PDF")
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "SHA-256 does not match"):
                VALIDATOR.validate_package(root, pdf)

    def test_manifest_detects_changed_chunk(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_package(Path(temp) / "package")
            VALIDATOR.write_manifest(root)
            chunk = root / "chunks" / "sample" / "sample-001.jsonl"
            chunk.write_text(chunk.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "SHA-256 mismatch"):
                VALIDATOR.validate_package(root)

    def test_manifest_zip_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_package(Path(temp) / "package")
            archive = Path(temp) / "source-package.zip"
            VALIDATOR.write_manifest(root, archive)
            result = VALIDATOR.validate_package(archive)
        self.assertTrue(result["valid"])
        self.assertTrue(result["manifest_verified"])
        self.assertEqual(result["chunk_count"], 1)

    def test_publication_check_blocks_unknown_redistribution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_package(Path(temp) / "package")
            VALIDATOR.write_manifest(root)
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "redistribution permission is unconfirmed"):
                VALIDATOR.validate_package(root, for_publication=True)

    def test_publication_requires_a_valid_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_package(Path(temp) / "package")
            metadata_path = root / "source-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["rights_and_provenance"] = {
                "redistribution_status": "permission_confirmed",
                "rights_holder": "Verified rights holder",
                "evidence_reference": "permission-document-001",
                "confirmed_on": "2026-10-31",
            }
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "valid SHA-256 manifest is required"):
                VALIDATOR.validate_package(root, for_publication=True)

    def test_path_traversal_in_chunk_index_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_package(Path(temp) / "package")
            index_path = root / "section-index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["chunks"][0]["file"] = "../outside.jsonl"
            index_path.write_text(json.dumps(index), encoding="utf-8")
            with self.assertRaisesRegex(VALIDATOR.ValidationError, "Unsafe package path"):
                VALIDATOR.validate_package(root)

    def test_windows_and_null_byte_paths_are_rejected(self):
        for path in ("..\\\\outside.jsonl", "C:/outside.jsonl", "chunks/\\x00bad"):
            with self.subTest(path=path):
                with self.assertRaises(VALIDATOR.ValidationError):
                    VALIDATOR.safe_relative_path(path)


if __name__ == "__main__":
    unittest.main()
