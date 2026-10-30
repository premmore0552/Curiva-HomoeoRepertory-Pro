# Import and validate the supplied J. T. Kent PDF

This workflow uses only the PDF supplied for this project. It does not add external repertories, websites, remedy aliases, synonyms, guessed rubric paths or invented grades.

## Findings for this supplied copy

- 2,834 physical PDF pages.
- The supplied PDF has selectable embedded text; the importer reads that text layer instead of running a second OCR pass.
- The extraction retains page-level layout spans, positions, font family, size, color, bold/italic style and source links.
- PDF page 36 states: **Capitals = 3; Italics = 2; Ordinary = 1**. This is source evidence. It is not permission to assign grades to text before the remedy tokens and rubric context have been identified.
- The cover prints **“REPERTOTY”**. The importer preserves source spelling and does not silently correct it.
- PDF page 7 visibly prints **Copyright © 1998 MEDI-T**. Redistribution status is not established by the PDF. Follow [Source PDF rights and data handling](SOURCE_DATA_RIGHTS.md); keep all extracted book data local-only until permission is confirmed.

The supplied extraction report records 6,836,597 extracted characters, 2,834 layout pages, no pages below 15 extracted characters and no replacement characters. Seven pages contain fewer than 300 characters and are retained for review. This does not prove every printed word is perfect: visually check doubtful pages against the PDF.

## Source section map

The source is divided into 40 import sections, including 34 repertory chapters plus preliminary matter and the final page. The chapter list follows the contents in the supplied PDF. Urinary organs retains its printed subheadings Bladder, Kidneys, Prostate gland and Urethra; Urine is kept separate. Skin is included from its visible text heading even though it is not a separate top-level PDF bookmark.

Physical PDF page numbers and internal repertory page numbers are separate fields. Section-boundary pages are preserved whole and flagged because a chapter transition can occur within a page. Chunks contain no more than 25 PDF pages.

## Android / Termux setup

In Termux, install the required tools:

~~~bash
pkg update
pkg install python poppler unzip -y
~~~

Download or copy the repository into your Termux working folder, then open that folder. Put the supplied PDF in Downloads (or use its actual path).

## Step 1 — Extract the source PDF

Run this from the repository root:

~~~bash
python scripts/prepare-kent-pdf.py "$HOME/storage/shared/Download/J.T. Kent s Repertory.pdf" --out "$HOME/Curiva/kent-source-chunks" --zip "$HOME/Curiva/Kent_Repertory_Source_Chunks.zip"
~~~

The script requires Poppler commands pdfinfo, pdftotext and pdftohtml, plus Python's standard library. It rejects a PDF whose page count does not match the section map. It creates source-metadata.json, section-index.json, QC_REPORT.md, README.md and page-aligned JSONL chunks.

## Step 2 — Validate page coverage and create the checksum manifest

Run:

~~~bash
python scripts/validate-kent-source-package.py "$HOME/Curiva/kent-source-chunks" --pdf "$HOME/storage/shared/Download/J.T. Kent s Repertory.pdf" --write-manifest --zip "$HOME/Curiva/Kent_Repertory_Source_Chunks.zip"
~~~

This checks:
- the source PDF's SHA-256 fingerprint (when --pdf is supplied);
- exact page coverage from PDF page 1 through the final page, with no duplicate or missing pages;
- section ranges with no gaps or overlaps;
- chunk paths, declared ranges, maximum chunk size and JSONL page records;
- the source text/layout extraction metadata and no-fabrication/no-grade-inference flags;
- the generated manifest's SHA-256 and byte-size checksums.

It writes manifest.json into the local source package and rebuilds the ZIP so the manifest is included. A later modification to any packaged file makes the manifest check fail; rebuild it after every extraction or data-package change.

You can validate a ZIP without extracting it:

~~~bash
python scripts/validate-kent-source-package.py "$HOME/Curiva/Kent_Repertory_Source_Chunks.zip" --pdf "$HOME/storage/shared/Download/J.T. Kent s Repertory.pdf"
~~~

To block a release unless permission has been documented in source-metadata.json, add --for-publication. The validator checks that rights fields are recorded; it does not make a legal determination. With the current supplied PDF, publication should remain blocked.

## Step 3 — Parse the PDF's own remedy abbreviation table

After source extraction:

~~~bash
python scripts/parse-kent-abbreviations.py --source "$HOME/Curiva/kent-source-chunks"
~~~

The output is written under structured/:
- remedy-abbreviations.json — abbreviations and full names as printed, with PDF page and column coordinates;
- remedy-abbreviations-audit.csv — review-friendly audit table;
- remedy-abbreviations-qc.json — duplicate, continuation and unclassified-line checks.

The parser preserves the source spellings and does not standardise names. Two split full names in the supplied copy are continued on the next line in their respective column: Aur-m-n. / Natronatum on PDF page 11, and Chen-an. / Anthelminticum on PDF page 12. These joins are recorded as source continuations, not independent corrections.

The existing local extraction audit contains 650 abbreviation entries. These are transcribed entries, not a claim that every name has already been proofread against the printed page.

## Step 4 — Prepare source-matched grade candidates

Run:

~~~bash
python scripts/parse-kent-grade-candidates.py --source "$HOME/Curiva/kent-source-chunks"
~~~

The existing audit of this supplied PDF found 433,541 candidate remedy-token occurrences across 127 repertory chunks. They are **candidates only**. The parser records the source text and style evidence, proposes a review navigation context, and leaves every record needs_review with rubric_assignment: unassigned. No record becomes a verified repertory entry at this stage.

The parser only matches remedy tokens against the abbreviation table extracted from this same PDF. Unrecognised or conflicting styles remain ungraded. The source typography and the PDF's grade key must be checked against the original page before acceptance.

## Step 5 — Install the local package into the app for development

The public repository intentionally ignores public/data/kent/. These files are local-only and must not be pushed to GitHub until redistribution rights are confirmed.

~~~bash
mkdir -p public/data/kent/structured
cp "$HOME/Curiva/kent-source-chunks/section-index.json" public/data/kent/section-index.json
cp -R "$HOME/Curiva/kent-source-chunks/chunks" public/data/kent/
cp "$HOME/storage/shared/Download/J.T. Kent s Repertory.pdf" public/data/kent/source.pdf
cp "$HOME/Curiva/kent-source-chunks/structured/remedy-abbreviations.json" public/data/kent/structured/remedy-abbreviations.json
cp "$HOME/Curiva/kent-source-chunks/structured/grade-candidates-index.json" public/data/kent/structured/grade-candidates-index.json
cp -R "$HOME/Curiva/kent-source-chunks/structured/grade-candidates" public/data/kent/structured/
cp "$HOME/Curiva/kent-source-chunks/structured/rubric-grade-candidates-qc.json" public/data/kent/structured/rubric-grade-candidates-qc.json
~~~

**Important path:** the app loader requests /data/kent/structured/remedy-abbreviations.json. Do not copy that file to /data/kent/remedy-abbreviations.json.

The browser's “Open original PDF” links use /data/kent/source.pdf#page=.... The PDF is also local-only. Source chunks, candidate files and the original PDF are not committed to this public repository.

## What Phase 1 does not claim

Phase 1 prepares a traceable source package. It does not establish the copyright status, verify every printed word, create a complete rubric hierarchy, approve candidate grades or make a clinically complete repertory. Those tasks require documented permission where applicable and manual source review.

## Refresh the manifest after every package change

The first manifest is created immediately after source extraction. Parsing the abbreviation table and candidate records later adds new files under `structured/`; therefore, after Step 4 finishes, run the manifest command again:

~~~bash
python scripts/validate-kent-source-package.py "$HOME/Curiva/kent-source-chunks" --pdf "$HOME/storage/shared/Download/J.T. Kent s Repertory.pdf" --write-manifest --zip "$HOME/Curiva/Kent_Repertory_Source_Chunks.zip"
~~~

This rebuilds the local ZIP and checks the ZIP that was just written. Repeat this command whenever you add, remove or change a file in the source package. The manifest records file integrity, not the correctness or copyright permission of the book-derived contents.
