#!/usr/bin/env python3
"""Build lazy, source-linked grade-candidate chunks from the supplied Kent PDF.

No rubric hierarchy is invented. Every occurrence remains needs_review until a
person checks its page and assigns the exact source rubric. The candidate grade
uses the PDF's own page-36 key plus the typography/color evidence preserved by
the source importer.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

TOKEN = re.compile(
    r"(?<![\w-])(?P<token>[A-Za-zÀ-ÖØ-öø-ÿÆæŒœ0-9]+(?:-[A-Za-zÀ-ÖØ-öø-ÿÆæŒœ0-9]+)*\.)(?!\w)",
    re.UNICODE,
)


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
    color = str(item.get("color", "")).strip().lower()
    is_red = color in {"#ff0000", "#f00", "red"}
    is_black = color in {"#000000", "#000", "black"}
    if italic and uppercase:
        return None, "conflicting_uppercase_and_italic_evidence"
    if italic:
        return 2, "italic_layout_span"
    if uppercase and is_red:
        return 3, "red_uppercase_token_as_printed"
    if uppercase:
        return None, "uppercase_token_without_red_grade_style_review"
    if is_black:
        return 1, "ordinary_black_layout_span"
    return None, "unrecognised_color_or_style_review"


def iter_chapter_chunks(source: Path, section_index: dict) -> Iterable[tuple[dict, list[dict]]]:
    chapter_ranges = {
        section["id"]: (int(section["pdf_page_start"]), int(section["pdf_page_end"]))
        for section in section_index.get("sections", [])
        if section.get("internal_page_range") is not None
    }
    expected_pages = {
        page
        for start, end in chapter_ranges.values()
        for page in range(start, end + 1)
    }
    seen_pages: set[int] = set()
    for chunk in section_index.get("chunks", []):
        if chunk.get("section_id") not in chapter_ranges:
            continue
        relative = Path(chunk["file"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe chunk path in section index: " + str(relative))
        path = source / relative
        if not path.is_file():
            raise FileNotFoundError("Missing chapter source chunk: " + str(path))
        pages: list[dict] = []
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                page = json.loads(line)
                page_number = int(page["pdf_page"])
                if page_number in seen_pages:
                    raise ValueError("Duplicate chapter PDF page: " + str(page_number))
                start, end = int(chunk["pdf_page_start"]), int(chunk["pdf_page_end"])
                if not start <= page_number <= end:
                    raise ValueError("Page outside declared chunk range: " + str(page_number))
                if page.get("section_id") != chunk["section_id"]:
                    raise ValueError("Page section ID does not match chunk metadata: " + str(page_number))
                seen_pages.add(page_number)
                pages.append(page)
        if len(pages) != int(chunk["page_count"]):
            raise ValueError(
                f"Chunk page count mismatch in {path}: expected {chunk['page_count']}, found {len(pages)}"
            )
        pages.sort(key=lambda page: int(page["pdf_page"]))
        yield chunk, pages
    missing = sorted(expected_pages - seen_pages)
    unexpected = sorted(seen_pages - expected_pages)
    if missing or unexpected:
        raise ValueError(
            "Chapter page coverage mismatch. Missing: " + str(missing[:20]) +
            "; unexpected: " + str(unexpected[:20])
        )


def candidate_records(page: dict, abbreviations: dict[str, str], chunk_id: str):
    items = page.get("text_items", [])
    if not items:
        return [], []
    records: list[dict] = []
    wrapped: list[dict] = []
    page_number = int(page["pdf_page"])
    section_id = str(page["section_id"])
    for group in group_lines(items):
        line_text = "".join(str(item.get("text", "")) for item in group).strip()
        for item_index, item in enumerate(group):
            span_text = str(item.get("text", ""))
            for token_index, match in enumerate(TOKEN.finditer(span_text)):
                token = match.group("token")
                source_abbreviation = abbreviations.get(token.casefold())
                if source_abbreviation is None:
                    continue
                grade, evidence = grade_evidence(token, item)
                records.append({
                    "id": (
                        f"{chunk_id}-p{page_number:04d}-y{round(float(item.get('top', 0)) * 100):06d}"
                        f"-x{round(float(item.get('left', 0)) * 100):06d}-i{item_index:03d}-t{token_index:02d}"
                    ),
                    "source_pdf_page": page_number,
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
            if span_text.rstrip().endswith("-") and re.search(
                r"[A-Za-zÀ-ÖØ-öø-ÿÆæŒœ]+-$", span_text.rstrip()
            ):
                wrapped.append({
                    "source_pdf_page": page_number,
                    "source_section_id": section_id,
                    "text_as_printed": span_text,
                    "top": float(item.get("top", 0)),
                    "left": float(item.get("left", 0)),
                    "review_reason": "possible_hyphenated_remedy_token_wrapped_at_line_end",
                })
    return records, wrapped


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract lazy source-grade candidate chunks from the supplied PDF.")
    parser.add_argument("--source", type=Path, default=Path("kent-source-chunks"))
    parser.add_argument("--abbreviations", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    abbreviation_path = args.abbreviations.expanduser().resolve() if args.abbreviations else source / "structured" / "remedy-abbreviations.json"
    output_dir = args.out_dir.expanduser().resolve() if args.out_dir else source / "structured" / "grade-candidates"
    index_path = source / "section-index.json"
    if not index_path.is_file():
        parser.error("Missing section-index.json in source package.")
    section_index = json.loads(index_path.read_text(encoding="utf-8"))
    abbreviations = load_abbreviation_map(abbreviation_path)

    total_pages = 0
    total_candidates = 0
    empty_pages: list[int] = []
    wrapped_fragments: list[dict] = []
    grade_counts: Counter[str] = Counter()
    chapter_counts: Counter[str] = Counter()
    chunk_index: list[dict] = []

    for chunk, pages in iter_chapter_chunks(source, section_index):
        section_id = str(chunk["section_id"])
        chunk_id = f"{section_id}-{int(chunk['part']):03d}"
        destination = output_dir / section_id / f"{chunk_id}.jsonl"
        destination.parent.mkdir(parents=True, exist_ok=True)
        chunk_candidates = 0
        with destination.open("w", encoding="utf-8") as handle:
            for page in pages:
                total_pages += 1
                if not page.get("text_items"):
                    empty_pages.append(int(page["pdf_page"]))
                records, wrapped = candidate_records(page, abbreviations, chunk_id)
                wrapped_fragments.extend(wrapped)
                for record in records:
                    grade = record["candidate_grade_from_source_key"]
                    grade_counts[str(grade) if grade is not None else "ungraded_review"] += 1
                    chapter_counts[section_id] += 1
                    handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                    chunk_candidates += 1
                    total_candidates += 1
        chunk_index.append({
            "chunk_id": chunk_id,
            "section_id": section_id,
            "part": int(chunk["part"]),
            "pdf_page_start": int(chunk["pdf_page_start"]),
            "pdf_page_end": int(chunk["pdf_page_end"]),
            "page_count": int(chunk["page_count"]),
            "candidate_count": chunk_candidates,
            "file": destination.relative_to(output_dir.parent).as_posix(),
        })

    metadata_path = source / "source-metadata.json"
    source_hash = None
    if metadata_path.is_file():
        source_hash = json.loads(metadata_path.read_text(encoding="utf-8")).get("source_sha256")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    dataset_index = {
        "dataset_id": "kent-pdf-rubric-grade-candidate-index",
        "source_file_sha256": source_hash,
        "candidate_count": total_candidates,
        "verification_status": "needs_review",
        "rubric_hierarchy_assigned": False,
        "chunks": chunk_index,
    }
    (output_dir.parent / "grade-candidates-index.json").write_text(
        json.dumps(dataset_index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    qc = {
        "source_file_sha256": source_hash,
        "chapter_pages_processed": total_pages,
        "candidate_count": total_candidates,
        "candidate_counts_by_grade_evidence": dict(grade_counts),
        "candidate_counts_by_chapter": dict(chapter_counts),
        "pages_without_layout_spans": empty_pages,
        "possible_wrapped_token_fragments": wrapped_fragments,
        "rubric_hierarchy_assigned": False,
        "records_verified": 0,
        "records_needing_review": total_candidates,
        "external_data_used": False,
        "fabricated_records": 0,
        "page_coverage": "validated against all chapter PDF pages",
        "policy": (
            "Candidates preserve PDF text and typography; no rubric hierarchy is inferred and no candidate is marked verified. "
            "Grade 3 requires uppercase token plus red source text style; conflicts and unrecognised styles remain ungraded."
        ),
    }
    (output_dir.parent / "rubric-grade-candidates-qc.json").write_text(
        json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "candidate_count": total_candidates,
        "chapter_pages_processed": total_pages,
        "candidate_counts_by_grade_evidence": dict(grade_counts),
        "chunks_created": len(chunk_index),
        "wrapped_token_fragments_flagged": len(wrapped_fragments),
        "records_verified": 0,
        "output_dir": str(output_dir),
        "index": str(output_dir.parent / "grade-candidates-index.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
