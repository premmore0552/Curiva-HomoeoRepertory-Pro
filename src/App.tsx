import { useMemo, useState } from 'react';
import { kentSourceCatalog } from './data/kent-source-catalog';
import {
  Activity, ArrowDownUp, BookOpen, ChevronDown, CircleHelp, Copy, Download,
  Filter, FolderOpen, Home, Info, Menu, Merge, Plus, Search, ShoppingBag,
  SlidersHorizontal, Trash2, Undo2, Redo2, Users, X, ChartNoAxesColumn,
} from 'lucide-react';

type Page = 'home' | 'repertory' | 'materia' | 'cases' | 'shop';
type Remedy = { id: string; abbr: string; name: string; author: string };
type RubricRow = {
  id: string;
  path: string;
  source: string;
  values: Record<string, number>;
};

// No placeholder repertory data is bundled. Records will come only from the supplied PDF.
const remedies: Remedy[] = [];
const initialRows: RubricRow[] = [];
const addableRubrics: RubricRow[] = [];

const cloneRows = (rows: RubricRow[]) => rows.map((row) => ({ ...row, values: { ...row.values } }));
const gradeClass = (grade: number) => `grade grade-${grade}`;

function Brand() {
  return (
    <div className="brand-lockup" aria-label="Curiva HomoeoRepertory Pro">
      <div className="brand-symbol"><Activity size={22} strokeWidth={2.1} /></div>
      <div className="brand-words">
        <strong>CURIVA</strong>
        <span>HOMOEOPATHY SOFTWARE</span>
      </div>
    </div>
  );
}

function App() {
  const [page, setPage] = useState<Page>('repertory');
  const [activeCase, setActiveCase] = useState('A');
  const [caseSets, setCaseSets] = useState<Record<string, RubricRow[]>>({ A: [], B: [], C: [], D: [] });
  const rows = caseSets[activeCase] ?? [];
  const [past, setPast] = useState<RubricRow[][]>([]);
  const [future, setFuture] = useState<RubricRow[][]>([]);
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [showGrades, setShowGrades] = useState(true);
  const [showTotals, setShowTotals] = useState(true);
  const [onlyRelevant, setOnlyRelevant] = useState(false);
  const [sortByTotal, setSortByTotal] = useState(false);
  const [showAuthors, setShowAuthors] = useState(false);
  const [showAddRubric, setShowAddRubric] = useState(false);
  const [rubricSearch, setRubricSearch] = useState('');
  const [caseName, setCaseName] = useState('New case');
  const [showHelp, setShowHelp] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [notice, setNotice] = useState('PDF chapter index loaded · structured rubric data not imported yet');

  const updateRows = (next: RubricRow[]) => {
    setPast((stack) => [...stack.slice(-29), cloneRows(rows)]);
    setFuture([]);
    setCaseSets((current) => ({ ...current, [activeCase]: cloneRows(next) }));
    setSelectedRows([]);
  };

  const undo = () => {
    if (!past.length) return;
    const previous = past[past.length - 1];
    setFuture((stack) => [cloneRows(rows), ...stack]);
    setCaseSets((current) => ({ ...current, [activeCase]: cloneRows(previous) }));
    setPast((stack) => stack.slice(0, -1));
    setSelectedRows([]);
  };

  const redo = () => {
    if (!future.length) return;
    const next = future[0];
    setPast((stack) => [...stack, cloneRows(rows)]);
    setCaseSets((current) => ({ ...current, [activeCase]: cloneRows(next) }));
    setFuture((stack) => stack.slice(1));
    setSelectedRows([]);
  };

  const remedyTotals = useMemo(() => {
    const totals: Record<string, { sum: number; count: number }> = {};
    remedies.forEach((remedy) => { totals[remedy.id] = { sum: 0, count: 0 }; });
    rows.forEach((row) => {
      Object.entries(row.values).forEach(([id, grade]) => {
        if (totals[id] && grade > 0) {
          totals[id].sum += grade;
          totals[id].count += 1;
        }
      });
    });
    return totals;
  }, [rows]);

  const visibleRemedies = useMemo(() => {
    let result = remedies.filter((remedy) => !onlyRelevant || rows.some((row) => row.values[remedy.id]));
    if (sortByTotal) result = [...result].sort((a, b) => remedyTotals[b.id].sum - remedyTotals[a.id].sum);
    return result;
  }, [onlyRelevant, rows, sortByTotal, remedyTotals]);

  const navItems = [
    { id: 'home' as Page, label: 'Home', icon: Home },
    { id: 'repertory' as Page, label: 'Repertory', icon: BookOpen },
    { id: 'materia' as Page, label: 'Materia Medica', icon: Activity },
    { id: 'cases' as Page, label: 'Cases', icon: FolderOpen },
    { id: 'shop' as Page, label: 'Shop', icon: ShoppingBag },
  ];

  const toggleRow = (id: string) => setSelectedRows((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);

  const mergeSelected = () => {
    const chosen = rows.filter((row) => selectedRows.includes(row.id));
    if (chosen.length < 2) {
      setNotice('Select at least two rubric rows to merge.');
      return;
    }
    const mergedValues: Record<string, number> = {};
    remedies.forEach((remedy) => {
      const grades = chosen.map((row) => row.values[remedy.id] ?? 0);
      const highest = Math.max(0, ...grades);
      if (highest) mergedValues[remedy.id] = highest;
    });
    const merged: RubricRow = {
      id: `merged-${Date.now()}`,
      path: chosen.map((row) => row.path).join(' + '),
      source: 'Combined view · verify before use',
      values: mergedValues,
    };
    updateRows([...rows.filter((row) => !selectedRows.includes(row.id)), merged]);
    setNotice('Selected rows combined for display. Review the combined rubric before relying on it.');
  };

  const removeSelected = () => {
    if (!selectedRows.length) {
      setNotice('Select one or more rubric rows first.');
      return;
    }
    updateRows(rows.filter((row) => !selectedRows.includes(row.id)));
    setNotice('Selected rows removed from this case.');
  };

  const addRubric = (rubric: RubricRow) => {
    if (rows.some((row) => row.id === rubric.id)) {
      setNotice('That sample rubric is already in this case.');
      return;
    }
    updateRows([...rows, cloneRows([rubric])[0]]);
    setShowAddRubric(false);
    setRubricSearch('');
    setNotice('Sample rubric added. Verify its data source before clinical or academic use.');
  };

  const exportCsv = () => {
    const lines = [
      ['Rubric', ...visibleRemedies.map((r) => r.name)].map(csvCell).join(','),
      ...rows.map((row) => [row.path, ...visibleRemedies.map((r) => row.values[r.id] ?? '')].map(csvCell).join(',')),
    ];
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `curiva-case-${activeCase.toLowerCase()}-matrix.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
    setNotice('CSV export created for the current case matrix.');
  };

  const filteredAddable = addableRubrics.filter((rubric) => rubric.path.toLowerCase().includes(rubricSearch.toLowerCase()));

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-brand"><Brand /></div>
        <button className="mobile-menu-button" onClick={() => setMobileMenu((value) => !value)} aria-label="Toggle navigation"><Menu size={21} /></button>
        <nav className={`main-nav ${mobileMenu ? 'nav-open' : ''}`} aria-label="Main navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            return <button key={item.id} className={`nav-item ${page === item.id ? 'active' : ''}`} onClick={() => { setPage(item.id); setMobileMenu(false); }}>
              <Icon size={17} /><span>{item.label}</span>
            </button>;
          })}
        </nav>
        <div className="topbar-actions">
          <button className="icon-button help-button" onClick={() => setShowHelp((value) => !value)} aria-label="Help"><CircleHelp size={21} /></button>
          <button className="profile-avatar" title="Local prototype profile">C</button>
        </div>
      </header>

      <main className="main-content">
        {page === 'repertory' && (
          <>
            <div className="case-toolbar">
              <div className="case-title-block">
                <div className="eyebrow">REPERTORIZATION WORKSPACE</div>
                <h1>Case: <input aria-label="Case name" value={caseName} onChange={(event) => setCaseName(event.target.value)} /> <span className="title-divider">|</span> <span className="created-date">Rep Created: 30/10/2026</span></h1>
              </div>
              <div className="toolbar-actions">
                <button className={`tool-button ${showTotals ? 'tool-selected' : ''}`} onClick={() => setShowTotals((value) => !value)}><ChartNoAxesColumn size={17} /> <span>Sum of Degrees</span></button>
                <button className={`tool-button ${onlyRelevant ? 'tool-selected' : ''}`} onClick={() => setOnlyRelevant((value) => !value)}><Filter size={17} /> <span>Filter</span></button>
                <button className={`tool-button ${showAuthors ? 'tool-selected' : ''}`} onClick={() => setShowAuthors((value) => !value)}><Users size={17} /> <span>Authors</span></button>
                <button className="tool-button" onClick={exportCsv}><Download size={17} /> <span>Export</span></button>
                <button className="close-button" onClick={() => setPage('cases')}><X size={17} /> <span>Close</span></button>
              </div>
            </div>

            <section className="repertory-panel">
              <div className="panel-topline">
                <Brand />
                <div className="case-tabs" role="tablist" aria-label="Case analysis sets">
                  {['A', 'B', 'C', 'D'].map((tab) => <button key={tab} role="tab" aria-selected={activeCase === tab} className={activeCase === tab ? 'case-tab active' : 'case-tab'} onClick={() => { setActiveCase(tab); setSelectedRows([]); setPast([]); setFuture([]); }}>{tab}</button>)}
                </div>
                <div className="panel-top-actions">
                  <button className="icon-button" onClick={() => setShowHelp((value) => !value)} aria-label="Matrix help"><Info size={18} /></button>
                </div>
              </div>

              <div className="matrix-toolbar">
                <div className="selection-summary">
                  <div><strong>Selected Rubrics: {rows.length}</strong><span className="sample-tag">SOURCE DATA PENDING</span></div>
                  <div className="history-actions">
                    <button className="undo-button" onClick={undo} disabled={!past.length}><Undo2 size={15} /> Undo</button>
                    <button className="redo-button" onClick={redo} disabled={!future.length}><Redo2 size={15} /> Redo</button>
                  </div>
                </div>
                <div className="matrix-tools">
                  <button className="soft-button" onClick={mergeSelected}><Merge size={15} /> Merge Rubrics</button>
                  <button className={`soft-button ${onlyRelevant ? 'soft-active' : ''}`} onClick={() => setOnlyRelevant((value) => !value)}><Filter size={15} /> Elimination</button>
                  <button className={`soft-button ${showGrades ? '' : 'soft-active'}`} onClick={() => setShowGrades((value) => !value)}><SlidersHorizontal size={15} /> Grade</button>
                  <button className={`soft-button ${sortByTotal ? 'soft-active' : ''}`} onClick={() => setSortByTotal((value) => !value)}><ArrowDownUp size={15} /> Sort</button>
                  <button className="soft-icon-button" onClick={() => setShowAddRubric((value) => !value)} aria-label="Search and add rubrics"><Search size={18} /></button>
                </div>
              </div>

              {showAddRubric && (
                <div className="add-rubric-panel">
                  <div className="add-rubric-heading"><div><strong>Add rubric</strong><span>Only verified PDF-derived rubrics will appear here</span></div><button className="icon-button" onClick={() => setShowAddRubric(false)} aria-label="Close add rubric"><X size={18} /></button></div>
                  <div className="rubric-search-box"><Search size={16} /><input autoFocus value={rubricSearch} onChange={(event) => setRubricSearch(event.target.value)} placeholder="Search rubric wording..." /></div>
                  <div className="rubric-candidates">
                    {filteredAddable.map((rubric) => <button key={rubric.id} onClick={() => addRubric(rubric)}><Plus size={15} /><span>{rubric.path}</span></button>)}
                    {!filteredAddable.length && <p>No verified rubric records have been imported yet. Browse the source chapter index below.</p>}
                  </div>
                </div>
              )}

              {showHelp && (
                <div className="inline-notice help-notice"><Info size={16} /><span>The matrix remains empty until PDF-derived rubric and remedy-grade records are parsed and verified. The PDF states capitals = 3, italics = 2, ordinary = 1 (PDF page 36).</span><button onClick={() => setShowHelp(false)} aria-label="Dismiss"><X size={15} /></button></div>
              )}

              <div className="matrix-scroll">
                <table className="repertory-matrix">
                  <thead>
                    <tr>
                      <th className="rubric-column-heading">
                        <div className="matrix-heading-label">Rubrics &amp; Remedies</div>
                        <div className="rubric-heading-sub">Select rows to merge or remove</div>
                      </th>
                      {visibleRemedies.map((remedy) => (
                        <th className="remedy-heading" key={remedy.id}>
                          <span className="remedy-abbr" title={remedy.name}>{remedy.abbr}</span>
                          {showTotals && <span className="remedy-total">{remedyTotals[remedy.id].sum}/{remedyTotals[remedy.id].count}</span>}
                          {showAuthors && <span className="remedy-author">{remedy.author}</span>}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id} className={selectedRows.includes(row.id) ? 'row-selected' : ''}>
                        <td className="rubric-cell">
                          <div className="rubric-cell-inner">
                            <input className="row-select" type="checkbox" checked={selectedRows.includes(row.id)} onChange={() => toggleRow(row.id)} aria-label={`Select ${row.path}`} />
                            <div className="rubric-copy">
                              <div className="rubric-path">{row.path}</div>
                              <div className="rubric-meta"><span className="source-chip">{row.source}</span><button className="tiny-icon" title="Copy rubric text" onClick={() => navigator.clipboard?.writeText(row.path)}><Copy size={14} /></button></div>
                            </div>
                            <button className="delete-row" onClick={() => updateRows(rows.filter((item) => item.id !== row.id))} title="Remove rubric"><Trash2 size={16} /></button>
                          </div>
                        </td>
                        {visibleRemedies.map((remedy) => {
                          const grade = row.values[remedy.id];
                          return <td className="grade-cell" key={remedy.id}>{grade ? <span className={gradeClass(grade)}>{showGrades ? grade : ''}</span> : null}</td>;
                        })}
                      </tr>
                    ))}
                    {!rows.length && <tr><td className="empty-matrix" colSpan={visibleRemedies.length + 1}>No verified rubric data has been imported yet. The PDF chapter directory is shown below.</td></tr>}
                  </tbody>
                </table>
              </div>

              <div className="matrix-footer">
                <div className="footer-notice"><Info size={15} /><span>{notice}</span></div>
                <div className="matrix-footer-actions"><span>{rows.length} rubrics · {visibleRemedies.length} remedies</span><button className="remove-selected-button" onClick={removeSelected} disabled={!selectedRows.length}><Trash2 size={14} /> Remove selected</button></div>
              </div>
            </section>
            <section className="library-browser">
              <div className="library-browser-heading">
                <div>
                  <div className="eyebrow">SOURCE INDEX · PDF PAGE {kentSourceCatalog.contentsPdfPage}</div>
                  <h2>Kent repertory chapter library</h2>
                  <p>{kentSourceCatalog.chapters.length} chapter headings copied from the supplied PDF contents. These are internal book pages, not PDF page numbers.</p>
                </div>
                <span className="catalog-status">Chapter index only</span>
              </div>
              <div className="library-chapter-grid">
                {kentSourceCatalog.chapters.map((chapter) => (
                  <article className="library-chapter-card" key={chapter.id}>
                    <div className="chapter-card-main">
                      <strong>{chapter.title}</strong>
                      <span>Book pages {chapter.bookPageStart}–{chapter.bookPageEnd}</span>
                    </div>
                    {chapter.subchapters?.map((subchapter) => (
                      <div className="chapter-subentry" key={subchapter.id}>
                        <span>{subchapter.title}</span>
                        <small>{subchapter.bookPageStart}–{subchapter.bookPageEnd}</small>
                      </div>
                    ))}
                    {chapter.pageSummaryDiscrepancy && (
                      <div className="chapter-source-flag">
                        Page {chapter.pageSummaryDiscrepancy.summaryPdfPage} summary lists {chapter.pageSummaryDiscrepancy.summaryBookPageStart}–{chapter.pageSummaryDiscrepancy.summaryBookPageEnd}; contents page {kentSourceCatalog.contentsPdfPage} lists {chapter.bookPageStart}–{chapter.bookPageEnd}.
                      </div>
                    )}
                  </article>
                ))}
              </div>
              <div className="source-grade-note">
                <Info size={16} />
                <span>Grade key on PDF page {kentSourceCatalog.gradeKey.pdfPage}: Capitals = {kentSourceCatalog.gradeKey.capitals}; Italics = {kentSourceCatalog.gradeKey.italics}; Ordinary = {kentSourceCatalog.gradeKey.ordinary}. Grades will remain hidden until actual rubric tokens have been parsed and checked.</span>
              </div>
            </section>
                        <div className="disclaimer"><Info size={15} /><p><strong>Source-only status:</strong> No sample rubrics, remedies or grades are loaded. The chapter directory comes from the supplied PDF; the structured library is still being prepared and checked.</p></div>
          </>
        )}

        {page === 'home' && <section className="page-card">
          <div className="page-hero"><div className="eyebrow">CURIVA HOMOEOPATHY SOFTWARE</div><h1>Your repertory workspace</h1><p>A focused workspace for rubric selection, remedy comparison, and case study.</p><button className="primary-button" onClick={() => setPage('repertory')}><BookOpen size={17} /> Open Repertory</button></div>
          <div className="dashboard-grid">
            <button className="dashboard-card" onClick={() => setPage('repertory')}><BookOpen /><strong>Repertory</strong><span>Select rubrics and compare remedy grades in a matrix.</span></button>
            <button className="dashboard-card" onClick={() => setPage('materia')}><Activity /><strong>Materia Medica</strong><span>Open the remedy reference area.</span></button>
            <button className="dashboard-card" onClick={() => setPage('cases')}><FolderOpen /><strong>Cases</strong><span>Open the local prototype case workspace.</span></button>
          </div>
        </section>}

        {page === 'materia' && <section className="page-card">
          <div className="page-heading"><div className="eyebrow">REFERENCE LIBRARY</div><h1>Materia Medica</h1><p>The PDF’s remedy abbreviation index (introductory PDF pages 10–18) will be parsed into this library. No external remedy entries are added.</p></div>
          <div className="remedy-library">{remedies.slice(0, 12).map((remedy) => <article className="remedy-card" key={remedy.id}><div className="remedy-avatar">{remedy.abbr.slice(0, 1)}</div><div><strong>{remedy.name}</strong><span>{remedy.abbr} · Author: {remedy.author}</span></div><span className="coming-label">Index preview</span></article>)}</div>
        </section>}

        {page === 'cases' && <section className="page-card">
          <div className="page-heading"><div className="eyebrow">CASE WORKSPACE</div><h1>Cases</h1><p>Prototype case sets are stored only in this browser session. There is no cloud sync or patient account system.</p></div>
          <div className="case-list">{['A', 'B', 'C', 'D'].map((tab) => <button key={tab} className="case-list-card" onClick={() => { setActiveCase(tab); setPage('repertory'); }}><div className="case-list-icon"><FolderOpen /></div><div><strong>Case set {tab}</strong><span>{(caseSets[tab] ?? []).length} verified rubrics selected · local prototype</span></div><ChevronDown className="case-list-arrow" /></button>)}</div>
          <div className="local-data-note"><Info size={16} /> Do not enter identifiable patient details. Case sets are not encrypted or saved to an account.</div>
        </section>}

        {page === 'shop' && <section className="page-card shop-page">
          <div className="shop-icon"><ShoppingBag size={30} /></div><div className="eyebrow">CURIVA STORE</div><h1>Shop</h1><p>The store area is reserved for future Curiva learning resources and software plans. No products or purchases are enabled in this prototype.</p><button className="secondary-button" onClick={() => setPage('repertory')}>Return to Repertory</button>
        </section>}
      </main>

      <footer className="app-footer"><Brand /><span>Curiva HomoeoRepertory Pro · Independent application · Prototype v0.1</span><span>Educational use only</span></footer>
    </div>
  );
}

function csvCell(value: string | number) {
  const text = String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

export default App;
