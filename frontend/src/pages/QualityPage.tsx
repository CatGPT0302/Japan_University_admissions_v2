import { useEffect, useMemo, useState } from "react";
import { getCorrectionEvents, getDocuments, getQualityMetrics, toErrorMessage } from "../api/client";
import { PieSummary, TreemapSummary } from "../components/DashboardCharts";
import type { CorrectionEvent, DocumentListItem, QualityMetricsResponse } from "../types";

const FIELD_LABELS: Record<string, string> = {
  application_period: "申请时间",
  deadline_rule: "截止规则",
  eju_session: "EJU 可用考试",
  eju_japanese: "EJU 日语",
  eju_general: "EJU 综合科目",
  eju_math: "EJU 数学",
  eju_physics: "EJU 物理",
  eju_chemistry: "EJU 化学",
  eju_biology: "EJU 生物",
  english_requirement: "英语要求",
  screening_method: "选考方式",
  screening_schedule: "考试时间",
  result_date: "结果公布",
  enrollment_period: "入学手续",
};

function percent(value?: number) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function fieldLabel(value: string) {
  return FIELD_LABELS[value] || value;
}

export default function QualityPage() {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [metrics, setMetrics] = useState<QualityMetricsResponse | null>(null);
  const [corrections, setCorrections] = useState<CorrectionEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load(docId: number | null = selectedDocId) {
    setLoading(true);
    setError("");
    try {
      const [docs, quality, correctionRows] = await Promise.all([
        getDocuments({ limit: 100 }),
        getQualityMetrics(docId || undefined),
        getCorrectionEvents({ doc_id: docId || undefined, limit: 80 }),
      ]);
      setDocuments(docs);
      setMetrics(quality);
      setCorrections(correctionRows);
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(null);
  }, []);

  const selectedDoc = useMemo(
    () => documents.find((item) => item.doc_id === selectedDocId) ?? null,
    [documents, selectedDocId],
  );
  const risk = metrics?.risk_distribution || { high: 0, medium: 0, low: 0 };
  const topCoverage = [...(metrics?.field_coverage || [])].sort((a, b) => a.fill_rate - b.fill_rate).slice(0, 8);
  const topModified = metrics?.top_modified_fields || [];
  const correctedTotal = topModified.reduce((sum, item) => sum + item.count, 0);

  return (
    <div className="page-shell">
      <section className="hero-panel">
        <div className="split-row split-row-start">
          <div>
            <div className="section-kicker">抽取质量</div>
            <h2 className="section-title">看清楚哪些内容稳定，哪些需要优先核对</h2>
            <p className="section-copy">
              这里只给 owner 使用，用来判断自动整理结果是否可靠、人工主要在修哪里，以及下一轮该优先优化哪类资料。
            </p>
          </div>
          <div className="hero-metrics">
            <div className="metric-card">
              <span className="metric-label">待核对条目</span>
              <strong className="metric-value">{metrics?.total_staging_records ?? "-"}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">重点核对</span>
              <strong className="metric-value">{risk.high || 0}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">人工修正</span>
              <strong className="metric-value">{correctedTotal}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="content-grid">
        <aside className="sidebar-panel">
          <div className="toolbar-shell">
            <h3 className="panel-title">查看范围</h3>
            <p className="panel-copy">可以看全部资料，也可以只看某一份 PDF 的整理质量。</p>
            <div className="list-stack">
              <button
                className={`item-card${selectedDocId === null ? " is-active" : ""}`}
                type="button"
                onClick={() => {
                  setSelectedDocId(null);
                  void load(null);
                }}
              >
                <div className="item-card-topline">
                  <span className="badge badge-blue">全部</span>
                </div>
                <h4 className="item-title">全部整理结果</h4>
                <p className="item-subtitle">适合看整体稳定性和常见修正点</p>
              </button>
              {documents.map((doc) => (
                <button
                  key={doc.doc_id}
                  className={`item-card${selectedDocId === doc.doc_id ? " is-active" : ""}`}
                  type="button"
                  onClick={() => {
                    setSelectedDocId(doc.doc_id);
                    void load(doc.doc_id);
                  }}
                >
                  <div className="item-card-topline">
                    <span className="badge badge-blue">{doc.admission_year || "未标年度"}</span>
                    <span className="badge badge-gray">{doc.staging_count || 0} 条</span>
                  </div>
                  <h4 className="item-title">{doc.university_name || "未命名资料"}</h4>
                  <p className="item-subtitle">{doc.filename}</p>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <div className="item-detail">
          {error ? <div className="message-box error">{error}</div> : null}
          <div className="detail-shell">
            <div className="detail-header">
              <div>
                <div className="card-kicker">{selectedDoc ? "单份资料" : "整体概览"}</div>
                <h3 className="panel-title">{selectedDoc?.university_name || "全部资料的抽取质量"}</h3>
                <p className="panel-copy">
                  {loading ? "正在更新质量报告..." : selectedDoc?.filename || "用于判断抽取稳定性，不对私塾或学生展示。"}
                </p>
              </div>
              <button className="btn btn-ghost" type="button" onClick={() => void load(selectedDocId)}>
                刷新
              </button>
            </div>

            <div className="quality-grid">
              <PieSummary
                title="核对优先级"
                subtitle="数值越高，越需要先看原文确认。"
                totalLabel="总数"
                totalValue={String(metrics?.total_staging_records || 0)}
                data={[
                  { label: "重点核对", value: risk.high || 0, color: "#ef4444" },
                  { label: "需要确认", value: risk.medium || 0, color: "#f59e0b" },
                  { label: "较稳定", value: risk.low || 0, color: "#2563eb" },
                ]}
              />
              <TreemapSummary
                title="经常被修正"
                subtitle="人工修正越集中，越值得优先改抽取规则。"
                data={
                  topModified.length
                    ? topModified.map((item, index) => ({
                        label: fieldLabel(item.field),
                        value: item.count,
                        color: ["#0f766e", "#2563eb", "#7c3aed", "#b45309", "#be123c"][index % 5],
                      }))
                    : [{ label: "暂无修正记录", value: 1, color: "#94a3b8" }]
                }
              />
            </div>

            <div className="quality-section">
              <div className="split-row">
                <div>
                  <h3 className="panel-title">优先补看的内容</h3>
                  <p className="panel-copy">按完整度从低到高排列，越靠前越需要在复核时多留意。</p>
                </div>
              </div>
              <div className="quality-table">
                {topCoverage.map((item) => (
                  <div className="quality-row" key={item.field}>
                    <div>
                      <strong>{fieldLabel(item.field)}</strong>
                      <span>
                        已填 {item.filled} 条 · 人工修正 {item.modified} 条
                      </span>
                    </div>
                    <div className="quality-bar" aria-label={`${fieldLabel(item.field)} ${percent(item.fill_rate)}`}>
                      <span style={{ width: percent(item.fill_rate) }} />
                    </div>
                    <em>{percent(item.fill_rate)}</em>
                  </div>
                ))}
                {!topCoverage.length ? <div className="empty-state empty-state-quiet">暂无可分析的整理结果。</div> : null}
              </div>
            </div>

            <div className="quality-section">
              <h3 className="panel-title">最近人工修正</h3>
              <div className="quality-corrections">
                {corrections.slice(0, 12).map((item) => (
                  <article className="quality-correction" key={item.id}>
                    <div className="item-card-topline">
                      <span className="badge badge-blue">{fieldLabel(item.field_name)}</span>
                      {item.page_number ? <span className="badge badge-gray">第 {item.page_number} 页</span> : null}
                    </div>
                    <p>
                      <span>{item.old_value || "空"}</span>
                      <strong>→</strong>
                      <span>{item.new_value || "空"}</span>
                    </p>
                    <small>{item.created_at}</small>
                  </article>
                ))}
                {!corrections.length ? <div className="empty-state empty-state-quiet">还没有人工修正记录。</div> : null}
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
