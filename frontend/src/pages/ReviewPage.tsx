import { useEffect, useMemo, useState } from "react";
import {
  confirmDoc,
  deleteDocument,
  getDocumentSummary,
  getDocuments,
  getStaging,
  patchStaging,
  toErrorMessage,
} from "../api/client";
import { PieSummary, TreemapSummary } from "../components/DashboardCharts";
import type { DocumentListItem, DocumentSummary, RiskLevel, StagingRecord } from "../types";

interface Props {
  defaultDocId?: number | null;
  onDone: () => void;
}

type RiskFilter = "all" | RiskLevel;

const REVIEW_FIELDS = [
  { key: "admission_period", label: "出愿时期", span: 2 },
  { key: "eju_japanese", label: "EJU 日语", span: 1 },
  { key: "eju_general", label: "EJU 综合科目", span: 1 },
  { key: "eju_math", label: "EJU 数学", span: 1 },
  { key: "eju_physics", label: "EJU 物理", span: 1 },
  { key: "eju_chemistry", label: "EJU 化学", span: 1 },
  { key: "eju_biology", label: "EJU 生物", span: 1 },
  { key: "prefecture", label: "都道府县", span: 1 },
  { key: "campus", label: "校区", span: 1 },
  { key: "university", label: "学校名称", span: 2 },
  { key: "faculty", label: "学部", span: 1 },
  { key: "department", label: "学科 / 专业", span: 1 },
  { key: "application_period", label: "出愿期间", span: 2 },
  { key: "deadline_rule", label: "截止规则", span: 1 },
  { key: "eju_session", label: "EJU 场次", span: 1 },
  { key: "english_requirement", label: "英语要求", span: 2 },
  { key: "screening_method", label: "选考方式", span: 2 },
  { key: "screening_schedule", label: "选考日程", span: 2 },
  { key: "result_date", label: "结果发布日期", span: 1 },
  { key: "enrollment_period", label: "入学手续期间", span: 1 },
] as const;

function riskText(risk: RiskLevel | undefined) {
  if (risk === "high") return "高风险";
  if (risk === "medium") return "中风险";
  return "低风险";
}

function riskBadge(risk: RiskLevel | undefined) {
  if (risk === "high") return "badge badge-red";
  if (risk === "medium") return "badge badge-amber";
  return "badge badge-green";
}

function fieldValue(record: StagingRecord | undefined, key: string) {
  if (!record) return "";
  return String(((record as unknown as Record<string, unknown>)[key]) ?? "");
}

export default function ReviewPage({ defaultDocId, onDone }: Props) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [summary, setSummary] = useState<DocumentSummary | null>(null);
  const [rows, setRows] = useState<StagingRecord[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(defaultDocId ?? null);
  const [selectedRowId, setSelectedRowId] = useState<number | null>(null);
  const [docQuery, setDocQuery] = useState("");
  const [docYear, setDocYear] = useState("");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [loadingRows, setLoadingRows] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [deletingDocId, setDeletingDocId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    void refreshDocuments();
  }, []);

  useEffect(() => {
    if (defaultDocId) void openDocument(defaultDocId);
  }, [defaultDocId]);

  const filteredRows = useMemo(() => {
    const sorted = [...rows].sort((a, b) => {
      const rank = (value?: RiskLevel) => (value === "high" ? 0 : value === "medium" ? 1 : 2);
      return rank(a.risk_level) - rank(b.risk_level);
    });
    return riskFilter === "all" ? sorted : sorted.filter((row) => row.risk_level === riskFilter);
  }, [riskFilter, rows]);

  const selectedRow = useMemo(() => rows.find((row) => row.id === selectedRowId) ?? null, [rows, selectedRowId]);

  useEffect(() => {
    if (!selectedRow) return;
    const nextDraft: Record<string, string> = {};
    for (const field of REVIEW_FIELDS) nextDraft[field.key] = fieldValue(selectedRow, field.key);
    setDraft(nextDraft);
  }, [selectedRow]);

  const reviewedCount = rows.filter((row) => Number(row.is_reviewed)).length;
  const pendingHighRisk = rows.some((row) => row.risk_level === "high" && !Number(row.is_reviewed));
  const riskCounts = {
    high: rows.filter((row) => row.risk_level === "high").length,
    medium: rows.filter((row) => row.risk_level === "medium").length,
    low: rows.filter((row) => row.risk_level === "low").length,
  };

  async function refreshDocuments() {
    setLoadingDocs(true);
    try {
      const data = await getDocuments({
        q: docQuery || undefined,
        year: docYear || undefined,
        limit: 100,
      });
      setDocuments(data);
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setLoadingDocs(false);
    }
  }

  async function openDocument(docId: number) {
    setLoadingRows(true);
    setError("");
    setMessage("");
    try {
      const [docSummary, stagingRows] = await Promise.all([getDocumentSummary(docId), getStaging(docId)]);
      setSelectedDocId(docId);
      setSummary(docSummary);
      setRows(stagingRows);
      setSelectedRowId(null);
      setRiskFilter("all");
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setLoadingRows(false);
    }
  }

  async function deleteCurrentDocument(doc: DocumentListItem) {
    const confirmed = window.confirm(`删除“${doc.university_name || doc.filename}”及其对应记录？`);
    if (!confirmed) return;
    setDeletingDocId(doc.doc_id);
    try {
      await deleteDocument(doc.doc_id);
      if (selectedDocId === doc.doc_id) {
        setSelectedDocId(null);
        setSummary(null);
        setRows([]);
        setSelectedRowId(null);
      }
      await refreshDocuments();
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setDeletingDocId(null);
    }
  }

  async function saveCurrent(markReviewed: boolean, goNext: boolean) {
    if (!selectedRow) return;
    setSaving(true);
    setError("");
    try {
      const updated = await patchStaging(selectedRow.id, {
        ...draft,
        ...(markReviewed ? { is_reviewed: 1, needs_review: 0 } : {}),
      });
      const nextRows = rows.map((row) => (row.id === selectedRow.id ? updated : row));
      setRows(nextRows);
      setMessage(markReviewed ? "已保存，并标记为已复核。" : "修改已保存。");
      if (goNext) {
        const nextPending = filteredRows.find((row) => row.id !== selectedRow.id && !Number(row.is_reviewed));
        setSelectedRowId(nextPending?.id ?? null);
      }
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setSaving(false);
    }
  }

  async function confirmCurrentDocument() {
    if (!selectedDocId || pendingHighRisk) return;
    setConfirming(true);
    setError("");
    try {
      await confirmDoc(selectedDocId);
      setMessage("这份文档已经确认入库。");
      onDone();
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className="page-shell">
      <section className="hero-panel">
        <div className="split-row split-row-start">
          <div>
            <div className="section-kicker">人工复核</div>
            <h2 className="section-title">逐条校对待确认内容</h2>
            <p className="section-copy">先选文档，再进入记录队列；每条内容都可以直接进入二级详情处理。</p>
          </div>
          <div className="hero-metrics">
            <div className="metric-card">
              <span className="metric-label">文档</span>
              <strong className="metric-value">{documents.length}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">待处理</span>
              <strong className="metric-value">{Math.max(rows.length - reviewedCount, 0)}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">高风险</span>
              <strong className="metric-value">{riskCounts.high}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="content-grid">
        <aside className="sidebar-panel">
          <div className="toolbar-shell">
            <div className="sidebar-section-label">入口</div>
            <div className="split-row" style={{ marginBottom: 12 }}>
              <div>
                <h3 className="panel-title">文档列表</h3>
                <p className="panel-copy">从左侧选择一份文档开始复核。</p>
              </div>
              <span className="badge badge-gray">{documents.length} 份</span>
            </div>

            <div className="list-stack">
              <label className="field-wrap">
                <span className="field-label">搜索</span>
                <input className="field" value={docQuery} onChange={(event) => setDocQuery(event.target.value)} placeholder="学校或文件名" />
              </label>
              <label className="field-wrap">
                <span className="field-label">年份</span>
                <input className="field" value={docYear} onChange={(event) => setDocYear(event.target.value)} placeholder="2026" />
              </label>
              <button className="btn btn-primary" onClick={() => void refreshDocuments()} type="button">
                {loadingDocs ? "刷新中..." : "刷新列表"}
              </button>
            </div>
          </div>

          <div className="document-list">
            {documents.map((doc) => (
              <button
                key={doc.doc_id}
                className={`item-card${selectedDocId === doc.doc_id ? " is-active" : ""}`}
                onClick={() => void openDocument(doc.doc_id)}
                type="button"
              >
                <div className="item-card-topline">
                  <span className="badge badge-gray">#{doc.doc_id}</span>
                  <span className="badge badge-blue">{doc.admission_year || "未标注年份"}</span>
                </div>
                <h4 className="item-title">{doc.university_name || "未命名文档"}</h4>
                <p className="item-subtitle">{doc.filename}</p>
                <div className="item-meta">
                  <span className="badge badge-gray">待复核 {doc.staging_count}</span>
                  <span className="badge badge-gray">已入库 {doc.confirmed_count}</span>
                </div>
                <div className="inline-actions">
                  <button
                    className="btn btn-red"
                    disabled={deletingDocId === doc.doc_id}
                    onClick={(event) => {
                      event.stopPropagation();
                      void deleteCurrentDocument(doc);
                    }}
                    type="button"
                  >
                    {deletingDocId === doc.doc_id ? "删除中..." : "删除"}
                  </button>
                </div>
              </button>
            ))}
          </div>
        </aside>

        <div className="item-detail">
          {error && <div className="message-box error">{error}</div>}

          {!selectedDocId && (
            <div className="empty-state empty-state-quiet">
              <div className="card-kicker">等待选择</div>
              <h3 className="panel-title">请选择一份文档</h3>
              <p className="panel-copy">文档打开后，右侧会展示当前队列和二级详情入口。</p>
            </div>
          )}

          {selectedDocId && !selectedRow && (
            <div className="detail-shell">
              <div className="detail-header">
                <div>
                  <div className="card-kicker">记录队列</div>
                  <h3 className="panel-title">{summary?.university_name || "人工复核队列"}</h3>
                  <p className="panel-copy">从高风险开始，左键进入每条记录的二级详情。</p>
                </div>
                <div className="item-meta">
                  <span className="badge badge-gray">共 {rows.length} 条</span>
                  <span className="badge badge-blue">已复核 {reviewedCount}</span>
                  {loadingRows && <span className="badge badge-gray">载入中...</span>}
                </div>
              </div>

              <div className="inline-actions inline-actions-tight">
                {[
                  { key: "all" as RiskFilter, label: `全部 ${rows.length}` },
                  { key: "high" as RiskFilter, label: `高风险 ${riskCounts.high}` },
                  { key: "medium" as RiskFilter, label: `中风险 ${riskCounts.medium}` },
                  { key: "low" as RiskFilter, label: `低风险 ${riskCounts.low}` },
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

              <TreemapSummary
                title="风险分布"
                subtitle="优先处理高风险记录。"
                data={[
                  { label: "高风险", value: riskCounts.high, color: "linear-gradient(180deg, rgba(191, 53, 53, 0.9), rgba(153, 27, 27, 0.82))" },
                  { label: "中风险", value: riskCounts.medium, color: "linear-gradient(180deg, rgba(190, 116, 18, 0.88), rgba(146, 64, 14, 0.82))" },
                  { label: "低风险", value: riskCounts.low, color: "linear-gradient(180deg, rgba(16, 127, 95, 0.84), rgba(6, 95, 70, 0.8))" },
                ]}
              />

              <div className="document-list">
                {filteredRows.map((row) => (
                  <button key={row.id} className="item-card" onClick={() => setSelectedRowId(row.id)} type="button">
                    <div className="detail-header">
                      <div>
                        <h4 className="item-title">{row.faculty || row.department || `记录 #${row.id}`}</h4>
                        <p className="item-subtitle">{row.department || row.university || "进入详情"}</p>
                      </div>
                      <div className="item-meta">
                        <span className={riskBadge(row.risk_level)}>{riskText(row.risk_level)}</span>
                        <span className="badge badge-gray">置信度 {Number(row.confidence ?? 0).toFixed(2)}</span>
                        <span className={Number(row.is_reviewed) ? "badge badge-green" : "badge badge-amber"}>
                          {Number(row.is_reviewed) ? "已复核" : "待复核"}
                        </span>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {selectedDocId && selectedRow && (
            <div className="detail-shell detail-shell-editing">
              <div className="detail-header">
                <div>
                  <button className="btn btn-ghost detail-back" onClick={() => setSelectedRowId(null)} type="button">
                    返回队列
                  </button>
                  <div className="card-kicker" style={{ marginTop: 16 }}>
                    人工复核
                  </div>
                  <h3 className="panel-title">记录详情</h3>
                  <p className="secondary-note">
                    {summary?.university_name || "当前文档"} · {riskText(selectedRow.risk_level)}
                  </p>
                </div>
                <div className="item-meta">
                  <span className={riskBadge(selectedRow.risk_level)}>{riskText(selectedRow.risk_level)}</span>
                  <span className="badge badge-gray">页码 {selectedRow.page_number ?? "—"}</span>
                </div>
              </div>

              <PieSummary
                title="复核进度"
                subtitle="当前文档的处理进度。"
                totalLabel="完成度"
                totalValue={rows.length ? `${Math.round((reviewedCount / rows.length) * 100)}%` : "0%"}
                data={[
                  { label: "已复核", value: reviewedCount, color: "#111827" },
                  { label: "待复核", value: Math.max(rows.length - reviewedCount, 0), color: "rgba(59, 130, 246, 0.78)" },
                ]}
              />

              <div className="detail-grid detail-grid-forms">
                {REVIEW_FIELDS.map((field) => (
                  <div key={field.key} className={`detail-field${field.span === 2 ? " is-span-2" : ""}`}>
                    <span className="detail-label">{field.label}</span>
                    <textarea
                      className="field-textarea"
                      style={field.span === 2 ? undefined : { minHeight: 88 }}
                      value={draft[field.key] || ""}
                      onChange={(event) => setDraft((prev) => ({ ...prev, [field.key]: event.target.value }))}
                    />
                    {selectedRow.field_evidence?.[field.key]?.text && (
                      <div className="evidence-snippet">
                        <span className="field-label">证据</span>
                        <div>{selectedRow.field_evidence[field.key]?.text}</div>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {message && !error && <div className="message-box info">{message}</div>}

              <div className="inline-actions inline-actions-wide">
                <button className="btn btn-ghost" disabled={saving} onClick={() => void saveCurrent(false, false)} type="button">
                  保存
                </button>
                <button className="btn btn-primary" disabled={saving} onClick={() => void saveCurrent(true, true)} type="button">
                  保存并下一条
                </button>
                <button className="btn btn-green" disabled={confirming || pendingHighRisk} onClick={() => void confirmCurrentDocument()} type="button">
                  {confirming ? "入库中..." : "确认整份文档入库"}
                </button>
              </div>

              {pendingHighRisk && <div className="secondary-note">仍有高风险记录未复核，当前不能直接入库。</div>}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
