#!/usr/bin/env python3
"""Prepare source-faithful, page-aligned chunks from the supplied Kent PDF.

Requirements: Python 3, pdfinfo, pdftotext and pdftohtml (Poppler).
No OCR, spell correction, rubric invention, remedy aliasing or grade inference is run.
"""
from __future__ import annotations
import argparse, hashlib, json, re, shutil, statistics, subprocess, tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

CHUNK_PAGES = 25
EXPECTED_PAGES = 2834

# Physical PDF page ranges from the supplied copy. Internal repertory pagination is separate.
SECTIONS = [
    ("preliminary", "Title, biography and introductory pages", 1, 9, None),
    ("remedy-abbreviations", "Remedies and their abbreviations", 10, 18, None),
    ("repertory-instructions", "Preface and use of the repertory", 19, 34, None),
    ("method-and-cases", "Repertorising, grading, cases and temperature lists", 35, 61, None),
    ("contents-and-mind-index", "Contents and Mind index", 62, 65, None),
    ("mind", "Mind", 66, 245, [1, 95]),
    ("vertigo", "Vertigo", 246, 266, [96, 106]),
    ("head", "Head", 267, 523, [107, 234]),
    ("eye", "Eye", 524, 598, [235, 270]),
    ("vision", "Vision", 599, 629, [271, 285]),
    ("ear", "Ear", 630, 703, [285, 320]),
    ("hearing", "Hearing", 704, 709, [321, 323]),
    ("nose", "Nose", 710, 771, [324, 354]),
    ("face", "Face", 772, 860, [355, 396]),
    ("mouth", "Mouth", 861, 926, [397, 430]),
    ("teeth", "Teeth", 927, 958, [430, 447]),
    ("throat", "Throat", 959, 1001, [448, 470]),
    ("external-throat", "External throat", 1002, 1011, [471, 475]),
    ("stomach", "Stomach", 1012, 1138, [476, 540]),
    ("abdomen", "Abdomen", 1139, 1268, [541, 605]),
    ("rectum", "Rectum", 1269, 1325, [606, 635]),
    ("stool", "Stool", 1326, 1341, [635, 644]),
    ("urinary-organs", "Urinary organs", 1342, 1411, [645, 680]),
    ("urine", "Urine", 1412, 1432, [680, 692]),
    ("genitalia-male", "Genitalia male", 1433, 1475, [693, 714]),
    ("genitalia-female", "Genitalia female", 1476, 1536, [714, 745]),
    ("larynx-trachea", "Larynx and trachea", 1537, 1568, [746, 762]),
    ("respiration", "Respiration", 1569, 1598, [762, 777]),
    ("cough", "Cough", 1599, 1660, [778, 811]),
    ("expectorations", "Expectoration", 1661, 1677, [812, 821]),
    ("chest", "Chest", 1678, 1802, [822, 883]),
    ("back", "Back", 1803, 1939, [884, 951]),
    ("extremities", "Extremities", 1940, 2510, [952, 1233]),
    ("sleep", "Sleep", 2511, 2555, [1234, 1258]),
    ("chill", "Chill", 2556, 2588, [1259, 1277]),
    ("fever", "Fever", 2589, 2614, [1278, 1292]),
    ("perspiration", "Perspiration", 2615, 2632, [1293, 1302]),
    ("skin", "Skin", 2633, 2698, [1303, 1340]),
    ("generalities", "Generalities", 2699, 2833, [1341, 1423]),
    ("end-matter", "Final page and source link", 2834, 2834, None),
]
URINARY_CHILDREN = [
    {"id": "bladder", "title": "Bladder", "pdf_page_start": 1342, "pdf_page_end": 1374, "internal_page_range": [645, 662]},
    {"id": "kidneys", "title": "Kidneys", "pdf_page_start": 1375, "pdf_page_end": 1383, "internal_page_range": [662, 667]},
    {"id": "prostate-gland", "title": "Prostate gland", "pdf_page_start": 1384, "pdf_page_end": 1388, "internal_page_range": [667, 668]},
    {"id": "urethra", "title": "Urethra", "pdf_page_start": 1389, "pdf_page_end": 1411, "internal_page_range": [669, 680]},
]

def run(args: list[str]) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout

def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def node_text(node: ET.Element) -> str:
    return "".join(node.itertext())

def main() -> None:
    parser = argparse.ArgumentParser(description="Extract the supplied Kent PDF into chapter chunks.")
    parser.add_argument("pdf", type=Path, help="Path to the supplied PDF")
    parser.add_argument("--out", type=Path, default=Path("kent-source-chunks"), help="Output folder")
    parser.add_argument("--zip", type=Path, default=Path("Kent_Repertory_Source_Chunks.zip"), help="Output ZIP")
    args = parser.parse_args()

    pdf = args.pdf.expanduser().resolve()
    out = args.out.expanduser().resolve()
    zip_path = args.zip.expanduser().resolve()
    if not pdf.is_file():
        parser.error("PDF not found: " + str(pdf))
    for binary in ("pdfinfo", "pdftotext", "pdftohtml"):
        if shutil.which(binary) is None:
            parser.error("Missing Poppler command: " + binary)

    info_text = run(["pdfinfo", str(pdf)])
    match = re.search(r"^Pages:\s+(\d+)\s*$", info_text, re.MULTILINE)
    if not match:
        parser.error("Could not read page count from pdfinfo.")
    page_count = int(match.group(1))
    if page_count != EXPECTED_PAGES:
        parser.error("This section map is for the supplied 2,834-page PDF. Found " + str(page_count) + " pages; review mappings before using another edition.")

    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kent-import-") as tmp:
        temp = Path(tmp)
        txt_path = temp / "kent.txt"
        xml_prefix = temp / "kent-layout"
        run(["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), str(txt_path)])
        run(["pdftohtml", "-xml", "-hidden", "-i", "-f", "1", "-l", str(page_count), str(pdf), str(xml_prefix)])
        xml_path = xml_prefix.with_suffix(".xml")
        if not xml_path.is_file():
            parser.error("pdftohtml did not create an XML layout file.")

        raw_pages = txt_path.read_text(encoding="utf-8", errors="replace").split("\f")
        if raw_pages and not raw_pages[-1].strip():
            raw_pages.pop()
        if len(raw_pages) != page_count:
            parser.error("Text extraction page count mismatch: got " + str(len(raw_pages)) + ", expected " + str(page_count))

        section_for_page = {}
        section_meta = []
        chunk_map = []
        writers = {}
        for sid, title, start, end, internal_range in SECTIONS:
            if start < 1 or end > page_count or start > end:
                parser.error("Invalid section range for " + sid + ": " + str(start) + "–" + str(end))
            section_meta.append({
                "id": sid, "title": title, "pdf_page_start": start, "pdf_page_end": end,
                "page_count": end - start + 1, "internal_page_range": internal_range,
                "subsections": URINARY_CHILDREN if sid == "urinary-organs" else [],
            })
            for page_no in range(start, end + 1):
                if page_no in section_for_page:
                    parser.error("Overlapping source section mapping at PDF page " + str(page_no))
                section_for_page[page_no] = (sid, title)
            part = 1
            for first in range(start, end + 1, CHUNK_PAGES):
                last = min(first + CHUNK_PAGES - 1, end)
                rel = Path("chunks") / sid / (sid + "-" + str(part).zfill(3) + ".jsonl")
                target = out / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                writers[(sid, part)] = target.open("w", encoding="utf-8")
                chunk_map.append({
                    "section_id": sid, "part": part, "pdf_page_start": first,
                    "pdf_page_end": last, "page_count": last - first + 1, "file": str(rel),
                })
                part += 1

        missing_section_pages = sorted(set(range(1, page_count + 1)) - set(section_for_page))
        if missing_section_pages:
            parser.error("Section map does not cover PDF pages: " + str(missing_section_pages[:20]))

        xml_pages = 0
        # pdftohtml may define a font only once and reuse its ID on later pages.
        # Keep a document-wide map; resetting per page loses italic/color grade evidence.
        font_map = {}
        for _, page in ET.iterparse(xml_path, events=("end",)):
            if page.tag != "page":
                continue
            page_no = int(page.attrib.get("number", "0"))
            if page_no < 1 or page_no > page_count:
                page.clear()
                continue
            xml_pages += 1
            sid, title = section_for_page[page_no]
            for fs in page.findall("fontspec"):
                font_map[fs.attrib.get("id", "")] = {
                    "family": fs.attrib.get("family", ""),
                    "size": fs.attrib.get("size", ""),
                    "color": fs.attrib.get("color", "#000000"),
                }
            items = []
            for node in page.findall("text"):
                value = node_text(node)
                if not value:
                    continue
                font = font_map.get(node.attrib.get("font", ""), {})
                bold = any(child.tag == "b" for child in node.iter())
                italic = any(child.tag == "i" for child in node.iter())
                links = [child.attrib["href"] for child in node.iter() if child.tag == "a" and "href" in child.attrib]
                def number(key: str) -> float:
                    try:
                        return round(float(node.attrib.get(key, "0")), 2)
                    except ValueError:
                        return 0.0
                item = {
                    "text": value, "top": number("top"), "left": number("left"),
                    "width": number("width"), "height": number("height"),
                    "font_family": font.get("family", ""), "font_size": font.get("size", ""),
                    "color": font.get("color", "#000000"), "bold": bold, "italic": italic,
                }
                if links:
                    item["source_links"] = links
                items.append(item)
            items.sort(key=lambda item: (item["top"], item["left"]))
            sec = next(item for item in section_meta if item["id"] == sid)
            record = {
                "pdf_page": page_no, "section_id": sid, "section_title": title,
                "boundary_page_review": page_no in (sec["pdf_page_start"], sec["pdf_page_end"]),
                "text": raw_pages[page_no - 1].strip("\r\n"),
                "text_items": items,
            }
            if sid == "urinary-organs":
                child_section = next((child for child in URINARY_CHILDREN if child["pdf_page_start"] <= page_no <= child["pdf_page_end"]), None)
                if child_section:
                    record["subsection_id"] = child_section["id"]
            part = ((page_no - sec["pdf_page_start"]) // CHUNK_PAGES) + 1
            writers[(sid, part)].write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            page.clear()
        for writer in writers.values():
            writer.close()
        if xml_pages != page_count:
            parser.error("Layout extraction page count mismatch: processed " + str(xml_pages) + ", expected " + str(page_count))

    lengths = [len(value.strip()) for value in raw_pages]
    under_15 = [i + 1 for i, value in enumerate(lengths) if value < 15]
    under_300 = [i + 1 for i, value in enumerate(lengths) if value < 300]
    replacements = [i + 1 for i, value in enumerate(raw_pages) if "\ufffd" in value]
    chapter_count = sum(1 for item in section_meta if item["internal_page_range"] is not None)
    source_sha = file_hash(pdf)
    metadata = {
        "dataset_id": "kent-repertory-uploaded-pdf",
        "source_file_name": pdf.name,
        "source_sha256": source_sha,
        "pdf_page_count": page_count,
        "pdf_metadata_text": info_text,
        "text_extraction": {
            "method": "pdftotext -layout plus pdftohtml -xml layout spans",
            "fresh_ocr_run": False,
            "reason": "The PDF contains selectable text on the repertory pages; the existing embedded text layer is used.",
            "extracted_characters": sum(lengths),
            "median_characters_per_page": statistics.median(lengths),
            "pages_under_15_characters": under_15,
            "pages_under_300_characters": under_300,
            "pages_with_replacement_characters": replacements,
            "xml_pages_processed": xml_pages,
        },
        "grade_key_from_source": {
            "pdf_page": 36,
            "source_statement": "Capitals = 3; Italics = 2; Ordinary = 1",
            "policy": "Typography is retained. Assign grades only after identifying actual remedy tokens in a rubric; do not assign grades to headings or prose.",
        },
        "rights_and_provenance": {
            "visible_rights_statement": "The PDF displays Copyright © 1998 MEDI-T on its introductory headings page.",
            "redistribution_status": "unknown_from_file_alone",
            "publication_policy": "Do not publish extracted contents in a public repository until redistribution rights are confirmed.",
        },
        "data_integrity": {
            "source_only": True, "fabricated_records": 0, "normalization_applied": False,
            "remedy_aliases_added": 0, "grade_inference_applied": False,
            "status": "page-aligned source text and typography; not yet verified structured rubric data",
        },
    }
    (out / "source-metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    index = {
        "source_metadata": "source-metadata.json", "chunk_pages_max": CHUNK_PAGES,
        "section_count": len(section_meta), "chapter_count": chapter_count,
        "sections": section_meta, "chunks": chunk_map,
        "boundary_page_policy": "Transition pages are kept whole and flagged; no source lines are silently trimmed.",
    }
    (out / "section-index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    report = f"""# Kent PDF extraction report

- Source file: {pdf.name}
- PDF pages: {page_count:,}
- SHA-256: {source_sha}
- Extracted characters (trimmed per page): {sum(lengths):,}
- Median characters per page: {statistics.median(lengths):,.0f}
- Pages under 15 characters: {under_15 or 'none'}
- Pages under 300 characters: {under_300 or 'none'}
- Pages with replacement characters: {replacements or 'none'}
- Layout XML pages processed: {xml_pages:,}

## OCR assessment

The PDF already contains selectable text. This importer does not run a new OCR pass. Absence of replacement characters is a useful extraction check, not proof every word is perfect. Compare doubtful wording with the PDF page image. The cover visibly spells the title “REPERTOTY”; the package preserves it as printed rather than silently correcting it.

## Grades

The PDF states on page 36: Capitals = 3; Italics = 2; Ordinary = 1. The importer retains font, color, bold/italic flags and positions. It does not yet assign grades: the next parser must first identify a remedy token in the context of a rubric.

## Sections and rights

The book is partitioned into {chapter_count} repertory chapters plus preliminary/end matter. Chunks are no larger than {CHUNK_PAGES} PDF pages. Urinary organs retains the PDF's Bladder, Kidneys, Prostate gland and Urethra subsections; Urine is separate. The supplied PDF itself displays Copyright © 1998 MEDI-T. Redistribution rights for this compilation are unknown from the file alone, so do not publish extracted contents in a public repository until rights are confirmed.

## Data policy

No rubric, remedy, alias, synonym or grade is invented. This package is source staging data, not yet the verified structured repertory database.
"""
    (out / "QC_REPORT.md").write_text(report, encoding="utf-8")
    readme = """# Kent repertory source chunks

All content comes from the supplied PDF only.

- source-metadata.json: source fingerprint, extraction checks and rights note
- section-index.json: category ranges and chunk paths
- chunks/<section-id>/<section-id>-NNN.jsonl: page records, maximum 25 PDF pages per file
- Each record preserves PDF page number, page text, coordinates, font family, size, color, bold/italic flags and source links.

This is a raw source staging pack, not verified structured rubric/remedy/grade data. Transition pages are preserved whole and flagged for review.
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    # Archive only this run's declared outputs. This prevents stale files from an older
    # extraction in a reused output directory from silently entering the ZIP.
    generated_files = [
        out / "source-metadata.json",
        out / "section-index.json",
        out / "QC_REPORT.md",
        out / "README.md",
        *sorted((out / "chunks").rglob("*.jsonl")),
    ]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file in generated_files:
            if not file.is_file():
                parser.error("Expected generated source file is missing: " + str(file))
            archive.write(file, Path("kent-source-chunks") / file.relative_to(out))
    print("Created " + str(zip_path) + " with " + str(len(chunk_map)) + " chunks from " + str(page_count) + " PDF pages.")

if __name__ == "__main__":
    main()
