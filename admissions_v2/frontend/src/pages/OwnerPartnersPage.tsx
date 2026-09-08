import { useEffect, useMemo, useState } from "react";
import {
  API_BASE_URL,
  createApiKey,
  getAdminSubmissions,
  getApiCenter,
  startAdminSubmission,
  toErrorMessage,
  updateAdminSubmission,
} from "../api/client";
import type {
  AdminSubmission,
  ApiCenterResponse,
  ApiKeyCreateResponse,
  ApiUsageLog,
  SubmissionStatus,
} from "../types";

type SettingsSection = "overview" | "access" | "documents" | "activity" | "handoff";

const OWNER_PARTNER_ROUTE = `#/${String(import.meta.env.VITE_OWNER_PARTNER_ROUTE || "owner-service").replace(/^#?\/?/, "")}`;
const OWNER_WORKSPACE_URL = String(import.meta.env.VITE_OWNER_WORKSPACE_URL || "").trim().replace(/\/$/, "");

interface Props {
  onOpenReview?: (docId: number) => void;
}

const SECTIONS: Array<{ key: SettingsSection; label: string; hint: string }> = [
  { key: "overview", label: "今日待办", hint: "按顺序走" },
  { key: "access", label: "开通合作方", hint: "输入名称" },
  { key: "documents", label: "资料进度", hint: "谁交了什么" },
  { key: "activity", label: "使用情况", hint: "有没有用上" },
  { key: "handoff", label: "复制给对方", hint: "发给负责人" },
];

const ABILITY_LABELS: Record<string, string> = {
  "programs:read": "查看招生要求",
  "recommendations:create": "按学生情况推荐学校",
  "documents:submit": "上传招生资料",
  "documents:read_status": "查看资料处理进度",
};

const HIDDEN_ABILITY_SCOPES = new Set(["bookings:create"]);

function abilityLabel(scope: string): string {
  return ABILITY_LABELS[scope] || "其他服务";
}

function visibleScopes(scopes?: string[]): string[] {
  return (scopes || []).filter((scope) => !HIDDEN_ABILITY_SCOPES.has(scope));
}

function statusLabel(status: string): string {
  if (status === "active") return "正常";
  if (status === "revoked") return "已停用";
  return status || "未设置";
}

function usageTitle(item: ApiUsageLog): string {
  if (item.scope) return abilityLabel(item.scope);
  if (item.path.includes("programs")) return "查看学校与招生要求";
  if (item.path.includes("recommendations")) return "生成推荐";
  if (item.path.includes("bookings")) return "一次旧接口使用";
  if (item.path.includes("documents")) return "提交或查看资料";
  return "一次使用记录";
}

function usageStatus(code: number): string {
  if (code >= 200 && code < 300) return "成功";
  if (code === 401 || code === 403) return "密码不对";
  return "需要检查";
}

function organizationName(name?: string): string {
  if (!name || name.toLowerCase().includes("owner")) return "本地工作台";
  return name;
}

function submissionStatusText(status?: string): string {
  if (status === "submitted") return "刚收到";
  if (status === "processing") return "整理中";
  if (status === "needs_owner_review") return "等你确认";
  if (status === "confirmed") return "已完成";
  if (status === "needs_more_info") return "需要补资料";
  if (status === "failed") return "处理失败";
  return "待处理";
}

function submissionHint(item: AdminSubmission): string {
  if (item.processing_status === "submitted") return "可以开始整理。整理后会进入后台核对。";
  if (item.processing_status === "processing") return "正在整理，请稍后刷新。";
  if (item.processing_status === "needs_owner_review") return "已经整理好，下一步去资料中心确认。";
  if (item.processing_status === "confirmed") return "已经进入正式资料，可以被学生端和授权查询使用。";
  if (item.processing_status === "needs_more_info") return "资料不够完整，先让对方补 PDF 或官网链接。";
  if (item.processing_status === "failed") return "这次没有整理成功，可以补充资料后再试。";
  return "等待处理。";
}

function submissionSource(item: AdminSubmission): string {
  if (item.original_file_name || item.file_name) return item.original_file_name || item.file_name || "PDF 文件";
  if (item.pdf_url) return "PDF 链接";
  if (item.page_url) return "官网页面";
  return "资料";
}

export default function SettingsPage({ onOpenReview }: Props) {
  const [center, setCenter] = useState<ApiCenterResponse | null>(null);
  const [submissions, setSubmissions] = useState<AdminSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [workingSubmissionId, setWorkingSubmissionId] = useState<number | null>(null);
  const [clientName, setClientName] = useState("合作方名称");
  const [newKey, setNewKey] = useState<ApiKeyCreateResponse | null>(null);
  const [message, setMessage] = useState("");
  const [section, setSection] = useState<SettingsSection>("overview");
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<number | null>(null);

  async function load() {
    setLoading(true);
    setMessage("");
    try {
      const [nextCenter, nextSubmissions] = await Promise.all([
        getApiCenter(),
        getAdminSubmissions({ limit: 30 }),
      ]);
      setCenter(nextCenter);
      setSubmissions(nextSubmissions);
    } catch (error) {
      setMessage(toErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const baseUrl = useMemo(() => `${API_BASE_URL}/v1`, []);
  const latestKey = center?.api_keys[0];
  const displayKey = newKey?.secret || latestKey?.masked_key || "尚未创建";
  const canConnect = Boolean(latestKey || newKey);
  const canCopyGuide = Boolean(newKey?.secret);
  const recentUsage = center?.recent_usage || [];
  const usageSummary = center?.usage_summary;
  const waitingSubmissions = submissions.filter((item) => item.processing_status !== "confirmed");
  const waitingForOwner = submissions.filter((item) => ["submitted", "needs_more_info", "failed"].includes(item.processing_status)).length;
  const readyForReview = submissions.filter((item) => item.processing_status === "needs_owner_review").length;
  const selectedSubmission = useMemo(
    () => submissions.find((item) => item.id === selectedSubmissionId) || submissions[0] || null,
    [selectedSubmissionId, submissions],
  );
  const progressItems = [
    {
      done: canConnect,
      title: canConnect ? "合作方已经开通" : "先开通一家合作方",
      note: canConnect ? "可以把信息发给对方了。" : "输入合作方名称，生成一份专用密码。",
    },
    {
      done: canCopyGuide,
      title: canCopyGuide ? "要发的信息已经准备好" : "等待生成可复制的信息",
      note: canCopyGuide ? "复制后发给对方负责人。" : "开通后这里会自动准备完整说明。",
    },
    {
      done: submissions.length > 0,
      title: submissions.length ? "已经收到资料" : "等待对方提交资料",
      note: submissions.length ? "下一步去资料进度里处理。" : "对方提交 PDF 或链接后，这里会出现进度。",
    },
  ];
  const guide = [
    "请把下面这段发给合作方负责系统的人：",
    "",
    `系统入口：${baseUrl}`,
    `专用密码：${displayKey}`,
    "",
    "可以做的事：",
    ...visibleScopes(center?.allowed_scopes).map((scope) => `- ${abilityLabel(scope)}`),
    "",
    "常用地址：",
    `- 查看招生信息：${baseUrl}/programs`,
    `- 提交招生资料：${baseUrl}/documents/submissions`,
  ].join("\n");

  async function handleCreateKey() {
    setCreating(true);
    setMessage("");
    try {
      const created = await createApiKey(clientName.trim() || "合作方名称");
      setNewKey(created);
      await load();
      setMessage("已开通。请先复制专用密码，发给合作方负责人。");
    } catch (error) {
      setMessage(toErrorMessage(error));
    } finally {
      setCreating(false);
    }
  }

  async function copyText(value: string, label: string) {
    await navigator.clipboard.writeText(value);
    setMessage(`${label}已复制。`);
  }

  function replaceSubmission(next: AdminSubmission) {
    setSubmissions((current) => current.map((item) => (item.id === next.id ? next : item)));
    setSelectedSubmissionId(next.id);
  }

  const reviewActionLabel = onOpenReview
    ? "去确认资料"
    : OWNER_WORKSPACE_URL
      ? "打开 Owner 工作台"
      : "查看确认方式";

  async function handleStartSubmission(submissionId: number) {
    setWorkingSubmissionId(submissionId);
    setMessage("");
    try {
      replaceSubmission(await startAdminSubmission(submissionId));
      setMessage("已经开始整理。整理完成后，请到资料中心确认。");
    } catch (error) {
      setMessage(toErrorMessage(error));
      await load();
    } finally {
      setWorkingSubmissionId(null);
    }
  }

  async function handleSetSubmissionStatus(submissionId: number, status: SubmissionStatus) {
    setWorkingSubmissionId(submissionId);
    setMessage("");
    try {
      replaceSubmission(await updateAdminSubmission(submissionId, { processing_status: status }));
      setMessage(status === "confirmed" ? "已标记完成。" : "进度已更新。");
    } catch (error) {
      setMessage(toErrorMessage(error));
    } finally {
      setWorkingSubmissionId(null);
    }
  }

  function openReviewForSubmission(item: AdminSubmission) {
    if (item.document_id && onOpenReview) {
      onOpenReview(item.document_id);
      return;
    }
    if (OWNER_WORKSPACE_URL) {
      window.location.href = `${OWNER_WORKSPACE_URL}/#/review`;
      return;
    }
    setMessage("请打开 Owner 资料中心，在人工复审中确认这份资料。");
  }

  if (loading && !center) {
    return (
      <div className="settings-shell-ios settings-page">
        <header className="settings-topbar">
          <a className="settings-brand" href={OWNER_PARTNER_ROUTE} aria-label="合作方管理首页">
            <span>
              <strong>合作方</strong>
              <small>Owner 管理</small>
            </span>
          </a>
        </header>
        <main className="settings-main">
          <section className="settings-hero settings-dashboard-hero">
            <p className="section-kicker">设置</p>
            <h2>正在打开设置</h2>
            <p>请稍等片刻。</p>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="settings-shell-ios settings-page">
      <header className="settings-topbar">
        <a className="settings-brand" href={OWNER_PARTNER_ROUTE} aria-label="合作方管理首页">
          <span>
            <strong>合作方</strong>
            <small>Owner 管理</small>
          </span>
        </a>
      </header>

      <main className="settings-main">
        <section className="settings-hero settings-dashboard-hero">
          <div>
            <p className="section-kicker">设置</p>
            <h2>合作方服务中心</h2>
            <p>先开通合作方，再让对方提交资料。收到资料后，你在这里安排整理和确认。</p>
          </div>
          <div className={`settings-status-card${canConnect ? " is-ready" : ""}`}>
            <span>现在进度</span>
            <strong>{waitingSubmissions.length ? `${waitingSubmissions.length} 件待处理` : canConnect ? "可以使用" : "还没开通"}</strong>
            <small>{organizationName(center?.organization.name)}</small>
          </div>
        </section>

        <section className="settings-summary-grid" aria-label="合作方概览">
          <div className="settings-summary-card">
            <span>待你处理</span>
            <strong>{waitingForOwner}</strong>
            <small>可开始整理或需要补资料</small>
          </div>
          <div className="settings-summary-card">
            <span>等你确认</span>
            <strong>{readyForReview}</strong>
            <small>整理完成后进资料中心</small>
          </div>
          <div className="settings-summary-card">
            <span>对方使用</span>
            <strong>{usageSummary?.total ?? 0}</strong>
            <small>{usageSummary?.needs_check ? `${usageSummary.needs_check} 次需要检查` : "暂无异常"}</small>
          </div>
        </section>

        {message ? <div className="message-box info">{message}</div> : null}

        {newKey ? (
          <section className="settings-once settings-save-card">
            <div>
              <p className="section-kicker">请先保存</p>
              <h3>这是合作方的专用密码</h3>
              <p>现在复制保存。离开页面后只会显示一部分。</p>
            </div>
            <code>{newKey.secret}</code>
            <button className="btn btn-primary" type="button" onClick={() => void copyText(newKey.secret, "专用密码")}>
              复制专用密码
            </button>
          </section>
        ) : null}

        <div className="settings-layout-panel">
          <nav className="settings-section-nav" aria-label="设置分类">
            {SECTIONS.map((item) => (
              <button
                className={`settings-section-button${section === item.key ? " is-active" : ""}`}
                key={item.key}
                type="button"
                onClick={() => setSection(item.key)}
              >
                <strong>{item.label}</strong>
                <span>{item.hint}</span>
              </button>
            ))}
          </nav>

          <div className="settings-section-view">
          {section === "overview" ? (
            <section className="settings-panel settings-next-panel">
              <div className="settings-section-head">
                <div>
                  <p className="section-kicker">从这里开始</p>
                  <h3>今天只要完成这三件事</h3>
                </div>
                <button className="btn btn-primary" type="button" onClick={() => setSection("access")}>
                  开始开通
                </button>
              </div>
              <div className="settings-plain-intro">
                <strong>一句话说明</strong>
                <p>这是给合作方使用的入口。你负责开通和确认数据，对方负责提交资料或录入学生信息。</p>
              </div>
              <div className="settings-action-grid">
                <button className="settings-action-card" type="button" onClick={() => setSection("access")}>
                  <span>1</span>
                  <strong>输入合作方名称</strong>
                  <p>给这个合作方生成一份只给它用的密码。</p>
                </button>
                <button className="settings-action-card" type="button" onClick={() => setSection("handoff")}>
                  <span>2</span>
                  <strong>复制给对方</strong>
                  <p>把入口和专用密码发给对方负责人。</p>
                </button>
                <button className="settings-action-card" type="button" onClick={() => setSection("documents")}>
                  <span>3</span>
                  <strong>处理提交资料</strong>
                  <p>对方交来的 PDF 或链接，会集中出现在这里。</p>
                </button>
              </div>
              <div className="settings-progress-list" aria-label="开通进度">
                {progressItems.map((item) => (
                  <div className={`settings-progress-item${item.done ? " is-done" : ""}`} key={item.title}>
                    <span>{item.done ? "✓" : ""}</span>
                    <div>
                      <strong>{item.title}</strong>
                      <p>{item.note}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {section === "access" ? (
            <section className="settings-panel settings-panel-primary">
              <div className="settings-section-head">
                <div>
                  <p className="section-kicker">第一步</p>
                  <h3>要开通哪个合作方？</h3>
                  <p>输入对方名称，页面会生成一份只给这家使用的专用密码。</p>
                </div>
                <span className="settings-pill">{statusLabel(latestKey?.status || "")}</span>
              </div>

              <div className="settings-create-row">
                <label className="field-wrap">
                  <span className="field-label">合作方名称</span>
                  <input className="field" value={clientName} onChange={(event) => setClientName(event.target.value)} />
                </label>
                <button className="btn btn-primary" type="button" disabled={creating} onClick={() => void handleCreateKey()}>
                  {creating ? "正在生成" : "生成专用密码"}
                </button>
              </div>

              <div className="settings-info-list">
                <div className="settings-copy-row">
                  <span>给对方的入口</span>
                  <strong>{baseUrl}</strong>
                  <button className="btn btn-ghost" type="button" onClick={() => void copyText(baseUrl, "系统入口")}>
                    复制
                  </button>
                </div>
                <div className="settings-copy-row">
                  <span>给对方的密码</span>
                  <strong>{displayKey}</strong>
                  <button className="btn btn-ghost" type="button" disabled={!newKey?.secret} onClick={() => void copyText(newKey?.secret || "", "专用密码")}>
                    复制
                  </button>
                </div>
              </div>
              {!newKey?.secret && latestKey ? (
                <p className="settings-soft-note">已经开通过的密码只显示一部分。要发给新负责人时，请重新开通一份。</p>
              ) : null}

              <div className="settings-key-list">
                <p className="settings-list-title">已经开通过的合作方</p>
                {(center?.api_keys || []).map((key) => (
                  <article className="settings-key-row" key={key.id}>
                    <div>
                      <strong>{key.client_name}</strong>
                      <span>{key.masked_key}</span>
                    </div>
                    <div className="settings-key-meta">
                      <span>{statusLabel(key.status)}</span>
                      <span>{key.last_used_at || "还没有使用记录"}</span>
                    </div>
                  </article>
                ))}
                {!center?.api_keys.length ? <p className="settings-empty">还没有开通过合作方。</p> : null}
              </div>
            </section>
          ) : null}

          {section === "documents" ? (
            <section className="settings-panel">
              <p className="section-kicker">收资料</p>
              <h3>对方交来的资料会在这里排队</h3>
              <p className="settings-note">你只需要看学校、资料来源和下一步。真正保存到正式资料前，仍然由你来确认。</p>

              <div className="settings-submission-workspace">
                <div className="settings-submission-list">
                  {submissions.map((item) => {
                    const canStart = ["submitted", "needs_more_info", "failed"].includes(item.processing_status);
                    const canComplete = Boolean(item.document_id);
                    const busy = workingSubmissionId === item.id;
                    return (
                      <article className={`settings-submission-card${selectedSubmission?.id === item.id ? " is-active" : ""}`} key={item.id}>
                        <button className="settings-submission-main" type="button" onClick={() => setSelectedSubmissionId(item.id)}>
                          <span className={`settings-submission-status is-${item.processing_status}`}>
                            {submissionStatusText(item.processing_status)}
                          </span>
                          <strong>{item.university || "未写学校名"}</strong>
                          <p>
                            {item.organization_name} · {item.admission_year || "年度未写"} · {submissionSource(item)}
                          </p>
                          {item.notes ? <small>{item.notes}</small> : null}
                          <em>{submissionHint(item)}</em>
                        </button>
                        <div className="settings-submission-actions">
                          {canStart ? (
                            <button className="btn btn-primary" type="button" disabled={busy} onClick={() => void handleStartSubmission(item.id)}>
                              {busy ? "整理中" : "开始整理"}
                            </button>
                          ) : null}
                          {item.processing_status === "needs_owner_review" ? (
                            <>
                              <button className="btn btn-primary" type="button" onClick={() => openReviewForSubmission(item)}>
                                {reviewActionLabel}
                              </button>
                              {canComplete ? (
                                <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => void handleSetSubmissionStatus(item.id, "confirmed")}>
                                  标记已完成
                                </button>
                              ) : (
                                <span className="settings-submission-action-note">先完成整理后再标记</span>
                              )}
                            </>
                          ) : null}
                          {item.processing_status === "processing" ? (
                            <button className="btn btn-ghost" type="button" onClick={() => void load()}>
                              刷新进度
                            </button>
                          ) : null}
                        </div>
                      </article>
                    );
                  })}
                  {!submissions.length ? (
                    <p className="settings-empty">还没有收到资料。开通合作方后，对方提交的 PDF 或官网链接会出现在这里。</p>
                  ) : null}
                </div>

                {selectedSubmission ? (
                  <aside className="settings-submission-detail" aria-label="资料详情">
                    <div>
                      <p className="section-kicker">资料详情</p>
                      <h4>{selectedSubmission.university || "未写学校名"}</h4>
                      <span className={`settings-submission-status is-${selectedSubmission.processing_status}`}>
                        {submissionStatusText(selectedSubmission.processing_status)}
                      </span>
                    </div>
                    <dl>
                      <div><dt>合作方</dt><dd>{selectedSubmission.organization_name || "-"}</dd></div>
                      <div><dt>年度</dt><dd>{selectedSubmission.admission_year || "-"}</dd></div>
                      <div><dt>来源</dt><dd>{submissionSource(selectedSubmission)}</dd></div>
                      <div><dt>提交时间</dt><dd>{selectedSubmission.created_at || "-"}</dd></div>
                      <div><dt>PDF 链接</dt><dd>{selectedSubmission.pdf_url || "-"}</dd></div>
                      <div><dt>官网页面</dt><dd>{selectedSubmission.page_url || "-"}</dd></div>
                      <div><dt>备注</dt><dd>{selectedSubmission.notes || "-"}</dd></div>
                      <div><dt>下一步</dt><dd>{submissionHint(selectedSubmission)}</dd></div>
                    </dl>
                    <div className="settings-submission-detail-actions">
                      {["submitted", "needs_more_info", "failed"].includes(selectedSubmission.processing_status) ? (
                        <button className="btn btn-primary" type="button" disabled={workingSubmissionId === selectedSubmission.id} onClick={() => void handleStartSubmission(selectedSubmission.id)}>
                          开始整理
                        </button>
                      ) : null}
                      {selectedSubmission.processing_status === "needs_owner_review" ? (
                        <button className="btn btn-primary" type="button" onClick={() => openReviewForSubmission(selectedSubmission)}>
                          {reviewActionLabel}
                        </button>
                      ) : null}
                      <button className="btn btn-ghost" type="button" onClick={() => void load()}>
                        刷新
                      </button>
                    </div>
                  </aside>
                ) : null}
              </div>

              <div className="settings-action-strip">
                <button className="btn btn-ghost" type="button" onClick={() => void copyText(`${baseUrl}/documents/submissions`, "提交资料地址")}>
                  复制给对方的提交地址
                </button>
                <button className="btn btn-ghost" type="button" onClick={() => void copyText(`${baseUrl}/documents/submissions/{编号}`, "查询进度地址")}>
                  复制查询进度地址
                </button>
              </div>
              <div className="settings-mini-steps">
                <div><span>1</span><strong>对方提交资料</strong><p>PDF 文件、官网页面、PDF 链接都可以。</p></div>
                <div><span>2</span><strong>你安排整理</strong><p>点“开始整理”，资料会进入现有整理流程。</p></div>
                <div><span>3</span><strong>你再确认保存</strong><p>处理完后仍由后台确认正式资料。</p></div>
              </div>
            </section>
          ) : null}

          {section === "activity" ? (
            <section className="settings-panel">
              <p className="section-kicker">使用情况</p>
              <h3>看对方有没有真正用上</h3>
              <p className="settings-note">这里只看结果：成功、密码不对、需要检查。对方第一次使用后，会自动出现记录。</p>
              <div className="settings-usage-list">
                {recentUsage.slice(0, 8).map((item, index) => (
                  <div className="settings-usage-row settings-usage-readable" key={`${item.created_at}-${index}`}>
                    <div>
                      <strong>{usageTitle(item)}</strong>
                      <span>{item.created_at || "刚刚"}</span>
                    </div>
                    <em>{usageStatus(item.status_code)}</em>
                  </div>
                ))}
                {!recentUsage.length ? <p className="settings-empty">还没有使用记录。开通后，对方第一次使用会显示在这里。</p> : null}
              </div>
            </section>
          ) : null}

          {section === "handoff" ? (
            <section className="settings-panel">
              <div className="settings-section-head">
                <div>
                  <p className="section-kicker">发给对方</p>
                  <h3>复制一段话给负责人</h3>
                  <p>开通后点一下复制，发给合作方负责系统的人就行。</p>
                </div>
                <button
                  className="btn btn-primary"
                  type="button"
                  disabled={!canCopyGuide}
                  onClick={() => void copyText(guide, "说明")}
                >
                  {canCopyGuide ? "复制整段说明" : "先开通合作方"}
                </button>
              </div>
              {!canCopyGuide ? <p className="settings-soft-note">先开通合作方，页面才会生成可复制的完整说明。</p> : null}
              <div className="settings-ability-list">
                {visibleScopes(center?.allowed_scopes).map((scope) => (
                  <div className="settings-ability-row" key={scope}>
                    <span />
                    <strong>{abilityLabel(scope)}</strong>
                  </div>
                ))}
              </div>
              <details className="settings-advanced-panel">
                <summary>对方负责人要具体地址时，再打开这里</summary>
                <div className="settings-code-grid">
                  <div>
                    <span>打开地址</span>
                    <code>{baseUrl}</code>
                  </div>
                  <div>
                    <span>查看招生资料地址</span>
                    <code>{`${baseUrl}/programs`}</code>
                  </div>
                  <div>
                    <span>提交资料地址</span>
                    <code>{`${baseUrl}/documents/submissions`}</code>
                  </div>
                </div>
              </details>
            </section>
          ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}
