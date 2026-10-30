# Repertory Library — ingestion plan

This repository is the standalone Curiva HomoeoRepertory Pro application. It is not the Curiva Homoeopathy website.

## Non-negotiable data rules

1. Never fabricate a rubric, remedy relationship, or repertory grade.
2. Keep the original source, edition, volume, page reference, attribution, and license status with imported material.
3. OCR output is searchable source text, not verified repertory structure.
4. Every rubric and every rubric–remedy grade has its own verification status.
5. Do not infer Kent grades from OCR layout, typography, or proximity.
6. Keep source text, normalized search text, and verified structured records separate.
7. Preserve historical spellings and abbreviations in source fields while also storing canonical remedy names.
8. Flag uncertain duplicates and abbreviations for review instead of silently merging them.

## Canonical data model

The TypeScript contracts live in `src/data/library-schema.ts`:

- Source → edition / volume metadata and license status
- Chapter → ordered hierarchy within a source
- Rubric → chapter, parent rubric, source page references, verification state
- Remedy → canonical name plus source abbreviations and spellings
- RubricRemedyGrade → explicit grade, source, page and verification state
- Import batch → reproducible audit record

## Import lifecycle

`received → license_checked → parsed → normalized → deduplicated → reviewed → verified → published`

Records that fail validation or have uncertain provenance remain quarantined. A batch must report accepted, rejected and flagged counts.

## Active source: the user's uploaded PDF

The current source is the file supplied in this conversation, **J.T. Kent s Repertory.pdf**. The importer checks for 2,834 physical PDF pages and preserves the PDF's embedded selectable text and page layout. The internal repertory page numbers are a separate numbering system.

- The uploaded file itself displays a 1998 MEDI-T copyright notice.
- Its precise edition, publication history, and redistribution permission are not established by the PDF alone.
- Do not substitute OCR or curated data from the separate Curiva Homoeopathy website project.
- The importer creates a local staging package; the package is not committed to this public repository.
- The supplied PDF's own page 36 states the grade key: capitals = 3, italics = 2, ordinary = 1. Keep this as source evidence, not an excuse to assign grades to text that has not been identified as a rubric remedy.

## Implemented in the current app branch

1. Canonical schemas for sources, chapters, rubrics, remedies and grade links.
2. PDF page extraction, page-layout retention, chapter chunking, source hash and page coverage checks.
3. PDF-derived chapter directory and searchable remedy abbreviation index.
4. Lazy source-page browser with a direct link to the original PDF page.
5. Source-matched remedy-token/grade candidates, per-chapter chunk files, typography evidence, suggested rubric context and QC reports.
6. Candidate review UI: manual rubric path, grade selection, source-page confirmation, local review storage and JSON export.
7. Verified-database builder that checks the uploaded PDF fingerprint, abbreviation membership, grade range, source check and conflicting pairs.
8. App loader and repertorization matrix connection for manually reviewed records.
9. Regression tests for chapter coverage, chunk sizing, abbreviation continuations, source style grading and conflict handling.

## Remaining human validation before the repertory can be called complete

- Review each candidate against the original PDF page.
- Confirm or correct the suggested rubric parent/child path and exact wording.
- Confirm grade 1, 2 or 3 from the printed type style; leave uncertain cases ungraded.
- Resolve the possible line-wrap warnings and any duplicate or conflicting rubric/remedy pairs.
- Export reviewed decisions and build the active database; only those checked records become matrix data.
- Test the installed local dataset on the Android device with large chunks and a full browser refresh.

These are intentionally not automated to completion: assigning rubric parents or confirming typography without checking the source page could create incorrect repertory records.

## Minimum validation before publishing a data batch

- Unique stable IDs
- Existing source, chapter, rubric and remedy references
- Valid grade range declared by the source format
- Positive page references within source pagination
- No silently merged remedy abbreviations
- Duplicate detection report
- Source license and attribution present
- Verification state explicitly set
