import { useEffect, useMemo, useState } from "react";
import {
  downloadExcel,
  getCorrectionEvents,
  getQualityMetrics,
  getRecords,
  getStats,
  toErrorMessage,
} from "../api/client";
import type {
  ConfirmedRecord,
  CorrectionEvent,
  QualityMetricsResponse,
  StatsResponse,
} from "../types";

const COLS: Array<{ key: keyof ConfirmedRecord; label: string; w?: number }> = [
  { key: "university", label: "University", w: 180 },
  { key: "faculty", label: "Faculty", w: 150 },
  { key: "department", label: "Department", w: 170 },
  { key: "admission_year", label: "Year", w: 84 },
  { key: "application_period", label: "Application", w: 190 },
  { key: "deadline_rule", label: "Deadline", w: 120 },
  { key: "eju_session", label: "EJU Session", w: 120 },
  { key: "eju_japanese", label: "EJU Japanese", w: 120 },
  { key: "english_requirement", label: "English", w: 220 },
  { key: "screening_method", label: "Method", w: 180 },
  { key: "result_date", label: "Result Date", w: 130 },
];

const FIELD_LABELS: Record<string, string> = {
  application_period: "Application Period",
  deadline_rule: "Deadline Rule",
  eju_session: "EJU Session",
  eju_japanese: "EJU Japanese",
  eju_general: "EJU General",
  eju_math: "EJU Math",
  eju_physics: "EJU Physics",
  eju_chemistry: "EJU Chemistry",
  eju_biology: "EJU Biology",
  english_requirement: "English Requirement",
  screening_method: "Screening Method",
  screening_schedule: "Screening Schedule",
  result_date: "Result Date",
  enrollment_period: "Enrollment Period",
};

export default function RecordsPage() {
  const [rows, setRows] = useState<ConfirmedRecord[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [quality, setQuality] = useState<QualityMetricsResponse | null>(null);
  const [corrections, setCorrections] = useState<CorrectionEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [univ, setUniv] = useState("");
  const [fac, setFac] = useState("");
  const [yr, setYr] = useState("");

  async function load() {
    setLoading(true);
    setErr("");
    try {
      const [recordRows, statsData, qualityData, correctionRows] = await Promise.all([
        getRecords({
          university: univ || undefined,
          faculty: fac || undefined,
          year: yr ? Number(yr) : undefined,
          limit: 1000,
        }),
        getStats(),
        getQualityMetrics(),
        getCorrectionEvents({ limit: 30 }),
      ]);
      setRows(recordRows);
      setStats(statsData);
      setQuality(qualityData);
      setCorrections(correctionRows);
    } catch (e) {
      setErr(toErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const topCoverage = useMemo(() => {
    if (!quality?.field_coverage?.length) return [];
    return [...quality.field_coverage]
      .sort((a, b) => b.fill_rate - a.fill_rate)
      .slice(0, 8);
  }, [quality]);

  const activeFilters = useMemo(() => {
    return [
      univ ? `University: ${univ}` : "",
      fac ? `Faculty: ${fac}` : "",
      yr ? `Year: ${yr}` : "",
    ].filter(Boolean);
  }, [fac, univ, yr]);

  return (
    <div className="page-shell">
      <section className="hero-panel">
        <div className="hero-grid">
          <div>
            <div className="section-eyebrow">Step 3 · Records</div>
            <h2 className="section-title">Search, audit, and export</h2>
            <p className="section-copy">
              Records is now positioned like the finish line of the admissions workflow: search across confirmed rows, keep quality signals visible,
              and export the current slice without leaving the dashboard.
            </p>
          </div>

          <div className="progress-stack">
            <div className="mini-stat">
              <span className="mini-stat-label">Search result</span>
              <span className="mini-stat-value">{loading ? "Loading" : `${rows.length} row(s)`}</span>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Active filters</span>
              <span className="mini-stat-value">{activeFilters.length || "None"}</span>
            </div>
            <div className="mini-stat">
              <span className="mini-stat-label">Export scope</span>
              <span className="mini-stat-value">{activeFilters.length ? "Filtered" : "All records"}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="toolbar-shell">
        <div className="toolbar-row">
          <div>
            <h3 className="panel-title">Records search</h3>
            <p className="panel-copy">
              Filter the confirmed dataset by university, faculty, and year. Export always respects the current search scope.
            </p>
          </div>
          <div className="inline-actions">
            <button className="btn btn-primary" onClick={() => void load()} type="button">
              {loading ? "Refreshing..." : "Run search"}
            </button>
            <button
              className="btn btn-green"
              onClick={() =>
                downloadExcel({
                  university: univ || undefined,
                  year: yr ? Number(yr) : undefined,
                  faculty: fac || undefined,
                })
              }
              type="button"
            >
              Export current view
            </button>
          </div>
        </div>

        <div className="input-grid" style={{ marginTop: 16 }}>
          {[
            {
              label: "University",
              value: univ,
              onChange: setUniv,
              placeholder: "Example: Waseda University",
            },
            {
              label: "Faculty",
              value: fac,
              onChange: setFac,
              placeholder: "Example: Engineering",
            },
            {
              label: "Year",
              value: yr,
              onChange: setYr,
              placeholder: "2026",
            },
          ].map((item) => (
            <label key={item.label} className="field-wrap">
              <span className="field-label">{item.label}</span>
              <input
                value={item.value}
                onChange={(event) => item.onChange(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && void load()}
                placeholder={item.placeholder}
                className="field"
              />
            </label>
          ))}
        </div>

        <div className="filter-row" style={{ marginTop: 14 }}>
          {activeFilters.length ? (
            activeFilters.map((item) => (
              <span key={item} className="badge badge-blue">
                {item}
              </span>
            ))
          ) : (
            <span className="badge badge-gray">No filters applied</span>
          )}
          <span className="badge badge-gray">{loading ? "Fetching latest records" : `${rows.length} matching row(s)`}</span>
        </div>
      </section>

      <section className="metric-grid">
        {[
          {
            label: "Universities",
            value: stats?.universities ?? "—",
            copy: "Distinct universities in confirmed records",
            tone: "badge badge-blue",
          },
          {
            label: "Confirmed rows",
            value: stats?.total_records ?? "—",
            copy: "Rows available for downstream use",
            tone: "badge badge-green",
          },
          {
            label: "Average confidence",
            value: stats ? stats.avg_confidence.toFixed(2) : "—",
            copy: "Global confidence across records",
            tone: "badge badge-amber",
          },
          {
            label: "Current view",
            value: loading ? "..." : rows.length,
            copy: "Rows matching the active search",
            tone: "badge badge-gray",
          },
        ].map((card) => (
          <div key={card.label} className="metric-card">
            <div className="split-row" style={{ marginBottom: 8 }}>
              <div className="metric-label">{card.label}</div>
              <span className={card.tone}>{card.label}</span>
            </div>
            <div className="metric-value">{card.value}</div>
            <div className="metric-copy">{card.copy}</div>
          </div>
        ))}
      </section>

      {quality && (
        <section className="insight-grid">
          <div className="insight-card">
            <div className="card-kicker">Risk monitor</div>
            <h3 className="panel-title">Staging risk distribution</h3>
            <div className="list-stack" style={{ marginTop: 12 }}>
              <div className="status-pill">
                <span>High risk</span>
                <strong>{quality.risk_distribution.high || 0}</strong>
              </div>
              <div className="status-pill">
                <span>Medium risk</span>
                <strong>{quality.risk_distribution.medium || 0}</strong>
              </div>
              <div className="status-pill">
                <span>Low risk</span>
                <strong>{quality.risk_distribution.low || 0}</strong>
              </div>
            </div>
          </div>

          <div className="insight-card">
            <div className="card-kicker">Manual corrections</div>
            <h3 className="panel-title">Most edited fields</h3>
            <div className="list-stack" style={{ marginTop: 12 }}>
              {(quality.top_modified_fields || []).slice(0, 5).map((item) => (
                <div key={item.field} className="status-pill">
                  <span>{FIELD_LABELS[item.field] || item.field}</span>
                  <strong>{item.count}</strong>
                </div>
              ))}
              {(!quality.top_modified_fields || quality.top_modified_fields.length === 0) && (
                <div className="empty-copy">No correction events yet.</div>
              )}
            </div>
          </div>

          <div className="insight-card">
            <div className="card-kicker">Calibration</div>
            <h3 className="panel-title">Correction rate by confidence</h3>
            <div className="list-stack" style={{ marginTop: 12 }}>
              {(quality.confidence_calibration || []).slice(0, 5).map((item) => (
                <div key={item.bucket} className="status-pill">
                  <span>{item.bucket}</span>
                  <strong>{Math.round(item.corrected_rate * 100)}%</strong>
                </div>
              ))}
              {(!quality.confidence_calibration || quality.confidence_calibration.length === 0) && (
                <div className="empty-copy">No calibration data yet.</div>
              )}
            </div>
          </div>
        </section>
      )}

      {topCoverage.length > 0 && (
        <section className="panel">
          <div className="split-row" style={{ marginBottom: 14 }}>
            <div>
              <h3 className="panel-title">Key field coverage</h3>
              <p className="panel-copy">A quick read on which high-value fields are densely populated and which ones need more manual work.</p>
            </div>
            <span className="badge badge-gray">Top 8 fields</span>
          </div>

          <div className="coverage-grid">
            {topCoverage.map((item) => (
              <div
                key={item.field}
                className="summary-box"
                style={{ background: "rgba(248, 250, 252, 0.92)", border: "1px solid rgba(148, 163, 184, 0.18)" }}
              >
                <div className="field-label">{FIELD_LABELS[item.field] || item.field}</div>
                <div className="metric-value" style={{ fontSize: 26, marginTop: 8 }}>
                  {Math.round(item.fill_rate * 100)}%
                </div>
                <div className="muted-text">Modified {Math.round(item.modified_rate * 100)}%</div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="panel">
        <div className="split-row" style={{ marginBottom: 14 }}>
          <div>
            <h3 className="panel-title">Recent correction events</h3>
            <p className="panel-copy">Keep the latest manual changes visible so the records team can spot recurring data quality themes.</p>
          </div>
          <span className="badge badge-gray">Latest 10</span>
        </div>

        <div className="correction-stack">
          {corrections.slice(0, 10).map((event: CorrectionEvent) => (
            <div
              key={event.id}
              className="summary-box"
              style={{ background: "rgba(248, 250, 252, 0.92)", border: "1px solid rgba(148, 163, 184, 0.18)" }}
            >
              <div className="split-row">
                <div>
                  <strong>{event.university || "Unknown university"}</strong>
                  <div className="muted-text">{FIELD_LABELS[event.field_name] || event.field_name}</div>
                </div>
                <span className="badge badge-blue">{event.admission_year || "No year"}</span>
              </div>
              <div className="muted-text" style={{ marginTop: 8 }}>
                Old: {event.old_value || "(empty)"} → New: {event.new_value || "(empty)"}
              </div>
            </div>
          ))}
          {corrections.length === 0 && (
            <div className="empty-state">
              <h4 className="empty-title">No correction events yet</h4>
              <p className="empty-copy">Manual edit history will appear here once the review team starts adjusting staging rows.</p>
            </div>
          )}
        </div>
      </section>

      {err && <section className="message-box error">{err}</section>}

      {rows.length === 0 && !loading ? (
        <section className="empty-state">
          <h3 className="empty-title">No confirmed records found</h3>
          <p className="empty-copy">
            Try broadening the search filters, or confirm rows in Review before exporting.
          </p>
        </section>
      ) : (
        <section className="table-shell">
          <div className="split-row" style={{ padding: "18px 20px 0" }}>
            <div>
              <h3 className="panel-title">Confirmed dataset</h3>
              <p className="panel-copy">The table stays compact for operators, but the search and export controls remain visible above it.</p>
            </div>
            <span className="badge badge-gray">{rows.length} visible rows</span>
          </div>

          <div className="table-scroll">
            <table className="records-table">
              <thead>
                <tr>
                  {COLS.map((column) => (
                    <th key={column.key} style={{ width: column.w }}>
                      {column.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    {COLS.map((column) => (
                      <td key={column.key} title={String(row[column.key] ?? "")} className={column.key === "university" ? "primary-cell" : ""}>
                        {row[column.key] || <span style={{ color: "var(--ink4)" }}>—</span>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
