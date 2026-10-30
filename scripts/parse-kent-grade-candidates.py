#!/usr/bin/env python3
"""Extract source-grade candidates from the supplied Kent PDF layout chunks.

This stage does NOT identify rubric hierarchy or publish verified grade records.
It matches only remedy abbreviations present in the PDF's own abbreviation table,
retains the source line and typography evidence, and flags every candidate for review.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

TOKEN = re.compile(r"(?<![\w-])(?P<token>[A-Za-zÀ-ÖØ-öø-ÿÆæŒœ0-9]+(?:-[A-Za-zÀ-ÖØ-öø-ÿÆæŒœ0-9]+)*\.)(?!\w)", re.UNICODE)

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_abbreviation_map(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("dataset_id") != "kent-pdf-remedy-abbreviation-index":
        raise ValueError("The abbreviation source is not the expected PDF-derived index.")
    if payload.get("duplicate_abbreviation_count") != 0:
        raise ValueError("The abbreviation index contains duplicate printed abbreviations.")
    result: dict[str, str] = {}
    for record in payload.get("records", []):
        abbreviation = record.get("abbreviation_as_printed")
        if not isinstance(abbreviation, str) or not abbreviation:
            raise ValueError("An abbreviation record has no printed abbreviation.")
        key = abbreviation.casefold()
        if key in result:
            raise ValueError("Duplicate abbreviation after case folding: " + abbreviation)
        result[key] = abbreviation
    if not result:
        raise ValueError("The abbreviation index contains no records.")
    return result


def group_lines(items: list[dict], tolerance: float = 3.0) -> list[list[dict]]:
    """Group layout spans sharing a visual baseline; keep original span objects intact."""
    ordered = sorted(items, key=lambda item: (float(item.get("top", 0)), float(item.get("left", 0))))
    groups: list[list[dict]] = []
    baselines: list[float] = []
    for item in ordered:
        top = float(item.get("top", 0))
        if groups and abs(top - baselines[-1]) <= tolerance:
            groups[-1].append(item)
            baselines[-1] = sum(float(part.get("top", 0)) for part in groups[-1]) / len(groups[-1])
        else:
            groups.append([item])
            baselines.append(top)
    for group in groups:
        group.sort(key=lambda item: float(item.get("left", 0)))
    return groups


def grade_evidence(token: str, item: dict) -> tuple[int | None, str]:
    letters = [character for character in token if character.isalpha()]
    uppercase = bool(letters) and all(character.isupper() for character in letters)
    italic = bool(item.get("italic", False))
    if uppercase and italic:
        return None, "conflicting_uppercase_and_italic_evidence"
    if uppercase:
        return 3, "uppercase_token_as_printed"
    if italic:
        return 2, "italic_layout_span"
    return 1, "ordinary_layout_span"


def iter_chapter_pages(source: Path, section_index: dict) -> Iterable[dict]:
    chapter_ids = {
        section["id"]
        for section in section_index.get("sections", [])
        if section.get("internal_page_range") is not None
    }
    expected_pages = {
        page_number
        for section in section_index.get("sections", [])
        if section.get("internal_page_range") is not None
        for page_number in range(int(section["pdf_page_start"]), int(section["pdf_page_end"]) + 1)
    }
    seen_pages: set[int] = set()
    for chunk in section_index.get("chunks", []):
        if chunk.get("section_id") not in chapter_ids:
            continue
        relative_path = Path(chunk["file"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("Unsafe chunk path in section index: " + str(relative_path))
        path = source / relative_path
        if not path.is_file():
            raise FileNotFoundError("Missing chapter source chunk: " + str(path))
        found = 0
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                page = json.loads(line)
                page_number = int(page["pdf_page"])
                if page_number in seen_pages:
                    raise ValueError("Duplicate chapter PDF page: " + str(page_number))
                if not (chunk["pdf_page_start"] <= page_number <= chunk["pdf_page_end"]):
                    raise ValueError("Page outside declared chunk range: " + str(page_number))
                if page.get("section_id") != chunk["section_id"]:
                    raise ValueError("Page section ID does not match chunk metadata: " + str(page_number))
                seen_pages.add(page_number)
                found += 1
                yield page
        if found != int(chunk["page_count"]):
            raise ValueError(
                f"Chunk page count mismatch in {path}: expected {chunk['page_count']}, found {found}"
            )
    missing_pages = sorted(expected_pages - seen_pages)
    unexpected_pages = sorted(seen_pages - expected_pages)
    if missing_pages or unexpected_pages:
        raise ValueError(
            "Chapter page coverage mismatch. Missing: " + str(missing_pages[:20]) +
            "; unexpected: " + str(unexpected_pages[:20])
        )


def extract_candidates(source: Path, abbreviations: dict[str, str]) -> tuple[list[dict], dict]:
    index_path = source / "section-index.json"
    if not index_path.is_file():
        raise FileNotFoundError("Missing section-index.json in source package.")
    section_index = json.loads(index_path.read_text(encoding="utf-8"))
    candidates: list[dict] = []
    grade_counts: Counter[str] = Counter()
    chapter_counts: Counter[str] = Counter()
    conflict_count = 0
    total_pages = 0
    pages_without_layout = []
    wrapped_fragments = []

    for page in iter_chapter_pages(source, section_index):
        total_pages += 1
        items = page.get("text_items", [])
        if not items:
            pages_without_layout.append(page["pdf_page"])
            continue
        for group in group_lines(items):
            line_text = "".join(str(item.get("text", "")) for item in group).strip()
            if not line_text:
                continue
            for item_index, item in enumerate(group):
                span_text = str(item.get("text", ""))
                for match in TOKEN.finditer(span_text):
                    token = match.group("token")
                    source_abbreviation = abbreviations.get(token.casefold())
                    if source_abbreviation is None:
                        continue
                    grade, evidence = grade_evidence(token, item)
                    if grade is None:
                        conflict_count += 1
                        grade_counts["conflict"] += 1
                    else:
                        grade_counts[str(grade)] += 1
                    section_id = str(page["section_id"])
                    chapter_counts[section_id] += 1
                    candidates.append({
                        "id": f"kent-pdf{int(page['pdf_page']):04d}-y{round(float(item.get('top', 0)) * 100):06d}-x{round(float(item.get('left', 0)) * 100):06d}-{item_index:02d}-{len(candidates) + 1:07d}",
                        "source_pdf_page": int(page["pdf_page"]),
                        "source_section_id": section_id,
                        "line_top": round(sum(float(part.get("top", 0)) for part in group) / len(group), 2),
                        "line_text_as_extracted": line_text,
                        "token_as_printed_in_rubric": token,
                        "matched_abbreviation_as_printed_in_index": source_abbreviation,
                        "candidate_grade_from_source_key": grade,
                        "grade_evidence": evidence,
                        "source_span": {
                            "text": span_text,
                            "top": float(item.get("top", 0)),
                            "left": float(item.get("left", 0)),
                            "font_family": str(item.get("font_family", "")),
                            "font_size": str(item.get("font_size", "")),
                            "color": str(item.get("color", "")),
                            "bold": bool(item.get("bold", False)),
                            "italic": bool(item.get("italic", False)),
                        },
                        "rubric_assignment": "unassigned",
                        "verification_status": "needs_review",
                    })
                if span_text.rstrip().endswith("-") and re.search(r"[A-Za-zÀ-ÖØ-öø-ÿÆæŒœ]+-$", span_text.rstrip()):
                    wrapped_fragments.append({
                        "source_pdf_page": int(page["pdf_page"]),
                        "source_section_id": str(page["section_id"]),
                        "text_as_printed": span_text,
                        "top": float(item.get("top", 0)),
                        "left": float(item.get("left", 0)),
                        "review_reason": "possible_hyphenated_remedy_token_wrapped_at_line_end",
                    })

    qc = {
        "source_file_sha256": None,
        "chapter_pages_processed": total_pages,
        "candidate_count": len(candidates),
        "candidate_counts_by_grade_evidence": dict(grade_counts),
        "candidate_counts_by_chapter": dict(chapter_counts),
        "conflicting_grade_evidence": conflict_count,
        "pages_without_layout_spans": pages_without_layout,
        "possible_wrapped_token_fragments": wrapped_fragments,
        "rubric_hierarchy_assigned": False,
        "records_verified": 0,
        "records_needing_review": len(candidates),
        "external_data_used": False,
        "fabricated_records": 0,
        "policy": "Candidates preserve PDF text and typography; no rubric hierarchy is inferred and no candidate is marked verified.",
    }
    metadata_path = source / "source-metadata.json"
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        qc["source_file_sha256"] = metadata.get("source_sha256")
    return candidates, qc


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract unverified grade candidates from PDF remedy tokens.")
    parser.add_argument("--source", type=Path, default=Path("kent-source-chunks"))
    parser.add_argument("--abbreviations", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    abbreviation_path = args.abbreviations.expanduser().resolve() if args.abbreviations else source / "structured" / "remedy-abbreviations.json"
    out_path = args.out.expanduser().resolve() if args.out else source / "structured" / "rubric-grade-candidates.jsonl"
    abbreviations = load_abbreviation_map(abbreviation_path)
    candidates, qc = extract_candidates(source, abbreviations)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            handle.write(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")) + "\n")
    qc_path = out_path.with_name(out_path.stem + "-qc.json")
    qc_path.write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "candidate_count": len(candidates),
        "chapter_pages_processed": qc["chapter_pages_processed"],
        "candidate_counts_by_grade_evidence": qc["candidate_counts_by_grade_evidence"],
        "conflicting_grade_evidence": qc["conflicting_grade_evidence"],
        "records_verified": qc["records_verified"],
        "output": str(out_path),
        "qc": str(qc_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
