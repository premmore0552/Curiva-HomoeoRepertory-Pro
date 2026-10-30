#!/usr/bin/env python3
"""Validate a locally extracted Kent source package and optionally seal it.

This checks source provenance, page coverage, section/chunk integrity and
SHA-256 checksums. It does not parse or verify repertory rubrics or grades.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


class ValidationError(ValueError):
    """Raised when a source package fails validation."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class PackageReader:
    def __init__(self, source: Path):
        self.source = source.expanduser().resolve()
        self.archive: zipfile.ZipFile | None = None
        self.prefix = ""
        if self.source.is_dir():
            self.kind = "directory"
        elif self.source.is_file() and zipfile.is_zipfile(self.source):
            self.kind = "zip"
            self.archive = zipfile.ZipFile(self.source, "r")
            candidates = [
                name for name in self.archive.namelist()
                if name.endswith("/section-index.json") or name == "section-index.json"
            ]
            if len(candidates) != 1:
                raise ValidationError("ZIP must contain exactly one section-index.json.")
            self.prefix = candidates[0][: -len("section-index.json")]
        else:
            raise ValidationError("Source must be an extracted folder or a ZIP package.")

    def close(self) -> None:
        if self.archive is not None:
            self.archive.close()

    def read_bytes(self, relative_path: str) -> bytes:
        safe = safe_relative_path(relative_path)
        if self.kind == "directory":
            target = self.source.joinpath(*PurePosixPath(safe).parts)
            if not target.resolve().is_relative_to(self.source):
                raise ValidationError("Package path escapes the source folder: " + safe)
            if not target.is_file():
                raise ValidationError("Missing package file: " + safe)
            return target.read_bytes()
        assert self.archive is not None
        archive_name = self.prefix + safe
        try:
            return self.archive.read(archive_name)
        except KeyError as exc:
            raise ValidationError("Missing ZIP package file: " + safe) from exc

    def exists(self, relative_path: str) -> bool:
        try:
            self.read_bytes(relative_path)
            return True
        except ValidationError:
            return False

    def package_files(self) -> list[str]:
        if self.kind != "directory":
            assert self.archive is not None
            return sorted(
                name[len(self.prefix):]
                for name in self.archive.namelist()
                if name.startswith(self.prefix)
                and name != self.prefix
                and not name.endswith("/")
            )
        result: list[str] = []
        for item in self.source.rglob("*"):
            if item.is_file() and not item.is_symlink():
                result.append(item.relative_to(self.source).as_posix())
        return sorted(result)


def safe_relative_path(value: str) -> str:
    # Package paths are portable POSIX-style paths, even when validated on Windows.
    if (
        not value
        or "\\\\" in value
        or "\\x00" in value
        or ":" in value
        or value.startswith("/")
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise ValidationError("Unsafe package path: " + repr(value))
    path = PurePosixPath(value)
    if path.is_absolute():
        raise ValidationError("Unsafe package path: " + repr(value))
    return path.as_posix()


def load_json(reader: PackageReader, path: str) -> dict[str, Any]:
    try:
        value = json.loads(reader.read_bytes(path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Invalid UTF-8 JSON file: " + path) from exc
    if not isinstance(value, dict):
        raise ValidationError("Expected a JSON object in " + path)
    return value


def validate_manifest(reader: PackageReader) -> bool:
    if not reader.exists("manifest.json"):
        return False
    manifest = load_json(reader, "manifest.json")
    if manifest.get("manifest_version") != 1:
        raise ValidationError("Unsupported manifest version.")
    listed = manifest.get("files")
    if not isinstance(listed, list):
        raise ValidationError("manifest.json must contain a files array.")
    seen: set[str] = set()
    for item in listed:
        if not isinstance(item, dict):
            raise ValidationError("Manifest file entry must be an object.")
        path = safe_relative_path(str(item.get("path", "")))
        if path == "manifest.json" or path in seen:
            raise ValidationError("Duplicate or self-referencing manifest path: " + path)
        seen.add(path)
        content = reader.read_bytes(path)
        if item.get("sha256") != sha256_bytes(content):
            raise ValidationError("SHA-256 mismatch for package file: " + path)
        if item.get("size_bytes") != len(content):
            raise ValidationError("Size mismatch for package file: " + path)
    actual = set(reader.package_files()) - {"manifest.json"}
    if seen != actual:
        missing = sorted(actual - seen)
        extra = sorted(seen - actual)
        raise ValidationError("Manifest file list mismatch. Unlisted=" + str(missing[:10]) + "; absent=" + str(extra[:10]))
    metadata = load_json(reader, "source-metadata.json")
    if manifest.get("source_sha256") != metadata.get("source_sha256"):
        raise ValidationError("Manifest source fingerprint does not match source-metadata.json.")
    return True


def validate_package(source: Path, pdf: Path | None = None, for_publication: bool = False) -> dict[str, Any]:
    reader = PackageReader(source)
    try:
        metadata = load_json(reader, "source-metadata.json")
        index = load_json(reader, "section-index.json")
        source_hash = metadata.get("source_sha256")
        page_count = metadata.get("pdf_page_count")
        if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
            raise ValidationError("source-metadata.json has no valid SHA-256 source fingerprint.")
        if not isinstance(page_count, int) or isinstance(page_count, bool) or page_count < 1:
            raise ValidationError("source-metadata.json has an invalid PDF page count.")

        if pdf is not None:
            if not pdf.is_file():
                raise ValidationError("PDF file not found: " + str(pdf))
            digest = hashlib.sha256()
            with pdf.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != source_hash:
                raise ValidationError("The supplied PDF SHA-256 does not match this source package.")

        sections = index.get("sections")
        chunks = index.get("chunks")
        max_chunk_pages = index.get("chunk_pages_max")
        if not isinstance(sections, list) or not sections:
            raise ValidationError("section-index.json has no sections.")
        if not isinstance(chunks, list) or not chunks:
            raise ValidationError("section-index.json has no chunks.")
        if not isinstance(max_chunk_pages, int) or max_chunk_pages < 1:
            raise ValidationError("section-index.json has an invalid chunk_pages_max.")

        section_by_id: dict[str, dict[str, Any]] = {}
        page_owner: dict[int, str] = {}
        for section in sections:
            if not isinstance(section, dict):
                raise ValidationError("Section entry must be an object.")
            section_id = section.get("id")
            start = section.get("pdf_page_start")
            end = section.get("pdf_page_end")
            if not isinstance(section_id, str) or not section_id or section_id in section_by_id:
                raise ValidationError("Section IDs must be unique, non-empty strings.")
            if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start or end > page_count:
                raise ValidationError("Invalid PDF page range for section: " + str(section_id))
            section_by_id[section_id] = section
            for page in range(start, end + 1):
                if page in page_owner:
                    raise ValidationError("Overlapping section page mapping at PDF page " + str(page))
                page_owner[page] = section_id

        expected_pages = set(range(1, page_count + 1))
        if set(page_owner) != expected_pages:
            missing = sorted(expected_pages - set(page_owner))
            raise ValidationError("Section map does not cover every PDF page. Missing: " + str(missing[:20]))

        observed_pages: dict[int, str] = {}
        seen_chunk_paths: set[str] = set()
        for chunk in chunks:
            if not isinstance(chunk, dict):
                raise ValidationError("Chunk entry must be an object.")
            path = safe_relative_path(str(chunk.get("file", "")))
            if path in seen_chunk_paths:
                raise ValidationError("Duplicate chunk file path: " + path)
            seen_chunk_paths.add(path)
            section_id = chunk.get("section_id")
            section = section_by_id.get(str(section_id))
            if section is None:
                raise ValidationError("Chunk points to an unknown section: " + str(section_id))
            start = chunk.get("pdf_page_start")
            end = chunk.get("pdf_page_end")
            declared_count = chunk.get("page_count")
            if not all(isinstance(x, int) for x in (start, end, declared_count)):
                raise ValidationError("Chunk page ranges and page_count must be integers.")
            if start < section["pdf_page_start"] or end > section["pdf_page_end"] or end < start:
                raise ValidationError("Chunk range falls outside its section: " + path)
            if end - start + 1 != declared_count or declared_count > max_chunk_pages:
                raise ValidationError("Chunk size does not match its declared bounds: " + path)
            content = reader.read_bytes(path)
            try:
                lines = content.decode("utf-8").splitlines()
            except UnicodeDecodeError as exc:
                raise ValidationError("Chunk is not valid UTF-8: " + path) from exc
            records = [line for line in lines if line.strip()]
            if len(records) != declared_count:
                raise ValidationError("Chunk record count mismatch: " + path)
            chunk_pages: set[int] = set()
            for line_number, line in enumerate(records, 1):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValidationError(f"Malformed JSON in {path}, line {line_number}.") from exc
                if not isinstance(record, dict):
                    raise ValidationError("Page record must be a JSON object in " + path)
                page = record.get("pdf_page")
                if not isinstance(page, int) or isinstance(page, bool) or page < start or page > end:
                    raise ValidationError("Page record falls outside its declared chunk: " + path)
                if page in chunk_pages or page in observed_pages:
                    raise ValidationError("Duplicate PDF page record: " + str(page))
                if record.get("section_id") != section_id or page_owner.get(page) != section_id:
                    raise ValidationError("Page record has the wrong section assignment: PDF page " + str(page))
                if not isinstance(record.get("text"), str) or not isinstance(record.get("text_items"), list):
                    raise ValidationError("Page record is missing text or layout spans: PDF page " + str(page))
                if not isinstance(record.get("boundary_page_review"), bool):
                    raise ValidationError("Page record is missing its boundary review flag: PDF page " + str(page))
                chunk_pages.add(page)
                observed_pages[page] = str(section_id)
            if chunk_pages != set(range(start, end + 1)):
                raise ValidationError("Chunk does not contain every declared page: " + path)

        if set(observed_pages) != expected_pages:
            missing = sorted(expected_pages - set(observed_pages))
            raise ValidationError("Chunk data does not cover every PDF page. Missing: " + str(missing[:20]))

        extraction = metadata.get("text_extraction", {})
        if not isinstance(extraction, dict):
            raise ValidationError("text_extraction metadata must be an object.")
        if extraction.get("xml_pages_processed") != page_count:
            raise ValidationError("Layout XML page count does not match the PDF page count.")
        if extraction.get("pages_with_replacement_characters") not in ([], None):
            raise ValidationError("Replacement characters were reported in extracted page text.")
        integrity = metadata.get("data_integrity", {})
        if not isinstance(integrity, dict) or integrity.get("fabricated_records") != 0:
            raise ValidationError("Source integrity metadata does not affirm zero fabricated records.")
        if integrity.get("grade_inference_applied") is not False:
            raise ValidationError("Source package must preserve grade evidence without assigning inferred grades.")

        manifest_verified = validate_manifest(reader)
        rights = metadata.get("rights_and_provenance", {})
        if not isinstance(rights, dict):
            rights = {}
        redistribution_status = rights.get("redistribution_status", "unknown_from_file_alone")
        if for_publication:
            allowed = {"permission_confirmed", "public_domain_confirmed", "licensed_for_redistribution"}
            required = ("rights_holder", "evidence_reference", "confirmed_on")
            if not manifest_verified:
                raise ValidationError("Publication blocked: a valid SHA-256 manifest is required.")
            if redistribution_status not in allowed or not all(rights.get(key) for key in required):
                raise ValidationError(
                    "Publication blocked: redistribution permission is unconfirmed. Record the rights holder, "
                    "evidence reference and confirmation date in source-metadata.json only after obtaining reliable permission."
                )
        return {
            "valid": True,
            "source_sha256": source_hash,
            "pdf_page_count": page_count,
            "section_count": len(sections),
            "repertory_chapter_count": sum(1 for item in sections if item.get("internal_page_range") is not None),
            "chunk_count": len(chunks),
            "page_records_validated": len(observed_pages),
            "manifest_verified": manifest_verified,
            "redistribution_status": redistribution_status,
            "publication_ready": redistribution_status in {
                "permission_confirmed", "public_domain_confirmed", "licensed_for_redistribution"
            } and all(rights.get(key) for key in ("rights_holder", "evidence_reference", "confirmed_on")),
        }
    finally:
        reader.close()


def write_manifest(source: Path, zip_path: Path | None = None) -> dict[str, Any]:
    root = source.expanduser().resolve()
    if not root.is_dir():
        raise ValidationError("--write-manifest requires an extracted source folder, not a ZIP.")
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        manifest_path.unlink()
    metadata = json.loads((root / "source-metadata.json").read_text(encoding="utf-8"))
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.is_symlink()):
        relative = path.relative_to(root).as_posix()
        if relative == "manifest.json":
            continue
        content = path.read_bytes()
        files.append({"path": relative, "size_bytes": len(content), "sha256": sha256_bytes(content)})
    manifest = {
        "manifest_version": 1,
        "dataset_id": metadata.get("dataset_id", "kent-source-package"),
        "source_file_name": metadata.get("source_file_name"),
        "source_sha256": metadata.get("source_sha256"),
        "pdf_page_count": metadata.get("pdf_page_count"),
        "redistribution_status": metadata.get("rights_and_provenance", {}).get("redistribution_status", "unknown_from_file_alone"),
        "file_count": len(files),
        "files": files,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if zip_path is not None:
        destination = zip_path.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(prefix=destination.stem + "-", suffix=".zip", dir=destination.parent)
        os.close(descriptor)
        temp_zip = Path(temp_name)
        try:
            with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.is_symlink()):
                    archive.write(path, PurePosixPath("kent-source-chunks") / path.relative_to(root))
            temp_zip.replace(destination)
        finally:
            if temp_zip.exists():
                temp_zip.unlink()
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Kent source package and verify its SHA-256 manifest.")
    parser.add_argument("source", type=Path, help="Extracted source folder or source ZIP")
    parser.add_argument("--pdf", type=Path, help="Optional original PDF; its fingerprint must match the package")
    parser.add_argument("--write-manifest", action="store_true", help="Create manifest.json in a source folder")
    parser.add_argument("--zip", type=Path, help="Write a fresh ZIP after creating the manifest")
    parser.add_argument("--for-publication", action="store_true", help="Require documented redistribution permission")
    args = parser.parse_args()
    try:
        if args.zip and not args.write_manifest:
            raise ValidationError("--zip can only be used together with --write-manifest.")
        if args.write_manifest:
            write_manifest(args.source, args.zip)
        validation_target = args.zip if args.write_manifest and args.zip else args.source
        result = validate_package(validation_target, args.pdf, args.for_publication)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValidationError, OSError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print("KENT SOURCE PACKAGE VALIDATION FAILED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
