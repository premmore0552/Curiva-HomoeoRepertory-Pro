# Import the supplied J. T. Kent PDF

This workflow is strict: it imports only the PDF selected by the user. It does not use external repertories, websites, generated examples, guessed remedy aliases, or inferred rubric data.

## Findings for the supplied copy

- 2,834 PDF pages.
- The repertory pages contain a selectable embedded text layer, so the pipeline extracts it instead of running a new OCR pass.
- Page-level layout/font/color metadata is retained.
- The source states on PDF page 36: **Capitals = 3; Italics = 2; Ordinary = 1**. The pipeline preserves this typographic evidence but does not assign a grade until it has identified a remedy token in a rubric.
- The cover visibly prints “REPERTOTY”. The importer preserves this source spelling rather than silently correcting it.
- The PDF includes “Copyright © 1998 MEDI-T”. The rights status of this particular compilation is not established from the file alone. Do not publish its complete extracted contents in a public repository without rights confirmation.

## Section map

The source is divided into the 34 repertory chapters listed in its contents, plus preliminary matter and the final page. Urinary organs preserves the source's subheadings: Bladder, Kidneys, Prostate gland and Urethra. Urine remains separate. Skin is included from its visible text heading even though it is not a separate top-level PDF bookmark.

PDF page numbers and internal repertory page numbers are stored separately. Transition pages are preserved whole and flagged because one PDF page can contain the end of one chapter and the index of the next.

## Termux / Linux use

Install Poppler and Python:

~~~bash
pkg install poppler python -y
~~~

Run the importer, replacing the path with the actual PDF location:

~~~bash
python scripts/prepare-kent-pdf.py "$HOME/storage/shared/Download/J.T. Kent s Repertory.pdf" --out "$HOME/Curiva/kent-source-chunks" --zip "$HOME/Curiva/Kent_Repertory_Source_Chunks.zip"
~~~

It uses Python's standard library plus Poppler commands pdfinfo, pdftotext and pdftohtml.

## Output format

Each file in chunks/<section-id>/ contains one JSON page record per line. Each record contains:
- pdf_page: exact 1-based PDF page number
- section_id and section_title: source chapter grouping
- text: extracted source page text
- text_items: span coordinates, font family, font size, color, bold and italic flags
- boundary_page_review: true on section transition pages

Each chunk has no more than 25 PDF pages, allowing the app to load sections incrementally rather than loading one monolithic dataset.

## Next stage before repertorization

A second-stage parser must build the rubric hierarchy and remedy entries from these spans, then map the source typography to the PDF's own grade key. It must keep page references and flag uncertain OCR/layout cases. Nothing becomes a verified record until reviewed.


## First structured slice: remedy abbreviation index

After extracting page chunks, parse the PDF's own abbreviation table (PDF pages 10–18):

```bash
python scripts/parse-kent-abbreviations.py --source "$HOME/Curiva/kent-source-chunks"
```

The script creates:
- `structured/remedy-abbreviations.json` — source abbreviation and full name as printed, with PDF page and column coordinates
- `structured/remedy-abbreviations-audit.csv` — review-friendly table
- `structured/remedy-abbreviations-qc.json` — duplicates, continuation joins and unclassified lines

The page layout has two split full names within their respective PDF pages: `Aur-m-n.` continues with `Natronatum` on PDF page 11, and `Chen-an.` continues with `Anthelminticum` on PDF page 12. The parser joins only short, next-line text in the same column and records each continuation. It does not standardize either name.

The app's Materia Medica navigation currently exposes this **abbreviation index only** when the local JSON file is installed. It is not a set of full remedy monographs.

For local testing, install both the source reader package and the abbreviation index:

```bash
mkdir -p public/data/kent
cp "$HOME/Curiva/kent-source-chunks/section-index.json" public/data/kent/section-index.json
cp -R "$HOME/Curiva/kent-source-chunks/chunks" public/data/kent/
cp "$HOME/Curiva/kent-source-chunks/structured/remedy-abbreviations.json" public/data/kent/remedy-abbreviations.json
```

The chapter browser expects the `section-index.json` file and `chunks/` directory. The Materia Medica abbreviation index expects the JSON file shown above. These paths are ignored by Git and must be copied again into a fresh local clone.

That data directory is ignored by Git on purpose. The repository is public and the supplied PDF displays a 1998 MEDI-T copyright notice, so full book-derived data must not be committed publicly without confirming redistribution rights. A private repository reduces exposure but is not itself proof of permission.


## Second structured stage: source grade candidates (not verified rubrics)

After the PDF abbreviation table is extracted, run:

```bash
python scripts/parse-kent-grade-candidates.py --source "$HOME/Curiva/kent-source-chunks"
```

The parser checks all 2,768 repertory pages in all 34 chapters. It matches remedy tokens only against the 650 abbreviations transcribed from this PDF. It writes:
- `structured/grade-candidates-index.json` — per-chunk page ranges and candidate counts
- `structured/grade-candidates/<chapter>/<chunk>.jsonl` — source-linked candidates, split into the same small chapter chunks used by the source reader
- `structured/rubric-grade-candidates-qc.json` — candidate counts, grade evidence, ungraded style conflicts and possible wrapped fragments

Current audit of the uploaded file produced **433,541 candidate occurrences** in 127 chapter chunks. Style evidence: 284,339 ordinary/grade-1 candidates, 116,412 italic/grade-2 candidates, 32,726 red-uppercase/grade-3 candidates, and 64 ambiguous style cases left ungraded. The parser also flags 9,537 possible line-wrapped fragments for review.

The source states the grade key on PDF page 36: capitals = 3, italics = 2, ordinary = 1. The implementation additionally checks the PDF's observed red text style when proposing grade 3. Uppercase tokens without the expected red style are left ungraded. Italic/uppercase conflicts and unrecognised styles are also left ungraded.

The parser supplies a **suggested rubric context** using the PDF's own heading font/color and text before a colon, then carries that context over wrapped continuation lines. This context is only a navigation aid; it is not an accepted rubric assignment.

**No candidate is verified.** Every record remains `needs_review` and `rubric_assignment: unassigned`. Review the original PDF page, enter/confirm the exact rubric path, select the grade and check the source-page box in the app. The source PDF's own wording, not an external repertory, is the only permitted basis.

## App installation after local extraction

For the source reader and grade-candidate review tabs, copy the extracted source package into the app's public data folder:

```bash
mkdir -p public/data/kent
cp "$HOME/Curiva/kent-source-chunks/section-index.json" public/data/kent/section-index.json
cp -R "$HOME/Curiva/kent-source-chunks/chunks" public/data/kent/
mkdir -p public/data/kent/structured
cp "$HOME/Curiva/kent-source-chunks/structured/remedy-abbreviations.json" public/data/kent/structured/
cp "$HOME/Curiva/kent-source-chunks/structured/grade-candidates-index.json" public/data/kent/structured/
cp -R "$HOME/Curiva/kent-source-chunks/structured/grade-candidates" public/data/kent/structured/
cp "$HOME/Curiva/kent-source-chunks/structured/rubric-grade-candidates-qc.json" public/data/kent/structured/
```

The Materia Medica section displays the PDF abbreviation index, and the chapter browser offers a **Grade candidates** review tab. Reviews are saved in this browser on this device. Use **Export reviews** to create a review JSON file. Do not clear browser site data before exporting reviews.

## Build the active repertory database from reviewed records

After checking candidate lines against the original PDF and entering the exact rubric path in the review panel, export the review file. Then run:

```bash
python scripts/build-verified-kent-database.py \\
  --reviews "$HOME/storage/shared/Download/curiva-kent-verified-review-decisions.json" \\
  --abbreviations "$HOME/Curiva/kent-source-chunks/structured/remedy-abbreviations.json" \\
  --out "$HOME/Curiva/kent-source-chunks/structured/verified-rubric-remedy-grades.json"
```

Install the generated JSON in the app:

```bash
cp "$HOME/Curiva/kent-source-chunks/structured/verified-rubric-remedy-grades.json" public/data/kent/structured/
```

Restart the Vite dev server or refresh the app. The repertorization matrix will then load only manually reviewed rubric/remedy/grade pairs.

The builder checks that the review export belongs to the exact supplied PDF SHA-256, every remedy abbreviation exists in that PDF's own abbreviation index, every record has a source-page check and grade 1–3, and conflicting grades for the same exact rubric/remedy pair are withheld. It never makes a rubric or remedy from outside the PDF.


For visual proofing, also copy your original PDF into the local app data folder:

```bash
cp "$HOME/storage/shared/Download/J.T. Kent s Repertory.pdf" public/data/kent/source.pdf
```

The source reader and grade-candidate review cards then provide an **Open original PDF page** link for the exact source page. The file is local-only and is not committed to GitHub.
