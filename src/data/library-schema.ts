/**
 * Curiva HomoeoRepertory Pro — canonical repertory library types.
 *
 * Important: repertory grades are source facts, not inferred values.
 * OCR text must never be converted into remedy-grade relationships automatically.
 */

export type VerificationStatus =
  | "unreviewed"
  | "ocr_imported"
  | "needs_review"
  | "verified"
  | "rejected";

export type SourceLicenseStatus =
  | "public_domain"
  | "open_license"
  | "permission_required"
  | "unknown";

export interface RepertorySource {
  id: string;
  title: string;
  author?: string;
  edition?: string;
  volume?: string;
  publicationYear?: number;
  sourceUrl?: string;
  attribution?: string;
  licenseStatus: SourceLicenseStatus;
  notes?: string;
}

export interface RepertoryChapter {
  id: string;
  sourceId: string;
  title: string;
  order: number;
  parentId?: string;
}

export interface Rubric {
  id: string;
  sourceId: string;
  chapterId: string;
  parentRubricId?: string;
  text: string;
  normalizedText?: string;
  pageReferences: number[];
  verification: VerificationStatus;
}

export interface Remedy {
  id: string;
  canonicalName: string;
  displayName: string;
  abbreviations: string[];
  sourceNames: string[];
}

export interface RubricRemedyGrade {
  id: string;
  rubricId: string;
  remedyId: string;
  grade: number;
  sourceId: string;
  pageReference: number;
  verification: VerificationStatus;
  verifiedBy?: string;
  verificationNote?: string;
}

export interface LibraryImportBatch {
  id: string;
  sourceId: string;
  importedAt: string;
  inputFileName: string;
  recordsRead: number;
  recordsAccepted: number;
  recordsFlagged: number;
  checksum?: string;
}

/** Search index entries retain stable IDs so UI search never becomes source data. */
export interface LibrarySearchEntry {
  id: string;
  kind: "chapter" | "rubric" | "remedy";
  label: string;
  normalizedLabel: string;
  parentLabel?: string;
}
