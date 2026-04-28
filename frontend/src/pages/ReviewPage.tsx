import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  confirmDoc,
  deleteStaging,
  getDocumentSummary,
  getDocuments,
  getStaging,
  patchStaging,
  toErrorMessage,
} from "../api/client";
import type { DocumentListItem, DocumentSummary, RiskLevel, StagingRecord } from "../types";

interface Props {
  defaultDocId?: number | null;
  onDone: () => void;
}

type RiskFilter = "all" | RiskLevel;

const REVIEW_FIELDS = [
  { key: "university", label: "大学名", span: 2, critical: false },
  { key: "faculty", label: "学部", span: 1, critical: false },
  { key: "department", label: "学科 / 专攻", span: 1, critical: false },
  { key: "application_period", label: "出愿期间", span: 2, critical: true },
  { key: "deadline_rule", label: "必着 / 消印", span: 1, critical: true },
  { key: "eju_session", label: "EJU 实施回", span: 1, critical: true },
  { key: "eju_japanese", label: "EJU 日本语", span: 1, critical: true },
  { key: "eju_general", label: "EJU 综合科目", span: 1, critical: true },
  { key: "eju_math", label: "EJU 数学", span: 1, critical: true },
  { key: "eju_physics", label: "EJU 物理", span: 1, critical: true },
  { key: "eju_chemistry", label: "EJU 化学", span: 1, critical: true },
  { key: "eju_biology", label: "EJU 生物", span: 1, critical: true },
  { key: "english_requirement", label: "英语外部资格试验", span: 2, critical: true },
  { key: "screening_method", label: "选考方法", span: 2, critical: true },
  { key: "screening_schedule", label: "选考日程", span: 2, critical: true },
  { key: "result_date", label: "合格发表日", span: 2, critical: true },
  { key: "enrollment_period", label: "入学手续期间", span: 2, critical: true },
  { key: "prefecture", label: "都道府县", span: 1, critical: false },
  { key: "campus", label: "校区", span: 1, critical: false },
] as const;

function riskRank(risk: RiskLevel | undefined): number {
  if (risk === "high") return 0;
  if (risk === "medium") return 1;
  return 2;
}

function riskLabel(risk: RiskLevel | undefined): string {
  if (risk === "high") return "高风险";
  if (risk === "medium") return "中风险";
  return "低风险";
}

function riskDescription(risk: RiskLevel | undefined): string {
  if (risk === "high") return "这条记录里至少有一个关键字段可信度偏低，建议先看。";
  if (risk === "medium") return "大部分内容可用，但还有几个字段值得人工确认。";
  return "这条记录整体比较稳，适合后面集中快速确认。";
}

function riskBadgeStyle(risk: RiskLevel | undefined): CSSProperties {
  if (risk === "high") return { background: "#fef2f2", color: "#b91c1c", border: "1px solid #fecaca" };
  if (risk === "medium") return { background: "#fffbeb", color: "#92400e", border: "1px solid #fde68a" };
  return { background: "#f0fdf4", color: "#166534", border: "1px solid #bbf7d0" };
}

function fmtDate(value?: string | null): string {
  if (!value) return "";
  return value.replace("T", " ").slice(0, 16);
}

function fieldValue(record: StagingRecord | undefined, key: string): string {
  if (!record) return "";
  return String(((record as unknown as Record<string, unknown>)[key]) ?? "");
}

export default function ReviewPage({ defaultDocId, onDone }: Props) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [summary, setSummary] = useState<DocumentSummary | null>(null);
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
      const [docSummary, stagingRows] = await Promise.all([getDocumentSummary(docId), getStaging(docId)]);
      setSelectedDocId(docId);
      setDocIdInput(String(docId));
      setSummary(docSummary);
      setRows(stagingRows);
      setSelectedRowId(stagingRows[0]?.id ?? null);
      setMsg(stagingRows.length ? `已经载入 ${stagingRows.length} 条记录，可以开始按风险复查。` : "这个文档还没有 staging 记录。");
    } catch (error) {
      setErr(toErrorMessage(error));
    } finally {
      setLoadingRows(false);
    }
  }

  async function refreshCurrentDocument(docId: number) {
    const [docSummary, stagingRows] = await Promise.all([getDocumentSummary(docId), getStaging(docId)]);
    setSummary(docSummary);
    setRows(stagingRows);
    const docs = await getDocuments({
      q: docQuery || undefined,
      year: docYear || undefined,
      limit: 100,
    });
    setDocuments(docs);
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
      setMsg("这条记录已经删除。");
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
      setMsg(`确认入库完成：新增 ${result.confirmed} 条，跳过 ${result.skipped} 条。`);
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
      setMsg("没有需要批量标记的低风险记录。");
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
      setMsg(`已批量标记 ${targets.length} 条低风险记录为已查看。`);
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
    ? "先选一份文档，我来帮你安排复查顺序"
    : blockingHighRisk
      ? `当前有 ${metrics.high} 条高风险记录，建议先从它们开始`
      : `这份文档里共有 ${metrics.total} 条记录，现在可以按节奏复查`;

  const statusDescription = !selectedDocId
    ? "文档进入这里后，会自动按 high → medium → low 排序，不需要你自己找重点。"
    : blockingHighRisk
      ? "高风险通常意味着关键字段置信度偏低。先处理这些记录，后面的确认会更放心。"
      : metrics.low > 0
        ? `低风险记录有 ${metrics.low} 条，可以考虑直接批量标记为已查看。`
        : "如果你已经看完关键字段，可以继续确认入库。";

  return (
    <div style={{ maxWidth: 1280 }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 10, letterSpacing: "0.2em", textTransform: "uppercase", color: "var(--red)", marginBottom: 10, fontWeight: 600 }}>Step 2</div>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <div>
            <h1 style={{ fontSize: 32, fontWeight: 700, letterSpacing: -0.4, lineHeight: 1.15, margin: 0 }}>复查协作</h1>
            <div style={{ marginTop: 8, fontSize: 13, color: "var(--ink2)" }}>
              这里不是后台列表，而是你和系统一起确认风险的工作台。
            </div>
          </div>
          {selectedDocId && <span style={{ fontSize: 12, color: "var(--ink3)" }}>当前文档 #{selectedDocId}</span>}
        </div>
      </div>

      <div
        style={{
          background: "#ffffff",
          border: "1px solid #e5e7eb",
          borderRadius: 20,
          padding: "18px 20px",
          boxShadow: "0 12px 28px rgba(15, 23, 42, 0.05)",
          marginBottom: 18,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "flex-start" }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink)", marginBottom: 6 }}>{statusTitle}</div>
            <div style={{ fontSize: 13, color: "var(--ink2)", lineHeight: 1.75 }}>{statusDescription}</div>
          </div>
          <div style={{ display: "grid", gap: 6, minWidth: 210 }}>
            <div className="badge badge-red">高风险 {metrics.high}</div>
            <div className="badge badge-amber">中风险 {metrics.medium}</div>
            <div className="badge badge-green">低风险 {metrics.low}</div>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 16 }}>
        <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card" style={{ padding: 16, borderRadius: 20 }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>文档列表</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 90px", gap: 8, marginBottom: 8 }}>
              <input className="field" value={docQuery} onChange={(event) => setDocQuery(event.target.value)} placeholder="大学 / 文件 / URL" />
              <input className="field" value={docYear} onChange={(event) => setDocYear(event.target.value)} placeholder="年度" />
            </div>
            <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
              <button className="btn btn-primary" onClick={() => void loadDocuments()}>
                {loadingDocs ? "加载中..." : "筛选文档"}
              </button>
              <button
                className="btn"
                onClick={() => {
                  const docId = Number(docIdInput);
                  if (docId) void loadDocument(docId);
                }}
              >
                用 doc_id 打开
              </button>
            </div>
            <input
              className="field"
              value={docIdInput}
              onChange={(event) => setDocIdInput(event.target.value)}
              placeholder="开发兜底：输入 doc_id"
              style={{ width: "100%", marginBottom: 12 }}
            />
            <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 420, overflowY: "auto" }}>
              {documents.map((doc) => {
                const active = selectedDocId === doc.doc_id;
                return (
                  <button
                    key={doc.doc_id}
                    onClick={() => void loadDocument(doc.doc_id)}
                    style={{
                      textAlign: "left",
                      padding: "12px 12px 10px",
                      background: active ? "#111827" : "#fafaf9",
                      color: active ? "#fff" : "var(--ink)",
                      border: active ? "1px solid #111827" : "1px solid var(--border)",
                      borderRadius: 14,
                      cursor: "pointer",
                      fontFamily: "inherit",
                    }}
                  >
                    <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>{doc.university_name || "未命名文档"}</div>
                    <div style={{ fontSize: 11, opacity: 0.8, marginBottom: 4 }}>{doc.filename}</div>
                    <div style={{ fontSize: 11, opacity: 0.75 }}>
                      {doc.admission_year || "—"} · staging {doc.staging_count} · confirmed {doc.confirmed_count}
                    </div>
                    <div style={{ fontSize: 10, opacity: 0.65, marginTop: 4 }}>{fmtDate(doc.created_at)}</div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="card" style={{ padding: 16, borderRadius: 20 }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>文档摘要</div>
            {summary ? (
              <div style={{ display: "grid", gap: 8, fontSize: 12, color: "var(--ink2)" }}>
                <div><strong style={{ color: "var(--ink)" }}>大学：</strong>{summary.university_name || "—"}</div>
                <div><strong style={{ color: "var(--ink)" }}>年度：</strong>{summary.admission_year || "—"}</div>
                <div><strong style={{ color: "var(--ink)" }}>文件：</strong>{summary.filename || "—"}</div>
                <div><strong style={{ color: "var(--ink)" }}>状态：</strong>{summary.status || "—"}</div>
                <div><strong style={{ color: "var(--ink)" }}>staging：</strong>{summary.staging_count}</div>
                <div><strong style={{ color: "var(--ink)" }}>待复查：</strong>{summary.review_count ?? 0}</div>
                <div><strong style={{ color: "var(--ink)" }}>已确认：</strong>{summary.confirmed_count}</div>
                <div><strong style={{ color: "var(--ink)" }}>平均置信度：</strong>{summary.avg_confidence?.toFixed(2) ?? "0.00"}</div>
                {summary.source_url && (
                  <a href={summary.source_url} target="_blank" rel="noreferrer" style={{ color: "var(--red)", textDecoration: "none" }}>
                    打开原始来源
                  </a>
                )}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: "var(--ink3)" }}>选中文档后，这里会告诉你当前整体进度。</div>
            )}
          </div>
        </aside>

        <section style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card" style={{ padding: "16px 18px", borderRadius: 20 }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", marginBottom: 10 }}>
              {[
                { key: "all" as RiskFilter, label: `全部 ${metrics.total}` },
                { key: "high" as RiskFilter, label: `高风险 ${metrics.high}` },
                { key: "medium" as RiskFilter, label: `中风险 ${metrics.medium}` },
                { key: "low" as RiskFilter, label: `低风险 ${metrics.low}` },
              ].map((item) => (
                <button key={item.key} className={riskFilter === item.key ? "btn btn-primary" : "btn"} onClick={() => setRiskFilter(item.key)}>
                  {item.label}
                </button>
              ))}

              <button className="btn" onClick={() => void bulkMarkLowRiskReviewed()} disabled={bulkReviewing}>
                {bulkReviewing ? "处理中..." : "一键标记低风险已查看"}
              </button>

              <div style={{ marginLeft: "auto", display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <span className="badge badge-gray">已查看 {metrics.reviewed}/{metrics.total}</span>
                <button className="btn btn-green" onClick={() => void confirmCurrentDocument()} disabled={!selectedDocId || confirming || !rows.length || blockingHighRisk}>
                  {confirming ? "入库中..." : "确认入库"}
                </button>
              </div>
            </div>

            <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.7 }}>
              {blockingHighRisk
                ? "建议先检查高风险字段。只要还有高风险记录没看过，系统就不会让整份文档直接确认。"
                : "高风险部分已经处理得差不多了。现在可以继续检查中风险，或者快速处理低风险记录。"}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
            {[
              { label: "高风险", value: metrics.high, color: "#b91c1c", hint: "优先检查" },
              { label: "中风险", value: metrics.medium, color: "#92400e", hint: "建议复核" },
              { label: "低风险", value: metrics.low, color: "#166534", hint: "可快速通过" },
              { label: "已查看", value: metrics.reviewed, color: "var(--ink)", hint: "人工已看过" },
            ].map((card) => (
              <div key={card.label} className="card" style={{ padding: 18, borderRadius: 18 }}>
                <div style={{ fontSize: 10, color: "var(--ink3)", marginBottom: 6 }}>{card.label}</div>
                <div style={{ fontSize: 28, lineHeight: 1, color: card.color, fontWeight: 700, marginBottom: 6 }}>{card.value}</div>
                <div style={{ fontSize: 12, color: "var(--ink2)" }}>{card.hint}</div>
              </div>
            ))}
          </div>

          {msg && <div style={{ padding: "12px 14px", background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 14, color: "#1d4ed8", fontSize: 13 }}>{msg}</div>}
          {err && <div style={{ padding: "12px 14px", background: "#fff7f7", border: "1px solid #fecaca", borderRadius: 14, color: "var(--red)", fontSize: 13 }}>{err}</div>}

          {!currentRow && !loadingRows && (
            <div className="card" style={{ padding: 32, color: "var(--ink3)", textAlign: "center", fontSize: 14, borderRadius: 20 }}>
              从左侧文档列表中选一份文档，我会按风险顺序把记录排给你。
            </div>
          )}

          {currentRow && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 16 }}>
              <div className="card" style={{ padding: 24, borderRadius: 22 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18, gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)", marginBottom: 6 }}>
                      记录 #{currentRow.id}
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
                      <span className="badge" style={riskBadgeStyle(currentRow.risk_level)}>{riskLabel(currentRow.risk_level)}</span>
                      <span className="badge badge-gray">整体置信度 {Number(currentRow.confidence ?? 0).toFixed(2)}</span>
                      <span className={Number(currentRow.is_reviewed) ? "badge badge-green" : "badge badge-amber"}>
                        {Number(currentRow.is_reviewed) ? "已查看" : "未查看"}
                      </span>
                    </div>
                    <div style={{ fontSize: 13, color: "var(--ink2)", lineHeight: 1.7 }}>{riskDescription(currentRow.risk_level)}</div>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--ink3)", textAlign: "right" }}>
                    <div>page {currentRow.page_number ?? "—"}</div>
                    <div>{fmtDate(currentRow.reviewed_at)}</div>
                  </div>
                </div>

                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: 14,
                    background: "#fafaf9",
                    border: "1px solid #e7e5e4",
                    marginBottom: 18,
                    fontSize: 12,
                    color: "var(--ink2)",
                    lineHeight: 1.7,
                  }}
                >
                  建议先看带红色提示的字段，它们代表 AI 自己也不够确定。绿色和灰色字段一般可以放在后面快速过一遍。
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px 14px", marginBottom: 18 }}>
                  {REVIEW_FIELDS.map((field) => {
                    const confidence = Number(currentRow.field_confidence?.[field.key] ?? 0);
                    const evidence = currentRow.field_evidence?.[field.key];
                    const modified = (currentRow.manual_modified_fields || []).includes(field.key);
                    const shouldWarn = field.critical && confidence < 0.8;
                    const inputStyle: CSSProperties = {
                      width: "100%",
                      minHeight: field.span === 2 ? 84 : 40,
                      padding: "10px 12px",
                      border: `1px solid ${shouldWarn ? "#fca5a5" : "#d6d3d1"}`,
                      borderRadius: 12,
                      fontSize: 13,
                      color: "var(--ink)",
                      background: shouldWarn ? "#fff7f7" : "#fafaf9",
                      resize: "vertical",
                      fontFamily: "inherit",
                    };

                    return (
                      <div key={field.key} style={field.span === 2 ? { gridColumn: "span 2" } : {}}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
                          <span style={{ fontSize: 11, fontWeight: 700, color: shouldWarn ? "#b91c1c" : "var(--ink3)" }}>
                            {field.label}
                          </span>
                          {field.critical && (
                            <span
                              style={{
                                fontSize: 11,
                                padding: "2px 8px",
                                borderRadius: 999,
                                background: shouldWarn ? "#fef2f2" : "#f5f5f4",
                                color: shouldWarn ? "#b91c1c" : "#57534e",
                                border: shouldWarn ? "1px solid #fecaca" : "1px solid #e7e5e4",
                              }}
                            >
                              {shouldWarn ? "建议优先检查" : `confidence ${confidence.toFixed(2)}`}
                            </span>
                          )}
                          {modified && <span className="badge badge-blue">你改过</span>}
                        </div>

                        {field.span === 2 ? (
                          <textarea value={draft[field.key] || ""} onChange={(event) => updateDraft(field.key, event.target.value)} style={inputStyle} />
                        ) : (
                          <input value={draft[field.key] || ""} onChange={(event) => updateDraft(field.key, event.target.value)} style={inputStyle} />
                        )}

                        {field.critical && evidence?.text && (
                          <details style={{ marginTop: 6 }}>
                            <summary style={{ fontSize: 12, color: "var(--ink2)", cursor: "pointer" }}>
                              查看依据 {evidence.page ? `(p.${evidence.page})` : ""}
                            </summary>
                            <div
                              style={{
                                marginTop: 6,
                                padding: "10px 12px",
                                background: "#ffffff",
                                border: "1px solid #e7e5e4",
                                borderRadius: 10,
                                fontSize: 12,
                                lineHeight: 1.7,
                                color: "var(--ink2)",
                              }}
                            >
                              {evidence.text}
                            </div>
                          </details>
                        )}
                      </div>
                    );
                  })}
                </div>

                {(currentRow.warnings_json || []).length > 0 && (
                  <div style={{ marginBottom: 18, padding: "12px 14px", border: "1px solid #fde68a", background: "#fffbeb", borderRadius: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "#92400e", marginBottom: 8 }}>系统提醒</div>
                    <div style={{ display: "grid", gap: 6, fontSize: 12, color: "#92400e" }}>
                      {(currentRow.warnings_json || []).map((warning, index) => (
                        <div key={`${warning}-${index}`}>• {warning}</div>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ display: "flex", gap: 8, paddingTop: 16, borderTop: "1px solid #ece8df", flexWrap: "wrap" }}>
                  <button className="btn" onClick={() => void savePatch({ ...draft, is_reviewed: 1 }, "修改已保存，同时已标记为已查看。")} disabled={saving}>
                    保存
                  </button>
                  <button className="btn btn-amber" onClick={() => void savePatch({ is_reviewed: 1, reviewed_at: "" }, "这条记录已标记为已查看。")} disabled={saving}>
                    标记已查看
                  </button>
                  <button
                    className="btn btn-green"
                    onClick={() => void savePatch({ ...draft, is_reviewed: 1, is_confirmed: 1, needs_review: 0 }, "这条记录已经确认。")}
                    disabled={saving}
                  >
                    确认此条
                  </button>
                  <button className="btn btn-red" onClick={() => void removeCurrent()} disabled={saving} style={{ marginLeft: "auto" }}>
                    删除
                  </button>
                </div>
              </div>

              <div className="card" style={{ padding: 16, borderRadius: 22 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", marginBottom: 8 }}>
                  记录队列 {riskFilter === "all" ? "" : `· ${riskLabel(riskFilter)}`}
                </div>
                <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.7, marginBottom: 12 }}>
                  这里已经帮你按风险排好序了。通常从最上面往下看就行。
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 720, overflowY: "auto" }}>
                  {filteredRows.map((row) => {
                    const active = row.id === currentRow.id;
                    return (
                      <button
                        key={row.id}
                        onClick={() => setSelectedRowId(row.id)}
                        style={{
                          textAlign: "left",
                          padding: "12px 12px",
                          borderRadius: 14,
                          border: active ? "1px solid #111827" : "1px solid #e5e7eb",
                          background: active ? "#111827" : "#fafaf9",
                          color: active ? "#fff" : "var(--ink)",
                          cursor: "pointer",
                          fontFamily: "inherit",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 4 }}>
                          <div style={{ fontSize: 12, fontWeight: 700 }}>
                            {row.faculty || row.department || `记录 #${row.id}`}
                          </div>
                          <span style={{ fontSize: 10, padding: "2px 7px", borderRadius: 999, ...riskBadgeStyle(row.risk_level) }}>
                            {riskLabel(row.risk_level)}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, opacity: 0.85 }}>整体置信度 {Number(row.confidence ?? 0).toFixed(2)}</div>
                        <div style={{ fontSize: 11, opacity: 0.75, marginTop: 2 }}>
                          {Number(row.is_reviewed) ? "已查看" : "未查看"} · {Number(row.is_confirmed) ? "已确认" : "未确认"}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
