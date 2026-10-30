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

function isSourcePageList(value: unknown): value is number[] {
  return Array.isArray(value) &&
    value.length > 0 &&
    value.every((page) => Number.isInteger(page) && (page as number) >= 1 && (page as number) <= 2834);
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
    !isObject(payload.data_policy) ||
    payload.data_policy.external_data_used !== false ||
    payload.data_policy.generated_rubrics !== 0 ||
    payload.data_policy.generated_remedies !== 0 ||
    payload.data_policy.automatic_grade_verification !== false ||
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
      typeof remedy.full_name_as_printed_in_pdf_index !== "string" ||
      !remedy.full_name_as_printed_in_pdf_index.trim()
    ) throw new Error("A remedy record does not match the source abbreviation index.");
    if (remedies.has(remedy.id)) throw new Error("The verified Kent database contains duplicate remedy IDs.");
    remedies.set(remedy.id, remedy.full_name_as_printed_in_pdf_index);
  }

  const rubricById = new Map<string, Record<string, unknown>>();
  let gradeCount = 0;
  for (const rubric of payload.rubrics) {
    if (
      !isObject(rubric) ||
      typeof rubric.id !== "string" ||
      typeof rubric.chapter_id !== "string" ||
      typeof rubric.text_as_entered_from_pdf !== "string" ||
      !rubric.text_as_entered_from_pdf.trim() ||
      !Array.isArray(rubric.path_as_entered_from_pdf) ||
      rubric.path_as_entered_from_pdf.length < 1 ||
      rubric.path_as_entered_from_pdf.some((part) => typeof part !== "string" || !part.trim()) ||
      !Number.isInteger(rubric.depth) ||
      rubric.depth !== (rubric.path_as_entered_from_pdf.length as number) - 1 ||
      rubric.text_as_entered_from_pdf !== rubric.path_as_entered_from_pdf[rubric.depth as number] ||
      !isSourcePageList(rubric.source_pdf_pages) ||
      !Array.isArray(rubric.grades) ||
      (rubric.parent_rubric_id !== null && typeof rubric.parent_rubric_id !== "string") ||
      !["user_verified_source_checked", "path_derived_from_verified_child_review"].includes(String(rubric.verification_status))
    ) throw new Error("A rubric record is incomplete or its hierarchy fields are malformed.");
    if (rubricById.has(rubric.id)) throw new Error("The verified Kent database contains duplicate rubric IDs.");
    rubricById.set(rubric.id, rubric);

    const gradeRemedies = new Set<string>();
    for (const grade of rubric.grades) {
      if (
        !isObject(grade) ||
        typeof grade.remedy_id !== "string" ||
        !remedies.has(grade.remedy_id) ||
        ![1, 2, 3].includes(grade.grade as number) ||
        !isSourcePageList(grade.source_pdf_pages) ||
        !Array.isArray(grade.source_candidate_ids) ||
        !grade.source_candidate_ids.length ||
        grade.source_candidate_ids.some((id) => typeof id !== "string" || !id) ||
        grade.verification_status !== "user_verified_source_checked"
      ) throw new Error("A rubric/remedy grade is missing source validation or verification.");
      if (gradeRemedies.has(grade.remedy_id)) throw new Error("A rubric has duplicate grade rows for one remedy.");
      gradeRemedies.add(grade.remedy_id);
      gradeCount += 1;
    }
  }

  for (const rubric of rubricById.values()) {
    const parentId = rubric.parent_rubric_id;
    if (rubric.depth === 0) {
      if (parentId !== null) throw new Error("A root rubric cannot have a parent.");
      continue;
    }
    if (typeof parentId !== "string") throw new Error("A child rubric is missing its parent ID.");
    const parent = rubricById.get(parentId);
    if (!parent) throw new Error("A rubric refers to a missing parent rubric.");
    if (parent.chapter_id !== rubric.chapter_id || parent.depth !== (rubric.depth as number) - 1) {
      throw new Error("A rubric parent belongs to the wrong chapter or hierarchy depth.");
    }
    const childPath = rubric.path_as_entered_from_pdf as string[];
    const parentPath = parent.path_as_entered_from_pdf as string[];
    if (parentPath.length !== childPath.length - 1 || !parentPath.every((part, index) => part === childPath[index])) {
      throw new Error("A rubric path is inconsistent with its parent.");
    }
  }

  if (payload.verified_grade_pair_count !== gradeCount) {
    throw new Error("Verified grade-pair count does not match the database contents.");
  }
  return payload as unknown as VerifiedKentDatabase;
}
