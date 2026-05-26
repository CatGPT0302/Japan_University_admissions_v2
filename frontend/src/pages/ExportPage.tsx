import { useEffect, useMemo, useState } from "react";
import { downloadCsv, downloadExcel, getExportPreview, toErrorMessage } from "../api/client";
import type { ConfirmedRecord, ExportPreviewResponse } from "../types";

const COLUMNS: Array<{ key: keyof ConfirmedRecord; label: string }> = [
  { key: "university", label: "学校" },
  { key: "admission_year", label: "年度" },
  { key: "faculty", label: "学部" },
  { key: "department", label: "学科・专攻" },
  { key: "application_period", label: "出愿时间" },
  { key: "eju_japanese", label: "EJU 日语" },
  { key: "english_requirement", label: "英语要求" },
  { key: "screening_schedule", label: "考试日程" },
  { key: "result_date", label: "结果公布" },
];

function splitItems(value: string) {
  return value
    .replace(/，/g, ",")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function RowPreview({ row }: { row: ConfirmedRecord }) {
  return (
    <tr>
      {COLUMNS.map((column) => (
        <td key={column.key}>{String(row[column.key] || "-")}</td>
      ))}
    </tr>
  );
}

export default function ExportPage() {
  const [quickSchool, setQuickSchool] = useState("");
  const [universities, setUniversities] = useState("");
  const [years, setYears] = useState("");
  const [faculties, setFaculties] = useState("");
  const [preview, setPreview] = useState<ExportPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const params = useMemo(
    () => ({
      universities: universities.trim() || undefined,
      years: years.trim() || undefined,
      faculties: faculties.trim() || undefined,
    }),
    [faculties, universities, years],
  );

  const quickParams = useMemo(
    () => ({
      universities: quickSchool.trim() || undefined,
      years: years.trim() || undefined,
      faculties: undefined,
    }),
    [quickSchool, years],
  );

  async function loadPreview(nextParams = params) {
    setLoading(true);
    setError("");
    try {
      const nextPreview = await getExportPreview({ ...nextParams, limit: 300 });
      setPreview(nextPreview);
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setLoading(false);
    }
  }

  function previewQuickSchool() {
    if (!quickSchool.trim()) return;
    setUniversities(quickSchool.trim());
    void loadPreview(quickParams);
  }

  useEffect(() => {
    void loadPreview();
  }, []);

  const filterCount = splitItems(universities).length + splitItems(years).length + splitItems(faculties).length;
  const rows = preview?.rows ?? [];

  return (
    <div className="page-shell export-page">
      <section className="export-hero">
        <div>
          <div className="section-kicker">导出中心</div>
          <h2 className="section-title">快速取出确认后的招生资料</h2>
          <p className="section-copy">
            面向表格工作流：可以查单所学校，也可以把多所学校、多个年度合并成一张表。导出内容只来自已确认资料，不包含内部复审信息。
          </p>
        </div>
        <div className="export-summary-strip">
          <div>
            <span>当前结果</span>
            <strong>{preview?.summary.records ?? "-"}</strong>
          </div>
          <div>
            <span>学校</span>
            <strong>{preview?.summary.universities ?? "-"}</strong>
          </div>
          <div>
            <span>条件</span>
            <strong>{filterCount}</strong>
          </div>
        </div>
      </section>

      <section className="export-layout">
        <aside className="export-panel">
          <div className="export-panel-header">
            <h3>单校快速取出</h3>
            <p>输入学校名，先预览，再导出 Excel。年度留空时会取出该校已有的确认资料。</p>
          </div>

          <label className="field-wrap">
            <span className="field-label">学校名</span>
            <input
              className="field"
              value={quickSchool}
              onChange={(event) => setQuickSchool(event.target.value)}
              placeholder="例：早稻田大学"
            />
          </label>

          <div className="export-quick-actions">
            <button className="btn btn-primary" type="button" onClick={previewQuickSchool} disabled={!quickSchool.trim() || loading}>
              预览这所学校
            </button>
            <button className="btn btn-green" type="button" onClick={() => downloadExcel(quickParams)} disabled={!quickSchool.trim()}>
              导出这所学校
            </button>
          </div>

          <div className="export-divider" />

          <div className="export-panel-header">
            <h3>批量合并取出</h3>
            <p>多个值用逗号分开。留空时不限制该项。</p>
          </div>

          <label className="field-wrap">
            <span className="field-label">学校</span>
            <textarea
              className="field export-textarea"
              value={universities}
              onChange={(event) => setUniversities(event.target.value)}
              placeholder="例：早稻田大学, 明治大学, 九州大学"
            />
          </label>

          <label className="field-wrap">
            <span className="field-label">年度</span>
            <input className="field" value={years} onChange={(event) => setYears(event.target.value)} placeholder="例：2026, 2027" />
          </label>

          <label className="field-wrap">
            <span className="field-label">学部</span>
            <input className="field" value={faculties} onChange={(event) => setFaculties(event.target.value)} placeholder="例：文学部, 工学部" />
          </label>

          {error ? <div className="message-box error">{error}</div> : null}

          <div className="export-actions">
            <button className="btn btn-primary" type="button" onClick={() => void loadPreview()} disabled={loading}>
              {loading ? "正在整理" : "刷新预览"}
            </button>
            <button className="btn btn-green" type="button" onClick={() => downloadExcel(params)} disabled={!rows.length}>
              导出合并 Excel
            </button>
            <button className="btn btn-ghost" type="button" onClick={() => downloadCsv(params)} disabled={!rows.length}>
              导出 CSV
            </button>
          </div>
        </aside>

        <div className="export-table-shell">
          <div className="export-table-header">
            <div>
              <div className="card-kicker">预览</div>
              <h3 className="panel-title">合并后的表格内容</h3>
            </div>
            <span className="badge badge-gray">{rows.length} 条</span>
          </div>

          <div className="export-table-scroll">
            <table className="export-table">
              <thead>
                <tr>
                  {COLUMNS.map((column) => (
                    <th key={column.key}>{column.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>{rows.map((row) => <RowPreview key={row.id} row={row} />)}</tbody>
            </table>
          </div>

          {!rows.length && !loading ? (
            <div className="empty-state empty-state-quiet">
              <h3 className="panel-title">没有符合条件的资料</h3>
              <p className="panel-copy">调整学校、年度或学部后再刷新预览。</p>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
