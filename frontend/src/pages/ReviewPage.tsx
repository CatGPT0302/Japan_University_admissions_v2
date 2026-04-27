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

function riskBadgeStyle(risk: RiskLevel | undefined): CSSProperties {
  if (risk === "high") return { background: "#fef2f2", color: "#b91c1c", border: "1px solid #fecaca" };
  if (risk === "medium") return { background: "#fffbeb", color: "#92400e", border: "1px solid #fde68a" };
  return { background: "#f0fdf4", color: "#166534", border: "1px solid #bbf7d0" };
}

function riskLabel(risk: RiskLevel | undefined): string {
  if (risk === "high") return "High Risk";
  if (risk === "medium") return "Medium Risk";
  return "Low Risk";
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
      setMsg(stagingRows.length ? `已加载 ${stagingRows.length} 条 staging 记录` : "这个文档还没有 staging 记录");
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
      setMsg("当前记录已删除");
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
      setMsg(`确认入库完成：新增 ${result.confirmed} 条，跳过 ${result.skipped} 条`);
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
      setMsg("没有需要批量标记的低风险记录");
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
      setMsg(`已批量标记 ${targets.length} 条低风险记录为已查看`);
    } catch (error) {
      setErr(toErrorMessage(error));
    } finally {
      setBulkReviewing(false);
    }
  }

  function updateDraft(field: string, value: string) {
    setDraft((prev) => ({ ...prev, [field]: value }));
  }

  return (
    <div style={{ maxWidth: 1280 }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 10, letterSpacing: "0.2em", textTransform: "uppercase", color: "var(--red)", marginBottom: 10, fontWeight: 600 }}>Step 2</div>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <div>
            <h1 style={{ fontSize: 32, fontWeight: 700, letterSpacing: -0.4, lineHeight: 1.15, margin: 0 }}>风险复查</h1>
            <div style={{ marginTop: 8, fontSize: 13, color: "var(--ink2)" }}>
              默认按 high → medium → low 排序，让人工先看 AI 最不确定的地方。
            </div>
          </div>
          {selectedDocId && <span style={{ fontSize: 12, color: "var(--ink3)" }}>当前文档 #{selectedDocId}</span>}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 16 }}>
        <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12 }}>文档列表</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 90px", gap: 8, marginBottom: 8 }}>
              <input
                className="field"
                value={docQuery}
                onChange={(event) => setDocQuery(event.target.value)}
                placeholder="大学 / 文件 / URL"
              />
              <input
                className="field"
                value={docYear}
                onChange={(event) => setDocYear(event.target.value)}
                placeholder="年度"
              />
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
                      background: active ? "var(--ink)" : "var(--bg)",
                      color: active ? "#fff" : "var(--ink)",
                      border: active ? "1px solid var(--ink)" : "1px solid var(--border)",
                      borderRadius: 10,
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

          <div className="card" style={{ padding: 16 }}>
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
              <div style={{ fontSize: 12, color: "var(--ink3)" }}>选择左侧文档后，这里会显示摘要。</div>
            )}
          </div>
        </aside>

        <section style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card" style={{ padding: "14px 16px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
              {[
                { key: "all" as RiskFilter, label: `全部 ${metrics.total}` },
                { key: "high" as RiskFilter, label: `High ${metrics.high}` },
                { key: "medium" as RiskFilter, label: `Medium ${metrics.medium}` },
                { key: "low" as RiskFilter, label: `Low ${metrics.low}` },
              ].map((item) => (
                <button
                  key={item.key}
                  className={riskFilter === item.key ? "btn btn-primary" : "btn"}
                  onClick={() => setRiskFilter(item.key)}
                >
                  {item.label}
                </button>
              ))}

              <button className="btn" onClick={() => void bulkMarkLowRiskReviewed()} disabled={bulkReviewing}>
                {bulkReviewing ? "批量处理中..." : "批量标记低风险已查看"}
              </button>

              <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <span className="badge badge-gray">已查看 {metrics.reviewed}/{metrics.total}</span>
                <button className="btn btn-green" onClick={() => void confirmCurrentDocument()} disabled={!selectedDocId || confirming || !rows.length || blockingHighRisk}>
                  {confirming ? "入库中..." : "确认入库"}
                </button>
              </div>
            </div>
            {blockingHighRisk && (
              <div style={{ marginTop: 10, fontSize: 12, color: "var(--red)" }}>
                还有高风险记录未标记为“已查看”，暂时不允许整份文档直接确认入库。
              </div>
            )}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
            {[
              { label: "High", value: metrics.high, color: "#b91c1c" },
              { label: "Medium", value: metrics.medium, color: "#92400e" },
              { label: "Low", value: metrics.low, color: "#166534" },
              { label: "Reviewed", value: metrics.reviewed, color: "var(--ink)" },
            ].map((card) => (
              <div key={card.label} className="card" style={{ padding: 18 }}>
                <div style={{ fontSize: 10, color: "var(--ink3)", marginBottom: 6 }}>{card.label}</div>
                <div style={{ fontSize: 28, lineHeight: 1, color: card.color, fontWeight: 700 }}>{card.value}</div>
              </div>
            ))}
          </div>

          {msg && <div style={{ padding: "10px 14px", background: "var(--blue-soft)", border: "1px solid #bfdbfe", borderRadius: 10, color: "var(--blue)", fontSize: 13 }}>{msg}</div>}
          {err && <div style={{ padding: "10px 14px", background: "var(--red-soft)", border: "1px solid #fecaca", borderRadius: 10, color: "var(--red)", fontSize: 13 }}>{err}</div>}

          {!currentRow && !loadingRows && (
            <div className="card" style={{ padding: 32, color: "var(--ink3)", textAlign: "center", fontSize: 14 }}>
              从左侧文档列表中选择一个文档开始复查。
            </div>
          )}

          {currentRow && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 260px", gap: 16 }}>
              <div className="card" style={{ padding: 24 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18, gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: "var(--ink)", marginBottom: 6 }}>
                      记录 #{currentRow.id}
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <span className="badge" style={riskBadgeStyle(currentRow.risk_level)}>{riskLabel(currentRow.risk_level)}</span>
                      <span className="badge badge-gray">整体置信度 {Number(currentRow.confidence ?? 0).toFixed(2)}</span>
                      <span className={Number(currentRow.is_reviewed) ? "badge badge-green" : "badge badge-amber"}>
                        {Number(currentRow.is_reviewed) ? "已查看" : "未查看"}
                      </span>
                    </div>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--ink3)", textAlign: "right" }}>
                    <div>page {currentRow.page_number ?? "—"}</div>
                    <div>{fmtDate(currentRow.reviewed_at)}</div>
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px 14px", marginBottom: 18 }}>
                  {REVIEW_FIELDS.map((field) => {
                    const confidence = Number(currentRow.field_confidence?.[field.key] ?? 0);
                    const evidence = currentRow.field_evidence?.[field.key];
                    const modified = (currentRow.manual_modified_fields || []).includes(field.key);
                    const shouldWarn = field.critical && confidence < 0.8;
                    const inputStyle: CSSProperties = {
                      width: "100%",
                      minHeight: field.span === 2 ? 80 : 38,
                      padding: "10px 12px",
                      border: `1px solid ${shouldWarn ? "var(--red)" : "var(--border)"}`,
                      borderRadius: 8,
                      fontSize: 13,
                      color: "var(--ink)",
                      background: shouldWarn ? "var(--red-soft)" : "var(--bg)",
                      resize: "vertical",
                      fontFamily: "inherit",
                    };

                    return (
                      <div key={field.key} style={field.span === 2 ? { gridColumn: "span 2" } : {}}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, flexWrap: "wrap" }}>
                          <span style={{ fontSize: 11, fontWeight: 700, color: shouldWarn ? "var(--red)" : "var(--ink3)" }}>
                            {field.label}
                          </span>
                          {field.critical && (
                            <span
                              style={{
                                fontSize: 11,
                                padding: "2px 8px",
                                borderRadius: 999,
                                background: confidence < 0.8 ? "#fef2f2" : "#f5f5f4",
                                color: confidence < 0.8 ? "#b91c1c" : "#57534e",
                                border: confidence < 0.8 ? "1px solid #fecaca" : "1px solid #e7e5e4",
                              }}
                            >
                              confidence {confidence.toFixed(2)}
                            </span>
                          )}
                          {modified && <span className="badge badge-blue">人工改过</span>}
                        </div>

                        {field.span === 2 ? (
                          <textarea
                            value={draft[field.key] || ""}
                            onChange={(event) => updateDraft(field.key, event.target.value)}
                            style={inputStyle}
                          />
                        ) : (
                          <input
                            value={draft[field.key] || ""}
                            onChange={(event) => updateDraft(field.key, event.target.value)}
                            style={inputStyle}
                          />
                        )}

                        {field.critical && evidence?.text && (
                          <details style={{ marginTop: 6 }}>
                            <summary style={{ fontSize: 12, color: "var(--ink2)", cursor: "pointer" }}>
                              查看依据 {evidence.page ? `(p.${evidence.page})` : ""}
                            </summary>
                            <div style={{ marginTop: 6, padding: "10px 12px", background: "#fafaf9", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12, lineHeight: 1.6, color: "var(--ink2)" }}>
                              {evidence.text}
                            </div>
                          </details>
                        )}
                      </div>
                    );
                  })}
                </div>

                {(currentRow.warnings_json || []).length > 0 && (
                  <div style={{ marginBottom: 18, padding: "12px 14px", border: "1px solid #fde68a", background: "#fffbeb", borderRadius: 10 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "#92400e", marginBottom: 8 }}>风险提示</div>
                    <div style={{ display: "grid", gap: 6, fontSize: 12, color: "#92400e" }}>
                      {(currentRow.warnings_json || []).map((warning, index) => (
                        <div key={`${warning}-${index}`}>• {warning}</div>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ display: "flex", gap: 8, paddingTop: 16, borderTop: "1px solid var(--border)", flexWrap: "wrap" }}>
                  <button className="btn" onClick={() => void savePatch({ ...draft, is_reviewed: 1 }, "已保存当前修改，并标记为已查看")} disabled={saving}>
                    保存
                  </button>
                  <button
                    className="btn btn-amber"
                    onClick={() => void savePatch({ is_reviewed: 1, reviewed_at: "" }, "当前记录已标记为已查看")}
                    disabled={saving}
                  >
                    标记已查看
                  </button>
                  <button
                    className="btn btn-green"
                    onClick={() => void savePatch({ ...draft, is_reviewed: 1, is_confirmed: 1, needs_review: 0 }, "当前记录已确认")}
                    disabled={saving}
                  >
                    确认此条
                  </button>
                  <button className="btn btn-red" onClick={() => void removeCurrent()} disabled={saving} style={{ marginLeft: "auto" }}>
                    删除
                  </button>
                </div>
              </div>

              <div className="card" style={{ padding: 16 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", marginBottom: 12 }}>
                  记录队列 {riskFilter === "all" ? "" : `· ${riskFilter}`}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 680, overflowY: "auto" }}>
                  {filteredRows.map((row) => {
                    const active = row.id === currentRow.id;
                    return (
                      <button
                        key={row.id}
                        onClick={() => setSelectedRowId(row.id)}
                        style={{
                          textAlign: "left",
                          padding: "10px 12px",
                          borderRadius: 10,
                          border: active ? "1px solid var(--ink)" : "1px solid var(--border)",
                          background: active ? "var(--ink)" : "var(--bg)",
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
                        <div style={{ fontSize: 11, opacity: 0.85 }}>confidence {Number(row.confidence ?? 0).toFixed(2)}</div>
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
