# Curiva HomoeoRepertory Pro

A standalone repertory and case-analysis workspace. This repository is intentionally separate from the **Curiva Homoeopathy** website.

## Interface direction

The repertorization workspace follows the workflow in the reference screenshot: case header and actions, A/B/C/D case tabs, selected rubrics at the left, and a horizontally scrollable remedy-by-rubric grade matrix with coloured grade markers.

The visual identity, icons, data, and code are original to Curiva. The reference is used only as a workflow/layout guide.

## Current prototype scope

- Responsive React + TypeScript + Vite application.
- Home, Repertory, Materia Medica, Cases, and Shop navigation.
- Interactive repertorization matrix with selectable rubrics, A/B/C/D case sets, undo/redo, grade visibility, sorting, elimination filter, author filter, and CSV export.
- Demo records are clearly labelled as sample data. They are **not** a verified Kent database and must not be used for patient decisions.
- Installable PWA shell for Android Chrome and desktop browsers.

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

Do not invent remedy grades or infer them from OCR formatting. Before real repertorization data is introduced, each rubric/remedy/grade entry must have a reliable source reference and verification status. The eventual engine should display its scoring method and the exact rubric evidence behind every result.

This is an educational study tool, not a diagnostic or prescribing system. Do not enter identifiable patient information into this prototype. No patient-account or cloud-sync system is included at this stage.

## Project boundary

This is the standalone **Curiva HomoeoRepertory Pro** repository. The existing **Curiva Homoeopathy** website remains in its own repository and is not imported, modified, or deployed by this project.
