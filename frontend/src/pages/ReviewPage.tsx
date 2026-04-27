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
import type { DocumentListItem, DocumentSummary, StagingRecord } from "../types";

interface Props {
  defaultDocId?: number | null;
  onDone: () => void;
}

const FIELDS = [
  { key: "university", label: "大学", span: 1 },
  { key: "admission_year", label: "年度", span: 1 },
  { key: "faculty", label: "学部", span: 1 },
  { key: "department", label: "学科", span: 1 },
  { key: "english_requirement", label: "英语要求", span: 2 },
  { key: "eju_japanese", label: "EJU 日语", span: 1 },
  { key: "eju_math", label: "EJU 数学", span: 1 },
  { key: "screening_method", label: "选拔方式", span: 2 },
  { key: "application_period", label: "出愿期间", span: 2 },
  { key: "result_date", label: "结果发表日", span: 1 },
  { key: "campus", label: "校区", span: 1 },
] as const;

function fieldValue(record: StagingRecord | undefined, key: string): string {
  if (!record) return "";
  return String(((record as unknown as Record<string, unknown>)[key]) ?? "");
}

function statusLabel(row: StagingRecord): string {
  if (Number(row.is_confirmed)) return "已确认";
  if (Number(row.needs_review)) return "待复查";
  if (Number(row.confidence ?? 0) < 0.75) return "低置信度";
  return "待处理";
}

function statusStyle(row: StagingRecord): CSSProperties {
  if (Number(row.is_confirmed)) {
    return { background: "#f0fdf4", color: "#166534", border: "1px solid #bbf7d0" };
  }
  if (Number(row.needs_review)) {
    return { background: "#fffbeb", color: "#92400e", border: "1px solid #fde68a" };
  }
  if (Number(row.confidence ?? 0) < 0.75) {
    return { background: "#fef2f2", color: "var(--red)", border: "1px solid #fecaca" };
  }
  return { background: "var(--bg)", color: "var(--ink3)", border: "1px solid var(--border)" };
}

function fmtDate(value?: string): string {
  if (!value) return "";
  return value.replace("T", " ").slice(0, 16);
}

export default function ReviewPage({ defaultDocId, onDone }: Props) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [summary, setSummary] = useState<DocumentSummary | null>(null);
  const [rows, setRows] = useState<StagingRecord[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(defaultDocId ?? null);
  const [docIdInput, setDocIdInput] = useState(defaultDocId ? String(defaultDocId) : "");
  const [docQuery, setDocQuery] = useState("");
  const [docYear, setDocYear] = useState("");
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [loadingRows, setLoadingRows] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [idx, setIdx] = useState(0);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const row = rows[idx];

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

  useEffect(() => {
    if (!row) return;
    const nextDraft: Record<string, string> = {};
    for (const field of FIELDS) nextDraft[field.key] = fieldValue(row, field.key);
    setDraft(nextDraft);
    setMsg("");
    setErr("");
  }, [row?.id]);

  const stats = useMemo(() => {
    const confirmed = rows.filter((item) => Number(item.is_confirmed)).length;
    const review = rows.filter((item) => Number(item.needs_review)).length;
    return { total: rows.length, confirmed, review };
  }, [rows]);

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
      const [docSummary, stagingRows] = await Promise.all([
        getDocumentSummary(docId),
        getStaging(docId),
      ]);
      setSelectedDocId(docId);
      setDocIdInput(String(docId));
      setSummary(docSummary);
      setRows(stagingRows);
      setIdx(0);
      setMsg(stagingRows.length ? `已加载 ${stagingRows.length} 条 staging 记录` : "该文档还没有 staging 记录");
    } catch (error) {
      setErr(toErrorMessage(error));
    } finally {
      setLoadingRows(false);
    }
  }

  async function refreshCurrentDocument(docId: number) {
    const [docSummary, stagingRows] = await Promise.all([
      getDocumentSummary(docId),
      getStaging(docId),
    ]);
    setSummary(docSummary);
    setRows(stagingRows);
    setIdx((current) => Math.min(current, Math.max(stagingRows.length - 1, 0)));
    const data = await getDocuments({
      q: docQuery || undefined,
      year: docYear || undefined,
      limit: 100,
    });
    setDocuments(data);
  }

  async function savePatch(patch: Record<string, unknown>, successMessage: string) {
    if (!row || saving) return;
    setSaving(true);
    setErr("");
    setMsg("");
    try {
      const updated = await patchStaging(row.id, patch);
      setRows((prev) => prev.map((item) => (item.id === row.id ? { ...item, ...updated, ...patch } : item)));
      setMsg(successMessage);
    } catch (error) {
      setErr(toErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function removeCurrent() {
    if (!row || saving) return;
    setSaving(true);
    setErr("");
    setMsg("");
    try {
      await deleteStaging(row.id);
      const nextRows = rows.filter((item) => item.id !== row.id);
      setRows(nextRows);
      setIdx((current) => Math.min(current, Math.max(nextRows.length - 1, 0)));
      setMsg("该记录已删除");
      if (selectedDocId) await refreshCurrentDocument(selectedDocId);
    } catch (error) {
      setErr(toErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function confirmCurrentDocument() {
    if (!selectedDocId || confirming) return;
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

  const progress = stats.total ? Math.round((stats.confirmed / stats.total) * 100) : 0;

  return (
    <div style={{ maxWidth: 1180 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 10, letterSpacing: "0.2em", textTransform: "uppercase", color: "var(--red)", marginBottom: 10, fontWeight: 500 }}>Step 2</div>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <h1 style={{ fontFamily: "Georgia,serif", fontSize: 34, fontStyle: "italic", fontWeight: 400, letterSpacing: -0.5, lineHeight: 1.1 }}>复查</h1>
          {selectedDocId && <span style={{ fontSize: 12, color: "var(--ink3)" }}>当前文档 #{selectedDocId}</span>}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 16 }}>
        <aside style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink)", marginBottom: 12 }}>最近文档</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 90px", gap: 8, marginBottom: 8 }}>
              <input
                value={docQuery}
                onChange={(event) => setDocQuery(event.target.value)}
                placeholder="大学 / 文件名 / URL"
                style={{ height: 36, padding: "0 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, background: "var(--bg)" }}
              />
              <input
                value={docYear}
                onChange={(event) => setDocYear(event.target.value)}
                placeholder="年度"
                style={{ height: 36, padding: "0 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, background: "var(--bg)" }}
              />
            </div>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <button
                onClick={() => void loadDocuments()}
                style={{ height: 34, padding: "0 14px", background: "var(--ink)", color: "#fff", border: "none", borderRadius: 8, fontSize: 13, cursor: "pointer", fontFamily: "inherit" }}
              >
                {loadingDocs ? "加载中..." : "筛选文档"}
              </button>
              <button
                onClick={() => {
                  const id = Number(docIdInput);
                  if (id) void loadDocument(id);
                }}
                style={{ height: 34, padding: "0 14px", background: "var(--surface)", color: "var(--ink)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, cursor: "pointer", fontFamily: "inherit" }}
              >
                用 doc_id 打开
              </button>
            </div>
            <input
              value={docIdInput}
              onChange={(event) => setDocIdInput(event.target.value)}
              placeholder="开发兜底：输入 doc_id"
              style={{ width: "100%", height: 34, padding: "0 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12, background: "var(--bg)", marginBottom: 12 }}
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
                    <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{doc.university_name || "未命名文档"}</div>
                    <div style={{ fontSize: 11, opacity: 0.8, marginBottom: 4 }}>{doc.filename}</div>
                    <div style={{ fontSize: 11, opacity: 0.75 }}>
                      {doc.admission_year || "—"} · staging {doc.staging_count} · confirmed {doc.confirmed_count}
                    </div>
                    <div style={{ fontSize: 10, opacity: 0.65, marginTop: 4 }}>{fmtDate(doc.created_at)}</div>
                  </button>
                );
              })}
              {!documents.length && !loadingDocs && (
                <div style={{ padding: 12, border: "1px dashed var(--border)", borderRadius: 10, color: "var(--ink3)", fontSize: 12 }}>
                  还没有可复查文档。先到“跑数据”上传 PDF。
                </div>
              )}
            </div>
          </div>

          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 16 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink)", marginBottom: 12 }}>文档摘要</div>
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
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: "14px 16px", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <button
              onClick={() => setIdx((current) => Math.max(current - 1, 0))}
              disabled={!rows.length || idx === 0}
              style={{ height: 36, padding: "0 14px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, cursor: "pointer", color: "var(--ink)", fontFamily: "inherit" }}
            >
              上一条
            </button>
            <button
              onClick={() => setIdx((current) => Math.min(current + 1, rows.length - 1))}
              disabled={!rows.length || idx >= rows.length - 1}
              style={{ height: 36, padding: "0 14px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, cursor: "pointer", color: "var(--ink)", fontFamily: "inherit" }}
            >
              下一条
            </button>
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ width: 120, height: 4, background: "var(--border)", borderRadius: 4, overflow: "hidden" }}>
                <div style={{ width: `${progress}%`, height: "100%", background: "var(--green)" }} />
              </div>
              <span style={{ fontSize: 12, color: "var(--ink3)" }}>
                {rows.length ? `第 ${idx + 1} / ${rows.length} 条` : "暂无记录"}
              </span>
            </div>
            <button
              onClick={() => void confirmCurrentDocument()}
              disabled={!selectedDocId || confirming || !rows.length}
              style={{ height: 36, padding: "0 16px", background: "var(--green)", color: "#fff", border: "none", borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: "pointer", fontFamily: "inherit" }}
            >
              {confirming ? "入库中..." : "确认入库"}
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
            {[
              { label: "总记录", value: stats.total, color: "var(--ink)" },
              { label: "已确认", value: stats.confirmed, color: "var(--green)" },
              { label: "待复查", value: stats.review, color: "var(--amber)" },
              { label: "当前状态", value: row ? statusLabel(row) : "—", color: "var(--ink)" },
            ].map((card) => (
              <div key={card.label} style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 18 }}>
                <div style={{ fontSize: 10, color: "var(--ink3)", marginBottom: 6 }}>{card.label}</div>
                <div style={{ fontFamily: "Georgia,serif", fontSize: 28, lineHeight: 1, color: card.color }}>{card.value}</div>
              </div>
            ))}
          </div>

          {msg && <div style={{ padding: "10px 14px", background: "var(--blue-soft)", border: "1px solid #bfdbfe", borderRadius: 10, color: "var(--blue)", fontSize: 13 }}>{msg}</div>}
          {err && <div style={{ padding: "10px 14px", background: "var(--red-soft)", border: "1px solid #fecaca", borderRadius: 10, color: "var(--red)", fontSize: 13 }}>{err}</div>}

          {!row && !loadingRows && (
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 32, color: "var(--ink3)", textAlign: "center", fontSize: 14 }}>
              从左侧文档列表选择一个文档开始复查。
            </div>
          )}

          {row && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 240px", gap: 16 }}>
              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 24 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 600, color: "var(--ink)", marginBottom: 4 }}>记录 #{row.id}</div>
                    <div style={{ fontSize: 12, color: "var(--ink3)" }}>置信度 {Number(row.confidence ?? 0).toFixed(2)}</div>
                  </div>
                  <span style={{ fontSize: 11, padding: "2px 9px", borderRadius: 20, fontWeight: 600, ...statusStyle(row) }}>{statusLabel(row)}</span>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 14px", marginBottom: 18 }}>
                  {FIELDS.map((field) => {
                    const warn = !draft[field.key] && (field.key === "faculty" || field.key === "english_requirement");
                    return (
                      <label key={field.key} style={field.span === 2 ? { gridColumn: "span 2" } : {}}>
                        <div style={{ fontSize: 11, fontWeight: 600, color: warn ? "var(--red)" : "var(--ink3)", marginBottom: 4 }}>
                          {field.label}{warn ? " *" : ""}
                        </div>
                        <input
                          value={draft[field.key] || ""}
                          onChange={(event) => setDraft((prev) => ({ ...prev, [field.key]: event.target.value }))}
                          style={{
                            width: "100%",
                            height: 36,
                            padding: "0 12px",
                            border: `1px solid ${warn ? "var(--red)" : "var(--border)"}`,
                            borderRadius: 8,
                            fontSize: 13,
                            color: "var(--ink)",
                            background: warn ? "var(--red-soft)" : "var(--bg)",
                          }}
                        />
                      </label>
                    );
                  })}
                </div>

                <div style={{ display: "flex", gap: 8, paddingTop: 16, borderTop: "1px solid var(--border)", flexWrap: "wrap" }}>
                  <button
                    onClick={() => void savePatch(draft, "已保存当前修改")}
                    disabled={saving}
                    style={{ height: 36, padding: "0 16px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: "pointer", fontFamily: "inherit", color: "var(--ink)" }}
                  >
                    保存
                  </button>
                  <button
                    onClick={() => void savePatch({ ...draft, needs_review: 1, is_confirmed: 0 }, "已标记为待复查")}
                    disabled={saving}
                    style={{ height: 36, padding: "0 16px", background: "transparent", border: "1px solid #fcd34d", borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: "pointer", fontFamily: "inherit", color: "var(--amber)" }}
                  >
                    标记复查
                  </button>
                  <button
                    onClick={async () => {
                      await savePatch({ ...draft, needs_review: 0, is_confirmed: 1 }, "当前记录已确认");
                      setIdx((current) => Math.min(current + 1, rows.length - 1));
                    }}
                    disabled={saving}
                    style={{ height: 36, padding: "0 16px", background: "var(--green)", border: "none", borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: "pointer", fontFamily: "inherit", color: "#fff" }}
                  >
                    确认此条
                  </button>
                  <button
                    onClick={() => void removeCurrent()}
                    disabled={saving}
                    style={{ height: 36, padding: "0 14px", background: "transparent", border: "1px solid #fecaca", borderRadius: 8, fontSize: 13, cursor: "pointer", fontFamily: "inherit", color: "var(--red)", marginLeft: "auto" }}
                  >
                    删除
                  </button>
                </div>
              </div>

              <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink)", marginBottom: 12 }}>跳转记录</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 420, overflowY: "auto" }}>
                  {rows.map((item, itemIndex) => (
                    <button
                      key={item.id}
                      onClick={() => setIdx(itemIndex)}
                      style={{
                        textAlign: "left",
                        padding: "8px 10px",
                        borderRadius: 8,
                        border: itemIndex === idx ? "1px solid var(--ink)" : "1px solid transparent",
                        background: itemIndex === idx ? "var(--ink)" : "transparent",
                        color: itemIndex === idx ? "#fff" : "var(--ink2)",
                        cursor: "pointer",
                        fontSize: 12,
                        fontFamily: "inherit",
                      }}
                    >
                      <div style={{ fontWeight: 600 }}>{item.faculty || `记录 #${item.id}`}</div>
                      <div style={{ fontSize: 11, opacity: 0.75 }}>{statusLabel(item)}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
