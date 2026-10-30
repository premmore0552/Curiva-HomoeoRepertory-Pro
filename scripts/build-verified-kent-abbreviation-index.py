#!/usr/bin/env python3
"""Build a proofread abbreviation index from human checks against the supplied PDF."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SOURCE_SHA256 = "8f7ef6e5029dfb0bf9a05800f63e5e05043d39c74d5dd0df500a27484aecec6e"
ALLOWED_STATUSES = {"verified", "uncertain", "rejected"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the proofread Kent abbreviation index from manual source-page decisions.")
    parser.add_argument("--source-index", type=Path, required=True, help="Base PDF-derived remedy-abbreviations.json")
    parser.add_argument("--reviews", type=Path, required=True, help="JSON exported by the in-app abbreviation review panel")
    parser.add_argument("--out", type=Path, required=True, help="Output proofread abbreviation index")
    parser.add_argument("--require-complete", action="store_true", help="Require every source abbreviation to be verified")
    args = parser.parse_args()
    source_path = args.source_index.expanduser().resolve()
    review_path = args.reviews.expanduser().resolve()
    out_path = args.out.expanduser().resolve()
    if not source_path.is_file() or not review_path.is_file():
        parser.error("The source abbreviation index or review export does not exist.")

    source = json.loads(source_path.read_text(encoding="utf-8"))
    reviews = json.loads(review_path.read_text(encoding="utf-8"))
    if source.get("dataset_id") != "kent-pdf-remedy-abbreviation-index" or source.get("duplicate_abbreviation_count") != 0:
        parser.error("The source abbreviation index is not recognised or contains duplicates.")
    if reviews.get("dataset_id") != "curiva-kent-abbreviation-review-decisions" or reviews.get("source_file_sha256") != SOURCE_SHA256:
        parser.error("Review export does not belong to this supplied Kent PDF.")
    review_records = reviews.get("records")
    if not isinstance(review_records, list):
        parser.error("Review export records must be an array.")

    originals = {item.get("id"): item for item in source.get("records", [])}
    if None in originals or len(originals) != len(source.get("records", [])):
        parser.error("Source abbreviation index has missing or duplicate stable IDs.")
    decisions = {}
    invalid = []
    for position, decision in enumerate(review_records, 1):
        if not isinstance(decision, dict):
            invalid.append({"record_number": position, "reason": "not_an_object"})
            continue
        record_id = decision.get("recordId")
        original = originals.get(record_id)
        status = decision.get("reviewStatus")
        reason = None
        if not isinstance(record_id, str) or not record_id:
            reason = "missing_record_id"
        elif record_id in decisions:
            reason = "duplicate_record_id"
        elif original is None:
            reason = "record_id_not_in_source_index"
        elif status not in ALLOWED_STATUSES:
            reason = "invalid_review_status"
        elif decision.get("sourcePdfPage") != original.get("source_pdf_page"):
            reason = "source_page_does_not_match_abbreviation_record"
        elif decision.get("sourceChecked") is not True:
            reason = "original_source_page_not_checked"
        elif status == "verified" and (
            not isinstance(decision.get("confirmedAbbreviation"), str)
            or not decision["confirmedAbbreviation"].strip()
            or not isinstance(decision.get("confirmedFullName"), str)
            or not decision["confirmedFullName"].strip()
        ):
            reason = "verified_entry_requires_abbreviation_and_full_name"
        if reason:
            invalid.append({"record_number": position, "record_id": record_id, "reason": reason})
            continue
        decisions[record_id] = decision

    verified = []
    uncertain = []
    rejected = []
    for record_id, original in originals.items():
        decision = decisions.get(record_id)
        if not decision:
            continue
        status = decision["reviewStatus"]
        if status == "uncertain":
            uncertain.append(record_id)
            continue
        if status == "rejected":
            rejected.append(record_id)
            continue
        item = dict(original)
        original_text = {
            "abbreviation_as_parsed": original["abbreviation_as_printed"],
            "full_name_as_parsed": original["full_name_as_printed"],
            "source_line_as_extracted": original.get("source_line_as_printed", ""),
        }
        item["abbreviation_as_printed"] = decision["confirmedAbbreviation"].strip()
        item["full_name_as_printed"] = decision["confirmedFullName"].strip()
        item["verification_status"] = "verified"
        item["proofreading"] = {
            "source_page_checked": True,
            "reviewed_at": decision.get("savedAt", ""),
            "review_note": decision.get("reviewNote", ""),
            "original_parser_transcription": original_text,
        }
        verified.append(item)

    abbreviations = [item["abbreviation_as_printed"].casefold() for item in verified]
    duplicates = sorted({value for value in abbreviations if abbreviations.count(value) > 1})
    empty_names = [item["id"] for item in verified if not item["full_name_as_printed"].strip()]
    if duplicates or empty_names:
        parser.error("Verified abbreviation corrections create duplicate abbreviations or empty names; resolve them before building.")
    if args.require_complete and (len(verified) != len(originals) or uncertain or rejected or invalid):
        parser.error(
            f"Complete proofreading required: verified {len(verified)}/{len(originals)}, "
            f"uncertain {len(uncertain)}, rejected {len(rejected)}, invalid decisions {len(invalid)}."
        )

    out = dict(source)
    out["source_file_sha256"] = SOURCE_SHA256
    out["record_count"] = len(verified)
    out["source_record_count"] = len(originals)
    out["duplicate_abbreviation_count"] = 0
    out["records"] = verified
    out["proofreading"] = {
        "status": "complete" if len(verified) == len(originals) and not uncertain and not rejected and not invalid else "partial",
        "source_record_count": len(originals),
        "verified_record_count": len(verified),
        "uncertain_record_count": len(uncertain),
        "rejected_record_count": len(rejected),
        "pending_record_count": len(originals) - len(decisions),
        "external_data_used": False,
        "source_pages_checked": sorted({item["source_pdf_page"] for item in verified}),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    qc = {
        "source_file_sha256": SOURCE_SHA256,
        "source_record_count": len(originals),
        "review_decisions_received": len(review_records),
        "verified_records": len(verified),
        "uncertain_records": len(uncertain),
        "rejected_records": len(rejected),
        "pending_records": len(originals) - len(decisions),
        "invalid_decisions": invalid,
        "duplicate_abbreviations_after_correction": duplicates,
        "empty_full_names_after_correction": empty_names,
        "verified_index": str(out_path),
        "policy": "Only source-checked entries marked verified enter this index. Parsed text is retained in proofreading.original_parser_transcription for audit.",
    }
    out_path.with_name(out_path.stem + "-qc.json").write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "source_abbreviations": len(originals),
        "verified": len(verified),
        "uncertain": len(uncertain),
        "rejected": len(rejected),
        "pending": len(originals) - len(decisions),
        "invalid_decisions": len(invalid),
        "output": str(out_path),
        "qc": str(out_path.with_name(out_path.stem + "-qc.json")),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
