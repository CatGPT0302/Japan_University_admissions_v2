import { useEffect, useMemo, useState } from "react";
import {
  getCorrectionEvents,
  getDocuments,
  getQualityMetrics,
  getQualityOverview,
  getSourceReviewQueue,
  getSourceWatchlist,
  reextractSourceReviewItem,
  runSourceChecks,
  toErrorMessage,
  updateSourceReviewItem,
} from "../api/client";
import { PieSummary, TreemapSummary } from "../components/DashboardCharts";
import type {
  CorrectionEvent,
  DocumentListItem,
  QualityMetricsResponse,
  QualityOverviewResponse,
  SourceReviewItem,
  SourceReviewResponse,
  SourceWatchlistResponse,
} from "../types";

interface Props {
  onOpenReview?: (docId: number) => void;
}

type SourceQueueFilter = "open" | "needs_reextract" | "reviewed" | "all";

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

const LANGUAGE_LABELS: Record<string, string> = {
  eju_japanese: "EJU 日语",
  jlpt_requirement: "JLPT",
  english_requirement: "英语要求",
};

function percent(value?: number) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function contentLabel(value: string) {
  return CONTENT_LABELS[value] || value;
}

function languageLabel(value: string) {
  return LANGUAGE_LABELS[value] || contentLabel(value);
}

function coverageTone(checked: number) {
  if (checked >= 10) return "覆盖较稳";
  if (checked >= 5) return "已有基础";
  if (checked > 0) return "还偏薄";
  return "未覆盖";
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

function reviewStatusText(value?: string) {
  if (value === "reviewed") return "已查看";
  if (value === "needs_reextract") return "需要重新整理";
  if (value === "deferred") return "暂不处理";
  return "待查看";
}

function reviewStatusClass(value?: string) {
  if (value === "reviewed") return "badge badge-green";
  if (value === "needs_reextract") return "badge badge-amber";
  if (value === "deferred") return "badge badge-gray";
  return "badge badge-blue";
}

const SOURCE_QUEUE_FILTERS: Array<{ key: SourceQueueFilter; label: string }> = [
  { key: "open", label: "待查看" },
  { key: "needs_reextract", label: "需重新整理" },
  { key: "reviewed", label: "已查看" },
  { key: "all", label: "全部" },
];

function filterSourceItems(items: SourceReviewItem[], filter: SourceQueueFilter) {
  if (filter === "all") return items;
  return items.filter((item) => (item.review_status || "open") === filter);
}

function sourceActionText(value: string) {
  if (value === "changed") return "打开对应资料，对照官网确认是否需要更新。";
  if (value === "marker_mismatch") return "来源内容和预期不一致，先确认链接是否仍然正确。";
  if (value === "not_pdf") return "学校可能换了链接或页面形式，需要重新确认来源。";
  if (value === "failed") return "这次没有检查成功，可以稍后重试或手动打开官网。";
  return "查看来源后决定是否需要复审。";
}

function attentionText(value?: string) {
  if (value === "needs_review") return "建议今天处理";
  if (value === "source_check") return "先确认来源";
  return "观察";
}

function attentionClass(value?: string) {
  if (value === "needs_review") return "badge badge-amber";
  if (value === "source_check") return "badge badge-blue";
  return "badge badge-gray";
}

function sourceTypeText(value?: string) {
  if (value === "pdf") return "PDF";
  if (value === "html") return "官网页面";
  if (value === "cached_text") return "已缓存文本";
  return "待补充";
}

function watchlistGapText(value: string) {
  if (value === "missing_source_url") return "缺官网链接";
  if (value === "missing_source_type") return "缺来源类型";
  if (value === "missing_hash") return "缺保存凭证";
  if (value === "missing_last_checked_at") return "缺最近检查";
  if (value === "missing_source_note") return "缺来源说明";
  if (value === "stale_last_checked_at") return "超过30天未检查";
  return value;
}

function checkStatusText(value?: string, days?: number | null) {
  if (value === "never_checked") return "还未检查";
  if (value === "stale") return days === null || days === undefined ? "需要复查" : `${days} 天未检查`;
  if (value === "recent") return days === null || days === undefined ? "近期已查" : `${days} 天前检查`;
  return "待确认";
}

function checkStatusClass(value?: string) {
  if (value === "never_checked" || value === "stale") return "badge badge-amber";
  if (value === "recent") return "badge badge-green";
  return "badge badge-gray";
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
  const [overview, setOverview] = useState<QualityOverviewResponse | null>(null);
  const [corrections, setCorrections] = useState<CorrectionEvent[]>([]);
  const [sourceQueue, setSourceQueue] = useState<SourceReviewResponse | null>(null);
  const [sourceWatchlist, setSourceWatchlist] = useState<SourceWatchlistResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [checkingSources, setCheckingSources] = useState(false);
  const [updatingSourceId, setUpdatingSourceId] = useState("");
  const [reextractingSourceId, setReextractingSourceId] = useState("");
  const [sourceFilter, setSourceFilter] = useState<SourceQueueFilter>("open");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load(docId: number | null = selectedDocId) {
    setLoading(true);
    setError("");
    try {
      const [docs, quality, correctionRows, queue, watchlist] = await Promise.all([
        getDocuments({ limit: 100 }),
        getQualityMetrics(docId || undefined),
        getCorrectionEvents({ doc_id: docId || undefined, limit: 80 }),
        getSourceReviewQueue(),
        getSourceWatchlist(),
      ]);
      const nextOverview = docId ? overview : await getQualityOverview();
      setDocuments(docs);
      setMetrics(quality);
      if (!docId) setOverview(nextOverview);
      setCorrections(correctionRows);
      setSourceQueue(queue);
      setSourceWatchlist(watchlist);
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
      const watchlist = await getSourceWatchlist();
      setSourceQueue(result.review_queue);
      setSourceWatchlist(watchlist);
      setMessage("官方来源检查完成。正式资料没有被自动改动。");
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setCheckingSources(false);
    }
  }

  async function setSourceItemStatus(itemId: string, reviewStatus: string) {
    setUpdatingSourceId(itemId);
    setError("");
    try {
      const state = await updateSourceReviewItem(itemId, { review_status: reviewStatus });
      setSourceQueue((current) => {
        if (!current) return current;
        return {
          ...current,
          summary: {
            ...current.summary,
            open: current.items.filter((item) => (item.item_id === itemId ? state.review_status : item.review_status) === "open").length,
            reviewed: current.items.filter((item) => (item.item_id === itemId ? state.review_status : item.review_status) === "reviewed").length,
            needs_reextract: current.items.filter((item) => (item.item_id === itemId ? state.review_status : item.review_status) === "needs_reextract").length,
            deferred: current.items.filter((item) => (item.item_id === itemId ? state.review_status : item.review_status) === "deferred").length,
          },
          items: current.items.map((item) =>
            item.item_id === itemId
              ? {
                  ...item,
                  review_status: state.review_status,
                  review_note: state.note,
                  review_updated_at: state.updated_at,
                }
              : item,
          ),
        };
      });
      setMessage(`已标记为：${reviewStatusText(state.review_status)}。`);
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setUpdatingSourceId("");
    }
  }

  async function reextractSourceItem(itemId: string) {
    setReextractingSourceId(itemId);
    setError("");
    setMessage("");
    try {
      const result = await reextractSourceReviewItem(itemId);
      setMessage(`已重新整理出 ${result.records || 0} 条待复审内容。`);
      await load(selectedDocId);
      if (result.doc_id && onOpenReview) onOpenReview(result.doc_id);
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setReextractingSourceId("");
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
  const filteredSourceItems = filterSourceItems(sourceItems, sourceFilter);
  const watchSummary = sourceWatchlist?.summary || { total: 0, by_type: {}, metadata_gaps: {} };
  const watchGaps = Object.entries(watchSummary.metadata_gaps)
    .filter(([, count]) => Number(count) > 0)
    .sort((a, b) => Number(b[1]) - Number(a[1]));
  const watchedTypes = Object.entries(watchSummary.by_type).sort((a, b) => Number(b[1]) - Number(a[1]));
  const recentWatchItems = (sourceWatchlist?.items || [])
    .filter((item) => item.source_url || item.cached_path)
    .sort((a, b) => {
      const priority = (item: typeof a) => (item.check_status === "never_checked" ? 0 : item.check_status === "stale" ? 1 : 2);
      return priority(a) - priority(b);
    })
    .slice(0, 4);
  const topCoverage = [...(metrics?.field_coverage || [])].sort((a, b) => a.fill_rate - b.fill_rate).slice(0, 8);
  const topModified = metrics?.top_modified_fields || [];
  const correctedTotal = topModified.reduce((sum, item) => sum + item.count, 0);
  const languageCoverage = Object.entries(overview?.language_requirement_coverage || {});
  const thinCoverageRows = overview?.per_seed_thin_coverage || [];

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
                  {loading ? "正在更新质量报告..." : selectedDoc?.filename || "用于判断抽取稳定性，不对学生或合作方展示。"}
                </p>
              </div>
              <button className="btn btn-ghost" type="button" onClick={() => void load(selectedDocId)}>
                刷新
              </button>
            </div>

            <section className="quality-section source-review-panel">
              <div className="split-row split-row-start">
                <div>
                  <h3 className="panel-title">来源登记</h3>
                  <p className="panel-copy">这里看每所学校的官网资料是否已经登记完整。先把来源管住，后面的整理和导出才稳。</p>
                </div>
                <span className="badge badge-blue">{watchSummary.total || 0} 份来源</span>
              </div>

              <div className="source-watch-grid">
                <div className="source-watch-block">
                  <span>来源形式</span>
                  <div className="source-watch-chips">
                    {watchedTypes.length ? (
                      watchedTypes.map(([type, count]) => (
                        <span className="badge badge-gray" key={type}>
                          {sourceTypeText(type)} · {count}
                        </span>
                      ))
                    ) : (
                      <span className="badge badge-gray">暂无登记</span>
                    )}
                  </div>
                </div>
                <div className="source-watch-block">
                  <span>需要补齐</span>
                  <div className="source-watch-chips">
                    {watchGaps.length ? (
                      watchGaps.slice(0, 4).map(([gap, count]) => (
                        <span className="badge badge-amber" key={gap}>
                          {watchlistGapText(gap)} · {count}
                        </span>
                      ))
                    ) : (
                      <span className="badge badge-green">来源登记完整</span>
                    )}
                  </div>
                </div>
                <div className="source-watch-block">
                  <span>维护节奏</span>
                  <div className="source-watch-chips">
                    {Number(watchSummary.metadata_gaps?.stale_last_checked_at || 0) > 0 ? (
                      <span className="badge badge-amber">
                        {watchSummary.metadata_gaps.stale_last_checked_at} 份超过 {watchSummary.stale_check_days || 30} 天未检查
                      </span>
                    ) : (
                      <span className="badge badge-green">最近检查节奏正常</span>
                    )}
                    {watchSummary.oldest_checked_at ? <span className="badge badge-gray">最早 {watchSummary.oldest_checked_at.slice(0, 10)}</span> : null}
                  </div>
                </div>
              </div>

              <div className="source-watch-list">
                {recentWatchItems.map((item) => (
                  <article className="source-watch-row" key={item.id || item.stem}>
                    <div>
                      <strong>{item.university || item.stem}</strong>
                      <span>{item.admission_year || "未标年度"} · {sourceTypeText(item.source_type)}</span>
                    </div>
                    <span className={checkStatusClass(item.check_status)}>{checkStatusText(item.check_status, item.days_since_checked)}</span>
                  </article>
                ))}
              </div>
            </section>

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
                  <strong>{sourceSummary.open ?? sourceSummary.needs_review ?? 0}</strong>
                </div>
                <div>
                  <span>需重新整理</span>
                  <strong>{sourceSummary.needs_reextract ?? 0}</strong>
                </div>
                <div>
                  <span>已查看</span>
                  <strong>{sourceSummary.reviewed ?? 0}</strong>
                </div>
              </div>

              <div className="source-review-filter-tabs" aria-label="来源变化范围">
                {SOURCE_QUEUE_FILTERS.map((item) => {
                  const count =
                    item.key === "open"
                      ? (sourceSummary.open ?? sourceSummary.needs_review ?? 0)
                      : item.key === "needs_reextract"
                        ? (sourceSummary.needs_reextract ?? 0)
                        : item.key === "reviewed"
                          ? (sourceSummary.reviewed ?? 0)
                          : sourceItems.length;
                  return (
                    <button
                      className={sourceFilter === item.key ? "is-active" : ""}
                      key={item.key}
                      onClick={() => setSourceFilter(item.key)}
                      type="button"
                    >
                      <span>{item.label}</span>
                      <strong>{count}</strong>
                    </button>
                  );
                })}
              </div>

              <div className="source-review-list">
                {filteredSourceItems.slice(0, 8).map((item) => {
                  const matchedDoc = findDocumentForSource(item, documents);
                  return (
                    <article className="source-review-card" key={`${item.stem}-${item.checked_at}-${item.status}`}>
                      <div className="item-card-topline">
                        <span className={sourceStatusClass(item.status)}>{item.status_label || sourceStatusText(item.status)}</span>
                        <span className={attentionClass(item.attention_level)}>{attentionText(item.attention_level)}</span>
                        <span className={reviewStatusClass(item.review_status)}>{reviewStatusText(item.review_status)}</span>
                        <span className="badge badge-gray">{item.admission_year || "未标年度"}</span>
                      </div>
                      <h4 className="item-title">{item.university || item.stem || "未命名来源"}</h4>
                      <p className="item-subtitle">{item.owner_summary || item.error || sourceActionText(item.status)}</p>
                      {item.likely_changed_areas?.length ? (
                        <div className="source-review-focus" aria-label="建议先看的内容">
                          <span>先看</span>
                          {item.likely_changed_areas.map((area) => (
                            <strong key={area}>{area}</strong>
                          ))}
                        </div>
                      ) : null}
                      {item.next_steps?.length ? (
                        <ol className="source-review-next-steps" aria-label="建议处理顺序">
                          {item.next_steps.slice(0, 3).map((step) => (
                            <li key={step}>{step}</li>
                          ))}
                        </ol>
                      ) : null}
                      <div className="source-review-actions">
                        <div className="inline-actions inline-actions-tight">
                          {matchedDoc && onOpenReview ? (
                            <button className="btn btn-primary btn-small" type="button" onClick={() => onOpenReview(matchedDoc.doc_id)}>
                              进入复审
                            </button>
                          ) : null}
                          <button
                            className="btn btn-green btn-small"
                            disabled={reextractingSourceId === item.item_id}
                            type="button"
                            onClick={() => void reextractSourceItem(item.item_id)}
                          >
                            {reextractingSourceId === item.item_id ? "正在整理" : "重新整理并复审"}
                          </button>
                          {item.source_url ? (
                            <a className="btn btn-ghost btn-small" href={item.source_url} target="_blank" rel="noreferrer">
                              打开官网资料
                            </a>
                          ) : null}
                        </div>
                        <span>{item.checked_at || sourceQueue?.generated_at || ""}</span>
                      </div>
                      <div className="source-review-decisions">
                        <button
                          className="btn btn-ghost btn-small"
                          disabled={updatingSourceId === item.item_id}
                          type="button"
                          onClick={() => void setSourceItemStatus(item.item_id, "reviewed")}
                        >
                          已查看
                        </button>
                        <button
                          className="btn btn-ghost btn-small"
                          disabled={updatingSourceId === item.item_id}
                          type="button"
                          onClick={() => void setSourceItemStatus(item.item_id, "needs_reextract")}
                        >
                          需要重新整理
                        </button>
                        <button
                          className="btn btn-ghost btn-small"
                          disabled={updatingSourceId === item.item_id}
                          type="button"
                          onClick={() => void setSourceItemStatus(item.item_id, "deferred")}
                        >
                          暂不处理
                        </button>
                      </div>
                    </article>
                  );
                })}
                {!filteredSourceItems.length ? <div className="empty-state empty-state-quiet">这个范围里暂时没有需要处理的来源变化。</div> : null}
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

            {!selectedDoc ? (
              <section className="quality-section quality-language-panel">
                <div className="split-row">
                  <div>
                    <h3 className="panel-title">留学生要求覆盖</h3>
                    <p className="panel-copy">这里只看人工基准里已经核过的语言要求，用来决定下一批要补看的资料。</p>
                  </div>
                  <span className="badge badge-blue">{overview?.overall_status === "quality_gate_ready" ? "基线可用" : "需要补看"}</span>
                </div>
                <div className="language-coverage-grid">
                  {languageCoverage.map(([field, stats]) => (
                    <article className="language-coverage-card" key={field}>
                      <span>{languageLabel(field)}</span>
                      <strong>{stats.checked}</strong>
                      <p>{coverageTone(Number(stats.checked || 0))} · 通过 {stats.passed}</p>
                    </article>
                  ))}
                  {!languageCoverage.length ? <div className="empty-state empty-state-quiet">暂无语言要求覆盖报告。</div> : null}
                </div>
                {thinCoverageRows.length ? (
                  <div className="thin-coverage-list">
                    <strong>下一批适合补看的地方</strong>
                    {thinCoverageRows.slice(0, 5).map((row) => (
                      <span key={`${row.seed}-${row.field}`}>
                        {row.seed} · {contentLabel(row.field)} 已核 {row.checked}/{row.minimum}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="thin-coverage-list is-quiet">
                    <strong>当前没有明显偏薄的基准项</strong>
                    <span>后续扩充学校时，再同步补人工基准。</span>
                  </div>
                )}
              </section>
            ) : null}

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
