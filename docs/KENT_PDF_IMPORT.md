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
