#!/usr/bin/env python3
"""Parse the remedy abbreviation table from the previously extracted PDF pages.

Input: chunks/remedy-abbreviations/*.jsonl produced by prepare-kent-pdf.py.
Output: structured/remedy-abbreviations.json, CSV audit and QC JSON.
This script does not canonicalize names, add aliases, or use external data.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
from pathlib import Path

ENTRY = re.compile(r"^\s*(?P<abbr>[\wÆæŒœ-]+\.?)\s*-{3,}\s*(?P<name>.*?)\s*$", re.UNICODE)
CONTINUATION = re.compile(r"^[\wÀ-ÿÆæŒœ().\- ]+$", re.UNICODE)
FIRST_PAGE = 10
LAST_PAGE = 18


def load_pages(source: Path) -> list[dict]:
    folder = source / "chunks" / "remedy-abbreviations"
    if not folder.is_dir():
        raise FileNotFoundError(
            f"Cannot find {folder}. Run prepare-kent-pdf.py first and use its output directory."
        )
    pages: dict[int, dict] = {}
    for path in sorted(folder.glob("*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                page_number = int(record["pdf_page"])
                if FIRST_PAGE <= page_number <= LAST_PAGE:
                    if page_number in pages:
                        raise ValueError(f"Duplicate page record {page_number} in {path}:{line_number}")
                    pages[page_number] = record
    missing = sorted(set(range(FIRST_PAGE, LAST_PAGE + 1)) - set(pages))
    if missing:
        raise ValueError(f"Missing abbreviation source pages: {missing}")
    return [pages[number] for number in range(FIRST_PAGE, LAST_PAGE + 1)]


def parse(source: Path) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    continuations: list[dict] = []
    flagged_lines: list[dict] = []
    for page in load_pages(source):
        pdf_page = int(page["pdf_page"])
        items = sorted(page.get("text_items", []), key=lambda item: (float(item.get("left", 0)), float(item.get("top", 0))))
        last_by_column: dict[str, dict] = {}
        for item in items:
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            top = float(item.get("top", 0))
            left = float(item.get("left", 0))
            column = "left" if left < 300 else "right"
            match = ENTRY.match(text)
            if match:
                record = {
                    "id": f"kent-pdf{pdf_page:04d}-{len(records) + 1:04d}",
                    "abbreviation_as_printed": match.group("abbr"),
                    "full_name_as_printed": match.group("name").strip(),
                    "source_pdf_page": pdf_page,
                    "source_pdf_pages": [pdf_page],
                    "source_column": column,
                    "source_position": {"top": top, "left": left},
                    "source_line_as_printed": text,
                    "continuation_lines": [],
                    "verification_status": "transcribed_not_manually_proofread",
                }
                records.append(record)
                last_by_column[column] = record
                continue

            # A continuation is joined only when it is a short, alphabetic line directly
            # below a parsed entry in the same column. The original line remains recorded.
            previous = last_by_column.get(column)
            if (
                previous is not None
                and 100 <= top < 1000
                and CONTINUATION.fullmatch(text)
                and top - float(previous["source_position"]["top"]) <= 35
                and len(text) <= 40
            ):
                previous["full_name_as_printed"] = (previous["full_name_as_printed"] + " " + text).strip()
                previous["source_pdf_pages"] = sorted(set(previous["source_pdf_pages"] + [pdf_page]))
                continuation = {
                    "pdf_page": pdf_page,
                    "text_as_printed": text,
                    "top": top,
                    "left": left,
                    "join_rule": "next short text line in same column within 35 layout units",
                }
                previous["continuation_lines"].append(continuation)
                continuations.append({
                    "abbreviation": previous["abbreviation_as_printed"],
                    "pdf_page": pdf_page,
                    "text_as_printed": text,
                })
            elif 100 <= top < 1000 and "-" not in text:
                # Leave unexplained lines visible in the QC file; never guess their role.
                flagged_lines.append({"pdf_page": pdf_page, "top": top, "left": left, "text": text})

    return records, continuations, flagged_lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse only Kent PDF pages 10–18 abbreviation table.")
    parser.add_argument("--source", type=Path, default=Path("kent-source-chunks"), help="Folder created by prepare-kent-pdf.py")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    records, continuations, flagged = parse(source)

    counts: dict[str, int] = {}
    for record in records:
        key = record["abbreviation_as_printed"]
        counts[key] = counts.get(key, 0) + 1
    duplicates = {key: count for key, count in counts.items() if count > 1}
    empty_names = [record for record in records if not record["full_name_as_printed"]]

    out_dir = source / "structured"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_id": "kent-pdf-remedy-abbreviation-index",
        "source": {
            "title_heading": "Remedies and their Abbreviations",
            "pdf_page_start": FIRST_PAGE,
            "pdf_page_end": LAST_PAGE,
        },
        "scope": "The supplied PDF abbreviation table only. This is not a materia medica monograph or remedy-grade table.",
        "parsing": {
            "method": "Read text-layout spans in PDF page and column order; split at the printed hyphen leaders.",
            "continuation_lines_joined_from_layout": continuations,
            "unclassified_text_lines": flagged,
            "normalization_applied": False,
            "canonical_aliases_added": 0,
            "external_data_used": False,
        },
        "record_count": len(records),
        "duplicate_abbreviation_count": len(duplicates),
        "records": records,
    }
    (out_dir / "remedy-abbreviations.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with (out_dir / "remedy-abbreviations-audit.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "abbreviation_as_printed", "full_name_as_printed", "source_pdf_pages",
            "source_column", "source_line_as_printed", "continuation_lines", "verification_status",
        ])
        for record in records:
            writer.writerow([
                record["abbreviation_as_printed"],
                record["full_name_as_printed"],
                ",".join(str(page) for page in record["source_pdf_pages"]),
                record["source_column"],
                record["source_line_as_printed"],
                "; ".join(line["text_as_printed"] for line in record["continuation_lines"]),
                record["verification_status"],
            ])

    qc = {
        "source_pages_processed": list(range(FIRST_PAGE, LAST_PAGE + 1)),
        "record_count": len(records),
        "duplicate_abbreviation_count": len(duplicates),
        "duplicate_abbreviations": duplicates,
        "empty_full_names": len(empty_names),
        "continuation_lines_joined": continuations,
        "unclassified_layout_lines": flagged,
        "review_required": True,
        "reason": "OCR/layout transcriptions must still be checked against the PDF page images.",
    }
    (out_dir / "remedy-abbreviations-qc.json").write_text(
        json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "records": len(records),
        "duplicates": len(duplicates),
        "empty_names": len(empty_names),
        "continuations_joined": len(continuations),
        "unclassified_lines": len(flagged),
        "output": str(out_dir),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
