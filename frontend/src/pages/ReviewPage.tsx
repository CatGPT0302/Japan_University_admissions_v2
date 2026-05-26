import { useEffect, useMemo, useState } from "react";
import {
  confirmDoc,
  documentPageImageUrl,
  documentPdfUrl,
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

type ReviewField = {
  key: keyof StagingRecord;
  label: string;
  rows?: number;
};

const FIELD_GROUPS: Array<{ title: string; fields: ReviewField[] }> = [
  {
    title: "基本信息",
    fields: [
      { key: "university", label: "学校" },
      { key: "admission_year", label: "年度" },
      { key: "admission_period", label: "入学时期" },
      { key: "faculty", label: "学部" },
      { key: "department", label: "学科・专攻", rows: 2 },
      { key: "prefecture", label: "地区" },
      { key: "campus", label: "校区" },
    ],
  },
  {
    title: "时间安排",
    fields: [
      { key: "application_period", label: "出愿时间", rows: 3 },
      { key: "deadline_rule", label: "截止规则", rows: 3 },
      { key: "screening_schedule", label: "考试日程", rows: 3 },
      { key: "result_date", label: "结果公布", rows: 2 },
      { key: "enrollment_period", label: "入学手续", rows: 3 },
    ],
  },
  {
    title: "考试要求",
    fields: [
      { key: "eju_session", label: "EJU 场次", rows: 2 },
      { key: "eju_japanese", label: "EJU 日语", rows: 2 },
      { key: "eju_general", label: "EJU 综合科目", rows: 2 },
      { key: "eju_math", label: "EJU 数学", rows: 2 },
      { key: "eju_physics", label: "EJU 物理", rows: 2 },
      { key: "eju_chemistry", label: "EJU 化学", rows: 2 },
      { key: "eju_biology", label: "EJU 生物", rows: 2 },
      { key: "english_requirement", label: "英语要求", rows: 3 },
      { key: "screening_method", label: "选考方式", rows: 3 },
    ],
  },
];

const REVIEW_KEYS = FIELD_GROUPS.flatMap((group) => group.fields.map((field) => field.key));

function textValue(row: StagingRecord | null, key: keyof StagingRecord) {
  if (!row) return "";
  const value = row[key];
  return value === undefined || value === null ? "" : String(value);
}

function reviewFieldLabel(key: string) {
  for (const group of FIELD_GROUPS) {
    const field = group.fields.find((item) => item.key === key);
    if (field) return field.label;
  }
  return key;
}

function rowTitle(row: StagingRecord) {
  const faculty = row.faculty || "未识别学部";
  const department = row.department || "未识别学科";
  return `${faculty} / ${department}`;
}

function rowStatus(row: StagingRecord) {
  if (Number(row.is_confirmed)) return "已入库";
  if (Number(row.is_reviewed)) return "已复审";
  if (Number(row.needs_review)) return "待复审";
  return "待确认";
}

function statusClass(row: StagingRecord) {
  if (Number(row.is_confirmed)) return "badge badge-green";
  if (Number(row.is_reviewed)) return "badge badge-blue";
  return "badge badge-amber";
}

function sortRows(rows: StagingRecord[]) {
  return [...rows].sort((a, b) => {
    const aDone = Number(a.is_reviewed) || Number(a.is_confirmed);
    const bDone = Number(b.is_reviewed) || Number(b.is_confirmed);
    if (aDone !== bDone) return aDone - bDone;
    return Number(a.page_number || 0) - Number(b.page_number || 0);
  });
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

  const orderedRows = useMemo(() => sortRows(rows), [rows]);
  const selectedRow = useMemo(() => rows.find((row) => row.id === selectedRowId) ?? null, [rows, selectedRowId]);
  const selectedIndex = useMemo(
    () => orderedRows.findIndex((row) => row.id === selectedRowId),
    [orderedRows, selectedRowId],
  );
  const reviewedCount = rows.filter((row) => Number(row.is_reviewed) || Number(row.is_confirmed)).length;
  const remainingCount = Math.max(rows.length - reviewedCount, 0);
  const currentPage = selectedRow?.page_number || 1;
  const changedFields = useMemo(
    () => REVIEW_KEYS.filter((key) => selectedRow && (draft[key] ?? "") !== textValue(selectedRow, key)),
    [draft, selectedRow],
  );
  const hasUnsavedChanges = changedFields.length > 0;

  useEffect(() => {
    void refreshDocuments();
  }, []);

  useEffect(() => {
    if (defaultDocId) void openDocument(defaultDocId);
  }, [defaultDocId]);

  useEffect(() => {
    if (!selectedRow) return;
    const nextDraft: Record<string, string> = {};
    for (const key of REVIEW_KEYS) nextDraft[key] = textValue(selectedRow, key);
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
    if (hasUnsavedChanges && !window.confirm("当前修改还没有保存。要先切换到其他资料吗？")) return;
    setError("");
    setMessage("");
    const [docSummary, stagingRows] = await Promise.all([getDocumentSummary(docId), getStaging(docId)]);
    const nextRows = sortRows(stagingRows);
    setSelectedDocId(docId);
    setSummary(docSummary);
    setRows(stagingRows);
    setSelectedRowId(nextRows[0]?.id ?? null);
  }

  async function save(markReviewed: boolean, moveNext = false) {
    if (!selectedRow) return;
    setSaving(true);
    setError("");
    try {
      const updated = await patchStaging(selectedRow.id, {
        ...draft,
        ...(markReviewed ? { is_reviewed: 1, needs_review: 0 } : {}),
      });
      const nextRows = rows.map((row) => (row.id === selectedRow.id ? updated : row));
      const nextOrdered = sortRows(nextRows);
      setRows(nextRows);
      if (moveNext) {
        const next = nextOrdered.find((row) => !Number(row.is_reviewed) && !Number(row.is_confirmed));
        setSelectedRowId(next?.id ?? updated.id);
      } else {
        setSelectedRowId(updated.id);
      }
      setMessage(markReviewed ? "已保存，并标记为复审完成。" : "修改已保存。");
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
      setMessage(`已写入确认数据 ${result.confirmed} 条，跳过 ${result.skipped} 条。`);
      onDone();
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    }
  }

  function selectRelative(offset: number) {
    if (!orderedRows.length) return;
    const nextIndex = Math.min(Math.max(selectedIndex + offset, 0), orderedRows.length - 1);
    selectRow(orderedRows[nextIndex]?.id ?? null);
  }

  function selectRow(rowId: number | null) {
    if (rowId === selectedRowId) return;
    if (hasUnsavedChanges && !window.confirm("当前修改还没有保存。要先切换到其他词条吗？")) return;
    setSelectedRowId(rowId);
  }

  return (
    <div className="review-workbench">
      <aside className="review-sidebar">
        <div className="review-sidebar-head">
          <div>
            <div className="section-kicker">人工复审</div>
            <h2>资料队列</h2>
          </div>
          <button className="btn btn-ghost btn-small" onClick={() => void refreshDocuments()} type="button">
            刷新
          </button>
        </div>

        <div className="review-doc-list">
          {documents.map((doc) => (
            <button
              key={doc.doc_id}
              className={`review-doc-card${selectedDocId === doc.doc_id ? " is-active" : ""}`}
              onClick={() => void openDocument(doc.doc_id)}
              type="button"
            >
              <span>{doc.admission_year || "未标年度"}</span>
              <strong>{doc.university_name || "未命名学校"}</strong>
              <em>
                {doc.staging_count} 条待处理 / {doc.confirmed_count} 条已入库
              </em>
            </button>
          ))}
        </div>
      </aside>

      <main className="review-main">
        <header className="review-topbar">
          <div>
            <div className="workspace-header-label">当前资料</div>
            <h1>{summary?.university_name || "请选择一份资料"}</h1>
            <p>{summary?.filename || "从左侧队列选择资料后，可以对照源 PDF 快速修改词条。"}</p>
          </div>
          <div className="review-topbar-actions">
            <div className="review-progress-pill">
              <strong>{reviewedCount}</strong>
              <span>已复审</span>
            </div>
            <div className="review-progress-pill">
              <strong>{remainingCount}</strong>
              <span>待处理</span>
            </div>
            <button
              className="btn btn-green"
              disabled={!selectedDocId || !rows.length}
              onClick={() => void confirmCurrentDocument()}
              type="button"
            >
              确认整份入库
            </button>
          </div>
        </header>

        {error ? <div className="message-box error">{error}</div> : null}
        {message ? <div className="message-box">{message}</div> : null}

        {!selectedRow ? (
          <div className="empty-state">
            <div className="card-kicker">等待选择</div>
            <h3 className="panel-title">请选择一份资料</h3>
            <p className="panel-copy">上传并整理后的内容会在这里复审。确认数据不会被来源监测自动覆盖。</p>
          </div>
        ) : (
          <section className="review-grid">
            <section className="review-row-list">
              <div className="review-panel-head">
                <h3>词条</h3>
                <span>{orderedRows.length} 条</span>
              </div>
              <div className="review-record-list">
                {orderedRows.map((row, index) => (
                  <button
                    key={row.id}
                    className={`review-record-card${row.id === selectedRow.id ? " is-active" : ""}`}
                    onClick={() => selectRow(row.id)}
                    type="button"
                  >
                    <span className={statusClass(row)}>{rowStatus(row)}</span>
                    <strong>{rowTitle(row)}</strong>
                    <em>
                      第 {row.page_number || 1} 页 · {index + 1}/{orderedRows.length}
                    </em>
                  </button>
                ))}
              </div>
            </section>

            <section className="review-pdf-panel">
              <div className="review-panel-head">
                <div>
                  <h3>源 PDF</h3>
                  <span>第 {currentPage} 页</span>
                </div>
                {selectedDocId ? (
                  <a className="btn btn-ghost btn-small" href={documentPdfUrl(selectedDocId, currentPage)} target="_blank" rel="noreferrer">
                    打开原文
                  </a>
                ) : null}
              </div>
              <div className="review-pdf-scroll">
                {selectedDocId ? (
                  <img className="review-pdf-image" alt="PDF 页面预览" src={documentPageImageUrl(selectedDocId, currentPage, 1.35)} />
                ) : null}
              </div>
            </section>

            <section className="review-editor-panel">
              <div className="review-panel-head">
                <div>
                  <h3>{rowTitle(selectedRow)}</h3>
                  <span>{rowStatus(selectedRow)}</span>
                </div>
                <div className="review-stepper">
                  <button className="btn btn-ghost btn-small" disabled={selectedIndex <= 0} onClick={() => selectRelative(-1)} type="button">
                    上一条
                  </button>
                  <button
                    className="btn btn-ghost btn-small"
                    disabled={selectedIndex >= orderedRows.length - 1}
                    onClick={() => selectRelative(1)}
                    type="button"
                  >
                    下一条
                  </button>
                </div>
              </div>

              <div className="review-editor-scroll">
                <div className={`review-change-summary${hasUnsavedChanges ? " is-dirty" : ""}`}>
                  <div>
                    <strong>{hasUnsavedChanges ? `${changedFields.length} 处修改未保存` : "当前词条没有未保存修改"}</strong>
                    <span>{hasUnsavedChanges ? "保存后再确认入库，避免改动丢失。" : "可以直接继续复审或切换下一条。"}</span>
                  </div>
                  {hasUnsavedChanges ? (
                    <div className="review-change-tags" aria-label="已修改内容">
                      {changedFields.slice(0, 6).map((key) => (
                        <span key={key}>{reviewFieldLabel(String(key))}</span>
                      ))}
                      {changedFields.length > 6 ? <span>另 {changedFields.length - 6} 处</span> : null}
                    </div>
                  ) : null}
                </div>
                {FIELD_GROUPS.map((group) => (
                  <fieldset key={group.title} className="review-fieldset">
                    <legend>{group.title}</legend>
                    {group.fields.map((field) => (
                      <label key={field.key} className="field-wrap">
                        <span className="field-label">{field.label}</span>
                        <textarea
                          className="field review-field"
                          rows={field.rows || 1}
                          value={draft[field.key] ?? ""}
                          onChange={(event) => setDraft({ ...draft, [field.key]: event.target.value })}
                        />
                      </label>
                    ))}
                  </fieldset>
                ))}
              </div>

              <div className="review-editor-actions">
                <button className="btn btn-ghost" disabled={saving} onClick={() => void save(false)} type="button">
                  保存草稿
                </button>
                <button className="btn btn-primary" disabled={saving} onClick={() => void save(true, true)} type="button">
                  保存并复审下一条
                </button>
              </div>
            </section>
          </section>
        )}
      </main>
    </div>
  );
}
