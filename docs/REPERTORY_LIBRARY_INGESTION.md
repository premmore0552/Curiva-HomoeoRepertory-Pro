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

## Next implementation stages

1. Add a source registry with rights and provenance checks.
2. Build a deterministic import/validation pipeline for structured CSV/JSON.
3. Add review tooling for OCR-to-rubric correction.
4. Build chapter and rubric browsing against verified records.
5. Connect verified grades to the repertorization matrix.
6. Add pagination, virtualized rows, debounced search and mobile-friendly layouts as dataset size grows.

## Minimum validation before publishing a data batch

- Unique stable IDs
- Existing source, chapter, rubric and remedy references
- Valid grade range declared by the source format
- Positive page references within source pagination
- No silently merged remedy abbreviations
- Duplicate detection report
- Source license and attribution present
- Verification state explicitly set
