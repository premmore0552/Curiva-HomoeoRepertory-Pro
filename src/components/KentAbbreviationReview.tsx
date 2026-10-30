import { useMemo, useState } from "react";
import { CheckCircle2, Download, Search } from "lucide-react";
import type { KentRemedyAbbreviationRecord } from "../data/kent-remedy-index";

type AbbreviationReviewStatus = "verified" | "uncertain" | "rejected";
type AbbreviationDecision = {
  recordId: string;
  sourcePdfPage: number;
  confirmedAbbreviation: string;
  confirmedFullName: string;
  sourceChecked: boolean;
  reviewStatus: AbbreviationReviewStatus;
  reviewNote?: string;
  savedAt: string;
};

const STORAGE_KEY = "curiva.kent.abbreviation-reviews.v1";

function readDecisions(): Record<string, AbbreviationDecision> {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (!value) return {};
    const parsed: unknown = JSON.parse(value);
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
      ? parsed as Record<string, AbbreviationDecision>
      : {};
  } catch {
    return {};
  }
}

function AbbreviationReviewCard({
  record,
  saved,
  onSave,
}: {
  record: KentRemedyAbbreviationRecord;
  saved?: AbbreviationDecision;
  onSave: (decision: AbbreviationDecision) => void;
}) {
  const [abbreviation, setAbbreviation] = useState(saved?.confirmedAbbreviation ?? record.abbreviation_as_printed);
  const [fullName, setFullName] = useState(saved?.confirmedFullName ?? record.full_name_as_printed);
  const [sourceChecked, setSourceChecked] = useState(saved?.sourceChecked ?? false);
  const [reviewNote, setReviewNote] = useState(saved?.reviewNote ?? "");

  const save = (reviewStatus: AbbreviationReviewStatus) => onSave({
    recordId: record.id,
    sourcePdfPage: record.source_pdf_page,
    confirmedAbbreviation: abbreviation.trim(),
    confirmedFullName: fullName.trim(),
    sourceChecked,
    reviewStatus,
    reviewNote: reviewNote.trim(),
    savedAt: new Date().toISOString(),
  });

  return (
    <article className={saved ? "candidate-review-card candidate-reviewed" : "candidate-review-card"}>
      <div className="candidate-card-top">
        <div>
          <strong>{record.abbreviation_as_printed}</strong>
          <span>PDF page {record.source_pdf_page} · {record.source_column} column</span>
        </div>
        {saved
          ? <span className="candidate-reviewed-label"><CheckCircle2 size={13} /> {saved.reviewStatus} · saved</span>
          : <span className="candidate-pending-label">Needs proofreading</span>}
      </div>
      <p className="candidate-source-line">{record.source_line_as_printed}</p>
      <a className="candidate-open-source" href={"/data/kent/source.pdf#page=" + record.source_pdf_page} target="_blank" rel="noreferrer">
        Open original PDF · page {record.source_pdf_page}
      </a>
      {record.continuation_lines.length > 0 && (
        <div className="candidate-context-hint">
          Continued in the source: {record.continuation_lines.map((line) => line.text_as_printed).join(" · ")}
        </div>
      )}
      <label className="candidate-rubric-field">
        Abbreviation exactly as printed
        <input value={abbreviation} onChange={(event) => setAbbreviation(event.target.value)} />
      </label>
      <label className="candidate-rubric-field">
        Full remedy name exactly as printed
        <input value={fullName} onChange={(event) => setFullName(event.target.value)} />
      </label>
      <label className="candidate-rubric-field">
        Proofreading note
        <input value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} placeholder="Optional note about a transcription correction…" />
      </label>
      <label className="candidate-source-check">
        <input type="checkbox" checked={sourceChecked} onChange={(event) => setSourceChecked(event.target.checked)} />
        I checked this abbreviation and full name against the original PDF page
      </label>
      <div className="candidate-review-actions">
        <button className="candidate-save-button" disabled={!sourceChecked || !abbreviation.trim() || !fullName.trim()} onClick={() => save("verified")}>
          Verify exact entry
        </button>
        <button className="secondary-button" disabled={!sourceChecked} onClick={() => save("uncertain")}>Mark uncertain</button>
        <button className="secondary-button" disabled={!sourceChecked} onClick={() => save("rejected")}>Reject transcription</button>
      </div>
    </article>
  );
}

export default function KentAbbreviationReview({ records }: { records: KentRemedyAbbreviationRecord[] }) {
  const [decisions, setDecisions] = useState<Record<string, AbbreviationDecision>>(readDecisions);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"pending" | AbbreviationReviewStatus | "all">("pending");
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const filtered = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return records.filter((record) => {
      const saved = decisions[record.id];
      const status = saved?.reviewStatus ?? "pending";
      const statusMatch = filter === "all" || status === filter;
      const textMatch = !term ||
        record.abbreviation_as_printed.toLocaleLowerCase().includes(term) ||
        record.full_name_as_printed.toLocaleLowerCase().includes(term);
      return statusMatch && textMatch;
    });
  }, [records, decisions, query, filter]);

  const counts = useMemo(() => {
    const result = { pending: 0, verified: 0, uncertain: 0, rejected: 0 };
    for (const record of records) {
      const status = decisions[record.id]?.reviewStatus ?? "pending";
      result[status] += 1;
    }
    return result;
  }, [records, decisions]);

  const onSave = (decision: AbbreviationDecision) => {
    setDecisions((current) => {
      const next = { ...current, [decision.recordId]: decision };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        window.alert("Device storage is full. Export your proofreading decisions before saving more.");
        return current;
      }
      return next;
    });
  };

  const exportDecisions = () => {
    const payload = {
      dataset_id: "curiva-kent-abbreviation-review-decisions",
      source_file_sha256: "8f7ef6e5029dfb0bf9a05800f63e5e05043d39c74d5dd0df500a27484aecec6e",
      records: Object.values(decisions),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "curiva-kent-abbreviation-review-decisions.json";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visible = filtered.slice(page * pageSize, (page + 1) * pageSize);

  return (
    <section className="abbreviation-review-panel">
      <div className="candidate-review-summary">
        <span>{records.length} source abbreviation entries</span>
        <span>{counts.verified} verified · {counts.uncertain} uncertain · {counts.rejected} rejected · {counts.pending} pending</span>
      </div>
      <div className="candidate-review-summary">
        <span>Proofread the abbreviation and full name against the linked original PDF page.</span>
        <button className="candidate-export-button" onClick={exportDecisions} disabled={!Object.keys(decisions).length}>
          <Download size={14} /> Export {Object.keys(decisions).length} decisions
        </button>
      </div>
      <div className="rubric-search-box remedy-index-search">
        <Search size={16} />
        <input aria-label="Search abbreviation proofreading queue" value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} placeholder="Search abbreviation or remedy name…" />
      </div>
      <label className="candidate-grade-field">
        Review status
        <select value={filter} onChange={(event) => { setFilter(event.target.value as typeof filter); setPage(0); }}>
          <option value="pending">Pending</option>
          <option value="verified">Verified</option>
          <option value="uncertain">Uncertain</option>
          <option value="rejected">Rejected</option>
          <option value="all">All entries</option>
        </select>
      </label>
      <div className="candidate-page-count">
        Showing {visible.length ? page * pageSize + 1 : 0}–{Math.min((page + 1) * pageSize, filtered.length)} of {filtered.length}
      </div>
      {visible.map((record) => (
        <AbbreviationReviewCard key={record.id} record={record} saved={decisions[record.id]} onSave={onSave} />
      ))}
      {!filtered.length && <div className="empty-library-note">No abbreviation entries match this filter.</div>}
      <div className="kent-chunk-controls">
        <button className="secondary-button" disabled={page === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}>Previous 20</button>
        <span>Page {page + 1} of {pageCount}</span>
        <button className="secondary-button" disabled={page >= pageCount - 1} onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))}>Next 20</button>
      </div>
    </section>
  );
}
