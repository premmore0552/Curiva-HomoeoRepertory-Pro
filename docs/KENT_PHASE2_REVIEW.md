# Phase 2 — verify the Kent abbreviation index and repertory candidates

This workflow builds an auditable local database from the supplied J.T. Kent PDF. It does not add data from another repertory or website. It does not automatically approve a rubric, hierarchy, remedy abbreviation or grade.

The original PDF, its extracted text/layout chunks, candidate records and final database are local development data. Keep them outside Git commits and public static deployments. The app's existing `.gitignore` rule for `public/data/kent/` is intentional.

## What the extracted package contains

- 650 abbreviation-table transcriptions from PDF pages 10–18. They still need human proofreading.
- 433,541 remedy-token candidate occurrences across all 2,768 repertory pages and 34 repertory chapters.
- A source page, source layout span and typography evidence for each candidate.
- Candidate grade evidence is only a suggestion from the printed key on PDF page 36. The candidate remains unverified until a person opens the original PDF page and checks it.
- 64 candidate occurrences have unclear or conflicting typography evidence and are not assigned a grade by the parser.
- Candidate duplicate flags are possible matches for review only. Do not delete/merge without checking the PDF.

The suggested rubric context is only a navigation aid. It is not an approved rubric path.

## 1. Install the local source package

Run these commands from the application repository root in Termux after Phase 1 extraction has completed:

~~~bash
mkdir -p public/data/kent/structured
cp "$HOME/Curiva/kent-source-chunks/section-index.json" public/data/kent/section-index.json
cp -R "$HOME/Curiva/kent-source-chunks/chunks" public/data/kent/
cp "$HOME/storage/shared/Download/J.T. Kent s Repertory.pdf" public/data/kent/source.pdf
cp "$HOME/Curiva/kent-source-chunks/structured/remedy-abbreviations.json" public/data/kent/structured/remedy-abbreviations.json
cp "$HOME/Curiva/kent-source-chunks/structured/grade-candidates-index.json" public/data/kent/structured/grade-candidates-index.json
cp -R "$HOME/Curiva/kent-source-chunks/structured/grade-candidates" public/data/kent/structured/
~~~

The source PDF must be saved as `public/data/kent/source.pdf` locally so the source-page links work. The app data directory is ignored by Git; do not force-add it.

## 2. Proofread the 650 remedy abbreviations

Open the app's **Materia Medica → Proofread the 650 source abbreviation entries** section.

For each entry, open the linked original PDF page and compare both the abbreviation and its full name against the printed source. Choose one decision:

- **Verify exact entry** only when both fields match the PDF.
- **Mark uncertain** when the printed evidence is not clear.
- **Reject transcription** when the parsed entry is not a valid transcription.

You can correct the two fields, but preserve the original spelling and punctuation exactly as printed. The export is a review decision file; it does not change the source PDF or approve entries that were not checked.

Use **Export decisions** to save `curiva-kent-abbreviation-review-decisions.json`.

## 3. Build the proofread abbreviation index

In Termux, run from the repository root:

~~~bash
python scripts/build-verified-kent-abbreviation-index.py \
  --source-index "$HOME/Curiva/kent-source-chunks/structured/remedy-abbreviations.json" \
  --reviews "$HOME/storage/shared/Download/curiva-kent-abbreviation-review-decisions.json" \
  --out "$HOME/Curiva/kent-source-chunks/structured/verified-remedy-abbreviations.json"
~~~

The output includes only entries marked **verified** after an original-page check. Uncertain, rejected and pending entries remain in its QC report, not in the verified abbreviation list. The original parser transcription is retained inside every verified record for audit.

The index may be partial while you work through the table. It must not contain duplicate abbreviations (case-insensitive) or empty full names. To require all source abbreviations to be reviewed before writing a complete index, add `--require-complete`.

## 4. Regenerate candidates against the exact proofread abbreviation index

Candidate chunks must be regenerated using the proofread index. This ensures that candidates can only refer to remedy abbreviations which have been source-checked.

~~~bash
python scripts/parse-kent-grade-candidates.py \
  --source "$HOME/Curiva/kent-source-chunks" \
  --abbreviations "$HOME/Curiva/kent-source-chunks/structured/verified-remedy-abbreviations.json" \
  --require-verified-abbreviations
~~~

This creates a new `grade-candidates-index.json` and candidate JSONL chunks. The index records the exact SHA-256 of the proofread abbreviation index. If you later change that index, regenerate the candidate chunks again.

## 5. Audit candidate IDs, grades and possible duplicates

~~~bash
python scripts/audit-kent-candidate-data.py \
  --source "$HOME/Curiva/kent-source-chunks" \
  --abbreviations "$HOME/Curiva/kent-source-chunks/structured/verified-remedy-abbreviations.json"
~~~

The audit checks unique candidate IDs, abbreviation membership, grade/style evidence mapping, chunk counts, source fingerprint and unverified candidate status. It writes:

- `candidate-data-audit.json` — counts and validation summary;
- `candidate-audit-errors.json` — any source/data integrity failures;
- `possible-duplicate-candidates.csv` and `.json` — occurrences that appear repeated on the same source line/page.

Possible duplicates are not automatically deleted. Check both records on the original PDF page before marking one duplicate in the review UI.

## 6. Install the regenerated review dataset into the app

Copy the proofread abbreviation list and the regenerated candidate index/chunks into the ignored local app data directory:

~~~bash
cp "$HOME/Curiva/kent-source-chunks/structured/verified-remedy-abbreviations.json" public/data/kent/structured/verified-remedy-abbreviations.json
cp "$HOME/Curiva/kent-source-chunks/structured/grade-candidates-index.json" public/data/kent/structured/grade-candidates-index.json
rm -rf public/data/kent/structured/grade-candidates
cp -R "$HOME/Curiva/kent-source-chunks/structured/grade-candidates" public/data/kent/structured/
~~~

Keep the original `remedy-abbreviations.json` file too: it is the unproofread source transcription used by the abbreviation review screen.

Open **Repertory → Kent source browser → Grade candidates**. Each candidate has a source PDF page link. Enter the complete hierarchy from chapter to rubric and child rubric, separated by `/`, for example:

~~~text
MIND / exact parent rubric / exact child rubric
~~~

This is only a format example, not a Kent rubric assertion. Enter the actual path you see in the PDF. The candidate's suggested context is not automatically accepted.

Choose the confirmed grade only after checking the printed style on the original page. The tool requires a review note when you override the parser's suggested grade. Mark a record uncertain or rejected when the source evidence does not support verification. Mark a duplicate only when you have compared it with the target candidate and confirmed they represent the same occurrence.

Candidate reviews are saved in IndexedDB on the device. Use **Export reviews** regularly to create `curiva-kent-verified-review-decisions.json`. Keep a backup of that file.

## 7. Build the verified rubric/remedy database

~~~bash
python scripts/build-verified-kent-database.py \
  --reviews "$HOME/storage/shared/Download/curiva-kent-verified-review-decisions.json" \
  --abbreviations "$HOME/Curiva/kent-source-chunks/structured/verified-remedy-abbreviations.json" \
  --candidate-index "$HOME/Curiva/kent-source-chunks/structured/grade-candidates-index.json" \
  --out "$HOME/Curiva/kent-source-chunks/structured/verified-rubric-remedy-grades.json"
~~~

The builder checks that:

- every reviewed candidate ID exists exactly in the current candidate chunks;
- the candidate index refers to the same PDF and the exact proofread abbreviation index;
- the review page and remedy abbreviation match the original candidate;
- a verified decision has a complete reviewer-entered rubric path, grade 1–3 and a source-page check;
- a grade override includes an explanatory review note;
- only verified abbreviation entries can be included;
- rejected, uncertain and duplicate decisions are excluded;
- different grades for the same exact rubric/remedy pair are withheld as conflicts;
- parent/child nodes are built only from the exact path entered by the reviewer.

It writes the database and a matching `*-qc.json` report. No unreviewed candidate is automatically promoted into the active repertory.

## 8. Install the verified database for local use

~~~bash
cp "$HOME/Curiva/kent-source-chunks/structured/verified-rubric-remedy-grades.json" public/data/kent/structured/verified-rubric-remedy-grades.json
~~~

Refresh the app. Only verified records with a source-checked grade are eligible for the repertorization matrix. Parent hierarchy is shown as a full path; empty parent nodes are not added as empty matrix rows.

## Review limits and accuracy

- The candidate total is not the count of verified repertory entries.
- A review checkbox records that the reviewer says they checked the PDF. The software cannot independently prove a human looked at the page.
- The parser's typography classification does not replace source-page checking.
- A source page can contain multiple rubrics or transition text. Use the printed hierarchy, not a guessed parent.
- Possible duplicate flags are not deletion instructions.
- A partial abbreviation index or partial repertory database is allowed for development, but the app must be described as incomplete until review is complete.
