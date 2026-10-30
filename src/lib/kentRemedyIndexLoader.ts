import type { KentRemedyAbbreviationDataset, KentRemedyAbbreviationRecord } from "../data/kent-remedy-index";

export class KentSourceDataNotInstalledError extends Error {
  constructor() {
    super("Kent remedy abbreviation data is not installed in public/data/kent yet.");
    this.name = "KentSourceDataNotInstalledError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validateEntry(value: unknown): value is KentRemedyAbbreviationRecord {
  if (!isRecord(value)) return false;
  return (
    typeof value.id === "string" &&
    typeof value.abbreviation_as_printed === "string" &&
    typeof value.full_name_as_printed === "string" &&
    typeof value.source_pdf_page === "number" &&
    value.source_pdf_page >= 10 &&
    value.source_pdf_page <= 18 &&
    Array.isArray(value.source_pdf_pages) &&
    (value.source_column === "left" || value.source_column === "right") &&
    isRecord(value.source_position) &&
    typeof value.source_position.top === "number" &&
    typeof value.source_position.left === "number" &&
    typeof value.source_line_as_printed === "string" &&
    Array.isArray(value.continuation_lines) &&
    typeof value.verification_status === "string"
  );
}

export async function loadKentRemedyAbbreviationIndex(
  signal?: AbortSignal,
): Promise<KentRemedyAbbreviationDataset> {
  let response: Response;
  try {
    response = await fetch("/data/kent/remedy-abbreviations.json", {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new Error("Could not read the local Kent remedy index file.");
  }

  if (response.status === 404) throw new KentSourceDataNotInstalledError();
  if (!response.ok) {
    throw new Error("Kent remedy index request failed with HTTP " + response.status + ".");
  }

  const payload: unknown = await response.json();
  if (!isRecord(payload) || payload.dataset_id !== "kent-pdf-remedy-abbreviation-index") {
    throw new Error("The local file is not a recognised Kent PDF abbreviation dataset.");
  }

  if (
    !isRecord(payload.source) ||
    payload.source.pdf_page_start !== 10 ||
    payload.source.pdf_page_end !== 18 ||
    !Array.isArray(payload.records) ||
    payload.record_count !== payload.records.length ||
    !payload.records.every(validateEntry)
  ) {
    throw new Error("The Kent abbreviation dataset failed its structure or page-range checks.");
  }

  const abbreviations = payload.records.map((record) => record.abbreviation_as_printed);
  if (new Set(abbreviations).size !== abbreviations.length) {
    throw new Error("The Kent abbreviation dataset contains duplicate printed abbreviations. Review the source import.");
  }

  return payload as unknown as KentRemedyAbbreviationDataset;
}
