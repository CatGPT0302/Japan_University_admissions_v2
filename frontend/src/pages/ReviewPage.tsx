import { useEffect, useMemo, useRef, useState } from "react";
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
import type { DocumentListItem, DocumentSummary, ReviewFocus, StagingRecord } from "../types";

interface Props {
  defaultDocId?: number | null;
  defaultFocus?: ReviewFocus | null;
  onDone: () => void;
  onOpenExports?: (filters: { university?: string; year?: string }) => void;
}

type ReviewField = {
  key: keyof StagingRecord;
  label: string;
  rows?: number;
};

type ReviewFilter = "all" | "pending" | "priority" | "done";

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
  {
    title: "材料与资格",
    fields: [
      { key: "eligibility", label: "出愿资格", rows: 4 },
      { key: "required_documents", label: "所需材料", rows: 4 },
      { key: "evidence", label: "来源依据", rows: 3 },
    ],
  },
];

const REVIEW_KEYS = FIELD_GROUPS.flatMap((group) => group.fields.map((field) => field.key));

const REVIEW_FILTERS: Array<{ key: ReviewFilter; label: string }> = [
  { key: "pending", label: "待处理" },
  { key: "priority", label: "先看" },
  { key: "done", label: "已完成" },
  { key: "all", label: "全部" },
];

function textValue(row: StagingRecord | null, key: keyof StagingRecord) {
  if (!row) return "";
  const value = row[key];
  return value === undefined || value === null ? "" : String(value);
}

function evidenceForField(row: StagingRecord | null, key: keyof StagingRecord) {
  const item = row?.field_evidence?.[String(key)];
  if (!item) return null;
  const text = String(item.text || "").trim();
  const page = item.page === null || item.page === undefined ? null : Number(item.page);
  if (!text && !page) return null;
  return { text, page: Number.isFinite(page) ? page : null };
}

function shortEvidence(text: string) {
  return text.length > 180 ? `${text.slice(0, 180)}...` : text;
}

function reviewFieldLabel(key: string) {
  for (const group of FIELD_GROUPS) {
    const field = group.fields.find((item) => item.key === key);
    if (field) return field.label;
  }
  return key;
}

function groupIndexForField(key: keyof StagingRecord) {
  const index = FIELD_GROUPS.findIndex((group) => group.fields.some((field) => field.key === key));
  return index < 0 ? 0 : index;
}

function reviewHints(row: StagingRecord | null, draft: Record<string, string>) {
  if (!row) return [];
  const hints: Array<{ key: keyof StagingRecord; label: string; reason: string }> = [];
  for (const key of REVIEW_KEYS) {
    const value = String(draft[key] ?? textValue(row, key)).trim();
    const confidence = Number(row.field_confidence?.[String(key)] ?? 0);
    if (!value) {
      hints.push({ key, label: reviewFieldLabel(String(key)), reason: "还没填" });
    } else if (confidence > 0 && confidence < 0.75) {
      hints.push({ key, label: reviewFieldLabel(String(key)), reason: "需要对照来源" });
    }
  }
  return hints.slice(0, 8);
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

function documentStatusText(doc: DocumentListItem) {
  const reviewCount = Number(doc.review_count || 0);
  const confirmedCount = Number(doc.confirmed_count || 0);
  const stagingCount = Number(doc.staging_count || 0);
  if (reviewCount > 0) return `${reviewCount} 条待复审`;
  if (confirmedCount > 0) return "可导出";
  if (stagingCount > 0) return "待确认入库";
  return "等待整理";
}

function documentStatusClass(doc: DocumentListItem) {
  if (Number(doc.review_count || 0) > 0) return "badge badge-amber";
  if (Number(doc.confirmed_count || 0) > 0) return "badge badge-green";
  if (Number(doc.staging_count || 0) > 0) return "badge badge-blue";
  return "badge badge-gray";
}

function isReviewed(row: StagingRecord) {
  return Boolean(Number(row.is_reviewed) || Number(row.is_confirmed));
}

function needsAttention(row: StagingRecord) {
  if (isReviewed(row)) return false;
  const confidence = Number(row.confidence || 0);
  return Boolean(Number(row.needs_review) || row.risk_level === "high" || (confidence > 0 && confidence < 0.75));
}

function statusClass(row: StagingRecord) {
  if (Number(row.is_confirmed)) return "badge badge-green";
  if (Number(row.is_reviewed)) return "badge badge-blue";
  return "badge badge-amber";
}

function filterRows(rows: StagingRecord[], filter: ReviewFilter) {
  if (filter === "pending") return rows.filter((row) => !isReviewed(row));
  if (filter === "priority") return rows.filter((row) => needsAttention(row));
  if (filter === "done") return rows.filter((row) => isReviewed(row));
  return rows;
}

function sortRows(rows: StagingRecord[]) {
  return [...rows].sort((a, b) => {
    const aDone = Number(isReviewed(a));
    const bDone = Number(isReviewed(b));
    const aAttention = Number(needsAttention(a));
    const bAttention = Number(needsAttention(b));
    if (aDone !== bDone) return aDone - bDone;
    if (aAttention !== bAttention) return bAttention - aAttention;
    return Number(a.page_number || 0) - Number(b.page_number || 0);
  });
}

function normalizedFocusValue(value?: string | null) {
  return String(value || "").trim().toLowerCase();
}

function findFocusedRow(rows: StagingRecord[], focus?: ReviewFocus | null) {
  if (!focus) return null;
  const faculty = normalizedFocusValue(focus.faculty);
  const department = normalizedFocusValue(focus.department);
  const university = normalizedFocusValue(focus.university);
  const year = normalizedFocusValue(focus.admission_year);
  return (
    rows.find((row) => {
      const sameFaculty = !faculty || normalizedFocusValue(row.faculty).includes(faculty) || faculty.includes(normalizedFocusValue(row.faculty));
      const sameDepartment =
        !department || normalizedFocusValue(row.department).includes(department) || department.includes(normalizedFocusValue(row.department));
      const sameUniversity =
        !university || normalizedFocusValue(row.university).includes(university) || university.includes(normalizedFocusValue(row.university));
      const sameYear = !year || normalizedFocusValue(row.admission_year).includes(year);
      return sameFaculty && sameDepartment && sameUniversity && sameYear;
    }) ??
    rows.find((row) => {
      const sameFaculty = !faculty || normalizedFocusValue(row.faculty).includes(faculty) || faculty.includes(normalizedFocusValue(row.faculty));
      const sameYear = !year || normalizedFocusValue(row.admission_year).includes(year);
      return sameFaculty && sameYear;
    }) ??
    null
  );
}

export default function ReviewPage({ defaultDocId, defaultFocus, onDone, onOpenExports }: Props) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [summary, setSummary] = useState<DocumentSummary | null>(null);
  const [rows, setRows] = useState<StagingRecord[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(defaultDocId ?? null);
  const [selectedRowId, setSelectedRowId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("pending");
  const [activeGroupIndex, setActiveGroupIndex] = useState(0);
  const [focusedEvidencePage, setFocusedEvidencePage] = useState<number | null>(null);
  const [focusNotice, setFocusNotice] = useState<ReviewFocus | null>(null);
  const [pageInput, setPageInput] = useState("1");
  const editorPanelRef = useRef<HTMLElement | null>(null);
  const pendingFocusRef = useRef<ReviewFocus | null>(null);

  const allOrderedRows = useMemo(() => sortRows(rows), [rows]);
  const orderedRows = useMemo(() => filterRows(allOrderedRows, reviewFilter), [allOrderedRows, reviewFilter]);
  const selectedRow = useMemo(() => rows.find((row) => row.id === selectedRowId) ?? null, [rows, selectedRowId]);
  const selectedIndex = useMemo(
    () => orderedRows.findIndex((row) => row.id === selectedRowId),
    [orderedRows, selectedRowId],
  );
  const reviewedCount = rows.filter((row) => Number(row.is_reviewed) || Number(row.is_confirmed)).length;
  const remainingCount = Math.max(rows.length - reviewedCount, 0);
  const priorityCount = rows.filter((row) => needsAttention(row)).length;
  const currentPage = focusedEvidencePage || selectedRow?.page_number || 1;
  const changedFields = useMemo(
    () => REVIEW_KEYS.filter((key) => selectedRow && (draft[key] ?? "") !== textValue(selectedRow, key)),
    [draft, selectedRow],
  );
  const hasUnsavedChanges = changedFields.length > 0;
  const activeGroup = FIELD_GROUPS[Math.min(activeGroupIndex, FIELD_GROUPS.length - 1)] ?? FIELD_GROUPS[0];
  const currentHints = useMemo(() => reviewHints(selectedRow, draft), [draft, selectedRow]);

  useEffect(() => {
    void refreshDocuments();
  }, []);

  useEffect(() => {
    setPageInput(String(currentPage));
  }, [currentPage]);

  useEffect(() => {
    if (defaultDocId && !defaultFocus?.docId) void openDocument(defaultDocId);
  }, [defaultDocId, defaultFocus?.docId]);

  useEffect(() => {
    if (defaultFocus?.docId) void openDocument(defaultFocus.docId, defaultFocus);
  }, [defaultFocus?.token]);

  useEffect(() => {
    if (!selectedRow) return;
    const nextDraft: Record<string, string> = {};
    for (const key of REVIEW_KEYS) nextDraft[key] = textValue(selectedRow, key);
    setDraft(nextDraft);
    const focus = pendingFocusRef.current;
    const focusKey = focus?.field as keyof StagingRecord | undefined;
    if (focusKey && REVIEW_KEYS.includes(focusKey)) {
      setActiveGroupIndex(groupIndexForField(focusKey));
      const evidence = evidenceForField(selectedRow, focusKey);
      setFocusedEvidencePage(evidence?.page ?? selectedRow.page_number ?? null);
      window.setTimeout(() => {
        const field = editorPanelRef.current?.querySelector<HTMLTextAreaElement>(`[data-review-key="${String(focusKey)}"]`);
        field?.focus();
        field?.scrollIntoView({ block: "center", behavior: "smooth" });
      }, 0);
      pendingFocusRef.current = null;
    } else {
      setActiveGroupIndex(0);
      setFocusedEvidencePage(null);
    }
  }, [selectedRow]);

  async function refreshDocuments() {
    try {
      setDocuments(await getDocuments({ limit: 100 }));
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    }
  }

  async function openDocument(docId: number, focus?: ReviewFocus | null) {
    if (hasUnsavedChanges && !window.confirm("当前修改还没有保存。要先切换到其他资料吗？")) return;
    setError("");
    setMessage("");
    const [docSummary, stagingRows] = await Promise.all([getDocumentSummary(docId), getStaging(docId)]);
    const nextRows = sortRows(stagingRows);
    const focusedRow = findFocusedRow(nextRows, focus);
    pendingFocusRef.current = focus ?? null;
    setFocusNotice(focus?.field ? focus : null);
    setSelectedDocId(docId);
    setSummary(docSummary);
    setRows(stagingRows);
    setSelectedRowId(focusedRow?.id ?? nextRows[0]?.id ?? null);
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
      const nextVisible = filterRows(nextOrdered, reviewFilter);
      setRows(nextRows);
      if (moveNext) {
        const next = nextVisible.find((row) => !isReviewed(row)) ?? nextOrdered.find((row) => !isReviewed(row));
        setFocusNotice(null);
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
      if (onOpenExports) {
        onOpenExports({
          university: summary?.university_name || selectedRow?.university || "",
          year: summary?.admission_year || selectedRow?.admission_year || "",
        });
      } else {
        onDone();
      }
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    }
  }

  function selectRelative(offset: number) {
    if (!orderedRows.length) return;
    const baseIndex = selectedIndex < 0 ? 0 : selectedIndex;
    const nextIndex = Math.min(Math.max(baseIndex + offset, 0), orderedRows.length - 1);
    selectRow(orderedRows[nextIndex]?.id ?? null);
  }

  function selectRow(rowId: number | null) {
    if (rowId === selectedRowId) return;
    if (hasUnsavedChanges && !window.confirm("当前修改还没有保存。要先切换到其他词条吗？")) return;
    setFocusNotice(null);
    setSelectedRowId(rowId);
  }

  function setPdfPage(page: number) {
    const nextPage = Math.max(1, Math.floor(Number.isFinite(page) ? page : 1));
    setFocusedEvidencePage(nextPage);
    setPageInput(String(nextPage));
  }

  function commitPdfPage() {
    setPdfPage(Number(pageInput));
  }

  function focusReviewField(key: keyof StagingRecord) {
    setActiveGroupIndex(groupIndexForField(key));
    const evidence = evidenceForField(selectedRow, key);
    if (evidence?.page) setFocusedEvidencePage(evidence.page);
    window.setTimeout(() => {
      const selector = `[data-review-key="${String(key)}"]`;
      const field = editorPanelRef.current?.querySelector<HTMLTextAreaElement>(selector);
      field?.focus();
      field?.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 0);
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (!selectedRow) return;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void save(false);
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        void save(true, true);
        return;
      }
      if (event.altKey && event.key === "ArrowDown") {
        event.preventDefault();
        selectRelative(1);
        return;
      }
      if (event.altKey && event.key === "ArrowUp") {
        event.preventDefault();
        selectRelative(-1);
        return;
      }
      if (event.altKey && event.key === "ArrowRight") {
        event.preventDefault();
        setPdfPage(currentPage + 1);
        return;
      }
      if (event.altKey && event.key === "ArrowLeft") {
        event.preventDefault();
        setPdfPage(currentPage - 1);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [currentPage, draft, hasUnsavedChanges, orderedRows, selectedIndex, selectedRow]);

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
              <div className="item-card-topline">
                <span>{doc.admission_year || "未标年度"}</span>
                <span className={documentStatusClass(doc)}>{documentStatusText(doc)}</span>
              </div>
              <strong>{doc.university_name || "未命名学校"}</strong>
              <em>
                {doc.staging_count} 条草稿 / {doc.confirmed_count} 条正式资料
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
            <div className="review-progress-pill">
              <strong>{priorityCount}</strong>
              <span>先看</span>
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
              <div className="review-filter-tabs" aria-label="复审范围">
                {REVIEW_FILTERS.map((item) => {
                  const count =
                    item.key === "pending"
                      ? remainingCount
                      : item.key === "priority"
                        ? priorityCount
                        : item.key === "done"
                          ? reviewedCount
                          : rows.length;
                  return (
                    <button
                      className={reviewFilter === item.key ? "is-active" : ""}
                      key={item.key}
                      onClick={() => setReviewFilter(item.key)}
                      type="button"
                    >
                      <span>{item.label}</span>
                      <strong>{count}</strong>
                    </button>
                  );
                })}
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
                {!orderedRows.length ? <div className="empty-state empty-state-quiet">这个范围里暂时没有需要处理的词条。</div> : null}
              </div>
            </section>

            <section className="review-pdf-panel">
              <div className="review-panel-head">
                <div>
                  <h3>源 PDF</h3>
                  <span>第 {currentPage} 页</span>
                </div>
                {selectedDocId ? (
                  <div className="review-pdf-tools" aria-label="PDF 页面操作">
                    <button className="btn btn-ghost btn-small" disabled={currentPage <= 1} onClick={() => setPdfPage(currentPage - 1)} type="button">
                      上一页
                    </button>
                    <form
                      className="review-page-jump"
                      onSubmit={(event) => {
                        event.preventDefault();
                        commitPdfPage();
                      }}
                    >
                      <label>
                        <span>跳到</span>
                        <input
                          aria-label="跳到 PDF 页码"
                          inputMode="numeric"
                          min="1"
                          onBlur={commitPdfPage}
                          onChange={(event) => setPageInput(event.target.value)}
                          type="number"
                          value={pageInput}
                        />
                      </label>
                      <button className="btn btn-ghost btn-small" type="submit">
                        前往
                      </button>
                    </form>
                    <button className="btn btn-ghost btn-small" onClick={() => setPdfPage(currentPage + 1)} type="button">
                      下一页
                    </button>
                    <a className="btn btn-ghost btn-small" href={documentPdfUrl(selectedDocId, currentPage)} target="_blank" rel="noreferrer">
                      打开原文
                    </a>
                  </div>
                ) : null}
              </div>
              <div className="review-pdf-scroll">
                {selectedDocId ? (
                  <img className="review-pdf-image" alt="PDF 页面预览" src={documentPageImageUrl(selectedDocId, currentPage, 1.35)} />
                ) : null}
              </div>
            </section>

            <section className="review-editor-panel" ref={editorPanelRef}>
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
                {focusNotice?.field && selectedRow ? (
                  <div className="review-focus-banner">
                    <div>
                      <strong>{focusNotice.origin_label || "从导出缺口进入"}</strong>
                      <span>先补齐：{reviewFieldLabel(focusNotice.field)}</span>
                    </div>
                    <button className="btn btn-primary btn-small" type="button" onClick={() => focusReviewField(focusNotice.field as keyof StagingRecord)}>
                      定位到这一项
                    </button>
                  </div>
                ) : null}
                {currentHints.length ? (
                  <div className="review-priority-strip">
                    <div>
                      <strong>建议先看</strong>
                      <span>这些内容会影响后续查询和导出。</span>
                    </div>
                    <div className="review-priority-chips" aria-label="建议先看的内容">
                      {currentHints.map((hint) => (
                        <button key={String(hint.key)} type="button" onClick={() => focusReviewField(hint.key)}>
                          <span>{hint.label}</span>
                          <em>{hint.reason}</em>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="review-group-tabs" aria-label="复审内容分组">
                  {FIELD_GROUPS.map((group, index) => {
                    const modifiedCount = group.fields.filter((field) => changedFields.includes(field.key)).length;
                    return (
                      <button
                        className={activeGroupIndex === index ? "is-active" : ""}
                        key={group.title}
                        onClick={() => setActiveGroupIndex(index)}
                        type="button"
                      >
                        <span>{group.title}</span>
                        {modifiedCount ? <strong>{modifiedCount}</strong> : null}
                      </button>
                    );
                  })}
                </div>
                <fieldset className="review-fieldset review-fieldset-active">
                  <legend>{activeGroup.title}</legend>
                  {activeGroup.fields.map((field) => {
                    const evidence = evidenceForField(selectedRow, field.key);
                    return (
                      <div key={field.key} className="review-field-block">
                        <label className="field-wrap">
                          <span className="field-label">{field.label}</span>
                          <textarea
                            className="field review-field"
                            data-review-key={String(field.key)}
                            rows={field.rows || 1}
                            value={draft[field.key] ?? ""}
                            onChange={(event) => setDraft({ ...draft, [field.key]: event.target.value })}
                          />
                        </label>
                        {evidence ? (
                          <div className="review-evidence-note">
                            <div>
                              <span>来源提示{evidence.page ? ` · 第 ${evidence.page} 页` : ""}</span>
                              <p>{evidence.text ? shortEvidence(evidence.text) : "这一项有页码提示，请对照原文确认。"}</p>
                            </div>
                            {evidence.page ? (
                              <button className="btn btn-ghost btn-small" type="button" onClick={() => setFocusedEvidencePage(evidence.page)}>
                                看这一页
                              </button>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </fieldset>
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
