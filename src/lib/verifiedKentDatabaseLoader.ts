import type { VerifiedKentDatabase } from "../data/verified-kent-database";

export const KENT_SOURCE_SHA256 = "8f7ef6e5029dfb0bf9a05800f63e5e05043d39c74d5dd0df500a27484aecec6e";

export class VerifiedKentDatabaseNotInstalledError extends Error {
  constructor() {
    super("No locally built verified Kent database is installed yet.");
    this.name = "VerifiedKentDatabaseNotInstalledError";
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export async function loadVerifiedKentDatabase(signal?: AbortSignal): Promise<VerifiedKentDatabase> {
  let response: Response;
  try {
    response = await fetch("/data/kent/structured/verified-rubric-remedy-grades.json", {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new Error("Could not read the local verified Kent database.");
  }
  if (response.status === 404) throw new VerifiedKentDatabaseNotInstalledError();
  if (!response.ok) throw new Error("Verified Kent database request failed with HTTP " + response.status + ".");

  const payload: unknown = await response.json();
  if (!isObject(payload) || payload.dataset_id !== "curiva-kent-verified-rubric-remedy-grades") {
    throw new Error("The local repertory data file is not a recognised verified Kent database.");
  }
  if (
    !isObject(payload.source) ||
    payload.source.source_file_sha256 !== KENT_SOURCE_SHA256 ||
    payload.source.grade_key_pdf_page !== 36 ||
    !isObject(payload.source.grade_key) ||
    payload.source.grade_key.ordinary !== 1 ||
    payload.source.grade_key.italics !== 2 ||
    payload.source.grade_key.capitals !== 3 ||
    !Array.isArray(payload.rubrics) ||
    !Array.isArray(payload.remedies) ||
    payload.rubric_count !== payload.rubrics.length ||
    payload.remedy_count !== payload.remedies.length
  ) {
    throw new Error("The verified Kent database failed its source fingerprint or structure checks.");
  }

  const remedies = new Map<string, string>();
  for (const remedy of payload.remedies) {
    if (
      !isObject(remedy) ||
      typeof remedy.id !== "string" ||
      typeof remedy.abbreviation_as_printed !== "string" ||
      remedy.id !== remedy.abbreviation_as_printed ||
      typeof remedy.full_name_as_printed_in_pdf_index !== "string"
    ) throw new Error("A remedy record does not match the source abbreviation index.");
    if (remedies.has(remedy.id)) throw new Error("The verified Kent database contains duplicate remedy IDs.");
    remedies.set(remedy.id, remedy.full_name_as_printed_in_pdf_index);
  }

  const rubricIds = new Set<string>();
  let gradeCount = 0;
  for (const rubric of payload.rubrics) {
    if (
      !isObject(rubric) ||
      typeof rubric.id !== "string" ||
      typeof rubric.text_as_entered_from_pdf !== "string" ||
      !rubric.text_as_entered_from_pdf.trim() ||
      !Array.isArray(rubric.grades)
    ) throw new Error("A rubric record is incomplete or malformed.");
    if (rubricIds.has(rubric.id)) throw new Error("The verified Kent database contains duplicate rubric IDs.");
    rubricIds.add(rubric.id);
    const gradeRemedies = new Set<string>();
    for (const grade of rubric.grades) {
      if (
        !isObject(grade) ||
        typeof grade.remedy_id !== "string" ||
        !remedies.has(grade.remedy_id) ||
        ![1, 2, 3].includes(grade.grade as number) ||
        !Array.isArray(grade.source_pdf_pages) ||
        !grade.source_pdf_pages.every((page) => Number.isInteger(page) && page >= 1 && page <= 2834) ||
        grade.verification_status !== "user_verified_source_checked"
      ) throw new Error("A rubric/remedy grade is missing source validation or verification.");
      if (gradeRemedies.has(grade.remedy_id)) throw new Error("A rubric has duplicate grade rows for one remedy.");
      gradeRemedies.add(grade.remedy_id);
      gradeCount += 1;
    }
  }
  if (payload.verified_grade_pair_count !== gradeCount) {
    throw new Error("Verified grade-pair count does not match the database contents.");
  }
  return payload as unknown as VerifiedKentDatabase;
}
