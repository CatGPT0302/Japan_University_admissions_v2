import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  API_BASE_URL,
  createPartnerSubmission,
  getApiCenter,
  getPartnerSubmissions,
  toErrorMessage,
} from "../api/client";
import type { AdminSubmission, ApiCenterResponse, ApiUsageLog } from "../types";

type PartnerSection = "submit" | "progress" | "services" | "account";

const SECTIONS: Array<{ key: PartnerSection; label: string; hint: string }> = [
  { key: "submit", label: "提交资料", hint: "把学校资料交过来" },
  { key: "progress", label: "整理进度", hint: "看资料到哪一步了" },
  { key: "services", label: "可用服务", hint: "能帮你做什么" },
  { key: "account", label: "账号信息", hint: "联系方式与接入" },
];

const SERVICE_LABELS: Record<string, string> = {
  "programs:read": "查询已整理好的招生要求",
  "recommendations:create": "按学生情况辅助筛选学校",
  "bookings:create": "提交学生咨询预约",
  "documents:submit": "提交新的招生资料",
  "documents:read_status": "查看资料整理进度",
};

function serviceLabel(scope: string): string {
  return SERVICE_LABELS[scope] || "其他可用服务";
}

function statusText(status?: string): string {
  if (status === "submitted") return "已收到";
  if (status === "processing") return "整理中";
  if (status === "needs_owner_review") return "整理完成，等待确认";
  if (status === "confirmed") return "可以使用";
  if (status === "needs_more_info") return "需要补充资料";
  if (status === "failed") return "需要重新提交";
  return "等待处理";
}

function statusHint(status?: string): string {
  if (status === "submitted") return "资料已经收到，会安排整理。";
  if (status === "processing") return "正在整理，请稍后再看。";
  if (status === "needs_owner_review") return "内容已经整理出来，正在做最后确认。";
  if (status === "confirmed") return "资料已经整理好，可以用于查询和咨询。";
  if (status === "needs_more_info") return "请补一个更完整的 PDF 或官网页面。";
  if (status === "failed") return "这次没有整理成功，可以重新提交资料。";
  return "我们会根据资料状态继续处理。";
}

function usageText(item: ApiUsageLog): string {
  if (item.scope) return serviceLabel(item.scope);
  if (item.path.includes("documents")) return "查看或提交资料";
  if (item.path.includes("programs")) return "查看招生要求";
  if (item.path.includes("bookings")) return "提交咨询预约";
  return "一次使用";
}

export default function SettingsPage() {
  const [section, setSection] = useState<PartnerSection>("submit");
  const [center, setCenter] = useState<ApiCenterResponse | null>(null);
  const [submissions, setSubmissions] = useState<AdminSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({
    university: "",
    admission_year: "2027",
    pdf_url: "",
    page_url: "",
    notes: "",
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const baseUrl = useMemo(() => `${API_BASE_URL}/v1`, []);
  const usageSummary = center?.usage_summary;
  const waitingCount = submissions.filter((item) => ["submitted", "needs_more_info", "failed"].includes(item.processing_status)).length;
  const inProgressCount = submissions.filter((item) => ["processing", "needs_owner_review"].includes(item.processing_status)).length;

  async function load() {
    setLoading(true);
    setMessage("");
    try {
      const [nextCenter, nextSubmissions] = await Promise.all([
        getApiCenter(),
        getPartnerSubmissions({ limit: 30 }),
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

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    try {
      await createPartnerSubmission({ ...form, file: selectedFile });
      setForm({ university: "", admission_year: form.admission_year, pdf_url: "", page_url: "", notes: "" });
      setSelectedFile(null);
      setSection("progress");
      await load();
      setMessage("资料已提交。你可以在整理进度里查看后续状态。");
    } catch (error) {
      setMessage(toErrorMessage(error));
    }
  }

  return (
    <div className="settings-shell-ios settings-page partner-console">
      <header className="settings-topbar partner-topbar">
        <a className="settings-brand" href="#/settings" aria-label="合作方服务中心">
          <span>
            <strong>服务中心</strong>
            <small>{center?.organization.name || "资料提交入口"}</small>
          </span>
        </a>
      </header>

      <main className="settings-main partner-main">
        <section className="settings-hero settings-dashboard-hero partner-hero">
          <div>
            <p className="section-kicker">合作方入口</p>
            <h2>提交资料，看整理进度</h2>
            <p>这里是给合作方使用的入口。你可以提交招生资料、查看整理进度，也可以把接入信息交给负责系统的人。</p>
          </div>
          <div className="settings-status-card is-ready">
            <span>当前资料</span>
            <strong>{submissions.length ? `${submissions.length} 份` : "暂无提交"}</strong>
            <small>{loading ? "正在刷新" : "可以使用"}</small>
          </div>
        </section>

        <section className="settings-summary-grid partner-summary-grid" aria-label="服务概览">
          <div className="settings-summary-card">
            <span>等待整理</span>
            <strong>{waitingCount}</strong>
            <small>需要我们处理的资料</small>
          </div>
          <div className="settings-summary-card">
            <span>正在确认</span>
            <strong>{inProgressCount}</strong>
            <small>整理中或等最后确认</small>
          </div>
          <div className="settings-summary-card">
            <span>服务使用</span>
            <strong>{usageSummary?.total ?? 0}</strong>
            <small>{usageSummary?.needs_check ? `${usageSummary.needs_check} 次需要检查` : "最近使用正常"}</small>
          </div>
        </section>

        {message ? <div className="message-box info">{message}</div> : null}

        <div className="settings-layout-panel partner-layout-panel">
          <nav className="settings-section-nav partner-section-nav" aria-label="服务中心菜单">
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
            {section === "submit" ? (
              <section className="settings-panel partner-panel">
                <p className="section-kicker">提交资料</p>
                <h3>把学校的招生资料交过来</h3>
                <p className="settings-note">填学校名称，上传 PDF 或贴官网链接。资料会先整理，确认后才会进入可查询内容。</p>
                <form className="partner-submit-form" onSubmit={(event) => void submit(event)}>
                  <label className="field-wrap">
                    <span className="field-label">学校名称</span>
                    <input
                      className="field"
                      value={form.university}
                      onChange={(event) => setForm({ ...form, university: event.target.value })}
                      placeholder="例如：明治大学"
                    />
                  </label>
                  <label className="field-wrap">
                    <span className="field-label">入学年度</span>
                    <input
                      className="field"
                      value={form.admission_year}
                      onChange={(event) => setForm({ ...form, admission_year: event.target.value })}
                      placeholder="2027"
                    />
                  </label>
                  <label className="field-wrap">
                    <span className="field-label">本地 PDF</span>
                    <input
                      className="field"
                      type="file"
                      accept="application/pdf,.pdf"
                      onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
                    />
                  </label>
                  <div className="partner-upload-note">
                    <strong>{selectedFile ? selectedFile.name : "可以直接上传学校 PDF"}</strong>
                    <span>{selectedFile ? "提交后会进入整理队列。" : "没有 PDF 文件时，也可以只填写下面的官网页面。"}</span>
                  </div>
                  <label className="field-wrap">
                    <span className="field-label">PDF 地址</span>
                    <input
                      className="field"
                      value={form.pdf_url}
                      onChange={(event) => setForm({ ...form, pdf_url: event.target.value })}
                      placeholder="https://..."
                    />
                  </label>
                  <label className="field-wrap">
                    <span className="field-label">官网页面</span>
                    <input
                      className="field"
                      value={form.page_url}
                      onChange={(event) => setForm({ ...form, page_url: event.target.value })}
                      placeholder="https://..."
                    />
                  </label>
                  <label className="field-wrap partner-wide">
                    <span className="field-label">补充说明</span>
                    <textarea
                      className="field"
                      value={form.notes}
                      onChange={(event) => setForm({ ...form, notes: event.target.value })}
                      placeholder="例如：这是外国人留学生入试页面"
                    />
                  </label>
                  <button className="btn btn-primary" type="submit">
                    提交资料
                  </button>
                </form>
              </section>
            ) : null}

            {section === "progress" ? (
              <section className="settings-panel partner-panel">
                <div className="settings-section-head">
                  <div>
                    <p className="section-kicker">整理进度</p>
                    <h3>你提交过的资料</h3>
                    <p>每份资料都会显示现在到哪一步了。需要补充时，重新提交更完整的链接即可。</p>
                  </div>
                  <button className="btn btn-ghost" type="button" onClick={() => void load()}>
                    刷新
                  </button>
                </div>
                <div className="settings-submission-list">
                  {submissions.map((item) => (
                    <article className="settings-submission-card partner-submission-card" key={item.id}>
                      <div className="settings-submission-main">
                        <span className={`settings-submission-status is-${item.processing_status}`}>
                          {statusText(item.processing_status)}
                        </span>
                        <strong>{item.university || "未填写学校"}</strong>
                        <p>{item.admission_year || "年度未填写"} · {item.original_file_name || item.file_name || item.pdf_url || item.page_url || "资料链接"}</p>
                        {item.notes ? <small>{item.notes}</small> : null}
                        <em>{statusHint(item.processing_status)}</em>
                      </div>
                    </article>
                  ))}
                  {!submissions.length ? <p className="settings-empty">还没有提交过资料。</p> : null}
                </div>
              </section>
            ) : null}

            {section === "services" ? (
              <section className="settings-panel partner-panel">
                <p className="section-kicker">可用服务</p>
                <h3>这套服务能帮你做什么</h3>
                <div className="settings-ability-list partner-service-list">
                  {(center?.allowed_scopes || []).map((scope) => (
                    <div className="settings-ability-row" key={scope}>
                      <span />
                      <strong>{serviceLabel(scope)}</strong>
                    </div>
                  ))}
                </div>
                <details className="settings-advanced-panel">
                  <summary>给技术负责人看的接入信息</summary>
                  <div className="settings-code-grid">
                    <div>
                      <span>打开地址</span>
                      <code>{baseUrl}</code>
                    </div>
                    <div>
                      <span>查询招生要求</span>
                      <code>{`${baseUrl}/programs`}</code>
                    </div>
                    <div>
                      <span>提交资料</span>
                      <code>{`${baseUrl}/documents/submissions`}</code>
                    </div>
                  </div>
                </details>
              </section>
            ) : null}

            {section === "account" ? (
              <section className="settings-panel partner-panel">
                <p className="section-kicker">账号信息</p>
                <h3>{center?.organization.name || "合作方"}</h3>
                <div className="settings-info-list">
                  <div className="settings-copy-row">
                    <span>服务状态</span>
                    <strong>{center?.organization.status === "active" ? "可以使用" : "暂不可用"}</strong>
                  </div>
                  <div className="settings-copy-row">
                    <span>最近使用</span>
                    <strong>{center?.recent_usage?.[0]?.created_at || "暂无记录"}</strong>
                  </div>
                  <div className="settings-copy-row">
                    <span>成功使用</span>
                    <strong>{usageSummary?.success ?? 0} 次</strong>
                  </div>
                </div>
                <div className="settings-usage-list">
                  {(center?.recent_usage || []).slice(0, 5).map((item, index) => (
                    <div className="settings-usage-row settings-usage-readable" key={`${item.created_at}-${index}`}>
                      <div>
                        <strong>{usageText(item)}</strong>
                        <span>{item.created_at || "刚刚"}</span>
                      </div>
                      <em>{item.status_code >= 200 && item.status_code < 300 ? "成功" : "需要检查"}</em>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}
