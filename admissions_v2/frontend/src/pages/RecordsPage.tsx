import { useEffect, useMemo, useState } from "react";
import { downloadCsv, downloadExcel, getRecords, getStats, toErrorMessage } from "../api/client";
import type { ExportDownloadParams } from "../api/client";
import type { ConfirmedRecord, StatsResponse } from "../types";

const RECORD_FIELDS: Array<{ key: keyof ConfirmedRecord; label: string }> = [
  { key: "university", label: "大学名称" },
  { key: "admission_year", label: "入学年度" },
  { key: "admission_period", label: "入试方式" },
  { key: "faculty", label: "学部" },
  { key: "department", label: "学科/专业" },
  { key: "application_period", label: "出愿期间" },
  { key: "deadline_rule", label: "截止规则" },
  { key: "eju_session", label: "EJU场次" },
  { key: "eju_japanese", label: "EJU日语" },
  { key: "eju_general", label: "EJU综合科目" },
  { key: "eju_math", label: "EJU数学" },
  { key: "eju_physics", label: "EJU物理" },
  { key: "eju_chemistry", label: "EJU化学" },
  { key: "eju_biology", label: "EJU生物" },
  { key: "english_requirement", label: "英语要求" },
  { key: "screening_method", label: "选考方式" },
  { key: "screening_schedule", label: "选考日程" },
  { key: "result_date", label: "合格发表日" },
  { key: "enrollment_period", label: "入学手续期间" },
  { key: "prefecture", label: "都道府县" },
  { key: "campus", label: "校区" },
];

function yearNumber(value?: string | number | null): number | undefined {
  const match = String(value || "").match(/\d{4}/);
  return match ? Number(match[0]) : undefined;
}

export default function RecordsPage() {
  const [rows, setRows] = useState<ConfirmedRecord[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [university, setUniversity] = useState("");
  const [faculty, setFaculty] = useState("");
  const [year, setYear] = useState("");
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [downloadBusy, setDownloadBusy] = useState(false);
  const [downloadMessage, setDownloadMessage] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [records, summary] = await Promise.all([
        getRecords({
          university: university || undefined,
          faculty: faculty || undefined,
          year: year ? Number(year) : undefined,
          limit: 1000,
        }),
        getStats(),
      ]);
      setRows(records);
      setStats(summary);
      setSelectedIndex(null);
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function runDownload(format: "excel" | "csv", params: ExportDownloadParams) {
    setDownloadBusy(true);
    setError("");
    setDownloadMessage("");
    try {
      const filename = format === "excel" ? await downloadExcel(params) : await downloadCsv(params);
      setDownloadMessage(`已生成 ${filename}`);
    } catch (nextError) {
      setError(`导出失败：${toErrorMessage(nextError)}`);
    } finally {
      setDownloadBusy(false);
    }
  }

  const selectedRow = selectedIndex === null ? null : rows[selectedIndex] ?? null;
  const activeFilters = useMemo(
    () => [university ? `大学：${university}` : "", faculty ? `学部：${faculty}` : "", year ? `年度：${year}` : ""].filter(Boolean),
    [faculty, university, year],
  );

  return (
    <div className="page-shell">
      <section className="hero-panel">
        <div className="split-row split-row-start">
          <div>
            <div className="section-kicker">正式资料</div>
            <h2 className="section-title">已发布的招生资料</h2>
          </div>
          <div className="hero-metrics">
            <div className="metric-card">
              <span className="metric-label">当前结果</span>
              <strong className="metric-value">{rows.length}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">正式资料总数</span>
              <strong className="metric-value">{stats?.total_records ?? "-"}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">大学数</span>
              <strong className="metric-value">{stats?.universities ?? "-"}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="content-grid">
        <aside className="sidebar-panel">
          <div className="toolbar-shell">
            <h3 className="panel-title">筛选与导出</h3>
            <p className="panel-copy">筛选只影响当前查看和导出范围；清空后即可导出全部正式资料。</p>
            <div className="list-stack">
              <label className="field-wrap">
                <span className="field-label">大学</span>
                <input className="field" value={university} onChange={(event) => setUniversity(event.target.value)} placeholder="例如：早稲田大学" />
              </label>
              <label className="field-wrap">
                <span className="field-label">学部</span>
                <input className="field" value={faculty} onChange={(event) => setFaculty(event.target.value)} placeholder="例如：文学部" />
              </label>
              <label className="field-wrap">
                <span className="field-label">年度</span>
                <input className="field" value={year} onChange={(event) => setYear(event.target.value)} placeholder="2027" />
              </label>
              <button className="btn btn-primary" onClick={() => void load()} type="button">
                {loading ? "查询中..." : "查询"}
              </button>
              <button
                className="btn btn-primary"
                onClick={() =>
                  void runDownload("excel", {
                    university: university || undefined,
                    faculty: faculty || undefined,
                    year: year ? Number(year) : undefined,
                  })
                }
                disabled={downloadBusy}
                type="button"
              >
                {downloadBusy ? "正在生成" : "导出 Excel 表"}
              </button>
              <button
                className="btn btn-ghost"
                onClick={() =>
                  void runDownload("csv", {
                    university: university || undefined,
                    faculty: faculty || undefined,
                    year: year ? Number(year) : undefined,
                  })
                }
                disabled={downloadBusy}
                type="button"
              >
                导出 CSV 表
              </button>
              <button
                className="btn btn-ghost"
                onClick={() => {
                  setUniversity("");
                  setFaculty("");
                  setYear("");
                }}
                type="button"
              >
                清空筛选
              </button>
            </div>
            <div className="filter-row">
              {activeFilters.length ? activeFilters.map((item) => <span key={item} className="badge badge-blue">{item}</span>) : <span className="badge badge-gray">全部正式资料</span>}
            </div>
          </div>
        </aside>

        <div className="item-detail">
          {error && <div className="message-box error">{error}</div>}
          {downloadMessage && <div className="message-box">{downloadMessage}</div>}

          {!selectedRow ? (
            <div className="detail-shell">
              <div className="detail-header">
                <div>
                  <div className="card-kicker">正式资料</div>
                  <h3 className="panel-title">点击学校查看完整内容</h3>
                </div>
                <span className="badge badge-gray">{rows.length} 条</span>
              </div>
              <div className="document-list">
                {rows.map((row, index) => (
                  <button key={`${row.id}-${index}`} className="item-card" onClick={() => setSelectedIndex(index)} type="button">
                    <div className="item-card-topline">
                      <span className="badge badge-blue">{row.admission_year || "未标年度"}</span>
                      {row.eju_session && <span className="badge badge-green">EJU已填</span>}
                    </div>
                    <h4 className="item-title">{row.university || "未命名大学"}</h4>
                    <p className="item-subtitle">
                      {row.faculty || "未标学部"} · {row.department || "未标学科"}
                    </p>
                  </button>
                ))}
              </div>
              {!rows.length && !loading && (
                <div className="empty-state empty-state-quiet">
                  <h3 className="panel-title">暂无正式资料</h3>
                  <p className="panel-copy">请先在人工核对页保存正式资料。</p>
                </div>
              )}
            </div>
          ) : (
            <div className="detail-shell detail-shell-editing">
              <button className="btn btn-ghost detail-back" onClick={() => setSelectedIndex(null)} type="button">
                返回列表
              </button>
              <div className="detail-header">
                <div>
                  <div className="card-kicker">资料详情</div>
                  <h3 className="panel-title">{selectedRow.university}</h3>
                </div>
                <div className="inline-actions inline-actions-tight">
                  <button
                    className="btn btn-primary"
                    type="button"
                    onClick={() =>
                      void runDownload("excel", {
                        university: selectedRow.university || undefined,
                        year: yearNumber(selectedRow.admission_year),
                      })
                    }
                    disabled={downloadBusy}
                  >
                    导出这所学校
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() =>
                      void runDownload("excel", {
                        university: selectedRow.university || undefined,
                        faculty: selectedRow.faculty || undefined,
                        year: yearNumber(selectedRow.admission_year),
                      })
                    }
                    disabled={downloadBusy}
                  >
                    导出当前学部
                  </button>
                  <button
                    className="btn btn-ghost"
                    type="button"
                    onClick={() =>
                      void runDownload("csv", {
                        university: selectedRow.university || undefined,
                        faculty: selectedRow.faculty || undefined,
                        year: yearNumber(selectedRow.admission_year),
                      })
                    }
                    disabled={downloadBusy}
                  >
                    导出 CSV
                  </button>
                </div>
              </div>
              <div className="detail-grid">
                {RECORD_FIELDS.map((field) => (
                  <div key={field.key} className="detail-field is-span-2">
                    <span className="detail-label">{field.label}</span>
                    <div className="detail-value">{String(selectedRow[field.key] || "-")}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
