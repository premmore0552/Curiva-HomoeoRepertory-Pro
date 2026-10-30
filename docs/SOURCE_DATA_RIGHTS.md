# Source PDF rights and data handling

## Current source finding

The local source file used by this project is **J.T. Kent s Repertory.pdf** (2,834 PDF pages). The supplied PDF visibly prints **Copyright © 1998 MEDI-T** on PDF page 7. Its PDF metadata identifies the title as “Kent's rpertory of the Materia Medica” and the PDF author field as “Ko. Paandu - VENN OLI”.

Those file facts do not establish who currently owns the compilation rights, whether permission has been granted, or whether the file may be redistributed. The exact rights status is therefore **unknown from the file alone**. This project must not treat the underlying historical authorship of Kent's work as automatic permission to redistribute this particular modern compilation or its extracted layout/text.

## Current release decision

- Keep the original PDF, extracted page text, layout spans, abbreviation index, candidate records and derived database in local-only folders.
- Do not commit those files to this public GitHub repository.
- Do not put the source PDF or extracted book contents into a public app deployment, CDN, public download, public archive or public static-data folder.
- Keeping a repository private does not itself establish permission.
- Do not remove the copyright notice or imply that Curiva owns the source text.
- Do not publish candidate records merely because they are machine-extracted; derived data may still reproduce protected contents.

The .gitignore entry for public/data/kent/ is intentional. Do not remove it as a convenience workaround.

## Permission checklist

Before distributing the PDF or any substantial extracted/derived source dataset, obtain reliable evidence that the relevant rights holder permits the intended use. Check that the permission covers the actual use, including as applicable:

1. storing and processing a local copy;
2. displaying page text and layout in an application;
3. redistributing searchable text, abbreviations, rubrics, remedy/grade relationships or other derived datasets;
4. hosting data in a publicly accessible web app or static deployment;
5. allowing users to download, cache or use the dataset offline;
6. modifying, indexing or transforming the source material.

Record the rights holder, the permission or license reference, the date confirmed, any attribution requirement, and the permitted scope. When ownership or scope is uncertain, ask a qualified copyright professional rather than guessing.

## Recording confirmed permission

Only after obtaining reliable permission, update the rights_and_provenance object in the local source-metadata.json. The publication validator expects all of these fields:

- redistribution_status: permission_confirmed, public_domain_confirmed, or licensed_for_redistribution;
- rights_holder: the verified person or entity that can grant the relevant rights;
- evidence_reference: a stable reference to the written permission or authoritative license evidence;
- confirmed_on: date in YYYY-MM-DD format.

Then rebuild the package manifest and run the publication check:

~~~bash
python scripts/validate-kent-source-package.py "$HOME/Curiva/kent-source-chunks" --write-manifest --zip "$HOME/Curiva/Kent_Repertory_Source_Chunks.zip"
python scripts/validate-kent-source-package.py "$HOME/Curiva/Kent_Repertory_Source_Chunks.zip" --pdf "$HOME/storage/shared/Download/J.T. Kent s Repertory.pdf" --for-publication
~~~

The validator checks that the required permission fields have been recorded; it does not decide legal ownership or verify the truth of a permission document. A successful technical check is not legal advice.

## Safe default until then

Use the source package privately for development and review. Keep the public repository limited to application code, extraction/validation tools, schemas, tests and documentation that do not reproduce the source book's protected contents. The active repertory database must remain unavailable in a public release until the redistribution status is resolved.
