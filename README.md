# Curiva HomoeoRepertory Pro

A standalone repertory and case-analysis workspace. This repository is intentionally separate from the **Curiva Homoeopathy** website.

## Interface direction

The repertorization workspace follows the workflow in the reference screenshot: case header and actions, A/B/C/D case tabs, selected rubrics at the left, and a horizontally scrollable remedy-by-rubric grade matrix with coloured grade markers.

The visual identity, icons, data, and code are original to Curiva. The reference is used only as a workflow/layout guide.

## Current prototype scope

- Responsive React + TypeScript + Vite application.
- Home, Repertory, Materia Medica, Cases, and Shop navigation.
- Repertorization workspace shell with A/B/C/D case tabs, undo/redo controls, grade visibility, sorting/filter controls, and CSV export. Rubric selection and remedy comparison remain inactive until verified source records are installed.
- No demo rubrics, remedy-grade relationships, or fabricated remedies are bundled. The repertorization matrix remains empty until source-derived records are imported and reviewed.
- The Kent chapter directory is source-indexed. The local data package adds the searchable 650-entry abbreviation index, page-by-page source reader and 433,541 source-matched remedy-token review candidates. The complete book-derived data is not shipped in this public repository.
- Candidate review lets a user confirm the exact rubric and grade against the original PDF. Only manually checked review decisions can be converted into the active repertory matrix; no candidate is silently treated as verified.
- Case rubric selections are stored locally in the current browser profile. No cloud sync or patient account is included.
- Installable PWA shell for Android Chrome and desktop browsers. Source chunks are generated locally and are not bundled into the public repository.

## Run locally

Requires Node.js 20 or later.

```bash
npm install
npm run dev -- --host 0.0.0.0
```

Open the local URL printed by Vite. On Android, use Chrome's **Add to Home screen** when the app is served over HTTPS.

Build:

```bash
npm run build
npm run preview -- --host 0.0.0.0
```

## Data and clinical-use policy

Do not invent remedy grades or infer them from OCR formatting. Every active rubric/remedy/grade entry must have a source page and a manually checked verification record. The matrix loads only a verified JSON dataset built from review exports; conflicting grades are withheld. The source matching/parser stage does not diagnose or prescribe, and the app does not invent missing rubric or remedy data.

This is an educational study tool, not a diagnostic or prescribing system. Do not enter identifiable patient information into this prototype. No patient-account or cloud-sync system is included at this stage.

## Project boundary

This is the standalone **Curiva HomoeoRepertory Pro** repository. The existing **Curiva Homoeopathy** website remains in its own repository and is not imported, modified, or deployed by this project.
