import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  confirmDoc,
  deleteDocument,
  deleteStaging,
  getDocumentSummary,
  getDocuments,
  getQualityMetrics,
  getStaging,
  patchStaging,
  toErrorMessage,
} from "../api/client";
import type {
  DocumentListItem,
  DocumentSummary,
  QualityMetricsResponse,
  RiskLevel,
  StagingRecord,
} from "../types";

interface Props {
  defaultDocId?: number | null;
  onDone: () => void;
}

type RiskFilter = "all" | RiskLevel;

const REVIEW_FIELDS = [
  { key: "university", label: "University", span: 2, critical: false },
  { key: "faculty", label: "Faculty", span: 1, critical: false },
  { key: "department", label: "Department / Major", span: 1, critical: false },
  { key: "application_period", label: "Application Period", span: 2, critical: true },
  { key: "deadline_rule", label: "Deadline Rule", span: 1, critical: true },
  { key: "eju_session", label: "EJU Session", span: 1, critical: true },
  { key: "eju_japanese", label: "EJU Japanese", span: 1, critical: true },
  { key: "eju_general", label: "EJU General", span: 1, critical: true },
  { key: "eju_math", label: "EJU Math", span: 1, critical: true },
  { key: "eju_physics", label: "EJU Physics", span: 1, critical: true },
  { key: "eju_chemistry", label: "EJU Chemistry", span: 1, critical: true },
  { key: "eju_biology", label: "EJU Biology", span: 1, critical: true },
  { key: "english_requirement", label: "English Requirement", span: 2, critical: true },
  { key: "screening_method", label: "Screening Method", span: 2, critical: true },
  { key: "screening_schedule", label: "Screening Schedule", span: 2, critical: true },
  { key: "result_date", label: "Result Date", span: 2, critical: true },
  { key: "enrollment_period", label: "Enrollment Period", span: 2, critical: true },
  { key: "prefecture", label: "Prefecture", span: 1, critical: false },
  { key: "campus", label: "Campus", span: 1, critical: false },
] as const;

function riskRank(risk: RiskLevel | undefined): number {
  if (risk === "high") return 0;
  if (risk === "medium") return 1;
  return 2;
}

function riskLabel(risk: RiskLevel | undefined): string {
  if (risk === "high") return "High risk";
  if (risk === "medium") return "Medium risk";
  return "Low risk";
}

function riskDescription(risk: RiskLevel | undefined): string {
  if (risk === "high") return "Critical fields are low-confidence or inconsistent. Resolve this row before mass confirmation.";
  if (risk === "medium") return "Most values look usable, but there are still a few fields worth validating manually.";
  return "This row looks stable. It can usually be reviewed quickly after the higher-risk queue is cleared.";
}

function riskBadgeClass(risk: RiskLevel | undefined): string {
  if (risk === "high") return "badge badge-red";
  if (risk === "medium") return "badge badge-amber";
  return "badge badge-green";
}

function fmtDate(value?: string | null): string {
  if (!value) return "Not available";
  return value.replace("T", " ").slice(0, 16);
}

function fieldValue(record: StagingRecord | undefined, key: string): string {
  if (!record) return "";
  return String(((record as unknown as Record<string, unknown>)[key]) ?? "");
}

export default function ReviewPage({ defaultDocId, onDone }: Props) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [summary, setSummary] = useState<DocumentSummary | null>(null);
  const [docQuality, setDocQuality] = useState<QualityMetricsResponse | null>(null);
  const [rows, setRows] = useState<StagingRecord[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(defaultDocId ?? null);
  const [selectedRowId, setSelectedRowId] = useState<number | null>(null);
  const [docIdInput, setDocIdInput] = useState(defaultDocId ? String(defaultDocId) : "");
  const [docQuery, setDocQuery] = useState("");
  const [docYear, setDocYear] = useState("");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [loadingRows, setLoadingRows] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [bulkReviewing, setBulkReviewing] = useState(false);
  const [deletingDocId, setDeletingDocId] = useState<number | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    void loadDocuments();
  }, []);

  useEffect(() => {
    if (defaultDocId) {
      setSelectedDocId(defaultDocId);
      setDocIdInput(String(defaultDocId));
      void loadDocument(defaultDocId);
    }
  }, [defaultDocId]);

  const orderedRows = useMemo(() => {
    return [...rows].sort((a, b) => {
      const riskCmp = riskRank(a.risk_level) - riskRank(b.risk_level);
      if (riskCmp !== 0) return riskCmp;
      const reviewCmp = Number(a.is_reviewed || 0) - Number(b.is_reviewed || 0);
      if (reviewCmp !== 0) return reviewCmp;
      return Number(a.confidence ?? 0) - Number(b.confidence ?? 0);
    });
  }, [rows]);

  const filteredRows = useMemo(() => {
    if (riskFilter === "all") return orderedRows;
    return orderedRows.filter((row) => row.risk_level === riskFilter);
  }, [orderedRows, riskFilter]);

  const currentRow = useMemo(() => {
    if (!filteredRows.length) return undefined;
    return filteredRows.find((row) => row.id === selectedRowId) ?? filteredRows[0];
  }, [filteredRows, selectedRowId]);

  useEffect(() => {
    if (currentRow) {
      setSelectedRowId(currentRow.id);
    } else {
      setSelectedRowId(null);
    }
  }, [currentRow?.id]);

  useEffect(() => {
    if (!currentRow) return;
    const nextDraft: Record<string, string> = {};
    for (const field of REVIEW_FIELDS) {
      nextDraft[field.key] = fieldValue(currentRow, field.key);
    }
    setDraft(nextDraft);
    setMsg("");
    setErr("");
  }, [currentRow?.id]);

  const metrics = useMemo(() => {
    const high = rows.filter((row) => row.risk_level === "high").length;
    const medium = rows.filter((row) => row.risk_level === "medium").length;
    const low = rows.filter((row) => row.risk_level === "low").length;
    const reviewed = rows.filter((row) => Number(row.is_reviewed)).length;
    return { high, medium, low, reviewed, total: rows.length };
  }, [rows]);

  const blockingHighRisk = rows.some((row) => row.risk_level === "high" && !Number(row.is_reviewed));

  async function loadDocuments() {
    setLoadingDocs(true);
    setErr("");
    try {
      const data = await getDocuments({
        q: docQuery || undefined,
        year: docYear || undefined,
        limit: 100,
      });
      setDocuments(data);
    } catch (error) {
      setErr(toErrorMessage(error));
    } finally {
      setLoadingDocs(false);
    }
  }

  async function loadDocument(docId: number) {
    setLoadingRows(true);
    setErr("");
    setMsg("");
    try {
      const [docSummary, stagingRows, quality] = await Promise.all([
        getDocumentSummary(docId),
        getStaging(docId),
        getQualityMetrics(docId),
      ]);
      setSelectedDocId(docId);
      setDocIdInput(String(docId));
      setSummary(docSummary);
      setDocQuality(quality);
      setRows(stagingRows);
      setSelectedRowId(stagingRows[0]?.id ?? null);
      setMsg(
        stagingRows.length
          ? `Loaded ${stagingRows.length} row(s). The queue is now sorted so the riskiest items surface first.`
          : "This document does not have staging rows yet.",
      );
    } catch (error) {
      setErr(toErrorMessage(error));
    } finally {
      setLoadingRows(false);
    }
  }

  async function refreshCurrentDocument(docId: number) {
    const [docSummary, stagingRows, quality] = await Promise.all([
      getDocumentSummary(docId),
      getStaging(docId),
      getQualityMetrics(docId),
    ]);
    setSummary(docSummary);
    setDocQuality(quality);
    setRows(stagingRows);
    const docs = await getDocuments({
      q: docQuery || undefined,
      year: docYear || undefined,
      limit: 100,
    });
    setDocuments(docs);
  }

  async function removeDocument(doc: DocumentListItem) {
    if (deletingDocId) return;
    const ok = window.confirm(
      `Delete document "${doc.university_name || doc.filename}" and its staging/confirmed records? Local PDF files are not deleted.`,
    );
    if (!ok) return;
    setDeletingDocId(doc.doc_id);
    setErr("");
    setMsg("");
    try {
      const result = await deleteDocument(doc.doc_id);
      setDocuments((prev) => prev.filter((item) => item.doc_id !== doc.doc_id));
      if (selectedDocId === doc.doc_id) {
        setSelectedDocId(null);
        setDocIdInput("");
        setSummary(null);
        setDocQuality(null);
        setRows([]);
        setSelectedRowId(null);
      }
      setMsg(`Deleted document. Removed ${result.deleted_staging} staging row(s) and ${result.deleted_records} confirmed row(s).`);
    } catch (error) {
      setErr(toErrorMessage(error));
    } finally {
      setDeletingDocId(null);
    }
  }

  async function savePatch(patch: Record<string, unknown>, successMessage: string) {
    if (!currentRow || saving) return;
    setSaving(true);
    setErr("");
    setMsg("");
    try {
      const updated = await patchStaging(currentRow.id, patch);
      setRows((prev) => prev.map((item) => (item.id === currentRow.id ? updated : item)));
      setMsg(successMessage);
    } catch (error) {
      setErr(toErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function removeCurrent() {
    if (!currentRow || saving) return;
    setSaving(true);
    setErr("");
    setMsg("");
    try {
      await deleteStaging(currentRow.id);
      const nextRows = rows.filter((item) => item.id !== currentRow.id);
      setRows(nextRows);
      setSelectedRowId(nextRows[0]?.id ?? null);
      setMsg("The selected staging row was removed.");
      if (selectedDocId) await refreshCurrentDocument(selectedDocId);
    } catch (error) {
      setErr(toErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function confirmCurrentDocument() {
    if (!selectedDocId || confirming || blockingHighRisk) return;
    setConfirming(true);
    setErr("");
    setMsg("");
    try {
      const result = await confirmDoc(selectedDocId);
      await refreshCurrentDocument(selectedDocId);
      setMsg(`Confirmation completed. ${result.confirmed} row(s) inserted, ${result.skipped} skipped.`);
      setTimeout(() => onDone(), 1200);
    } catch (error) {
      setErr(toErrorMessage(error));
    } finally {
      setConfirming(false);
    }
  }

  async function bulkMarkLowRiskReviewed() {
    if (!selectedDocId || bulkReviewing) return;
    const targets = rows.filter((row) => row.risk_level === "low" && !Number(row.is_reviewed));
    if (!targets.length) {
      setMsg("There are no low-risk rows waiting for bulk review.");
      return;
    }

    setBulkReviewing(true);
    setErr("");
    setMsg("");
    try {
      await Promise.all(
        targets.map((row) =>
          patchStaging(row.id, {
            is_reviewed: 1,
            needs_review: 0,
          }),
        ),
      );
      await refreshCurrentDocument(selectedDocId);
      setMsg(`Marked ${targets.length} low-risk row(s) as reviewed.`);
    } catch (error) {
      setErr(toErrorMessage(error));
    } finally {
      setBulkReviewing(false);
    }
  }

  function updateDraft(field: string, value: string) {
    setDraft((prev) => ({ ...prev, [field]: value }));
  }

  const statusTitle = !selectedDocId
    ? "Choose a document and the queue will organize itself for you"
    : blockingHighRisk
      ? `${metrics.high} high-risk row(s) still need attention before confirmation`
      : `${metrics.total} row(s) are loaded and the review queue is in a healthy state`;

  const statusDescription = !selectedDocId
    ? "This screen now presents the review workflow like an operations desk: document selection on the left, risk-guided record review in the center, and a fast queue on the right."
    : blockingHighRisk
      ? "High risk usually means critical fields have weak evidence or low confidence. Resolve those rows first so confirmation stays safe."
      : metrics.low > 0
        ? `There are ${metrics.low} low-risk row(s) that can usually be reviewed in bulk once the priority queue is clear.`
        : "The document is ready for a final pass before confirmation into records.";

  return (
    <div className="page-shell">
      <section className="hero-panel">
        <div className="hero-grid">
          <div>
            <div className="section-eyebrow">Step 2 · Review</div>
            <h2 className="section-title">Risk-guided review queue</h2>
            <p className="section-copy">
              The review stage now behaves like a professional internal SaaS workspace: triage documents, surface risky rows first,
              inspect evidence snippets inline, and only unlock confirmation after the highest-risk items are reviewed.
            </p>
          </div>

          <div className="progress-stack">
            <div className="mini-stat">
              <span className="mini-stat-label">Selected document</span>
              <span className="mini-stat-value">{selectedDocId ? `#${selectedDocId}` : "None"}</span>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Reviewed rows</span>
              <span className="mini-stat-value">{metrics.reviewed}/{metrics.total}</span>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Confirmation gate</span>
              <span className="mini-stat-value">{blockingHighRisk ? "Locked" : "Available"}</span>
            </div>
          </div>
        </div>
      </section>

      <section className={`tone-banner ${blockingHighRisk ? "warning" : selectedDocId ? "success" : "neutral"}`}>
        <div>
          <h3 className="tone-title">{statusTitle}</h3>
          <p className="tone-copy">{statusDescription}</p>
        </div>
        <div className="status-grid">
          <div className="status-pill">
            <span>High risk</span>
            <strong>{metrics.high}</strong>
          </div>
          <div className="status-pill">
            <span>Medium risk</span>
            <strong>{metrics.medium}</strong>
          </div>
          <div className="status-pill">
            <span>Low risk</span>
            <strong>{metrics.low}</strong>
          </div>
          <div className="status-pill">
            <span>Reviewed</span>
            <strong>{metrics.reviewed}</strong>
          </div>
        </div>
      </section>

      <section className="doc-layout">
        <aside className="sidebar-panel">
          <div className="panel">
            <div className="split-row" style={{ marginBottom: 12 }}>
              <div>
                <h3 className="panel-title">Document tray</h3>
                <p className="panel-copy">Filter documents, open by ID, and keep the intake backlog manageable.</p>
              </div>
              <span className="badge badge-gray">{documents.length} loaded</span>
            </div>

            <div className="input-grid" style={{ marginBottom: 10 }}>
              <label className="field-wrap">
                <span className="field-label">Search documents</span>
                <input className="field" value={docQuery} onChange={(event) => setDocQuery(event.target.value)} placeholder="University / file / URL" />
              </label>
              <label className="field-wrap">
                <span className="field-label">Year</span>
                <input className="field" value={docYear} onChange={(event) => setDocYear(event.target.value)} placeholder="2026" />
              </label>
            </div>

            <div className="inline-actions" style={{ marginBottom: 10 }}>
              <button className="btn btn-primary" onClick={() => void loadDocuments()} type="button">
                {loadingDocs ? "Loading..." : "Refresh tray"}
              </button>
              <button
                className="btn btn-ghost"
                onClick={() => {
                  const docId = Number(docIdInput);
                  if (docId) void loadDocument(docId);
                }}
                type="button"
              >
                Open by ID
              </button>
            </div>

            <label className="field-wrap" style={{ marginBottom: 14 }}>
              <span className="field-label">Document ID</span>
              <input
                className="field"
                value={docIdInput}
                onChange={(event) => setDocIdInput(event.target.value)}
                placeholder="Enter a doc_id"
              />
            </label>

            <div className="list-stack" style={{ maxHeight: 520, overflowY: "auto" }}>
              {documents.map((doc) => {
                const active = selectedDocId === doc.doc_id;
                return (
                  <button
                    key={doc.doc_id}
                    className={`doc-card${active ? " is-active" : ""}`}
                    onClick={() => void loadDocument(doc.doc_id)}
                    type="button"
                  >
                    <div className="queue-head">
                      <div>
                        <h4 className="doc-title">{doc.university_name || "Unnamed document"}</h4>
                        <div className="doc-meta">{doc.filename}</div>
                      </div>
                      <span className="badge badge-gray">#{doc.doc_id}</span>
                    </div>

                    <div className="doc-meta" style={{ marginTop: 10 }}>
                      {doc.admission_year || "No year"} · staging {doc.staging_count} · confirmed {doc.confirmed_count}
                    </div>
                    <div className="doc-meta">{fmtDate(doc.created_at)}</div>

                    <div className="inline-actions" style={{ marginTop: 12 }}>
                      <button
                        className="btn btn-red"
                        disabled={deletingDocId === doc.doc_id}
                        onClick={(event) => {
                          event.stopPropagation();
                          void removeDocument(doc);
                        }}
                        type="button"
                      >
                        {deletingDocId === doc.doc_id ? "Deleting..." : "Delete"}
                      </button>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="panel">
            <h3 className="panel-title">Document summary</h3>
            {summary ? (
              <div className="list-stack">
                <div className="summary-box" style={{ background: "rgba(248, 250, 252, 0.92)", border: "1px solid rgba(148, 163, 184, 0.18)" }}>
                  <div className="field-label">University</div>
                  <div className="muted-text">{summary.university_name || "Unknown"}</div>
                </div>
                <div className="summary-box" style={{ background: "rgba(248, 250, 252, 0.92)", border: "1px solid rgba(148, 163, 184, 0.18)" }}>
                  <div className="field-label">Status snapshot</div>
                  <div className="muted-text">
                    {summary.status || "Unknown"} · staging {summary.staging_count} · review {summary.review_count ?? 0} · confirmed {summary.confirmed_count}
                  </div>
                </div>
                <div className="summary-box" style={{ background: "rgba(248, 250, 252, 0.92)", border: "1px solid rgba(148, 163, 184, 0.18)" }}>
                  <div className="field-label">Average confidence</div>
                  <div className="muted-text">{summary.avg_confidence?.toFixed(2) ?? "0.00"}</div>
                </div>
                {summary.source_url && (
                  <a href={summary.source_url} target="_blank" rel="noreferrer" className="btn btn-ghost">
                    Open original source
                  </a>
                )}
              </div>
            ) : (
              <div className="empty-state">
                <h4 className="empty-title">No document selected</h4>
                <p className="empty-copy">Choose a document to populate its quality snapshot and review queue.</p>
              </div>
            )}
          </div>

          {docQuality && (
            <div className="panel">
              <h3 className="panel-title">Quality snapshot</h3>
              <div className="list-stack">
                <div className="summary-box" style={{ background: "rgba(248, 250, 252, 0.92)", border: "1px solid rgba(148, 163, 184, 0.18)" }}>
                  <div className="field-label">Risk distribution</div>
                  <div className="muted-text">
                    High {docQuality.risk_distribution.high || 0} · Medium {docQuality.risk_distribution.medium || 0} · Low {docQuality.risk_distribution.low || 0}
                  </div>
                </div>
                <div className="summary-box" style={{ background: "rgba(248, 250, 252, 0.92)", border: "1px solid rgba(148, 163, 184, 0.18)" }}>
                  <div className="field-label">Most edited fields</div>
                  <div className="muted-text">
                    {(docQuality.top_modified_fields || [])
                      .slice(0, 3)
                      .map((item) => `${item.field} (${item.count})`)
                      .join(", ") || "No manual edits captured yet."}
                  </div>
                </div>
                <div className="summary-box" style={{ background: "rgba(248, 250, 252, 0.92)", border: "1px solid rgba(148, 163, 184, 0.18)" }}>
                  <div className="field-label">Coverage alerts</div>
                  <div className="muted-text">
                    {docQuality.field_coverage
                      .filter((item) => item.fill_rate < 0.7)
                      .slice(0, 3)
                      .map((item) => `${item.field} ${Math.round(item.fill_rate * 100)}%`)
                      .join(" · ") || "No low-coverage key fields in this snapshot."}
                  </div>
                </div>
              </div>
            </div>
          )}
        </aside>

        <section className="record-shell">
          <div className="toolbar-shell">
            <div className="toolbar-row">
              <div>
                <h3 className="panel-title">Review controls</h3>
                <p className="panel-copy">
                  The queue is sorted by high → medium → low risk. Confirmation only unlocks when high-risk rows are not left unreviewed.
                </p>
              </div>
              <div className="inline-actions">
                {[
                  { key: "all" as RiskFilter, label: `All ${metrics.total}` },
                  { key: "high" as RiskFilter, label: `High ${metrics.high}` },
                  { key: "medium" as RiskFilter, label: `Medium ${metrics.medium}` },
                  { key: "low" as RiskFilter, label: `Low ${metrics.low}` },
                ].map((item) => (
                  <button
                    key={item.key}
                    className={`filter-chip${riskFilter === item.key ? " is-active" : ""}`}
                    onClick={() => setRiskFilter(item.key)}
                    type="button"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="toolbar-flex" style={{ marginTop: 14 }}>
              <div className="inline-actions">
                <button className="btn btn-ghost" onClick={() => void bulkMarkLowRiskReviewed()} disabled={bulkReviewing} type="button">
                  {bulkReviewing ? "Marking..." : "Mark low-risk rows reviewed"}
                </button>
                <span className="badge badge-gray">Reviewed {metrics.reviewed}/{metrics.total}</span>
              </div>

              <button
                className="btn btn-green"
                onClick={() => void confirmCurrentDocument()}
                disabled={!selectedDocId || confirming || !rows.length || blockingHighRisk}
                type="button"
              >
                {confirming ? "Confirming..." : "Confirm into records"}
              </button>
            </div>
          </div>

          <div className="metric-grid">
            {[
              { label: "High risk", value: metrics.high, copy: "Immediate review priority", className: "badge badge-red" },
              { label: "Medium risk", value: metrics.medium, copy: "Needs targeted validation", className: "badge badge-amber" },
              { label: "Low risk", value: metrics.low, copy: "Eligible for quick pass", className: "badge badge-green" },
              { label: "Reviewed", value: metrics.reviewed, copy: "Human-reviewed rows", className: "badge badge-blue" },
            ].map((card) => (
              <div key={card.label} className="metric-card">
                <div className="split-row" style={{ marginBottom: 8 }}>
                  <div className="metric-label">{card.label}</div>
                  <span className={card.className}>{card.label}</span>
                </div>
                <div className="metric-value">{card.value}</div>
                <div className="metric-copy">{card.copy}</div>
              </div>
            ))}
          </div>

          {msg && <div className="message-box info">{msg}</div>}
          {err && <div className="message-box error">{err}</div>}

          {!currentRow && !loadingRows && (
            <div className="empty-state">
              <h3 className="empty-title">No review row selected</h3>
              <p className="empty-copy">Pick a document from the tray and the system will route you to the most important row first.</p>
            </div>
          )}

          {currentRow && (
            <div className="review-layout">
              <div className="panel">
                <div className="toolbar-flex" style={{ marginBottom: 18 }}>
                  <div>
                    <span className={riskBadgeClass(currentRow.risk_level)}>{riskLabel(currentRow.risk_level)}</span>
                    <h3 className="panel-title" style={{ marginTop: 10 }}>
                      Review row #{currentRow.id}
                    </h3>
                    <p className="panel-copy">{riskDescription(currentRow.risk_level)}</p>
                  </div>

                  <div className="list-stack" style={{ minWidth: 200 }}>
                    <span className="badge badge-gray">Confidence {Number(currentRow.confidence ?? 0).toFixed(2)}</span>
                    <span className={Number(currentRow.is_reviewed) ? "badge badge-green" : "badge badge-amber"}>
                      {Number(currentRow.is_reviewed) ? "Reviewed" : "Needs review"}
                    </span>
                    <span className="badge badge-gray">Page {currentRow.page_number ?? "—"}</span>
                    <span className="badge badge-gray">Reviewed at {fmtDate(currentRow.reviewed_at)}</span>
                  </div>
                </div>

                <div className="summary-box" style={{ background: "rgba(248, 250, 252, 0.92)", border: "1px solid rgba(148, 163, 184, 0.18)", marginBottom: 18 }}>
                  <strong style={{ display: "block", marginBottom: 6 }}>Review guidance</strong>
                  <span className="helper-text" style={{ color: "var(--ink2)" }}>
                    Critical fields show stronger warnings when confidence is weak. Evidence snippets stay beside the fields they support so reviewers do not need to jump around the interface.
                  </span>
                </div>

                <div className="field-grid">
                  {REVIEW_FIELDS.map((field) => {
                    const confidence = Number(currentRow.field_confidence?.[field.key] ?? 0);
                    const evidence = currentRow.field_evidence?.[field.key];
                    const modified = (currentRow.manual_modified_fields || []).includes(field.key);
                    const shouldWarn = field.critical && confidence < 0.8;
                    const textarea = field.span === 2;
                    const inputStyle: CSSProperties = textarea
                      ? { minHeight: 96 }
                      : {};

                    return (
                      <div
                        key={field.key}
                        className={`review-field${field.span === 2 ? " is-span-2" : ""}${field.critical ? " is-critical" : ""}${shouldWarn ? " is-warning" : ""}`}
                      >
                        <div className="field-header">
                          <span className="field-name">{field.label}</span>
                          <div className="inline-actions">
                            {field.critical && (
                              <span className={shouldWarn ? "badge badge-red" : "badge badge-blue"}>
                                {shouldWarn ? "Priority check" : `Confidence ${confidence.toFixed(2)}`}
                              </span>
                            )}
                            {modified && <span className="badge badge-green">Manually edited</span>}
                          </div>
                        </div>

                        {textarea ? (
                          <textarea
                            value={draft[field.key] || ""}
                            onChange={(event) => updateDraft(field.key, event.target.value)}
                            className="field-textarea"
                            style={inputStyle}
                          />
                        ) : (
                          <input
                            value={draft[field.key] || ""}
                            onChange={(event) => updateDraft(field.key, event.target.value)}
                            className="field"
                            style={inputStyle}
                          />
                        )}

                        {field.critical && evidence?.text && (
                          <div className="evidence-box">
                            <div className="field-label">Evidence snippet {evidence.page ? `(p.${evidence.page})` : ""}</div>
                            <div className="muted-text">{evidence.text}</div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {(currentRow.warnings_json || []).length > 0 && (
                  <div className="warning-box" style={{ marginTop: 18 }}>
                    <h4 className="warning-title">System warnings</h4>
                    <div className="warning-stack">
                      {(currentRow.warnings_json || []).map((warning, index) => (
                        <div key={`${warning}-${index}`} className="muted-text">
                          • {warning}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="inline-actions" style={{ marginTop: 18 }}>
                  <button
                    className="btn btn-ghost"
                    onClick={() => void savePatch({ ...draft, is_reviewed: 1 }, "Changes saved and the row was marked reviewed.")}
                    disabled={saving}
                    type="button"
                  >
                    Save
                  </button>
                  <button
                    className="btn btn-amber"
                    onClick={() => void savePatch({ is_reviewed: 1, reviewed_at: "" }, "This row was marked reviewed.")}
                    disabled={saving}
                    type="button"
                  >
                    Mark reviewed
                  </button>
                  <button
                    className="btn btn-green"
                    onClick={() => void savePatch({ ...draft, is_reviewed: 1, needs_review: 0 }, "Changes saved and the row is now marked reviewed.")}
                    disabled={saving}
                    type="button"
                  >
                    Save and close risk
                  </button>
                  <button className="btn btn-red" onClick={() => void removeCurrent()} disabled={saving} type="button">
                    Delete row
                  </button>
                </div>
              </div>

              <aside className="panel">
                <div className="split-row" style={{ marginBottom: 12 }}>
                  <div>
                    <h3 className="panel-title">Queue</h3>
                    <p className="panel-copy">Work top-to-bottom to keep the review motion steady.</p>
                  </div>
                  <span className="badge badge-gray">{riskFilter === "all" ? "All risks" : riskLabel(riskFilter)}</span>
                </div>

                <div className="list-stack" style={{ maxHeight: 760, overflowY: "auto" }}>
                  {filteredRows.map((row) => {
                    const active = row.id === currentRow.id;
                    return (
                      <button
                        key={row.id}
                        className={`queue-card${active ? " is-active" : ""}`}
                        onClick={() => setSelectedRowId(row.id)}
                        type="button"
                      >
                        <div className="queue-head">
                          <div>
                            <h4 className="queue-title">{row.faculty || row.department || `Row #${row.id}`}</h4>
                            <div className="queue-meta">{row.department || row.university || "Unlabeled row"}</div>
                          </div>
                          <span className={riskBadgeClass(row.risk_level)}>{riskLabel(row.risk_level)}</span>
                        </div>

                        <div className="queue-meta" style={{ marginTop: 8 }}>
                          Confidence {Number(row.confidence ?? 0).toFixed(2)}
                        </div>
                        <div className="queue-meta">
                          {Number(row.is_reviewed) ? "Reviewed" : "Needs review"} · {Number(row.is_confirmed) ? "Confirmed" : "Not confirmed"}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </aside>
            </div>
          )}
        </section>
      </section>
    </div>
  );
}
