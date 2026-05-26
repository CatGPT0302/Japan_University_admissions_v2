import { useEffect, useMemo, useState } from "react";
import { downloadAdminBookingsCsv, getAdminBookings, toErrorMessage, updateAdminBooking } from "../api/client";
import type { AdminConsultationBooking, ConsultationBookingStatus } from "../types";

const STATUS_OPTIONS: Array<{ key: ConsultationBookingStatus | ""; label: string }> = [
  { key: "", label: "全部" },
  { key: "new", label: "待联系" },
  { key: "contacted", label: "已联系" },
  { key: "done", label: "已处理" },
  { key: "closed", label: "暂不跟进" },
];

type FollowUpBucket = "overdue" | "today" | "later" | "unscheduled";

const FOLLOW_UP_BUCKET_LABELS: Record<FollowUpBucket, string> = {
  overdue: "逾期跟进",
  today: "今天要跟进",
  later: "之后跟进",
  unscheduled: "未安排",
};

function statusText(status?: string): string {
  if (status === "new") return "待联系";
  if (status === "contacted") return "已联系";
  if (status === "done") return "已处理";
  if (status === "closed") return "暂不跟进";
  return "待联系";
}

function statusClass(status?: string): string {
  if (status === "new") return "badge badge-amber";
  if (status === "contacted") return "badge badge-blue";
  if (status === "done") return "badge badge-green";
  return "badge badge-gray";
}

function contactText(item: AdminConsultationBooking): string {
  return item.contact_email || item.contact_phone || "未留联系方式";
}

function programText(item: AdminConsultationBooking): string {
  const school = item.school_name || "未选择学校";
  const program = [item.faculty, item.department].filter(Boolean).join(" / ");
  return program ? `${school} · ${program}` : school;
}

function dateKey(value?: string): string {
  const match = String(value || "").match(/(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
  if (!match) return "";
  const [, year, month, day] = match;
  return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
}

function todayKey(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function followUpBucket(item: AdminConsultationBooking, today = todayKey()): FollowUpBucket {
  if (item.status === "done" || item.status === "closed") return "unscheduled";
  const key = dateKey(item.next_action_at);
  if (!key) return "unscheduled";
  if (key < today) return "overdue";
  if (key === today) return "today";
  return "later";
}

function printBookingHandoff() {
  window.print();
}

export default function BookingsPage() {
  const [items, setItems] = useState<AdminConsultationBooking[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [status, setStatus] = useState<ConsultationBookingStatus | "">("new");
  const [loading, setLoading] = useState(false);
  const [workingId, setWorkingId] = useState<number | null>(null);
  const [ownerNote, setOwnerNote] = useState("");
  const [nextActionAt, setNextActionAt] = useState("");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load(nextStatus = status, nextQuery = query) {
    setLoading(true);
    setError("");
    try {
      const rows = await getAdminBookings({ status: nextStatus || undefined, q: nextQuery.trim() || undefined, limit: 100 });
      setItems(rows);
      setSelectedId((current) => (current && rows.some((item) => item.id === current) ? current : rows[0]?.id ?? null));
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) ?? items[0] ?? null,
    [items, selectedId],
  );
  const openCount = items.filter((item) => item.status === "new").length;
  const groupedItems = useMemo(() => {
    const today = todayKey();
    return (["overdue", "today", "later", "unscheduled"] as FollowUpBucket[])
      .map((bucket) => ({
        bucket,
        label: FOLLOW_UP_BUCKET_LABELS[bucket],
        items: items.filter((item) => followUpBucket(item, today) === bucket),
      }))
      .filter((group) => group.items.length > 0);
  }, [items]);
  const overdueCount = groupedItems.find((group) => group.bucket === "overdue")?.items.length ?? 0;
  const todayCount = groupedItems.find((group) => group.bucket === "today")?.items.length ?? 0;
  const summaryCards = (["overdue", "today", "later", "unscheduled"] as FollowUpBucket[]).map((bucket) => {
    const group = groupedItems.find((item) => item.bucket === bucket);
    return {
      bucket,
      label: FOLLOW_UP_BUCKET_LABELS[bucket],
      count: group?.items.length ?? 0,
      firstId: group?.items[0]?.id ?? null,
      note:
        bucket === "overdue"
          ? "先处理这些"
          : bucket === "today"
            ? "今天要联系"
            : bucket === "later"
              ? "已有安排"
              : "需要定下一步",
    };
  });

  useEffect(() => {
    setOwnerNote(selected?.owner_note || "");
    setNextActionAt(selected?.next_action_at || "");
  }, [selected?.id, selected?.next_action_at, selected?.owner_note]);

  function replaceBooking(updated: AdminConsultationBooking) {
    setItems((current) => current.map((row) => (row.id === updated.id ? updated : row)));
    setSelectedId(updated.id);
  }

  async function setBookingStatus(item: AdminConsultationBooking, nextStatus: ConsultationBookingStatus) {
    setWorkingId(item.id);
    setError("");
    setMessage("");
    try {
      const updated = await updateAdminBooking(item.id, { status: nextStatus });
      replaceBooking(updated);
      setMessage(`已标记为：${statusText(updated.status)}。`);
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setWorkingId(null);
    }
  }

  async function saveFollowUp(item: AdminConsultationBooking) {
    setWorkingId(item.id);
    setError("");
    setMessage("");
    try {
      const updated = await updateAdminBooking(item.id, {
        owner_note: ownerNote.trim(),
        next_action_at: nextActionAt.trim(),
      });
      replaceBooking(updated);
      setMessage("跟进安排已保存。");
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setWorkingId(null);
    }
  }

  return (
    <div className="page-shell bookings-page">
      <section className="hero-panel">
        <div className="split-row split-row-start">
          <div>
            <div className="section-kicker">咨询请求</div>
            <h2 className="section-title">学生预约与后续联系</h2>
            <p className="section-copy">学生端提交的预约会到这里。先看联系方式、目标学校和问题，再标记跟进状态。</p>
          </div>
          <div className="hero-metrics">
            <div className="metric-card">
              <span className="metric-label">当前筛选</span>
              <strong className="metric-value">{items.length}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">待联系</span>
              <strong className="metric-value">{openCount}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">逾期跟进</span>
              <strong className="metric-value">{overdueCount}</strong>
            </div>
            <div className="metric-card">
              <span className="metric-label">今天跟进</span>
              <strong className="metric-value">{todayCount}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="content-grid">
        <aside className="sidebar-panel">
          <div className="toolbar-shell">
            <h3 className="panel-title">跟进状态</h3>
            <p className="panel-copy">用状态把新预约和已处理请求分开。</p>
            <div className="filter-row">
              {STATUS_OPTIONS.map((option) => (
                <button
                  className={`filter-chip${status === option.key ? " is-active" : ""}`}
                  key={option.label}
                  type="button"
                  onClick={() => {
                    setStatus(option.key);
                    void load(option.key);
                  }}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <label className="booking-search field-wrap">
              <span className="detail-label">快速查找</span>
              <input
                className="field"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void load(status, query);
                }}
                placeholder="姓名、电话、学校或备注"
              />
            </label>
            <div className="inline-actions inline-actions-tight">
              <button className="btn btn-primary" type="button" onClick={() => void load(status, query)}>
                查找
              </button>
              <button
                className="btn btn-ghost"
                type="button"
                onClick={() => {
                  setQuery("");
                  void load(status, "");
                }}
              >
                清空
              </button>
            </div>
            <button className="btn btn-ghost" type="button" onClick={() => void load()}>
              {loading ? "刷新中" : "刷新"}
            </button>
            <button className="btn btn-primary" type="button" onClick={() => downloadAdminBookingsCsv(status, query)}>
              导出当前咨询
            </button>
          </div>
        </aside>

        <div className="item-detail">
          {error ? <div className="message-box error">{error}</div> : null}
          {message ? <div className="message-box info">{message}</div> : null}

          <div className="detail-shell">
            <div className="detail-header">
              <div>
                <div className="card-kicker">今日摘要</div>
                <h3 className="panel-title">先处理最需要跟进的请求</h3>
              </div>
              <span className="badge badge-gray">{items.length} 条</span>
            </div>
            <div className="booking-daily-summary" aria-label="每日咨询摘要">
              {summaryCards.map((item) => (
                <button
                  className={`booking-summary-card is-${item.bucket}`}
                  disabled={!item.firstId}
                  key={item.bucket}
                  type="button"
                  onClick={() => {
                    if (item.firstId) setSelectedId(item.firstId);
                  }}
                >
                  <span>{item.label}</span>
                  <strong>{item.count}</strong>
                  <small>{item.note}</small>
                </button>
              ))}
            </div>
          </div>

          <div className="detail-shell">
            <div className="detail-header">
              <div>
                <div className="card-kicker">预约列表</div>
                <h3 className="panel-title">选择一条请求查看详情</h3>
              </div>
              <span className="badge badge-gray">{items.length} 条</span>
            </div>

            <div className="document-list">
              {groupedItems.map((group) => (
                <section className="booking-followup-group" key={group.bucket} aria-label={group.label}>
                  <div className="booking-followup-group-head">
                    <strong>{group.label}</strong>
                    <span>{group.items.length} 条</span>
                  </div>
                  {group.items.map((item) => (
                    <button
                      className={`item-card${selected?.id === item.id ? " is-active" : ""}`}
                      key={item.id}
                      type="button"
                      onClick={() => setSelectedId(item.id)}
                    >
                      <div className="item-card-topline">
                        <span className={statusClass(item.status)}>{statusText(item.status)}</span>
                        <span className="badge badge-gray">{item.target_year || item.admission_year || "未填年度"}</span>
                      </div>
                      <h4 className="item-title">{item.student_name || "未填写姓名"}</h4>
                      <p className="item-subtitle">{programText(item)}</p>
                      <p className="item-subtitle">{contactText(item)}</p>
                      {item.next_action_at ? <p className="item-subtitle">下次跟进：{item.next_action_at}</p> : null}
                    </button>
                  ))}
                </section>
              ))}
            </div>

            {!items.length && !loading ? (
              <div className="empty-state empty-state-quiet">
                <h3 className="panel-title">暂时没有预约</h3>
                <p className="panel-copy">学生端提交后，这里会出现联系方式和想咨询的问题。</p>
              </div>
            ) : null}
          </div>

          {selected ? (
            <div className="detail-shell detail-shell-editing">
              <div className="detail-header">
                <div>
                  <div className="card-kicker">请求详情</div>
                  <h3 className="panel-title">{selected.student_name}</h3>
                </div>
                <span className={statusClass(selected.status)}>{statusText(selected.status)}</span>
              </div>

              <div className="detail-grid">
                <div className="detail-field">
                  <span className="detail-label">联系方式</span>
                  <div className="detail-value">{contactText(selected)}</div>
                </div>
                <div className="detail-field">
                  <span className="detail-label">身份</span>
                  <div className="detail-value">{selected.role || "-"}</div>
                </div>
                <div className="detail-field is-span-2">
                  <span className="detail-label">目标学校</span>
                  <div className="detail-value">{programText(selected)}</div>
                </div>
                <div className="detail-field">
                  <span className="detail-label">目标年度</span>
                  <div className="detail-value">{selected.target_year || selected.admission_year || "-"}</div>
                </div>
                <div className="detail-field">
                  <span className="detail-label">方便时间</span>
                  <div className="detail-value">{selected.preferred_times || "-"}</div>
                </div>
                <div className="detail-field is-span-2">
                  <span className="detail-label">想咨询的问题</span>
                  <div className="detail-value">{selected.question || "-"}</div>
                </div>
                <div className="detail-field is-span-2">
                  <span className="detail-label">提交时间</span>
                  <div className="detail-value">{selected.created_at || "-"}</div>
                </div>
                <label className="detail-field is-span-2 field-wrap">
                  <span className="detail-label">跟进备注</span>
                  <textarea
                    className="field"
                    value={ownerNote}
                    onChange={(event) => setOwnerNote(event.target.value)}
                    placeholder="例如：先确认 EJU 分数，再约一次家长沟通"
                  />
                </label>
                <label className="detail-field field-wrap">
                  <span className="detail-label">下次跟进</span>
                  <input
                    className="field"
                    value={nextActionAt}
                    onChange={(event) => setNextActionAt(event.target.value)}
                    placeholder="例如：2026-06-01 14:00"
                  />
                </label>
              </div>

              <div className="booking-print-sheet" aria-label="咨询交接摘要">
                <div className="booking-print-head">
                  <div>
                    <div className="card-kicker">交接摘要</div>
                    <h3>{selected.student_name || "未填写姓名"}</h3>
                  </div>
                  <span>{statusText(selected.status)}</span>
                </div>
                <dl>
                  <div>
                    <dt>联系方式</dt>
                    <dd>{contactText(selected)}</dd>
                  </div>
                  <div>
                    <dt>目标学校</dt>
                    <dd>{programText(selected)}</dd>
                  </div>
                  <div>
                    <dt>目标年度</dt>
                    <dd>{selected.target_year || selected.admission_year || "-"}</dd>
                  </div>
                  <div>
                    <dt>方便时间</dt>
                    <dd>{selected.preferred_times || "-"}</dd>
                  </div>
                  <div>
                    <dt>想咨询的问题</dt>
                    <dd>{selected.question || "-"}</dd>
                  </div>
                  <div>
                    <dt>跟进备注</dt>
                    <dd>{ownerNote || selected.owner_note || "-"}</dd>
                  </div>
                  <div>
                    <dt>下次跟进</dt>
                    <dd>{nextActionAt || selected.next_action_at || "-"}</dd>
                  </div>
                </dl>
              </div>

              <div className="inline-actions">
                <button
                  className="btn btn-primary"
                  type="button"
                  disabled={workingId === selected.id}
                  onClick={() => void saveFollowUp(selected)}
                >
                  保存跟进安排
                </button>
                <button className="btn btn-ghost" type="button" onClick={printBookingHandoff}>
                  打印交接单
                </button>
                <button
                  className="btn btn-ghost"
                  type="button"
                  disabled={workingId === selected.id}
                  onClick={() => void setBookingStatus(selected, "contacted")}
                >
                  标记已联系
                </button>
                <button
                  className="btn btn-green"
                  type="button"
                  disabled={workingId === selected.id}
                  onClick={() => void setBookingStatus(selected, "done")}
                >
                  标记已处理
                </button>
                <button
                  className="btn btn-ghost"
                  type="button"
                  disabled={workingId === selected.id}
                  onClick={() => void setBookingStatus(selected, "closed")}
                >
                  暂不跟进
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
