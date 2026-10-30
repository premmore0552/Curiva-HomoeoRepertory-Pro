#!/usr/bin/env python3
"""Audit source-linked Kent candidate chunks without approving any records."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

SOURCE_SHA256 = "8f7ef6e5029dfb0bf9a05800f63e5e05043d39c74d5dd0df500a27484aecec6e"
GRADE_EVIDENCE = {
    1: {"ordinary_black_layout_span"},
    2: {"italic_layout_span"},
    3: {"red_uppercase_token_as_printed"},
    None: {
        "unrecognised_color_or_style_review",
        "uppercase_token_without_red_grade_style_review",
        "conflicting_uppercase_and_italic_evidence",
    },
}


def safe_chunk_path(base: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if not relative or path.is_absolute() or "\\\\" in relative or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("Unsafe candidate chunk path: " + relative)
    target = (base / Path(*path.parts)).resolve()
    if not target.is_relative_to(base.resolve()):
        raise ValueError("Candidate chunk escapes the candidate index folder.")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Check candidate IDs, source references and possible repeated occurrences.")
    parser.add_argument("--source", type=Path, required=True, help="Root of the extracted Kent source package")
    parser.add_argument("--out", type=Path, default=None, help="Output folder; defaults to source/structured")
    args = parser.parse_args()
    root = args.source.expanduser().resolve()
    output = (args.out or root / "structured").expanduser().resolve()
    metadata = json.loads((root / "source-metadata.json").read_text(encoding="utf-8"))
    index = json.loads((output / "grade-candidates-index.json").read_text(encoding="utf-8"))
    abbreviation_payload = json.loads((output / "remedy-abbreviations.json").read_text(encoding="utf-8"))
    if metadata.get("source_sha256") != SOURCE_SHA256 or index.get("source_file_sha256") != SOURCE_SHA256:
        parser.error("Source PDF fingerprint mismatch.")
    if index.get("dataset_id") != "kent-pdf-rubric-grade-candidate-index":
        parser.error("Unexpected candidate dataset.")
    if abbreviation_payload.get("dataset_id") != "kent-pdf-remedy-abbreviation-index":
        parser.error("Unexpected abbreviation dataset.")
    abbreviation_map = {item["abbreviation_as_printed"].casefold() for item in abbreviation_payload.get("records", [])}
    if len(abbreviation_map) != len(abbreviation_payload.get("records", [])):
        parser.error("Duplicate abbreviation in source abbreviation index.")

    seen_ids: set[str] = set()
    grade_counts: Counter[str] = Counter()
    chapter_counts: Counter[str] = Counter()
    context_methods: Counter[str] = Counter()
    duplicate_signatures: dict[tuple[int, str, str], list[dict]] = defaultdict(list)
    errors: list[dict] = []
    total = 0
    for chunk in index.get("chunks", []):
        path = safe_chunk_path(output, str(chunk.get("file", "")))
        if not path.is_file():
            parser.error("Candidate chunk file is missing: " + str(path))
        chunk_count = 0
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    errors.append({"file": str(path), "line": line_number, "reason": "invalid_json"})
                    continue
                total += 1
                chunk_count += 1
                candidate_id = item.get("id")
                if not isinstance(candidate_id, str) or not candidate_id or candidate_id in seen_ids:
                    errors.append({"candidate_id": candidate_id, "reason": "missing_or_duplicate_id"})
                else:
                    seen_ids.add(candidate_id)
                abbreviation = str(item.get("matched_abbreviation_as_printed_in_index", ""))
                if abbreviation.casefold() not in abbreviation_map:
                    errors.append({"candidate_id": candidate_id, "reason": "abbreviation_not_in_source_index"})
                if item.get("verification_status") != "needs_review" or item.get("rubric_assignment") != "unassigned":
                    errors.append({"candidate_id": candidate_id, "reason": "candidate_must_remain_unverified"})
                grade = item.get("candidate_grade_from_source_key")
                if grade not in (1, 2, 3, None) or item.get("grade_evidence") not in GRADE_EVIDENCE[grade]:
                    errors.append({"candidate_id": candidate_id, "reason": "grade_evidence_mapping_mismatch"})
                grade_counts[str(grade) if grade is not None else "uncertain"] += 1
                chapter_counts[item.get("source_section_id", "unknown")] += 1
                context_methods[item.get("suggested_context_method", "unknown")] += 1
                line_text = re.sub(r"\s+", " ", str(item.get("line_text_as_extracted", ""))).strip().casefold()
                duplicate_signatures[(int(item.get("source_pdf_page", 0)), line_text, abbreviation.casefold())].append({
                    "candidate_id": candidate_id,
                    "grade": grade,
                })
        if chunk_count != chunk.get("candidate_count"):
            errors.append({"chunk": chunk.get("chunk_id"), "reason": "chunk_candidate_count_mismatch"})
    if total != index.get("candidate_count"):
        errors.append({"reason": "total_candidate_count_mismatch", "actual": total, "expected": index.get("candidate_count")})

    possible_duplicates = []
    for (page, line, abbreviation), items in duplicate_signatures.items():
        if len(items) > 1:
            possible_duplicates.append({
                "source_pdf_page": page,
                "line_text_as_extracted": line,
                "remedy_abbreviation": abbreviation,
                "occurrence_count": len(items),
                "candidate_ids": [item["candidate_id"] for item in items],
                "grade_evidence": [item["grade"] for item in items],
                "review_instruction": "Possible repeated layout/source occurrence; inspect the PDF. Do not auto-delete or merge.",
            })

    report = {
        "dataset_id": "curiva-kent-candidate-audit",
        "source_file_sha256": SOURCE_SHA256,
        "candidate_count": total,
        "unique_candidate_ids": len(seen_ids),
        "validation_error_count": len(errors),
        "candidate_counts_by_grade_evidence": dict(grade_counts),
        "candidate_counts_by_chapter": dict(chapter_counts),
        "suggested_context_methods": dict(context_methods),
        "possible_exact_occurrence_duplicate_groups": len(possible_duplicates),
        "candidates_in_possible_duplicate_groups": sum(item["occurrence_count"] for item in possible_duplicates),
        "reviewed_records": 0,
        "verified_records": 0,
        "policy": "Candidate audit only. Suggested context is not a verified rubric path; duplicate flags never delete or merge source occurrences.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "candidate-data-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "possible-duplicate-candidates.json").write_text(json.dumps(possible_duplicates, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "candidate-audit-errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "possible-duplicate-candidates.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["pdf_page", "remedy_abbreviation", "occurrence_count", "candidate_ids", "grade_evidence", "source_line", "review_instruction"])
        for item in possible_duplicates:
            writer.writerow([
                item["source_pdf_page"], item["remedy_abbreviation"], item["occurrence_count"],
                ";".join(item["candidate_ids"]),
                ";".join("?" if value is None else str(value) for value in item["grade_evidence"]),
                item["line_text_as_extracted"], item["review_instruction"],
            ])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
