import { useEffect, useMemo, useState } from "react";
import {
  getCorrectionEvents,
  getDocuments,
  getQualityMetrics,
  getSourceReviewQueue,
  runSourceChecks,
  toErrorMessage,
} from "../api/client";
import { PieSummary, TreemapSummary } from "../components/DashboardCharts";
import type { CorrectionEvent, DocumentListItem, QualityMetricsResponse, SourceReviewItem, SourceReviewResponse } from "../types";

interface Props {
  onOpenReview?: (docId: number) => void;
}

const CONTENT_LABELS: Record<string, string> = {
  application_period: "出愿时间",
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

function contentLabel(value: string) {
  return CONTENT_LABELS[value] || value;
}

function sourceStatusText(value: string) {
  if (value === "changed") return "官方资料有变化";
  if (value === "failed") return "检查失败";
  if (value === "marker_mismatch") return "内容不匹配";
  if (value === "not_pdf") return "链接需确认";
  return "需要查看";
}

function sourceStatusClass(value: string) {
  if (value === "changed") return "badge badge-amber";
  if (value === "failed" || value === "not_pdf") return "badge badge-red";
  if (value === "marker_mismatch") return "badge badge-blue";
  return "badge badge-gray";
}

function sourceActionText(value: string) {
  if (value === "changed") return "打开对应资料，对照官网确认是否需要更新。";
  if (value === "marker_mismatch") return "来源内容和预期不一致，先确认链接是否仍然正确。";
  if (value === "not_pdf") return "学校可能换了链接或页面形式，需要重新确认来源。";
  if (value === "failed") return "这次没有检查成功，可以稍后重试或手动打开官网。";
  return "查看来源后决定是否需要复审。";
}

function normalized(value?: string | null) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[#?].*$/, "")
    .replace(/\/$/, "");
}

function findDocumentForSource(item: SourceReviewItem, documents: DocumentListItem[]) {
  const itemUrl = normalized(item.source_url);
  if (itemUrl) {
    const exact = documents.find((doc) => normalized(doc.source_url) === itemUrl);
    if (exact) return exact;
  }
  const itemUniversity = normalized(item.university);
  const itemYear = normalized(item.admission_year);
  return documents.find((doc) => {
    const docUniversity = normalized(doc.university_name);
    const sameSchool = Boolean(itemUniversity && docUniversity && (docUniversity.includes(itemUniversity) || itemUniversity.includes(docUniversity)));
    const sameYear = !itemYear || normalized(doc.admission_year) === itemYear;
    return sameSchool && sameYear;
  });
}

export default function QualityPage({ onOpenReview }: Props) {
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null);
  const [metrics, setMetrics] = useState<QualityMetricsResponse | null>(null);
  const [corrections, setCorrections] = useState<CorrectionEvent[]>([]);
  const [sourceQueue, setSourceQueue] = useState<SourceReviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [checkingSources, setCheckingSources] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load(docId: number | null = selectedDocId) {
    setLoading(true);
    setError("");
    try {
      const [docs, quality, correctionRows, queue] = await Promise.all([
        getDocuments({ limit: 100 }),
        getQualityMetrics(docId || undefined),
        getCorrectionEvents({ doc_id: docId || undefined, limit: 80 }),
        getSourceReviewQueue(),
      ]);
      setDocuments(docs);
      setMetrics(quality);
      setCorrections(correctionRows);
      setSourceQueue(queue);
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setLoading(false);
    }
  }

  async function checkSources() {
    setCheckingSources(true);
    setError("");
    setMessage("");
    try {
      const result = await runSourceChecks();
      setSourceQueue(result.review_queue);
      setMessage("官方来源检查完成。正式资料没有被自动改动。");
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setCheckingSources(false);
    }
  }

  useEffect(() => {
    void load(null);
  }, []);

  const selectedDoc = useMemo(
    () => documents.find((item) => item.doc_id === selectedDocId) ?? null,
    [documents, selectedDocId],
  );
  const priority = metrics?.risk_distribution || { high: 0, medium: 0, low: 0 };
  const sourceSummary = sourceQueue?.summary || { needs_review: 0, changed: 0, failed: 0 };
  const sourceItems = sourceQueue?.items || [];
  const topCoverage = [...(metrics?.field_coverage || [])].sort((a, b) => a.fill_rate - b.fill_rate).slice(0, 8);
  const topModified = metrics?.top_modified_fields || [];
  const correctedTotal = topModified.reduce((sum, item) => sum + item.count, 0);

  return (
    <div className="page-shell quality-page">
      <section className="hero-panel">
        <div className="split-row split-row-start">
          <div>
            <div className="section-kicker">质量与来源</div>
            <h2 className="section-title">先发现变化，再决定要不要更新正式资料</h2>
            <p className="section-copy">
              这里只给 owner 使用：看抽取结果是否稳定、官方资料是否变化，以及人工主要应该先看哪里。正式资料不会因为来源检查自动覆盖。
            </p>
          </div>
          <div className="hero-metrics">
            <div className="metric-card">
              <span className="metric-label">待复审词条</span>
              <strong className="metric-value">{metrics?.total_staging_records ?? "-"}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">来源待查看</span>
              <strong className="metric-value">{sourceSummary.needs_review ?? 0}</strong>
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
            <p className="panel-copy">可以看全部资料，也可以只看某一份 PDF 的整理情况。</p>
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
                <h4 className="item-title">全部资料</h4>
                <p className="item-subtitle">适合看整体稳定性和常见修正点。</p>
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
          {message ? <div className="message-box">{message}</div> : null}

          <div className="detail-shell">
            <div className="detail-header">
              <div>
                <div className="card-kicker">{selectedDoc ? "单份资料" : "整体概览"}</div>
                <h3 className="panel-title">{selectedDoc?.university_name || "资料稳定性"}</h3>
                <p className="panel-copy">
                  {loading ? "正在更新质量报告..." : selectedDoc?.filename || "用于判断抽取稳定性，不对学生或私塾展示。"}
                </p>
              </div>
              <button className="btn btn-ghost" type="button" onClick={() => void load(selectedDocId)}>
                刷新
              </button>
            </div>

            <section className="quality-section source-review-panel">
              <div className="split-row split-row-start">
                <div>
                  <h3 className="panel-title">官方来源变化</h3>
                  <p className="panel-copy">检查学校官网或 PDF 是否更新。发现变化后，只进入待查看清单，不会改动正式资料。</p>
                </div>
                <button className="btn btn-primary" disabled={checkingSources} type="button" onClick={() => void checkSources()}>
                  {checkingSources ? "正在检查" : "检查官方来源"}
                </button>
              </div>

              <div className="source-review-summary">
                <div>
                  <span>待查看</span>
                  <strong>{sourceSummary.needs_review ?? 0}</strong>
                </div>
                <div>
                  <span>内容变化</span>
                  <strong>{sourceSummary.changed ?? 0}</strong>
                </div>
                <div>
                  <span>检查失败</span>
                  <strong>{sourceSummary.failed ?? 0}</strong>
                </div>
              </div>

              <div className="source-review-list">
                {sourceItems.slice(0, 8).map((item) => {
                  const matchedDoc = findDocumentForSource(item, documents);
                  return (
                    <article className="source-review-card" key={`${item.stem}-${item.checked_at}-${item.status}`}>
                      <div className="item-card-topline">
                        <span className={sourceStatusClass(item.status)}>{sourceStatusText(item.status)}</span>
                        <span className="badge badge-gray">{item.admission_year || "未标年度"}</span>
                      </div>
                      <h4 className="item-title">{item.university || item.stem || "未命名来源"}</h4>
                      <p className="item-subtitle">{item.error || sourceActionText(item.status)}</p>
                      <div className="source-review-actions">
                        <div className="inline-actions inline-actions-tight">
                          {matchedDoc && onOpenReview ? (
                            <button className="btn btn-primary btn-small" type="button" onClick={() => onOpenReview(matchedDoc.doc_id)}>
                              进入复审
                            </button>
                          ) : null}
                          {item.source_url ? (
                            <a className="btn btn-ghost btn-small" href={item.source_url} target="_blank" rel="noreferrer">
                              打开官网资料
                            </a>
                          ) : null}
                        </div>
                        <span>{item.checked_at || sourceQueue?.generated_at || ""}</span>
                      </div>
                    </article>
                  );
                })}
                {!sourceItems.length ? <div className="empty-state empty-state-quiet">目前没有需要查看的来源变化。</div> : null}
              </div>
            </section>

            <div className="quality-grid">
              <PieSummary
                title="复审优先级"
                subtitle="数值越高，越需要先看原文确认。"
                totalLabel="总数"
                totalValue={String(metrics?.total_staging_records || 0)}
                data={[
                  { label: "优先查看", value: priority.high || 0, color: "#ef4444" },
                  { label: "需要确认", value: priority.medium || 0, color: "#f59e0b" },
                  { label: "较稳定", value: priority.low || 0, color: "#2563eb" },
                ]}
              />
              <TreemapSummary
                title="经常被修正"
                subtitle="人工修正越集中，越值得优先改抽取规则。"
                data={
                  topModified.length
                    ? topModified.map((item, index) => ({
                        label: contentLabel(item.field),
                        value: item.count,
                        color: ["#0f766e", "#2563eb", "#7c3aed", "#b45309", "#be123c"][index % 5],
                      }))
                    : [{ label: "暂无修正记录", value: 1, color: "#94a3b8" }]
                }
              />
            </div>

            <section className="quality-section">
              <div className="split-row">
                <div>
                  <h3 className="panel-title">优先补看的内容</h3>
                  <p className="panel-copy">按完整度从低到高排列，越靠前越需要在复审时多留意。</p>
                </div>
              </div>
              <div className="quality-table">
                {topCoverage.map((item) => (
                  <div className="quality-row" key={item.field}>
                    <div>
                      <strong>{contentLabel(item.field)}</strong>
                      <span>
                        已填 {item.filled} 条 · 人工修正 {item.modified} 条
                      </span>
                    </div>
                    <div className="quality-bar" aria-label={`${contentLabel(item.field)} ${percent(item.fill_rate)}`}>
                      <span style={{ width: percent(item.fill_rate) }} />
                    </div>
                    <em>{percent(item.fill_rate)}</em>
                  </div>
                ))}
                {!topCoverage.length ? <div className="empty-state empty-state-quiet">暂无可分析的整理结果。</div> : null}
              </div>
            </section>

            <section className="quality-section">
              <h3 className="panel-title">最近人工修正</h3>
              <div className="quality-corrections">
                {corrections.slice(0, 12).map((item) => (
                  <article className="quality-correction" key={item.id}>
                    <div className="item-card-topline">
                      <span className="badge badge-blue">{contentLabel(item.field_name)}</span>
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
            </section>
          </div>
        </div>
      </section>
    </div>
  );
}
