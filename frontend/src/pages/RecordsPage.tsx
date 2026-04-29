import { useEffect, useMemo, useState } from "react";
import { downloadExcel, getRecords, getStats, toErrorMessage } from "../api/client";
import { PieSummary } from "../components/DashboardCharts";
import type { ConfirmedRecord, StatsResponse } from "../types";

const RECORD_FIELDS: Array<{ key: keyof ConfirmedRecord; label: string; span?: 1 | 2 }> = [
  { key: "university", label: "学校", span: 2 },
  { key: "faculty", label: "学部" },
  { key: "department", label: "学科 / 专业" },
  { key: "admission_year", label: "年份" },
  { key: "application_period", label: "出愿期间", span: 2 },
  { key: "deadline_rule", label: "截止规则" },
  { key: "eju_session", label: "EJU 场次" },
  { key: "eju_japanese", label: "EJU 日语" },
  { key: "eju_general", label: "EJU 综合科目" },
  { key: "eju_math", label: "EJU 数学" },
  { key: "eju_physics", label: "EJU 物理" },
  { key: "eju_chemistry", label: "EJU 化学" },
  { key: "eju_biology", label: "EJU 生物" },
  { key: "english_requirement", label: "英语要求", span: 2 },
  { key: "screening_method", label: "选考方式", span: 2 },
  { key: "screening_schedule", label: "选考日程", span: 2 },
  { key: "result_date", label: "结果发布日期" },
  { key: "enrollment_period", label: "入学手续期间" },
  { key: "prefecture", label: "都道府县" },
  { key: "campus", label: "校区" },
];

export default function RecordsPage() {
  const [rows, setRows] = useState<ConfirmedRecord[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [university, setUniversity] = useState("");
  const [faculty, setFaculty] = useState("");
  const [year, setYear] = useState("");
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

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

  const activeFilters = useMemo(
    () => [university ? `学校：${university}` : "", faculty ? `学部：${faculty}` : "", year ? `年份：${year}` : ""].filter(Boolean),
    [faculty, university, year],
  );

  const selectedRow = selectedIndex === null ? null : rows[selectedIndex] ?? null;

  return (
    <div className="page-shell">
      <section className="hero-panel">
        <div className="split-row split-row-start">
          <div>
            <div className="section-kicker">记录</div>
            <h2 className="section-title">查看已确认档案</h2>
          <p className="section-copy">查询已确认数据，并导出完整主表。</p>
          </div>
          <div className="hero-metrics">
            <div className="metric-card">
              <span className="metric-label">当前结果</span>
              <strong className="metric-value">{rows.length}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">总记录</span>
              <strong className="metric-value">{stats?.total_records ?? "—"}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">学校数</span>
              <strong className="metric-value">{stats?.universities ?? "—"}</strong>
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
                <h3 className="panel-title">筛选与导出</h3>
                <p className="panel-copy">筛选当前记录范围，再按需要导出。</p>
              </div>
              <span className="badge badge-gray">{rows.length} 条</span>
            </div>

            <div className="list-stack">
              <label className="field-wrap">
                <span className="field-label">学校</span>
                <input className="field" value={university} onChange={(event) => setUniversity(event.target.value)} placeholder="例如：早稻田大学" />
              </label>
              <label className="field-wrap">
                <span className="field-label">学部</span>
                <input className="field" value={faculty} onChange={(event) => setFaculty(event.target.value)} placeholder="例如：工学部" />
              </label>
              <label className="field-wrap">
                <span className="field-label">年份</span>
                <input className="field" value={year} onChange={(event) => setYear(event.target.value)} placeholder="2026" />
              </label>
            </div>

            <div className="list-stack section-stack">
              <button className="btn btn-primary" onClick={() => void load()} type="button">
                {loading ? "检索中..." : "执行检索"}
              </button>
              <button
                className="btn btn-green"
                onClick={() =>
                  downloadExcel({
                    university: university || undefined,
                    faculty: faculty || undefined,
                    year: year ? Number(year) : undefined,
                  })
                }
                type="button"
              >
                导出当前结果
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
              {activeFilters.length ? (
                activeFilters.map((item) => (
                  <span key={item} className="badge badge-blue">
                    {item}
                  </span>
                ))
              ) : (
                <span className="badge badge-gray">全部记录</span>
              )}
            </div>
          </div>

          <PieSummary
            title="结果占比"
            subtitle="当前筛选结果在全部记录中的占比。"
            totalLabel="命中"
            totalValue={stats?.total_records ? `${Math.round((rows.length / Math.max(stats.total_records, 1)) * 100)}%` : "0%"}
            data={[
              { label: "当前命中", value: rows.length, color: "#111827" },
              { label: "其他记录", value: Math.max((stats?.total_records || 0) - rows.length, 0), color: "rgba(59, 130, 246, 0.78)" },
            ]}
          />
        </aside>

        <div className="item-detail">
          {error && <div className="message-box error">{error}</div>}

          {selectedRow === null ? (
            <div className="detail-shell">
              <div className="detail-header">
                <div>
                  <div className="card-kicker">记录列表</div>
                  <h3 className="panel-title">已确认内容</h3>
            <p className="panel-copy">点击记录查看完整字段。</p>
                </div>
                <div className="item-meta">
                  <span className="badge badge-gray">总记录 {stats?.total_records ?? "—"}</span>
                  <span className="badge badge-blue">学校数 {stats?.universities ?? "—"}</span>
                </div>
              </div>

              <div className="document-list">
                {rows.map((row, index) => (
                  <button key={`${row.university}-${row.department}-${index}`} className="item-card" onClick={() => setSelectedIndex(index)} type="button">
                    <div className="item-card-topline">
                      <span className="badge badge-blue">{row.admission_year || "未标注年份"}</span>
                      {row.result_date && <span className="badge badge-green">有结果日</span>}
                    </div>
                    <h4 className="item-title">{row.university || "未命名记录"}</h4>
                    <p className="item-subtitle">
                      {row.faculty || "未标注学部"} · {row.department || "未标注学科"}
                    </p>
                    <div className="item-meta">
                      {row.application_period && <span className="badge badge-gray">有出愿期间</span>}
                      {row.screening_method && <span className="badge badge-gray">有选考方式</span>}
                    </div>
                  </button>
                ))}
              </div>

              {!rows.length && !loading && (
                <div className="empty-state empty-state-quiet">
                  <div className="card-kicker">暂无结果</div>
                  <h3 className="panel-title">没有匹配记录</h3>
                  <p className="panel-copy">调整筛选条件后再试一次。</p>
                </div>
              )}
            </div>
          ) : (
            <div className="detail-shell detail-shell-editing">
              <div className="detail-header">
                <div>
                  <button className="btn btn-ghost detail-back" onClick={() => setSelectedIndex(null)} type="button">
                    返回列表
                  </button>
                  <div className="card-kicker" style={{ marginTop: 16 }}>
                    记录详情
                  </div>
                  <h3 className="panel-title">档案信息</h3>
                </div>
                <div className="item-meta">
                  <span className="badge badge-blue">{selectedRow.university || "未命名"}</span>
                  <span className="badge badge-gray">{selectedRow.admission_year || "未标注年份"}</span>
                </div>
              </div>

              <div className="detail-grid">
                {RECORD_FIELDS.map((field) => (
                  <div key={field.key} className={`detail-field${field.span === 2 ? " is-span-2" : ""}`}>
                    <span className="detail-label">{field.label}</span>
                    <div className="detail-value">{String(selectedRow[field.key] || "—")}</div>
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
