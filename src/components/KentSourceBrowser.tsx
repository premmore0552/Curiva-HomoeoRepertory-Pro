import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2, ChevronLeft, ChevronRight, ClipboardCheck, Download,
  FileText, LoaderCircle, Search, X,
} from "lucide-react";

type ChunkMeta = {
  section_id: string;
  part: number;
  pdf_page_start: number;
  pdf_page_end: number;
  page_count: number;
  file: string;
};

type SourceTextItem = {
  text: string;
  top: number;
  left: number;
  width: number;
  height: number;
  font_family: string;
  font_size: string;
  color: string;
  bold: boolean;
  italic: boolean;
};

type SourcePage = {
  pdf_page: number;
  section_id: string;
  section_title: string;
  boundary_page_review: boolean;
  text: string;
  text_items: SourceTextItem[];
  subsection_id?: string;
};

type SectionIndex = { chunks: ChunkMeta[] };

type CandidateChunk = ChunkMeta & { candidate_count: number };

type CandidateRecord = {
  id: string;
  source_pdf_page: number;
  source_section_id: string;
  line_text_as_extracted: string;
  token_as_printed_in_rubric: string;
  matched_abbreviation_as_printed_in_index: string;
  candidate_grade_from_source_key: number | null;
  grade_evidence: string;
  suggested_rubric_context?: string | null;
  suggested_context_method?: string;
  source_span: {
    text: string;
    top: number;
    left: number;
    font_family: string;
    font_size: string;
    color: string;
    bold: boolean;
    italic: boolean;
  };
  rubric_assignment: "unassigned";
  verification_status: "needs_review";
};

type CandidateReview = {
  candidateId: string;
  remedyAbbreviation: string;
  rubricText: string;
  approvedGrade: number;
  sourcePdfPage: number;
  sourceChecked: true;
  savedAt: string;
};

const REVIEW_STORAGE_KEY = "curiva.kent.candidate-reviews.v1";

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseJsonLines<T>(raw: string, validate: (value: unknown) => value is T): T[] {
  const records: T[] = [];
  for (const [index, line] of raw.split(/\r?\n/).entries()) {
    if (!line.trim()) continue;
    let value: unknown;
    try {
      value = JSON.parse(line);
    } catch {
      throw new Error("JSONL contains an invalid record on line " + (index + 1) + ".");
    }
    if (!validate(value)) throw new Error("JSONL record " + (index + 1) + " has an unexpected shape.");
    records.push(value);
  }
  return records;
}

function validateSourcePage(value: unknown): value is SourcePage {
  return isObject(value) &&
    Number.isInteger(value.pdf_page) &&
    typeof value.section_id === "string" &&
    typeof value.section_title === "string" &&
    typeof value.text === "string" &&
    Array.isArray(value.text_items);
}

function validateCandidate(value: unknown): value is CandidateRecord {
  return isObject(value) &&
    typeof value.id === "string" &&
    Number.isInteger(value.source_pdf_page) &&
    typeof value.source_section_id === "string" &&
    typeof value.line_text_as_extracted === "string" &&
    typeof value.token_as_printed_in_rubric === "string" &&
    typeof value.matched_abbreviation_as_printed_in_index === "string" &&
    (value.candidate_grade_from_source_key === null ||
      (Number.isInteger(value.candidate_grade_from_source_key) &&
        [1, 2, 3].includes(value.candidate_grade_from_source_key as number))) &&
    typeof value.grade_evidence === "string" &&
    typeof value.rubric_assignment === "string" &&
    value.rubric_assignment === "unassigned" &&
    value.verification_status === "needs_review";
}

function validateSectionIndex(value: unknown): value is SectionIndex {
  return isObject(value) && Array.isArray(value.chunks) && value.chunks.every((chunk) =>
    isObject(chunk) &&
    typeof chunk.section_id === "string" &&
    Number.isInteger(chunk.part) && (chunk.part as number) > 0 &&
    Number.isInteger(chunk.pdf_page_start) &&
    Number.isInteger(chunk.pdf_page_end) &&
    Number.isInteger(chunk.page_count) &&
    (chunk.page_count as number) === (chunk.pdf_page_end as number) - (chunk.pdf_page_start as number) + 1 &&
    typeof chunk.file === "string" &&
    chunk.file.startsWith("chunks/") &&
    !chunk.file.includes("..") &&
    chunk.file.endsWith(".jsonl")
  );
}

function validateCandidateIndex(value: unknown): value is { dataset_id: string; source_file_sha256: string; chunks: CandidateChunk[] } {
  return isObject(value) &&
    value.dataset_id === "kent-pdf-rubric-grade-candidate-index" &&
    value.source_file_sha256 === "8f7ef6e5029dfb0bf9a05800f63e5e05043d39c74d5dd0df500a27484aecec6e" &&
    Array.isArray(value.chunks) &&
    value.chunks.every((chunk) =>
      isObject(chunk) &&
      typeof chunk.section_id === "string" &&
      Number.isInteger(chunk.part) &&
      Number.isInteger(chunk.candidate_count) &&
      Number.isInteger(chunk.pdf_page_start) &&
      Number.isInteger(chunk.pdf_page_end) &&
      Number.isInteger(chunk.page_count) &&
      (chunk.page_count as number) === (chunk.pdf_page_end as number) - (chunk.pdf_page_start as number) + 1 &&
      typeof chunk.file === "string" &&
      chunk.file.startsWith("grade-candidates/") &&
      !chunk.file.includes("..") &&
      chunk.file.endsWith(".jsonl")
    );
}

function readSavedReviews(): Record<string, CandidateReview> {
  try {
    const raw = localStorage.getItem(REVIEW_STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    return isObject(parsed) ? parsed as Record<string, CandidateReview> : {};
  } catch {
    return {};
  }
}

function CandidateReviewCard({
  candidate,
  saved,
  onSave,
}: {
  candidate: CandidateRecord;
  saved?: CandidateReview;
  onSave: (review: CandidateReview) => void;
}) {
  const [rubric, setRubric] = useState(saved?.rubricText ?? candidate.suggested_rubric_context ?? "");
  const [grade, setGrade] = useState<number | "">(
    saved?.approvedGrade ?? candidate.candidate_grade_from_source_key ?? "",
  );
  const [sourceChecked, setSourceChecked] = useState(saved?.sourceChecked ?? false);

  useEffect(() => {
    setRubric(saved?.rubricText ?? candidate.suggested_rubric_context ?? "");
    setGrade(saved?.approvedGrade ?? candidate.candidate_grade_from_source_key ?? "");
    setSourceChecked(saved?.sourceChecked ?? false);
  }, [candidate.id, saved]);

  const gradeLabel = candidate.candidate_grade_from_source_key === null
    ? "Unclear style"
    : "Grade " + candidate.candidate_grade_from_source_key + " candidate";

  return (
    <article className={saved ? "candidate-review-card candidate-reviewed" : "candidate-review-card"}>
      <div className="candidate-card-top">
        <div>
          <strong>{candidate.matched_abbreviation_as_printed_in_index}</strong>
          <span>PDF page {candidate.source_pdf_page} · {gradeLabel}</span>
        </div>
        {saved ? <span className="candidate-reviewed-label"><CheckCircle2 size={13} /> Reviewed locally</span> :
          <span className="candidate-pending-label">Needs review</span>}
      </div>
      <p className="candidate-source-line">{candidate.line_text_as_extracted || candidate.source_span.text}</p>
      <a className="candidate-open-source" href={"/data/kent/source.pdf#page=" + candidate.source_pdf_page} target="_blank" rel="noreferrer">Open original PDF · page {candidate.source_pdf_page}</a>
      {candidate.suggested_rubric_context && <div className="candidate-context-hint">Suggested from source heading/line layout · {candidate.suggested_context_method?.replace(/_/g, " ")}</div>}
      <div className="candidate-style-evidence">
        Source token: <strong>{candidate.token_as_printed_in_rubric}</strong>
        <span>{candidate.grade_evidence.replace(/_/g, " ")}</span>
        <small>{candidate.source_span.color} · {candidate.source_span.font_family}{candidate.source_span.italic ? " · italic" : ""}</small>
      </div>
      <label className="candidate-rubric-field">
        Suggested rubric path — confirm or correct against the PDF
        <input value={rubric} onChange={(event) => setRubric(event.target.value)} placeholder="Enter rubric and parent path from source…" />
      </label>
      <div className="candidate-review-actions">
        <label className="candidate-grade-field">
          Confirmed grade
          <select value={grade} onChange={(event) => setGrade(event.target.value ? Number(event.target.value) : "")}>
            <option value="">Select grade</option>
            <option value="1">1 · Ordinary</option>
            <option value="2">2 · Italics</option>
            <option value="3">3 · Capitals</option>
          </select>
        </label>
        <label className="candidate-source-check">
          <input type="checkbox" checked={sourceChecked} onChange={(event) => setSourceChecked(event.target.checked)} />
          I checked the original PDF page
        </label>
        <button
          className="candidate-save-button"
          disabled={!rubric.trim() || !grade || !sourceChecked}
          onClick={() => onSave({
            candidateId: candidate.id,
            remedyAbbreviation: candidate.matched_abbreviation_as_printed_in_index,
            rubricText: rubric.trim(),
            approvedGrade: grade as number,
            sourcePdfPage: candidate.source_pdf_page,
            sourceChecked: true,
            savedAt: new Date().toISOString(),
          })}
        >
          {saved ? "Update review" : "Save verified record"}
        </button>
      </div>
    </article>
  );
}

export default function KentSourceBrowser({
  sectionId,
  sectionTitle,
  onClose,
}: {
  sectionId: string;
  sectionTitle: string;
  onClose: () => void;
}) {
  const [chunks, setChunks] = useState<ChunkMeta[]>([]);
  const [candidateChunks, setCandidateChunks] = useState<CandidateChunk[]>([]);
  const [chunkIndex, setChunkIndex] = useState(0);
  const [pages, setPages] = useState<SourcePage[]>([]);
  const [candidates, setCandidates] = useState<CandidateRecord[]>([]);
  const [selectedPageNumber, setSelectedPageNumber] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [candidateQuery, setCandidateQuery] = useState("");
  const [candidateLimit, setCandidateLimit] = useState(50);
  const [view, setView] = useState<"source" | "candidates">("source");
  const [loadingIndex, setLoadingIndex] = useState(true);
  const [loadingChunk, setLoadingChunk] = useState(false);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [error, setError] = useState("");
  const [candidateError, setCandidateError] = useState("");
  const [reviews, setReviews] = useState<Record<string, CandidateReview>>(readSavedReviews);

  const activeChunk = chunks[chunkIndex];
  const candidateChunk = candidateChunks.find((chunk) =>
    chunk.section_id === activeChunk?.section_id && chunk.part === activeChunk?.part
  );

  useEffect(() => {
    const controller = new AbortController();
    setLoadingIndex(true);
    setError("");
    setChunks([]);
    setCandidateChunks([]);
    setPages([]);
    setCandidates([]);
    setSelectedPageNumber(null);
    setChunkIndex(0);
    Promise.all([
      fetch("/data/kent/section-index.json", { signal: controller.signal }),
      fetch("/data/kent/structured/grade-candidates-index.json", { signal: controller.signal }),
    ]).then(async ([sectionResponse, candidateResponse]) => {
      if (sectionResponse.status === 404) throw new Error("The chapter source package is not installed. Copy section-index.json and the chunks folder into public/data/kent/.");
      if (!sectionResponse.ok) throw new Error("Could not load source section index (HTTP " + sectionResponse.status + ").");
      const sectionPayload: unknown = await sectionResponse.json();
      if (!validateSectionIndex(sectionPayload)) throw new Error("The chapter source index is malformed.");
      const selected = sectionPayload.chunks.filter((item) => item.section_id === sectionId).sort((a, b) => a.part - b.part);
      if (!selected.length) throw new Error("No source chunks were found for " + sectionTitle + ".");
      for (let index = 1; index < selected.length; index += 1) {
        if (selected[index].part !== selected[index - 1].part + 1 ||
            selected[index].pdf_page_start !== selected[index - 1].pdf_page_end + 1) {
          throw new Error("The chapter source index has a missing or duplicate part.");
        }
      }
      setChunks(selected);

      if (candidateResponse.ok) {
        const candidatePayload: unknown = await candidateResponse.json();
        if (!validateCandidateIndex(candidatePayload)) throw new Error("The grade-candidate index is malformed.");
        setCandidateChunks(candidatePayload.chunks.filter((item) => item.section_id === sectionId).sort((a, b) => a.part - b.part));
      } else if (candidateResponse.status !== 404) {
        throw new Error("Could not load grade candidate index (HTTP " + candidateResponse.status + ").");
      }
    }).catch((reason: unknown) => {
      if (controller.signal.aborted) return;
      setError(reason instanceof Error ? reason.message : "Could not load the source index.");
    }).finally(() => {
      if (!controller.signal.aborted) setLoadingIndex(false);
    });
    return () => controller.abort();
  }, [sectionId, sectionTitle]);

  useEffect(() => {
    if (!activeChunk) return;
    const controller = new AbortController();
    setLoadingChunk(true);
    setError("");
    setPages([]);
    setSelectedPageNumber(null);
    fetch("/data/kent/" + activeChunk.file, { signal: controller.signal })
      .then(async (response) => {
        if (response.status === 404) throw new Error("The source page chunk is missing: " + activeChunk.file);
        if (!response.ok) throw new Error("Could not load source chunk (HTTP " + response.status + ").");
        return response.text();
      })
      .then((raw) => {
        const loaded = parseJsonLines(raw, validateSourcePage);
        if (loaded.length !== activeChunk.page_count) throw new Error("Source chunk page count does not match its index.");
        const sorted = loaded.sort((a, b) => a.pdf_page - b.pdf_page);
        if (sorted.some((page) => page.section_id !== sectionId ||
            page.pdf_page < activeChunk.pdf_page_start || page.pdf_page > activeChunk.pdf_page_end)) {
          throw new Error("Source chunk contains a page outside its declared chapter or page range.");
        }
        setPages(sorted);
        if (sorted.length) setSelectedPageNumber(sorted[0].pdf_page);
      }).catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "Could not load this source chunk.");
      }).finally(() => {
        if (!controller.signal.aborted) setLoadingChunk(false);
      });
    return () => controller.abort();
  }, [activeChunk, sectionId]);

  useEffect(() => {
    if (view !== "candidates" || !activeChunk) return;
    const match = candidateChunk;
    if (!match) {
      setCandidates([]);
      setCandidateError("No grade-candidate chunk exists for this chapter part. Run the grade-candidate importer first.");
      return;
    }
    const controller = new AbortController();
    setLoadingCandidates(true);
    setCandidateError("");
    setCandidates([]);
    setCandidateLimit(50);
    fetch("/data/kent/structured/" + match.file, { signal: controller.signal })
      .then(async (response) => {
        if (response.status === 404) throw new Error("Grade-candidate file is missing: " + match.file);
        if (!response.ok) throw new Error("Could not load grade candidates (HTTP " + response.status + ").");
        return response.text();
      })
      .then((raw) => {
        const loaded = parseJsonLines(raw, validateCandidate);
        if (loaded.length !== match.candidate_count) throw new Error("Candidate count does not match the candidate index.");
        if (loaded.some((record) => record.source_section_id !== sectionId ||
            record.source_pdf_page < match.pdf_page_start || record.source_pdf_page > match.pdf_page_end)) {
          throw new Error("Candidate records contain a page outside their declared source chunk.");
        }
        setCandidates(loaded);
      }).catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setCandidateError(reason instanceof Error ? reason.message : "Could not load this grade-candidate chunk.");
      }).finally(() => {
        if (!controller.signal.aborted) setLoadingCandidates(false);
      });
    return () => controller.abort();
  }, [view, activeChunk, candidateChunk, sectionId]);

  const sourceMatches = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return !term ? pages : pages.filter((page) => page.text.toLocaleLowerCase().includes(term));
  }, [pages, query]);

  const candidateMatches = useMemo(() => {
    const term = candidateQuery.trim().toLocaleLowerCase();
    if (!term) return candidates;
    return candidates.filter((candidate) =>
      candidate.token_as_printed_in_rubric.toLocaleLowerCase().includes(term) ||
      candidate.line_text_as_extracted.toLocaleLowerCase().includes(term)
    );
  }, [candidates, candidateQuery]);

  const selectedPage = pages.find((page) => page.pdf_page === selectedPageNumber) ?? null;

  const saveReview = (review: CandidateReview) => {
    setReviews((current) => {
      const next = { ...current, [review.candidateId]: review };
      try {
        localStorage.setItem(REVIEW_STORAGE_KEY, JSON.stringify(next));
      } catch {
        setCandidateError("This device's local storage is full. Export existing reviews before continuing.");
      }
      return next;
    });
  };

  const exportReviews = () => {
    const payload = {
      dataset_id: "curiva-kent-user-verified-review-decisions",
      source_file_sha256: "8f7ef6e5029dfb0bf9a05800f63e5e05043d39c74d5dd0df500a27484aecec6e",
      records: Object.values(reviews),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "curiva-kent-verified-review-decisions.json";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const candidateCountReviewed = candidates.filter((candidate) => reviews[candidate.id]).length;
  const reviewedTotal = Object.keys(reviews).length;

  return (
    <section className="kent-source-browser">
      <div className="kent-source-browser-top">
        <div className="kent-source-title">
          <div className="eyebrow">UPLOADED PDF · PAGE-ALIGNED SOURCE</div>
          <h3>{sectionTitle}</h3>
          <p>Original page text and source typography. PDF page numbers refer to your supplied file.</p>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Close source browser"><X size={18} /></button>
      </div>

      <div className="kent-source-view-tabs">
        <button className={view === "source" ? "active" : ""} onClick={() => setView("source")}><FileText size={14} /> PDF pages</button>
        <button className={view === "candidates" ? "active" : ""} onClick={() => setView("candidates")}><ClipboardCheck size={14} /> Grade candidates</button>
        <button className="candidate-export-button" onClick={exportReviews} disabled={!reviewedTotal}><Download size={14} /> Export {reviewedTotal} reviews</button>
      </div>

      {loadingIndex && <div className="empty-library-note"><LoaderCircle className="inline-spin" size={15} /> Loading chapter index…</div>}
      {!loadingIndex && activeChunk && (
        <>
          <div className="kent-chunk-controls">
            <button className="secondary-button" disabled={chunkIndex === 0 || loadingChunk} onClick={() => setChunkIndex((value) => Math.max(0, value - 1))}><ChevronLeft size={15} /> Previous chunk</button>
            <span>Chunk {chunkIndex + 1} of {chunks.length} · PDF pages {activeChunk.pdf_page_start}–{activeChunk.pdf_page_end}</span>
            <button className="secondary-button" disabled={chunkIndex >= chunks.length - 1 || loadingChunk} onClick={() => setChunkIndex((value) => Math.min(chunks.length - 1, value + 1))}>Next chunk <ChevronRight size={15} /></button>
          </div>

          {view === "source" && <>
            <div className="rubric-search-box kent-source-search"><Search size={16} /><input aria-label="Search within current source chunk" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search text in these pages…" /></div>
            {loadingChunk && <div className="empty-library-note"><LoaderCircle className="inline-spin" size={15} /> Loading source pages…</div>}
            {!loadingChunk && (
              <div className="kent-source-layout">
                <div className="kent-source-page-list">
                  <div className="kent-source-page-count">{sourceMatches.length} matching pages</div>
                  {sourceMatches.map((page) => (
                    <button key={page.pdf_page} className={selectedPageNumber === page.pdf_page ? "kent-source-page-option selected" : "kent-source-page-option"} onClick={() => setSelectedPageNumber(page.pdf_page)}>
                      <span><FileText size={14} /> PDF page {page.pdf_page}</span>
                      <small>{page.boundary_page_review ? "Chapter boundary · review" : sectionTitle}</small>
                      <p>{page.text.replace(/\s+/g, " ").slice(0, 180)}</p>
                    </button>
                  ))}
                  {!sourceMatches.length && <div className="empty-library-note">No page in this chunk matches the search.</div>}
                </div>
                <div className="kent-source-page-view">
                  {selectedPage ? <>
                    <div className="kent-source-page-heading">
                      <strong>PDF page {selectedPage.pdf_page}</strong>
                      <a href={"/data/kent/source.pdf#page=" + selectedPage.pdf_page} target="_blank" rel="noreferrer">Open original PDF</a>
                      {selectedPage.boundary_page_review && <span>Boundary page · check chapter transition</span>}
                    </div>
                    <pre>{selectedPage.text}</pre>
                    <details className="source-style-details">
                      <summary>Inspect source typography ({selectedPage.text_items.length} layout spans)</summary>
                      <div className="source-style-legend">Source grade key (PDF page 36): capitals = 3 · italics = 2 · ordinary = 1. Typography is retained for review; it is not a verified grade record by itself.</div>
                      <div className="source-style-spans">
                        {selectedPage.text_items.map((item, index) => (
                          <span key={index} style={{ color: item.color, fontWeight: item.bold ? 700 : 400, fontStyle: item.italic ? "italic" : "normal" }} title={"PDF position " + item.left + ", " + item.top + " · " + item.font_family + " " + item.font_size}>
                            {item.text}
                          </span>
                        ))}
                      </div>
                    </details>
                  </> : <div className="empty-library-note">Select a source page.</div>}
                </div>
              </div>
            )}
          </>}

          {view === "candidates" && <>
            <div className="candidate-review-summary">
              <span>{candidateChunk?.candidate_count ?? 0} candidate occurrences in this 25-page chunk</span>
              <span>{candidateCountReviewed} reviewed here · {reviewedTotal} saved on this device</span>
            </div>
            <div className="rubric-search-box kent-source-search"><Search size={16} /><input aria-label="Search grade candidates" value={candidateQuery} onChange={(event) => setCandidateQuery(event.target.value)} placeholder="Search remedy abbreviation or source line…" /></div>
            {loadingCandidates && <div className="empty-library-note"><LoaderCircle className="inline-spin" size={15} /> Loading candidate records…</div>}
            {candidateError && <div className="empty-library-note source-load-error"><strong>Candidate review unavailable.</strong><p>{candidateError}</p></div>}
            {!loadingCandidates && !candidateError && <>
              <div className="candidate-page-count">Showing {Math.min(candidateLimit, candidateMatches.length)} of {candidateMatches.length} matching candidates</div>
              <div className="candidate-review-list">
                {candidateMatches.slice(0, candidateLimit).map((candidate) => (
                  <CandidateReviewCard key={candidate.id} candidate={candidate} saved={reviews[candidate.id]} onSave={saveReview} />
                ))}
                {!candidateMatches.length && <div className="empty-library-note">No candidate matches your search.</div>}
              </div>
              {candidateLimit < candidateMatches.length && <button className="candidate-more-button" onClick={() => setCandidateLimit((value) => value + 50)}>Show next 50 candidates</button>}
            </>}
          </>}
        </>
      )}
      {error && <div className="empty-library-note source-load-error"><strong>Source data unavailable.</strong><p>{error}</p></div>}
      <div className="candidate-review-footnote">Saving a review records your manual source check, exact rubric path and approved grade on this device. It does not modify the original candidate or automatically publish a rubric into the repertorization matrix.</div>
    </section>
  );
}
