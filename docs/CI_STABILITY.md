# CI stability and maintenance

The repository uses a single GitHub Actions workflow at `.github/workflows/build.yml`.

## Why the previous checks appeared to fail repeatedly

The earlier development PR was updated through a series of separate file commits. GitHub starts a new pull-request workflow after each branch update. Several of those runs therefore tested intermediate commits while related TypeScript, parser, test and workflow files were still being updated. The completed, internally consistent commit passed.

There were also genuine intermediate defects that the checks correctly exposed:
- a Python pip cache was configured even though the import scripts use only the standard library and the repository has no pip requirements file;
- a candidate-parser test used a field name that did not match the parser output;
- the new review UI had a mismatched abbreviation property and used `String.replaceAll`, which is outside the project's ES2020 target.

These are corrected in the current main branch.

## Current safeguards

- A committed `package-lock.json` pins the complete npm dependency graph.
- CI uses `npm ci`; it does not resolve a new dependency tree on each run.
- The runner and runtimes are pinned to Ubuntu 24.04, Python 3.12.15 and Node 22.23.4.
- Third-party GitHub Actions are pinned to immutable commit SHAs, with release tags documented in comments.
- The concurrency group cancels older runs for the same pull request or branch when a new commit arrives. The latest commit is the one that should be used for the final status.
- The job has a 20-minute timeout.
- Python syntax checks, Python regression tests, TypeScript checking and the production build run in the same job.

## Contributor rules

1. When adding or updating an npm dependency, update `package.json` and `package-lock.json` together and commit both.
2. Do not replace `npm ci` in CI with `npm install`.
3. Do not add pip caching unless a Python requirements or project dependency file is introduced and the cache path is configured.
4. Keep data extracted from the copyrighted source PDF out of the public repository unless redistribution permission is confirmed.
5. Prefer a single logical commit containing mutually dependent file changes. Superseded in-progress checks are cancelled automatically, but completed historical runs remain visible in GitHub.
6. When a check fails, inspect the first failing step and its log; do not treat a rerun as a code fix.

## Current verified status

The latest main-branch workflow after the CI repair passed:
- Python importer syntax validation
- all Python regression tests
- locked npm install
- TypeScript checking
- Vite production build
