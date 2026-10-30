# Curiva HomoeoRepertory Pro

A standalone repertory and case-analysis workspace. This repository is intentionally separate from the **Curiva Homoeopathy** website.

## Interface direction

The repertorization workspace follows the workflow in the supplied reference screenshot: case header and actions, A/B/C/D case tabs, selected rubrics at the left, and a horizontally scrollable remedy-by-rubric grade matrix with coloured grade markers.

The visual identity, icons, data and code are original to Curiva. The reference is used only as a workflow/layout guide.

## Current prototype scope

- Responsive React + TypeScript + Vite application.
- Home, Repertory, Materia Medica, Cases and Shop navigation.
- Repertorization workspace shell with A/B/C/D case tabs, undo/redo controls, grade visibility, sorting/filter controls and CSV export. Rubric selection and remedy comparison remain inactive until verified source records are installed.
- No demo rubrics, remedy-grade relationships or fabricated remedies are bundled. The repertorization matrix remains empty until source-derived records are imported and reviewed.
- The supplied Kent PDF has a local-only extraction workflow with page-aligned source chunks, layout/style retention, a section index, a checksum manifest and a package validator.
- The existing local extraction audit contains a 650-entry abbreviation index and 433,541 source-matched remedy-token review candidates. These are not verified repertory entries and the book-derived data is not shipped in this public repository.
- Phase 2 adds a source-page proofreading queue for remedy abbreviations, IndexedDB-backed candidate review, explicit verified/rejected/uncertain/duplicate dispositions, exact rubric-path entry, candidate-ID/source-page checks, grade-conflict quarantine and a parent-child database builder. The full process is documented in [Kent Phase 2 review](docs/KENT_PHASE2_REVIEW.md).
- The candidate count (433,541) is a machine-extracted review queue, not a verified-record count. The app does not treat suggested rubric context or typography as a final human verification.
- Case rubric selections are stored locally in the current browser profile. No cloud sync or patient account is included.
- Installable PWA shell for Android Chrome and desktop browsers. Source chunks are generated locally and are not bundled into the public repository.

## Run locally

Requires Node.js 20 or later.

~~~bash
npm install
npm run dev -- --host 0.0.0.0
~~~

Open the local URL printed by Vite. On Android, use Chrome's **Add to Home screen** when the app is served over HTTPS.

Build:

~~~bash
npm run build
npm run preview -- --host 0.0.0.0
~~~

## Kent source-data workflow

See:
- [PDF extraction and validation](docs/KENT_PDF_IMPORT.md)
- [Source PDF rights and data handling](docs/SOURCE_DATA_RIGHTS.md)
- [Repertory library ingestion rules](docs/REPERTORY_LIBRARY_INGESTION.md)

The public repository must contain code and documentation, not the supplied PDF or its extracted book contents, until redistribution rights are confirmed. The .gitignore rule for public/data/kent/ is intentional.

## Data and clinical-use policy

Do not invent remedy grades or infer them from OCR/layout formatting. Every active rubric/remedy/grade entry must have a source page and a manually checked verification record. The matrix loads only a verified JSON dataset built from review exports; conflicting grades are withheld. The source matching/parser stage does not diagnose or prescribe and the app does not invent missing rubric or remedy data.

This is an educational study tool, not a diagnostic or prescribing system. Do not enter identifiable patient information into this prototype. No patient-account or cloud-sync system is included at this stage.

## Project boundary

This is the standalone **Curiva HomoeoRepertory Pro** repository. The existing **Curiva Homoeopathy** website remains in its own repository and is not imported, modified or deployed by this project.
