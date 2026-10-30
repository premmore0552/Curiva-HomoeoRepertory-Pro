import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, FileText, LoaderCircle, Search, X } from "lucide-react";

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

function parseJsonLines(raw: string, expectedSectionId: string, chunk: ChunkMeta): SourcePage[] {
  const records: SourcePage[] = [];
  const seenPages = new Set<number>();
  for (const [index, line] of raw.split(/\r?\n/).entries()) {
    if (!line.trim()) continue;
    let value: unknown;
    try {
      value = JSON.parse(line);
    } catch {
      throw new Error("Chunk JSONL has an invalid record on line " + (index + 1) + ".");
    }
    if (
      typeof value !== "object" || value === null ||
      typeof (value as SourcePage).pdf_page !== "number" ||
      typeof (value as SourcePage).text !== "string" ||
      !Array.isArray((value as SourcePage).text_items)
    ) {
      throw new Error("Chunk contains a page record with an unexpected shape.");
    }
    const page = value as SourcePage;
    if (
      page.section_id !== expectedSectionId ||
      page.pdf_page < chunk.pdf_page_start ||
      page.pdf_page > chunk.pdf_page_end ||
      seenPages.has(page.pdf_page)
    ) {
      throw new Error("Chunk contains a duplicate page or a page outside its declared chapter range.");
    }
    seenPages.add(page.pdf_page);
    records.push(page);
  }
  if (records.length !== chunk.page_count) {
    throw new Error("Chunk page count mismatch: expected " + chunk.page_count + ", received " + records.length + ".");
  }
  records.sort((a, b) => a.pdf_page - b.pdf_page);
  return records;
}

function validateChunkIndex(value: unknown): value is SectionIndex {
  if (typeof value !== "object" || value === null || !Array.isArray((value as SectionIndex).chunks)) return false;
  return (value as SectionIndex).chunks.every((chunk) =>
    typeof chunk === "object" && chunk !== null &&
    typeof chunk.section_id === "string" &&
    Number.isInteger(chunk.part) && chunk.part > 0 &&
    Number.isInteger(chunk.pdf_page_start) &&
    Number.isInteger(chunk.pdf_page_end) &&
    chunk.pdf_page_start > 0 &&
    chunk.pdf_page_end >= chunk.pdf_page_start &&
    chunk.page_count === chunk.pdf_page_end - chunk.pdf_page_start + 1 &&
    typeof chunk.file === "string" &&
    chunk.file.startsWith("chunks/") &&
    !chunk.file.includes("..") &&
    chunk.file.endsWith(".jsonl")
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
  const [chunkIndex, setChunkIndex] = useState(0);
  const [pages, setPages] = useState<SourcePage[]>([]);
  const [selectedPageNumber, setSelectedPageNumber] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [loadingIndex, setLoadingIndex] = useState(true);
  const [loadingChunk, setLoadingChunk] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoadingIndex(true);
    setError("");
    setChunks([]);
    setPages([]);
    setSelectedPageNumber(null);
    setChunkIndex(0);
    fetch("/data/kent/section-index.json", { signal: controller.signal })
      .then(async (response) => {
        if (response.status === 404) throw new Error("The chapter chunk index is not installed. Copy section-index.json and the chunks folder into public/data/kent/.");
        if (!response.ok) throw new Error("Could not load source section index (HTTP " + response.status + ").");
        const payload: unknown = await response.json();
        if (!validateChunkIndex(payload)) throw new Error("The chapter chunk index is malformed.");
        return payload;
      })
      .then((index) => {
        const selected = index.chunks.filter((item) => item.section_id === sectionId);
        if (!selected.length) throw new Error("No page chunks were found for " + sectionTitle + ".");
        const ordered = selected.sort((a, b) => a.part - b.part);
        for (let index = 1; index < ordered.length; index += 1) {
          if (ordered[index].part !== ordered[index - 1].part + 1 ||
              ordered[index].pdf_page_start !== ordered[index - 1].pdf_page_end + 1) {
            throw new Error("The chapter chunk index has a gap or duplicate part.");
          }
        }
        setChunks(ordered);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "Could not load the source index.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingIndex(false);
      });
    return () => controller.abort();
  }, [sectionId, sectionTitle]);

  useEffect(() => {
    if (!chunks.length || !chunks[chunkIndex]) return;
    const controller = new AbortController();
    setLoadingChunk(true);
    setError("");
    setPages([]);
    setSelectedPageNumber(null);
    const file = chunks[chunkIndex].file;
    fetch("/data/kent/" + file, { signal: controller.signal })
      .then(async (response) => {
        if (response.status === 404) throw new Error("The chunk file is missing: " + file);
        if (!response.ok) throw new Error("Could not load chunk (HTTP " + response.status + ").");
        return response.text();
      })
      .then((raw) => {
        const loaded = parseJsonLines(raw, sectionId, chunks[chunkIndex]);
        setPages(loaded);
        if (loaded.length) setSelectedPageNumber(loaded[0].pdf_page);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "Could not load this chapter chunk.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingChunk(false);
      });
    return () => controller.abort();
  }, [chunks, chunkIndex]);

  const matches = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    if (!term) return pages;
    return pages.filter((page) => page.text.toLocaleLowerCase().includes(term));
  }, [pages, query]);

  const selectedPage = pages.find((page) => page.pdf_page === selectedPageNumber) ?? null;
  const activeChunk = chunks[chunkIndex];

  return (
    <section className="kent-source-browser">
      <div className="kent-source-browser-top">
        <div className="kent-source-title">
          <div className="eyebrow">ORIGINAL PDF TEXT · PAGE-ALIGNED SOURCE</div>
          <h3>{sectionTitle}</h3>
          <p>Browse the extracted page text and source formatting. PDF page numbers refer to the uploaded file.</p>
        </div>
        <button className="icon-button" onClick={onClose} aria-label="Close source browser"><X size={18} /></button>
      </div>

      {loadingIndex && <div className="empty-library-note"><LoaderCircle className="inline-spin" size={15} /> Loading chapter index…</div>}
      {!loadingIndex && !error && activeChunk && (
        <>
          <div className="kent-chunk-controls">
            <button className="secondary-button" disabled={chunkIndex === 0 || loadingChunk} onClick={() => setChunkIndex((value) => Math.max(0, value - 1))}><ChevronLeft size={15} /> Previous chunk</button>
            <span>Chunk {chunkIndex + 1} of {chunks.length} · PDF pages {activeChunk.pdf_page_start}–{activeChunk.pdf_page_end}</span>
            <button className="secondary-button" disabled={chunkIndex >= chunks.length - 1 || loadingChunk} onClick={() => setChunkIndex((value) => Math.min(chunks.length - 1, value + 1))}>Next chunk <ChevronRight size={15} /></button>
          </div>
          <div className="rubric-search-box kent-source-search"><Search size={16} /><input aria-label="Search within current source chunk" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search text in these pages…" /></div>
          {loadingChunk && <div className="empty-library-note"><LoaderCircle className="inline-spin" size={15} /> Loading up to 25 source pages…</div>}
          {!loadingChunk && (
            <div className="kent-source-layout">
              <div className="kent-source-page-list">
                <div className="kent-source-page-count">{matches.length} matching pages in this chunk</div>
                {matches.map((page) => (
                  <button key={page.pdf_page} className={selectedPageNumber === page.pdf_page ? "kent-source-page-option selected" : "kent-source-page-option"} onClick={() => setSelectedPageNumber(page.pdf_page)}>
                    <span><FileText size={14} /> PDF page {page.pdf_page}</span>
                    <small>{page.boundary_page_review ? "Chapter boundary · review" : sectionTitle}</small>
                    <p>{page.text.replace(/\s+/g, " ").slice(0, 180)}</p>
                  </button>
                ))}
                {!matches.length && <div className="empty-library-note">No page in this chunk matches the search. Try another chunk or shorten the term.</div>}
              </div>
              <div className="kent-source-page-view">
                {selectedPage ? (
                  <>
                    <div className="kent-source-page-heading">
                      <strong>PDF page {selectedPage.pdf_page}</strong>
                      {selectedPage.boundary_page_review && <span>Boundary page · check chapter transition</span>}
                    </div>
                    <pre>{selectedPage.text}</pre>
                    <details className="source-style-details">
                      <summary>Inspect source typography ({selectedPage.text_items.length} layout spans)</summary>
                      <div className="source-style-legend">Original style evidence: ordinary = grade 1 · italics = grade 2 · capitals = grade 3 (source key, PDF page 36). This view is for checking, not automatic grading.</div>
                      <div className="source-style-spans">
                        {selectedPage.text_items.map((item, index) => (
                          <span key={index} style={{ color: item.color, fontWeight: item.bold ? 700 : 400, fontStyle: item.italic ? "italic" : "normal" }} title={"PDF position " + item.left + ", " + item.top + " · " + item.font_family + " " + item.font_size}>
                            {item.text}
                          </span>
                        ))}
                      </div>
                    </details>
                  </>
                ) : <div className="empty-library-note">Select a matching source page to read it.</div>}
              </div>
            </div>
          )}
        </>
      )}
      {error && <div className="empty-library-note source-load-error"><strong>Source data unavailable.</strong><p>{error}</p></div>}
    </section>
  );
}
