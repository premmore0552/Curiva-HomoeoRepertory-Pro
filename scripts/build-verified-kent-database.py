#!/usr/bin/env python3
"""Build a local verified rubric/remedy database from manually checked app reviews.

Only review records exported by Curiva's source review screen are accepted.
No rubric wording, remedy, or grade is generated or normalized here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

SOURCE_SHA256 = "8f7ef6e5029dfb0bf9a05800f63e5e05043d39c74d5dd0df500a27484aecec6e"


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    return prefix + "-" + digest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a source-linked database only from manually verified Curiva review decisions."
    )
    parser.add_argument("--reviews", type=Path, required=True, help="JSON exported by the Curiva review screen")
    parser.add_argument("--abbreviations", type=Path, default=Path("kent-source-chunks/structured/remedy-abbreviations.json"))
    parser.add_argument("--out", type=Path, default=Path("verified-rubric-remedy-grades.json"))
    args = parser.parse_args()

    review_path = args.reviews.expanduser().resolve()
    abbreviation_path = args.abbreviations.expanduser().resolve()
    out_path = args.out.expanduser().resolve()
    if not review_path.is_file():
        parser.error("Review JSON not found: " + str(review_path))
    if not abbreviation_path.is_file():
        parser.error("PDF abbreviation index not found: " + str(abbreviation_path))

    reviews = json.loads(review_path.read_text(encoding="utf-8"))
    if reviews.get("dataset_id") != "curiva-kent-user-verified-review-decisions":
        parser.error("This is not a Curiva Kent verified-review export.")
    if reviews.get("source_file_sha256") != SOURCE_SHA256:
        parser.error("Review export source fingerprint does not match the uploaded Kent PDF.")
    records = reviews.get("records")
    if not isinstance(records, list) or not records:
        parser.error("No manually checked review records were supplied.")

    abbreviation_payload = json.loads(abbreviation_path.read_text(encoding="utf-8"))
    if abbreviation_payload.get("dataset_id") != "kent-pdf-remedy-abbreviation-index":
        parser.error("The abbreviation index is not from the supplied PDF.")
    abbreviations = {
        item["abbreviation_as_printed"]: item["full_name_as_printed"]
        for item in abbreviation_payload.get("records", [])
    }

    accepted = []
    rejected = []
    seen_ids = set()
    for position, record in enumerate(records, 1):
        reason = None
        if not isinstance(record, dict):
            reason = "record_not_object"
        elif not isinstance(record.get("candidateId"), str) or not record["candidateId"]:
            reason = "missing_candidate_id"
        elif record["candidateId"] in seen_ids:
            reason = "duplicate_candidate_id"
        elif record.get("sourceChecked") is not True:
            reason = "source_page_not_checked"
        elif record.get("remedyAbbreviation") not in abbreviations:
            reason = "remedy_not_in_pdf_abbreviation_index"
        elif not isinstance(record.get("rubricText"), str) or not record["rubricText"].strip():
            reason = "missing_exact_rubric_text"
        elif record.get("approvedGrade") not in (1, 2, 3):
            reason = "invalid_grade"
        elif not isinstance(record.get("sourcePdfPage"), int) or not (1 <= record["sourcePdfPage"] <= 2834):
            reason = "invalid_source_page"
        elif not isinstance(record.get("savedAt"), str) or not record["savedAt"]:
            reason = "missing_review_timestamp"

        if reason:
            rejected.append({"record_number": position, "candidate_id": record.get("candidateId") if isinstance(record, dict) else None, "reason": reason})
            continue
        seen_ids.add(record["candidateId"])
        accepted.append(record)

    # Never silently let two user-verified entries assign different grades to the
    # same exact rubric/remedy pair. Conflicting pairs are withheld from the output.
    pair_groups = defaultdict(list)
    for record in accepted:
        pair_groups[(record["rubricText"], record["remedyAbbreviation"])].append(record)
    conflicts = []
    conflict_keys = set()
    for key, group in pair_groups.items():
        grades = sorted({item["approvedGrade"] for item in group})
        if len(grades) > 1:
            conflict_keys.add(key)
            conflicts.append({
                "rubric_text_as_entered": key[0],
                "remedy_abbreviation_as_printed": key[1],
                "conflicting_grades": grades,
                "source_pages": sorted({item["sourcePdfPage"] for item in group}),
                "candidate_ids": [item["candidateId"] for item in group],
            })

    grouped_rubrics = {}
    remedy_records = {}
    published_grade_pairs = 0
    for (rubric_text, abbreviation), group in pair_groups.items():
        if (rubric_text, abbreviation) in conflict_keys:
            continue
        rubric_id = stable_id("kent-rubric", rubric_text)
        remedy_id = abbreviation
        rubric = grouped_rubrics.setdefault(rubric_id, {
            "id": rubric_id,
            "text_as_entered_from_pdf": rubric_text,
            "source_id": "kent-uploaded-pdf",
            "grades": [],
            "verification_status": "user_verified_source_checked",
        })
        remedy_records[remedy_id] = {
            "id": remedy_id,
            "abbreviation_as_printed": abbreviation,
            "full_name_as_printed_in_pdf_index": abbreviations[abbreviation],
            "source_id": "kent-uploaded-pdf",
        }
        grade = group[0]["approvedGrade"]
        rubric["grades"].append({
            "remedy_id": remedy_id,
            "grade": grade,
            "source_pdf_pages": sorted({item["sourcePdfPage"] for item in group}),
            "source_candidate_ids": [item["candidateId"] for item in group],
            "reviewed_at": sorted({item["savedAt"] for item in group}),
            "verification_status": "user_verified_source_checked",
        })
        published_grade_pairs += 1

    for rubric in grouped_rubrics.values():
        rubric["grades"].sort(key=lambda item: item["remedy_id"])

    database = {
        "dataset_id": "curiva-kent-verified-rubric-remedy-grades",
        "source": {
            "source_id": "kent-uploaded-pdf",
            "source_file_sha256": SOURCE_SHA256,
            "source_file_name": "J.T. Kent s Repertory.pdf",
            "grade_key_pdf_page": 36,
            "grade_key": {"ordinary": 1, "italics": 2, "capitals": 3},
        },
        "data_policy": {
            "external_data_used": False,
            "generated_rubrics": 0,
            "generated_remedies": 0,
            "automatic_grade_verification": False,
            "note": "Only manually reviewed source candidates are included. Rubric wording is the exact text entered by the reviewer.",
        },
        "rubric_count": len(grouped_rubrics),
        "remedy_count": len(remedy_records),
        "verified_grade_pair_count": published_grade_pairs,
        "rubrics": sorted(grouped_rubrics.values(), key=lambda item: item["text_as_entered_from_pdf"].casefold()),
        "remedies": sorted(remedy_records.values(), key=lambda item: item["abbreviation_as_printed"].casefold()),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(database, ensure_ascii=False, indent=2), encoding="utf-8")
    qc = {
        "review_records_received": len(records),
        "review_records_accepted": len(accepted),
        "review_records_rejected": rejected,
        "conflicting_rubric_remedy_pairs": conflicts,
        "rubric_count_published": len(grouped_rubrics),
        "remedy_count_published": len(remedy_records),
        "grade_pairs_published": published_grade_pairs,
        "grade_pairs_withheld_for_conflict": len(conflict_keys),
        "data_file": str(out_path),
        "policy": "Conflicting pairs are withheld; no data is added from external sources.",
    }
    qc_path = out_path.with_name(out_path.stem + "-qc.json")
    qc_path.write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "reviews_received": len(records),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "conflicts": len(conflicts),
        "rubrics": len(grouped_rubrics),
        "remedies": len(remedy_records),
        "grade_pairs": published_grade_pairs,
        "database": str(out_path),
        "qc": str(qc_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
