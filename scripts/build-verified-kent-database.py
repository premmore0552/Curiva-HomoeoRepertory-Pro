#!/usr/bin/env python3
"""Build the source-traceable Kent database from individually verified review decisions.

Candidate IDs must resolve to the current extracted candidate dataset. Rejected and
uncertain decisions are retained in QC only. Rubric path segments create explicit
parent-child hierarchy; no hierarchy or grade is inferred by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

SOURCE_SHA256 = "8f7ef6e5029dfb0bf9a05800f63e5e05043d39c74d5dd0df500a27484aecec6e"
ALLOWED_STATUSES = {"verified", "rejected", "uncertain", "duplicate"}


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    return prefix + "-" + digest


def safe_path(base: Path, relative: str) -> Path:
    rel = PurePosixPath(relative)
    if not relative or rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts) or "\\" in relative:
        raise ValueError("Unsafe candidate file path: " + relative)
    target = (base / Path(*rel.parts)).resolve()
    if not target.is_relative_to(base.resolve()):
        raise ValueError("Candidate path escapes its index folder: " + relative)
    return target


def load_candidate_references(index_path: Path, required_ids: set[str], abbreviation_index_sha256: str) -> dict[str, dict[str, Any]]:
    if not index_path.is_file():
        raise ValueError("Candidate index not found: " + str(index_path))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("dataset_id") != "kent-pdf-rubric-grade-candidate-index":
        raise ValueError("Candidate index is not the Kent PDF candidate dataset.")
    if index.get("source_file_sha256") != SOURCE_SHA256:
        raise ValueError("Candidate index source fingerprint does not match the supplied PDF.")
    if index.get("abbreviation_index_sha256") != abbreviation_index_sha256 or index.get("abbreviation_index_verified") is not True:
        raise ValueError("Candidate chunks must be regenerated from this exact proofread abbreviation index before verification.")

    # Candidate IDs begin with their source chunk ID, so only read chunks that
    # can contain a reviewed ID. This avoids scanning hundreds of MB on every build.
    chunks_by_id = {}
    for chunk in index.get("chunks", []):
        chunk_id = chunk.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id or chunk_id in chunks_by_id:
            raise ValueError("Candidate index chunk IDs must be unique, non-empty strings.")
        chunks_by_id[chunk_id] = chunk

    requested_by_chunk: dict[str, set[str]] = defaultdict(set)
    unknown_ids = []
    candidate_id_pattern = re.compile(r"^(?P<chunk>.+)-p\d{4}-y\d+-x\d+-i\d+-t\d+$")
    for candidate_id in required_ids:
        match = candidate_id_pattern.fullmatch(candidate_id)
        if not match:
            unknown_ids.append(candidate_id)
            continue
        chunk_id = match.group("chunk")
        if chunk_id not in chunks_by_id:
            unknown_ids.append(candidate_id)
            continue
        requested_by_chunk[chunk_id].add(candidate_id)
    if unknown_ids:
        raise ValueError("Review export contains candidate IDs with no source chunk: " + ", ".join(sorted(unknown_ids)[:10]))

    references: dict[str, dict[str, Any]] = {}
    base = index_path.parent
    for chunk_id, requested_ids in requested_by_chunk.items():
        chunk = chunks_by_id[chunk_id]
        path = safe_path(base, str(chunk.get("file", "")))
        if not path.is_file():
            raise FileNotFoundError("Candidate source chunk is missing: " + str(path))
        observed_count = 0
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                observed_count += 1
                candidate = json.loads(line)
                candidate_id = candidate.get("id")
                if candidate_id not in requested_ids:
                    continue
                if candidate_id in references:
                    raise ValueError("Duplicate candidate ID in source index: " + str(candidate_id))
                page = candidate.get("source_pdf_page")
                section = candidate.get("source_section_id")
                if (
                    not isinstance(page, int)
                    or isinstance(page, bool)
                    or page < int(chunk.get("pdf_page_start", 0))
                    or page > int(chunk.get("pdf_page_end", -1))
                    or section != chunk.get("section_id")
                ):
                    raise ValueError("Candidate source page or chapter disagrees with its chunk index: " + str(candidate_id))
                references[candidate_id] = {
                    "id": candidate_id,
                    "source_pdf_page": page,
                    "source_section_id": section,
                    "matched_abbreviation_as_printed_in_index": candidate.get("matched_abbreviation_as_printed_in_index"),
                    "token_as_printed_in_rubric": candidate.get("token_as_printed_in_rubric"),
                    "candidate_grade_from_source_key": candidate.get("candidate_grade_from_source_key"),
                    "grade_evidence": candidate.get("grade_evidence"),
                    "chunk_file": str(path),
                    "line_number": line_number,
                }
        if observed_count != int(chunk.get("candidate_count", -1)):
            raise ValueError(
                f"Candidate count mismatch in {path}: expected {chunk.get('candidate_count')}, found {observed_count}"
            )
        missing = sorted(requested_ids - set(references))
        if missing:
            raise ValueError("Reviewed candidate IDs are missing from source chunk: " + ", ".join(missing[:10]))

    unresolved = sorted(required_ids - set(references))
    if unresolved:
        raise ValueError("Review export contains candidate IDs not found in source dataset: " + ", ".join(unresolved[:10]))
    return references


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the verified Kent database from source-checked candidate reviews.")
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--abbreviations", type=Path, default=Path("kent-source-chunks/structured/verified-remedy-abbreviations.json"))
    parser.add_argument("--candidate-index", type=Path, default=None, help="grade-candidates-index.json; defaults beside the abbreviation index")
    parser.add_argument("--out", type=Path, default=Path("verified-rubric-remedy-grades.json"))
    args = parser.parse_args()

    review_path = args.reviews.expanduser().resolve()
    abbreviation_path = args.abbreviations.expanduser().resolve()
    candidate_index_path = args.candidate_index.expanduser().resolve() if args.candidate_index else abbreviation_path.parent / "grade-candidates-index.json"
    out_path = args.out.expanduser().resolve()
    if not review_path.is_file():
        parser.error("Review JSON not found: " + str(review_path))
    if not abbreviation_path.is_file():
        parser.error("PDF abbreviation index not found: " + str(abbreviation_path))

    reviews = json.loads(review_path.read_text(encoding="utf-8"))
    if reviews.get("dataset_id") != "curiva-kent-user-verified-review-decisions":
        parser.error("This is not a Curiva Kent review-decision export.")
    if reviews.get("source_file_sha256") != SOURCE_SHA256:
        parser.error("Review export source fingerprint does not match the uploaded Kent PDF.")
    records = reviews.get("records")
    if not isinstance(records, list) or not records:
        parser.error("No review decisions were supplied.")

    abbreviation_payload = json.loads(abbreviation_path.read_text(encoding="utf-8"))
    abbreviation_records = abbreviation_payload.get("records")
    proofreading = abbreviation_payload.get("proofreading")
    if (
        abbreviation_payload.get("dataset_id") != "kent-pdf-remedy-abbreviation-index"
        or abbreviation_payload.get("duplicate_abbreviation_count") != 0
        or abbreviation_payload.get("source_file_sha256") != SOURCE_SHA256
        or not isinstance(abbreviation_records, list)
        or not isinstance(proofreading, dict)
        or proofreading.get("status") not in {"partial", "complete"}
        or proofreading.get("verified_record_count") != len(abbreviation_records)
        or not isinstance(proofreading.get("source_record_count"), int)
        or proofreading["source_record_count"] < len(abbreviation_records)
        or (
            proofreading.get("status") == "complete"
            and proofreading["source_record_count"] != len(abbreviation_records)
        )
    ):
        parser.error("The abbreviation index must be a consistent, source-proofread index for this supplied PDF.")
    abbreviations = {}
    for item in abbreviation_records:
        key = item.get("abbreviation_as_printed")
        if (
            not isinstance(key, str) or not key or key in abbreviations
            or not isinstance(item.get("full_name_as_printed"), str)
            or not item.get("full_name_as_printed").strip()
        ):
            parser.error("The proofread abbreviation index contains a missing, duplicate or incomplete printed entry.")
        if item.get("verification_status") != "verified":
            parser.error("Only source-proofread abbreviation entries can be used in the active repertory.")
        abbreviations[key] = item.get("full_name_as_printed")
    abbreviation_index_sha256 = hashlib.sha256(abbreviation_path.read_bytes()).hexdigest()

    review_candidate_ids = [
        record.get("candidateId")
        for record in records
        if isinstance(record, dict) and isinstance(record.get("candidateId"), str) and record.get("candidateId")
    ]
    candidate_ids = set(review_candidate_ids)
    if len(candidate_ids) != len(review_candidate_ids):
        parser.error("The review export contains duplicate candidate IDs.")
    duplicate_targets = {
        record.get("duplicateOfCandidateId")
        for record in records
        if isinstance(record, dict) and isinstance(record.get("duplicateOfCandidateId"), str) and record.get("duplicateOfCandidateId")
    }
    candidate_ids.update(duplicate_targets)
    try:
        candidate_refs = load_candidate_references(candidate_index_path, candidate_ids, abbreviation_index_sha256)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    accepted = []
    rejected = []
    uncertain = []
    duplicates = []
    invalid = []
    seen_ids = set()
    for position, record in enumerate(records, 1):
        if not isinstance(record, dict):
            invalid.append({"record_number": position, "reason": "record_not_object"})
            continue
        candidate_id = record.get("candidateId")
        candidate = candidate_refs.get(candidate_id)
        status = record.get("reviewStatus", "verified" if record.get("sourceChecked") is True else "uncertain")
        reason = None
        if not isinstance(candidate_id, str) or not candidate_id:
            reason = "missing_candidate_id"
        elif candidate_id in seen_ids:
            reason = "duplicate_candidate_id"
        elif candidate is None:
            reason = "candidate_id_not_in_source_dataset"
        elif status not in ALLOWED_STATUSES:
            reason = "invalid_review_status"
        elif record.get("remedyAbbreviation") != candidate["matched_abbreviation_as_printed_in_index"]:
            reason = "remedy_abbreviation_does_not_match_candidate"
        elif record.get("sourcePdfPage") != candidate["source_pdf_page"]:
            reason = "source_page_does_not_match_candidate"
        elif record.get("sourceChecked") is not True:
            reason = "source_page_not_checked"
        elif status == "verified":
            path_segments = record.get("rubricPath")
            if not isinstance(path_segments, list) or not path_segments or any(not isinstance(x, str) or not x.strip() for x in path_segments):
                legacy = record.get("rubricText")
                path_segments = [part.strip() for part in legacy.split(" / ")] if isinstance(legacy, str) else []
            if not path_segments or any(not segment.strip() for segment in path_segments):
                reason = "missing_exact_rubric_path"
            elif isinstance(record.get("approvedGrade"), bool) or record.get("approvedGrade") not in (1, 2, 3):
                reason = "invalid_grade"
            elif record.get("approvedGrade") != candidate["candidate_grade_from_source_key"] and not str(record.get("reviewNote", "")).strip():
                reason = "grade_override_requires_review_note"
            else:
                record["_rubric_path"] = [segment.strip() for segment in path_segments]
        if status == "duplicate" and reason is None:
            duplicate_target = record.get("duplicateOfCandidateId")
            if not isinstance(duplicate_target, str) or not duplicate_target or duplicate_target == candidate_id or duplicate_target not in candidate_refs:
                reason = "duplicate_target_candidate_not_found_or_invalid"
        if reason:
            invalid.append({"record_number": position, "candidate_id": candidate_id, "reason": reason})
            continue
        seen_ids.add(candidate_id)
        if status == "rejected":
            rejected.append({"candidate_id": candidate_id, "source_pdf_page": candidate["source_pdf_page"], "review_note": record.get("reviewNote", "")})
        elif status == "uncertain":
            uncertain.append({"candidate_id": candidate_id, "source_pdf_page": candidate["source_pdf_page"], "review_note": record.get("reviewNote", "")})
        elif status == "duplicate":
            duplicates.append({
                "candidate_id": candidate_id,
                "duplicate_of_candidate_id": record["duplicateOfCandidateId"],
                "source_pdf_page": candidate["source_pdf_page"],
                "review_note": record.get("reviewNote", ""),
            })
        else:
            enriched = dict(record)
            enriched["_candidate"] = candidate
            accepted.append(enriched)

    # Group verified source decisions by exact hierarchical path and remedy.
    pair_groups = defaultdict(list)
    for record in accepted:
        candidate = record["_candidate"]
        section_id = str(candidate["source_section_id"])
        path = record["_rubric_path"]
        rubric_key = section_id + "\\0" + "\\0".join(path)
        pair_groups[(rubric_key, record["remedyAbbreviation"])].append(record)

    conflicts = []
    conflict_keys = set()
    for key, group in pair_groups.items():
        grades = sorted({item["approvedGrade"] for item in group})
        if len(grades) > 1:
            conflict_keys.add(key)
            conflicts.append({
                "chapter_id": group[0]["_candidate"]["source_section_id"],
                "rubric_path": group[0]["_rubric_path"],
                "remedy_abbreviation": key[1],
                "conflicting_grades": grades,
                "source_pages": sorted({item["sourcePdfPage"] for item in group}),
                "candidate_ids": [item["candidateId"] for item in group],
            })

    conflicted_candidate_ids = {
        item["candidateId"]
        for key, group in pair_groups.items()
        if key in conflict_keys
        for item in group
    }
    publishable_candidate_ids = {
        item["candidateId"] for item in accepted
        if item["candidateId"] not in conflicted_candidate_ids
    }
    valid_duplicates = []
    for duplicate in duplicates:
        if duplicate["duplicate_of_candidate_id"] not in publishable_candidate_ids:
            invalid.append({
                "candidate_id": duplicate["candidate_id"],
                "reason": "duplicate_target_must_be_a_non_conflicting_verified_record",
                "duplicate_of_candidate_id": duplicate["duplicate_of_candidate_id"],
            })
        else:
            valid_duplicates.append(duplicate)
    duplicates = valid_duplicates

    rubric_nodes: dict[str, dict[str, Any]] = {}
    remedies: dict[str, dict[str, Any]] = {}
    grade_groups = []
    for (rubric_key, abbreviation), group in pair_groups.items():
        if (rubric_key, abbreviation) in conflict_keys:
            continue
        path = group[0]["_rubric_path"]
        chapter_id = str(group[0]["_candidate"]["source_section_id"])
        parent_id = None
        for depth, segment in enumerate(path):
            prefix = chapter_id + "\\0" + "\\0".join(path[: depth + 1])
            rubric_id = stable_id("kent-rubric", prefix)
            node = rubric_nodes.setdefault(rubric_id, {
                "id": rubric_id,
                "source_id": "kent-uploaded-pdf",
                "chapter_id": chapter_id,
                "parent_rubric_id": parent_id,
                "depth": depth,
                "text_as_entered_from_pdf": segment,
                "path_as_entered_from_pdf": path[: depth + 1],
                "source_pdf_pages": [],
                "verification_status": "user_verified_source_checked" if depth == len(path) - 1 else "path_derived_from_verified_child_review",
            })
            node["source_pdf_pages"] = sorted(set(node["source_pdf_pages"]) | {item["sourcePdfPage"] for item in group})
            parent_id = rubric_id
        leaf_id = parent_id
        remedies[abbreviation] = {
            "id": abbreviation,
            "abbreviation_as_printed": abbreviation,
            "full_name_as_printed_in_pdf_index": abbreviations[abbreviation],
            "source_id": "kent-uploaded-pdf",
            "abbreviation_verification_status": "verified",
        }
        grade_groups.append((leaf_id, abbreviation, group))

    grades_by_rubric = defaultdict(list)
    published_pairs = 0
    for rubric_id, abbreviation, group in grade_groups:
        grades_by_rubric[rubric_id].append({
            "remedy_id": abbreviation,
            "grade": group[0]["approvedGrade"],
            "source_pdf_pages": sorted({item["sourcePdfPage"] for item in group}),
            "source_candidate_ids": [item["candidateId"] for item in group],
            "reviewed_at": sorted({item.get("savedAt", "") for item in group if item.get("savedAt")}),
            "grade_evidence_in_candidate": sorted({item["_candidate"]["grade_evidence"] for item in group}),
            "review_notes": [item["reviewNote"] for item in group if item.get("reviewNote")],
            "verification_status": "user_verified_source_checked",
        })
        published_pairs += 1

    rubrics = []
    for rubric_id, node in rubric_nodes.items():
        node["grades"] = sorted(grades_by_rubric.get(rubric_id, []), key=lambda item: item["remedy_id"])
        rubrics.append(node)
    rubrics.sort(key=lambda item: (item["chapter_id"], item["depth"], item["path_as_entered_from_pdf"]))

    database = {
        "dataset_id": "curiva-kent-verified-rubric-remedy-grades",
        "source": {
            "source_id": "kent-uploaded-pdf",
            "source_file_sha256": SOURCE_SHA256,
            "abbreviation_index_sha256": abbreviation_index_sha256,
            "abbreviation_index_proofreading_status": abbreviation_payload.get("proofreading", {}).get("status"),
            "source_file_name": "J.T. Kent s Repertory.pdf",
            "grade_key_pdf_page": 36,
            "grade_key": {"ordinary": 1, "italics": 2, "capitals": 3},
        },
        "data_policy": {
            "external_data_used": False,
            "generated_rubrics": 0,
            "generated_remedies": 0,
            "automatic_grade_verification": False,
            "hierarchy_method": "only reviewer-entered exact rubric path segments; parent nodes are explicit path prefixes",
            "note": "Only individually source-checked candidate reviews are published. No rubric wording, hierarchy or grade is inferred.",
        },
        "rubric_count": len(rubrics),
        "remedy_count": len(remedies),
        "verified_grade_pair_count": published_pairs,
        "rubrics": rubrics,
        "remedies": sorted(remedies.values(), key=lambda item: item["abbreviation_as_printed"].casefold()),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(database, ensure_ascii=False, indent=2), encoding="utf-8")
    qc = {
        "review_records_received": len(records),
        "verified_decisions_accepted": len(accepted),
        "rejected_decisions": len(rejected),
        "uncertain_decisions": len(uncertain),
        "confirmed_duplicate_decisions": len(duplicates),
        "duplicate_decisions": duplicates,
        "invalid_decisions": invalid,
        "conflicting_rubric_remedy_pairs": conflicts,
        "rubric_node_count": len(rubrics),
        "remedy_count_published": len(remedies),
        "grade_pairs_published": published_pairs,
        "grade_pairs_withheld_for_conflict": len(conflict_keys),
        "records_not_published": rejected + uncertain + duplicates,
        "candidate_index": str(candidate_index_path),
        "abbreviation_index_sha256": abbreviation_index_sha256,
        "data_file": str(out_path),
        "policy": "Verified only means that the reviewer confirmed the original PDF. Rejected/uncertain items are excluded. Conflicts are withheld; hierarchy is the exact reviewer-entered path.",
    }
    qc_path = out_path.with_name(out_path.stem + "-qc.json")
    qc_path.write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "reviews_received": len(records),
        "verified_decisions_accepted": len(accepted),
        "rejected": len(rejected),
        "uncertain": len(uncertain),
        "duplicates": len(duplicates),
        "invalid": len(invalid),
        "grade_conflicts": len(conflicts),
        "rubric_nodes": len(rubrics),
        "remedies": len(remedies),
        "grade_pairs": published_pairs,
        "database": str(out_path),
        "qc": str(qc_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
