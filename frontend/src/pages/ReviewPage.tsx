import { useEffect, useMemo, useState } from "react";
import {
  confirmDoc,
  documentPageImageUrl,
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

const REVIEW_FIELDS = [
  ["university", "大学名称"],
  ["admission_year", "入学年度"],
  ["admission_period", "入学时期"],
  ["faculty", "学部"],
  ["department", "学科/专业"],
  ["application_period", "出愿期间"],
  ["deadline_rule", "截止规则"],
  ["eju_session", "EJU场次"],
  ["eju_japanese", "EJU日语"],
  ["eju_general", "EJU综合科目"],
  ["eju_math", "EJU数学"],
  ["eju_physics", "EJU物理"],
  ["eju_chemistry", "EJU化学"],
  ["eju_biology", "EJU生物"],
  ["english_requirement", "英语要求"],
  ["screening_method", "选考方式"],
  ["screening_schedule", "选考日程"],
  ["result_date", "合格发表日"],
  ["enrollment_period", "入学手续期间"],
  ["prefecture", "都道府县"],
  ["campus", "校区"],
] as const;

function riskText(risk?: RiskLevel) {
  if (risk === "high") return "需重点确认";
  if (risk === "low") return "较清楚";
  return "需确认";
}

function riskClass(risk?: RiskLevel) {
  if (risk === "high") return "badge badge-red";
  if (risk === "low") return "badge badge-green";
  return "badge badge-amber";
}

function valueOf(row: StagingRecord | null, key: string) {
  if (!row) return "";
  return String((row as unknown as Record<string, unknown>)[key] ?? "");
}

export default function ReviewPage({ defaultDocId, onDone }: Props) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [summary, setSummary] = useState<DocumentSummary | null>(null);
  const [rows, setRows] = useState<StagingRecord[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(defaultDocId ?? null);
  const [selectedRowId, setSelectedRowId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void refreshDocuments();
  }, []);

  useEffect(() => {
    if (defaultDocId) void openDocument(defaultDocId);
  }, [defaultDocId]);

  const selectedRow = useMemo(() => rows.find((row) => row.id === selectedRowId) ?? null, [rows, selectedRowId]);
  const reviewedCount = rows.filter((row) => Number(row.is_reviewed)).length;
  const highRiskCount = rows.filter((row) => row.risk_level === "high").length;

  useEffect(() => {
    if (!selectedRow) return;
    const nextDraft: Record<string, string> = {};
    for (const [key] of REVIEW_FIELDS) nextDraft[key] = valueOf(selectedRow, key);
    setDraft(nextDraft);
  }, [selectedRow]);

  async function refreshDocuments() {
    try {
      setDocuments(await getDocuments({ limit: 100 }));
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    }
  }

  async function openDocument(docId: number) {
    setError("");
    setMessage("");
    const [docSummary, stagingRows] = await Promise.all([getDocumentSummary(docId), getStaging(docId)]);
    setSelectedDocId(docId);
    setSummary(docSummary);
    setRows(stagingRows);
    setSelectedRowId(stagingRows[0]?.id ?? null);
  }

  async function save(markReviewed: boolean) {
    if (!selectedRow) return;
    setSaving(true);
    setError("");
    try {
      const updated = await patchStaging(selectedRow.id, {
        ...draft,
        ...(markReviewed ? { is_reviewed: 1, needs_review: 0 } : {}),
      });
      setRows(rows.map((row) => (row.id === selectedRow.id ? updated : row)));
      setSelectedRowId(updated.id);
      setMessage(markReviewed ? "已保存，并标记为已核对。" : "修改已保存。");
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setSaving(false);
    }
  }

  async function confirmCurrentDocument() {
    if (!selectedDocId) return;
    setError("");
    try {
      const result = await confirmDoc(selectedDocId);
      setMessage(`已保存为正式资料 ${result.confirmed} 条，跳过 ${result.skipped} 条。`);
      onDone();
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    }
  }

  return (
    <div className="page-shell">
      <section className="hero-panel">
        <div className="split-row split-row-start">
          <div>
            <div className="section-kicker">人工核对</div>
            <h2 className="section-title">核对自动整理结果，再保存为正式资料</h2>
            <p className="section-copy">系统整理结果先放在这里。你可以修改内容、查看注意事项，并把确认后的条目保存为正式资料。</p>
          </div>
          <div className="hero-metrics">
            <div className="metric-card">
              <span className="metric-label">条目数</span>
              <strong className="metric-value">{rows.length}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">已核对</span>
              <strong className="metric-value">{reviewedCount}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">需重点确认</span>
              <strong className="metric-value">{highRiskCount}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="content-grid">
        <aside className="sidebar-panel">
          <div className="toolbar-shell">
            <div className="split-row">
              <div>
                <h3 className="panel-title">待核对资料</h3>
                <p className="panel-copy">选择一份 PDF 查看整理结果。</p>
              </div>
              <button className="btn btn-ghost" onClick={() => void refreshDocuments()} type="button">
                刷新
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
                  <span className="badge badge-blue">{doc.admission_year || "未标年度"}</span>
                  <span className="badge badge-gray">待核对 {doc.staging_count}</span>
                </div>
                <h4 className="item-title">{doc.university_name || "待识别大学"}</h4>
                <p className="item-subtitle">{doc.filename}</p>
              </button>
            ))}
          </div>
        </aside>

        <div className="item-detail">
          {error && <div className="message-box error">{error}</div>}
          {message && <div className="message-box">{message}</div>}

          {!selectedRow ? (
            <div className="empty-state">
              <div className="card-kicker">暂无内容</div>
              <h3 className="panel-title">请选择左侧文档</h3>
              <p className="panel-copy">上传并整理后，待核对内容会出现在这里。</p>
            </div>
          ) : (
            <div className="detail-shell detail-shell-editing">
              <div className="detail-header">
                <div>
                  <div className="card-kicker">{summary?.university_name || "待核对内容"}</div>
                  <h3 className="panel-title">
                    {selectedRow.faculty || "未识别学部"} · {selectedRow.department || "未识别学科"}
                  </h3>
                </div>
                <div className="item-meta">
                  <span className={riskClass(selectedRow.risk_level)}>{riskText(selectedRow.risk_level)}</span>
                  <span className="badge badge-gray">{Number(selectedRow.is_reviewed) ? "已核对" : "待核对"}</span>
                </div>
              </div>

              {selectedRow.warnings_json?.length ? (
                <div className="message-box">
                  <strong>需要注意：</strong>
                  <ul>
                    {selectedRow.warnings_json.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="detail-grid">
                {REVIEW_FIELDS.map(([key, label]) => (
                  <label key={key} className="field-wrap detail-field is-span-2">
                    <span className="field-label">{label}</span>
                    <textarea
                      className="field"
                      rows={key.includes("period") || key.includes("schedule") || key === "deadline_rule" ? 3 : 2}
                      value={draft[key] ?? ""}
                      onChange={(event) => setDraft({ ...draft, [key]: event.target.value })}
                    />
                  </label>
                ))}
              </div>

              <div className="split-row">
                <div className="inline-actions">
                  <button className="btn btn-primary" disabled={saving} onClick={() => void save(false)} type="button">
                    保存修改
                  </button>
                  <button className="btn btn-green" disabled={saving} onClick={() => void save(true)} type="button">
                    保存并标记已核对
                  </button>
                </div>
                <button className="btn btn-green" onClick={() => void confirmCurrentDocument()} type="button">
                  保存整份资料
                </button>
              </div>

              {selectedDocId && (
                <div className="summary-box">
                  <h3 className="panel-title">PDF 预览</h3>
                  <p className="panel-copy">当前显示相关页面或第 1 页。需要精看时可打开原 PDF。</p>
                  <img alt="PDF 页面预览" style={{ width: "100%", borderRadius: 18 }} src={documentPageImageUrl(selectedDocId, selectedRow.page_number || 1)} />
                </div>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
