import { useEffect, useMemo, useState } from "react";
import {
  downloadExcel,
  getQualityMetrics,
  getRecords,
  getStats,
  toErrorMessage,
} from "../api/client";
import type { ConfirmedRecord, QualityMetricsResponse, StatsResponse } from "../types";

const COLS: Array<{ key: keyof ConfirmedRecord; label: string; w?: number }> = [
  { key: "university", label: "大学", w: 140 },
  { key: "faculty", label: "学部", w: 120 },
  { key: "department", label: "学科", w: 130 },
  { key: "admission_year", label: "年度", w: 70 },
  { key: "application_period", label: "出愿期间", w: 170 },
  { key: "deadline_rule", label: "必着/消印", w: 100 },
  { key: "eju_session", label: "EJU实施回", w: 100 },
  { key: "eju_japanese", label: "EJU日本语", w: 110 },
  { key: "english_requirement", label: "英语要求", w: 180 },
  { key: "screening_method", label: "选拔方式", w: 140 },
  { key: "result_date", label: "结果日期", w: 110 },
];

const FIELD_LABELS: Record<string, string> = {
  application_period: "出愿期间",
  deadline_rule: "必着/消印",
  eju_session: "EJU实施回",
  eju_japanese: "EJU日本语",
  eju_general: "EJU综合科目",
  eju_math: "EJU数学",
  eju_physics: "EJU物理",
  eju_chemistry: "EJU化学",
  eju_biology: "EJU生物",
  english_requirement: "英语要求",
  screening_method: "选考方法",
  screening_schedule: "选考日程",
  result_date: "合格发表日",
  enrollment_period: "入学手续期间",
};

export default function RecordsPage() {
  const [rows, setRows] = useState<ConfirmedRecord[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [quality, setQuality] = useState<QualityMetricsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [univ, setUniv] = useState("");
  const [fac, setFac] = useState("");
  const [yr, setYr] = useState("");

  async function load() {
    setLoading(true);
    setErr("");
    try {
      const [recordRows, statsData, qualityData] = await Promise.all([
        getRecords({
          university: univ || undefined,
          faculty: fac || undefined,
          year: yr ? Number(yr) : undefined,
          limit: 1000,
        }),
        getStats(),
        getQualityMetrics(),
      ]);
      setRows(recordRows);
      setStats(statsData);
      setQuality(qualityData);
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
            记录
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
            导出 Excel
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 12, marginBottom: 20 }}>
        {[
          { l: "覆盖大学", v: stats?.universities ?? "—" },
          { l: "已确认总数", v: stats?.total_records ?? "—" },
          { l: "平均置信度", v: stats ? stats.avg_confidence.toFixed(2) : "—" },
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
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 10 }}>风险分布（staging）</div>
            <div style={{ display: "grid", gap: 6, fontSize: 12, color: "var(--ink2)" }}>
              <div>高风险：{quality.risk_distribution.high || 0}</div>
              <div>中风险：{quality.risk_distribution.medium || 0}</div>
              <div>低风险：{quality.risk_distribution.low || 0}</div>
            </div>
          </div>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 10 }}>人工修改集中字段</div>
            <div style={{ display: "grid", gap: 6, fontSize: 12, color: "var(--ink2)" }}>
              {(quality.top_modified_fields || []).slice(0, 5).map((item) => (
                <div key={item.field}>
                  {FIELD_LABELS[item.field] || item.field}：{item.count}
                </div>
              ))}
              {(!quality.top_modified_fields || quality.top_modified_fields.length === 0) && <div>暂无修改事件</div>}
            </div>
          </div>
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: 16 }}>
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 10 }}>置信度校准（修改率）</div>
            <div style={{ display: "grid", gap: 6, fontSize: 12, color: "var(--ink2)" }}>
              {(quality.confidence_calibration || []).slice(0, 5).map((item) => (
                <div key={item.bucket}>
                  {item.bucket}：{Math.round(item.corrected_rate * 100)}%
                </div>
              ))}
              {(!quality.confidence_calibration || quality.confidence_calibration.length === 0) && <div>暂无校准数据</div>}
            </div>
          </div>
        </div>
      )}

      {topCoverage.length > 0 && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10, padding: "14px 16px", marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 10 }}>关键字段覆盖率（Top 8）</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: 8 }}>
            {topCoverage.map((item) => (
              <div key={item.field} style={{ border: "1px solid var(--border)", borderRadius: 8, padding: "8px 10px", background: "var(--bg)" }}>
                <div style={{ fontSize: 11, color: "var(--ink2)", marginBottom: 4 }}>{FIELD_LABELS[item.field] || item.field}</div>
                <div style={{ fontSize: 14, color: "var(--ink)", fontWeight: 600 }}>
                  {Math.round(item.fill_rate * 100)}%
                </div>
                <div style={{ fontSize: 10, color: "var(--ink3)" }}>
                  修改率 {Math.round(item.modified_rate * 100)}%
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
          { val: univ, set: setUniv, ph: "大学", w: 160 },
          { val: fac, set: setFac, ph: "学部", w: 140 },
          { val: yr, set: setYr, ph: "年度", w: 100 },
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
          搜索
        </button>
        <span style={{ fontSize: 12, color: "var(--ink3)", marginLeft: 4 }}>
          {loading ? "加载中…" : `${rows.length} 条`}
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
          暂无已确认记录
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
