import { useEffect, useMemo, useState } from "react";
import { checkHealth } from "./api/client";
import RunPage from "./pages/RunPage";
import RecordsPage from "./pages/RecordsPage";
import ReviewPage from "./pages/ReviewPage";
import SettingsPage from "./pages/SettingsPage";
import StudentApp from "./pages/StudentApp";
import type { NavPage } from "./types";

const NAV: Array<{ key: NavPage; label: string; hint: string; short: string }> = [
  { key: "run", label: "上传整理", hint: "提交招生资料，生成待核对内容", short: "01" },
  { key: "review", label: "人工核对", hint: "修正不确定内容，确认后保存", short: "02" },
  { key: "records", label: "正式资料", hint: "查看已确认资料，按需导出 Excel", short: "03" },
  { key: "settings", label: "设置", hint: "合作方与资料", short: "04" },
];

function serviceText(backendOk: boolean | null) {
  if (backendOk === null) return "服务检查中";
  return backendOk ? "服务正常" : "服务异常";
}

function pageFromHash(): NavPage {
  const value = window.location.hash.replace(/^#\/?/, "");
  return NAV.some((item) => item.key === value) ? (value as NavPage) : "run";
}

export default function App() {
  const [page, setPage] = useState<NavPage>(() => pageFromHash());
  const [activeDocId, setActiveDocId] = useState<number | null>(null);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);
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
  }, []);

  const activeItem = useMemo(() => NAV.find((item) => item.key === page) ?? NAV[0], [page]);

  if (isStudentApp) return <StudentApp />;
  if (isSettingsApp) return <SettingsPage />;

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
                    if (item.key === "settings") {
                      window.location.hash = "#/settings";
                      return;
                    }
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
            <SettingsPage />
          )}
        </main>
      </div>
    </div>
  );
}
