import { FormEvent, useEffect, useMemo, useState } from "react";
import { checkHealth, getCurrentUser, login, logout, toErrorMessage } from "./api/client";
import OwnerPartnersPage from "./pages/OwnerPartnersPage";
import RunPage from "./pages/RunPage";
import RecordsPage from "./pages/RecordsPage";
import ReviewPage from "./pages/ReviewPage";
import SettingsPage from "./pages/SettingsPage";
import StudentApp from "./pages/StudentApp";
import type { AppRole, AppUser, OwnerPage } from "./types";

const NAV: Array<{ key: OwnerPage; label: string; hint: string; short: string }> = [
  { key: "run", label: "上传整理", hint: "提交招生资料，生成待核对内容", short: "01" },
  { key: "review", label: "人工核对", hint: "修正不确定内容，确认后保存", short: "02" },
  { key: "records", label: "正式资料", hint: "查看已确认资料，按需导出 Excel", short: "03" },
  { key: "partners", label: "合作私塾", hint: "开通使用权，处理对方提交的资料", short: "04" },
];

function serviceText(backendOk: boolean | null) {
  if (backendOk === null) return "正在连接";
  return backendOk ? "可以使用" : "暂时连不上";
}

function pageFromHash(): OwnerPage {
  const value = window.location.hash.replace(/^#\/?/, "");
  return NAV.some((item) => item.key === value) ? (value as OwnerPage) : "run";
}

function roleHome(role?: AppRole) {
  return role === "partner_staff" ? "#/settings" : "#/";
}

function LoginScreen({ expectedRole, onSignedIn }: { expectedRole?: AppRole; onSignedIn: (user: AppUser) => void }) {
  const [email, setEmail] = useState(expectedRole === "partner_staff" ? "partner@example.com" : "owner@example.com");
  const [password, setPassword] = useState(expectedRole === "partner_staff" ? "partner-demo" : "owner-admin");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const user = await login(email, password);
      onSignedIn(user);
      window.location.hash = roleHome(user.role);
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={(event) => void submit(event)}>
        <p className="section-kicker">{expectedRole === "partner_staff" ? "私塾后台" : "Owner 工作台"}</p>
        <h1>{expectedRole === "partner_staff" ? "登录服务中心" : "登录资料中心"}</h1>
        <p>{expectedRole === "partner_staff" ? "提交资料、查看整理进度。" : "上传、整理、核对和维护正式资料。"}</p>
        <label className="field-wrap">
          <span className="field-label">邮箱</span>
          <input className="field" value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label className="field-wrap">
          <span className="field-label">密码</span>
          <input className="field" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        {error ? <div className="message-box error">{error}</div> : null}
        <button className="btn btn-primary" disabled={busy} type="submit">
          {busy ? "正在登录" : "登录"}
        </button>
      </form>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<OwnerPage>(() => pageFromHash());
  const [activeDocId, setActiveDocId] = useState<number | null>(null);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
  const [user, setUser] = useState<AppUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const publicStudentOnly = import.meta.env.VITE_PUBLIC_STUDENT_ONLY === "true";
  const [isStudentApp, setIsStudentApp] = useState(() => publicStudentOnly || window.location.hash.startsWith("#/student"));
  const [isSettingsApp, setIsSettingsApp] = useState(() => window.location.hash.startsWith("#/settings"));

  useEffect(() => {
    const syncRoute = () => {
      const studentRoute = publicStudentOnly || window.location.hash.startsWith("#/student");
      const settingsRoute = !studentRoute && window.location.hash.startsWith("#/settings");
      setIsStudentApp(studentRoute);
      setIsSettingsApp(settingsRoute);
      if (!studentRoute && !settingsRoute) setPage(pageFromHash());
    };
    window.addEventListener("hashchange", syncRoute);
    return () => window.removeEventListener("hashchange", syncRoute);
  }, [publicStudentOnly]);

  useEffect(() => {
    void checkHealth().then(setBackendOk);
    void getCurrentUser()
      .then(setUser)
      .finally(() => setAuthChecked(true));
  }, []);

  const activeItem = useMemo(() => NAV.find((item) => item.key === page) ?? NAV[0], [page]);

  if (isStudentApp) return <StudentApp />;
  if (!authChecked) {
    return (
      <div className="login-shell">
        <div className="login-card">
          <p className="section-kicker">正在打开</p>
          <h1>请稍等</h1>
        </div>
      </div>
    );
  }
  if (isSettingsApp) {
    if (!user) return <LoginScreen expectedRole="partner_staff" onSignedIn={setUser} />;
    if (user.role !== "partner_staff") return <LoginScreen expectedRole="partner_staff" onSignedIn={setUser} />;
    return <SettingsPage />;
  }
  if (!user) return <LoginScreen expectedRole="owner_admin" onSignedIn={setUser} />;
  if (user.role !== "owner_admin") return <LoginScreen expectedRole="owner_admin" onSignedIn={setUser} />;

  return (
    <div className="app-shell app-shell-product">
      <aside className="sidebar product-sidebar">
        <div className="product-brand">
          <div className="brand-overline">本地工作台</div>
          <h1 className="brand-title">招生资料中心</h1>
          <p className="brand-subtitle">整理 PDF，核对内容，维护招生资料。</p>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-label">工作区</div>
          <nav className="product-nav" aria-label="主导航">
            {NAV.map((item) => {
              const active = item.key === page;
              return (
                <button
                  key={item.key}
                  className={`workspace-tab${active ? " is-active" : ""}`}
                  onClick={() => {
                    window.location.hash = item.key === "run" ? "#/" : `#/${item.key}`;
                    setPage(item.key);
                  }}
                  type="button"
                >
                  <span className="workspace-tab-icon" aria-hidden="true">
                    {item.short}
                  </span>
                  <span className="workspace-tab-copy">
                    <span className="workspace-tab-label">{item.label}</span>
                    <span className="workspace-tab-hint">{item.hint}</span>
                  </span>
                </button>
              );
            })}
          </nav>
        </div>

        <div className="product-sidebar-footer">
          <div className={`connection-pill${backendOk === false ? " is-down" : ""}`}>
            <span className="connection-dot" />
            {serviceText(backendOk)}
          </div>
        </div>
      </aside>

      <div className="workspace workspace-product">
        <header className="workspace-header">
          <div className="workspace-heading">
            <div className="workspace-header-label">当前位置</div>
            <div className="workspace-header-title">{activeItem.label}</div>
            <p className="workspace-header-copy">{activeItem.hint}</p>
          </div>
          <div className="workspace-header-side">
            <div className={`connection-pill workspace-connection${backendOk === false ? " is-down" : ""}`}>
              <span className="connection-dot" />
              {serviceText(backendOk)}
            </div>
            <button
              className="btn btn-ghost btn-small"
              type="button"
              onClick={() => {
                void logout().then(() => setUser(null));
              }}
            >
              退出
            </button>
          </div>
        </header>

        <main className="workspace-body workspace-body-product">
          {page === "run" ? (
            <RunPage
              onDone={(docId) => {
                setActiveDocId(docId);
                setPage("review");
              }}
            />
          ) : page === "review" ? (
            <ReviewPage
              defaultDocId={activeDocId}
              onDone={() => {
                setActiveDocId(null);
                setPage("records");
              }}
            />
          ) : page === "records" ? (
            <RecordsPage />
          ) : (
            <OwnerPartnersPage />
          )}
        </main>
      </div>
    </div>
  );
}
