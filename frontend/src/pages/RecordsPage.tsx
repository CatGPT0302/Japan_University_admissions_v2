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
  { key: "university", label: "University", w: 140 },
  { key: "faculty", label: "Faculty", w: 120 },
  { key: "department", label: "Department", w: 130 },
  { key: "admission_year", label: "Year", w: 70 },
  { key: "application_period", label: "Application", w: 170 },
  { key: "deadline_rule", label: "Deadline", w: 100 },
  { key: "eju_session", label: "EJU Session", w: 110 },
  { key: "eju_japanese", label: "EJU Japanese", w: 110 },
  { key: "english_requirement", label: "English", w: 180 },
  { key: "screening_method", label: "Method", w: 140 },
  { key: "result_date", label: "Result Date", w: 120 },
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

  return (
    <div style={{ maxWidth: 1160 }}>
      <div style={{ marginBottom: 24 }}>
        <div
          style={{
            fontSize: 10,
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            color: "var(--red)",
            marginBottom: 10,
            fontWeight: 500,
          }}
        >
          Step 3
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <h1
            style={{
              fontFamily: "Georgia,serif",
              fontSize: 34,
              fontStyle: "italic",
              fontWeight: 400,
              letterSpacing: -0.5,
              lineHeight: 1.1,
            }}
          >
            Records
          </h1>
          <button
            onClick={() =>
              downloadExcel({
                university: univ || undefined,
                year: yr ? Number(yr) : undefined,
                faculty: fac || undefined,
              })
            }
            style={{
              height: 38,
              padding: "0 18px",
              background: "var(--ink)",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Export Excel
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginBottom: 20 }}>
        {[
          { l: "Universities", v: stats?.universities ?? "—" },
          { l: "Confirmed", v: stats?.total_records ?? "—" },
          { l: "Avg Confidence", v: stats ? stats.avg_confidence.toFixed(2) : "—" },
        ].map((c) => (
          <div
            key={c.l}
            style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: "20px" }}
          >
            <div style={{ fontSize: 10, color: "var(--ink3)", marginBottom: 6 }}>{c.l}</div>
            <div
              style={{
                fontFamily: "Georgia,serif",
                fontSize: 30,
                fontWeight: 400,
                color: "var(--ink)",
                lineHeight: 1,
              }}
            >
              {c.v}
            </div>
          </div>
        ))}
      </div>

      {quality && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginBottom: 20 }}>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 10 }}>Risk Distribution (Staging)</div>
            <div style={{ display: "grid", gap: 6, fontSize: 12, color: "var(--ink2)" }}>
              <div>High: {quality.risk_distribution.high || 0}</div>
              <div>Medium: {quality.risk_distribution.medium || 0}</div>
              <div>Low: {quality.risk_distribution.low || 0}</div>
            </div>
          </div>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 10 }}>Top Manually Modified Fields</div>
            <div style={{ display: "grid", gap: 6, fontSize: 12, color: "var(--ink2)" }}>
              {(quality.top_modified_fields || []).slice(0, 5).map((item) => (
                <div key={item.field}>
                  {FIELD_LABELS[item.field] || item.field}: {item.count}
                </div>
              ))}
              {(!quality.top_modified_fields || quality.top_modified_fields.length === 0) && <div>No correction events yet.</div>}
            </div>
          </div>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 10 }}>Confidence Calibration (Correction Rate)</div>
            <div style={{ display: "grid", gap: 6, fontSize: 12, color: "var(--ink2)" }}>
              {(quality.confidence_calibration || []).slice(0, 5).map((item) => (
                <div key={item.bucket}>
                  {item.bucket}: {Math.round(item.corrected_rate * 100)}%
                </div>
              ))}
              {(!quality.confidence_calibration || quality.confidence_calibration.length === 0) && <div>No calibration data yet.</div>}
            </div>
          </div>
        </div>
      )}

      {topCoverage.length > 0 && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: "14px 16px", marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 10 }}>Key Field Coverage (Top 8)</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: 8 }}>
            {topCoverage.map((item) => (
              <div key={item.field} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: "8px 10px", background: "var(--bg)" }}>
                <div style={{ fontSize: 11, color: "var(--ink2)", marginBottom: 4 }}>{FIELD_LABELS[item.field] || item.field}</div>
                <div style={{ fontSize: 14, color: "var(--ink)", fontWeight: 600 }}>
                  {Math.round(item.fill_rate * 100)}%
                </div>
                <div style={{ fontSize: 10, color: "var(--ink3)" }}>
                  Modified {Math.round(item.modified_rate * 100)}%
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: "14px 16px", marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 10 }}>Recent Correction Events (Top 10)</div>
        <div style={{ display: "grid", gap: 8 }}>
          {corrections.slice(0, 10).map((event) => (
            <div key={event.id} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: "8px 10px", background: "var(--bg)" }}>
              <div style={{ fontSize: 12, color: "var(--ink)", marginBottom: 4 }}>
                [{event.university || "Unknown"}] {FIELD_LABELS[event.field_name] || event.field_name}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink2)", lineHeight: 1.6 }}>
                Old: {event.old_value || "(empty)"} {"=>"} New: {event.new_value || "(empty)"}
              </div>
            </div>
          ))}
          {corrections.length === 0 && <div style={{ fontSize: 12, color: "var(--ink3)" }}>No correction events yet.</div>}
        </div>
      </div>

      <div
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: "14px 16px",
          marginBottom: 16,
          display: "flex",
          gap: 10,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        {[
          { val: univ, set: setUniv, ph: "University", w: 160 },
          { val: fac, set: setFac, ph: "Faculty", w: 140 },
          { val: yr, set: setYr, ph: "Year", w: 100 },
        ].map((f) => (
          <input
            key={f.ph}
            value={f.val}
            onChange={(e) => f.set(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void load()}
            placeholder={f.ph}
            style={{
              height: 36,
              width: f.w,
              padding: "0 12px",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 13,
              color: "var(--ink)",
              background: "var(--bg)",
              outline: "none",
            }}
          />
        ))}
        <button
          onClick={() => void load()}
          style={{
            height: 36,
            padding: "0 16px",
            background: "var(--ink)",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 500,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          Search
        </button>
        <span style={{ fontSize: 12, color: "var(--ink3)", marginLeft: 4 }}>
          {loading ? "Loading..." : `${rows.length} rows`}
        </span>
      </div>

      {err && (
        <div
          style={{
            marginBottom: 16,
            padding: "10px 16px",
            background: "var(--red-soft)",
            border: "1px solid #fecaca",
            borderRadius: 8,
            fontSize: 13,
            color: "var(--red)",
          }}
        >
          {err}
        </div>
      )}

      {rows.length === 0 && !loading ? (
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 10,
            padding: "32px",
            fontSize: 14,
            color: "var(--ink3)",
            textAlign: "center",
          }}
        >
          No confirmed records.
        </div>
      ) : (
        <div style={{ overflowX: "auto", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10 }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "var(--bg)", borderBottom: "1px solid var(--border)" }}>
                {COLS.map((c) => (
                  <th
                    key={c.key}
                    style={{
                      padding: "10px 14px",
                      textAlign: "left",
                      fontSize: 10,
                      fontWeight: 500,
                      letterSpacing: "0.08em",
                      textTransform: "uppercase",
                      color: "var(--ink3)",
                      whiteSpace: "nowrap",
                      width: c.w,
                    }}
                  >
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr
                  key={r.id}
                  style={{
                    borderBottom: "1px solid var(--border)",
                    background: i % 2 === 0 ? "var(--surface)" : "var(--bg)",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg)")}
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = i % 2 === 0 ? "var(--surface)" : "var(--bg)")
                  }
                >
                  {COLS.map((c) => (
                    <td
                      key={c.key}
                      style={{
                        padding: "10px 14px",
                        color: c.key === "university" ? "var(--ink)" : "var(--ink2)",
                        maxWidth: c.w,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                      title={String(r[c.key] ?? "")}
                    >
                      {r[c.key] || <span style={{ color: "var(--ink3)" }}>—</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
