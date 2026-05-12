import { useEffect, useMemo, useState } from "react";
import { checkHealth } from "./api/client";
import RunPage from "./pages/RunPage";
import RecordsPage from "./pages/RecordsPage";
import ReviewPage from "./pages/ReviewPage";
import type { NavPage } from "./types";

const NAV: Array<{ key: NavPage; label: string; hint: string; short: string }> = [
  { key: "run", label: "导入", hint: "来源与处理", short: "01" },
  { key: "review", label: "人工复核", hint: "逐条校对", short: "02" },
  { key: "records", label: "记录", hint: "档案与导出", short: "03" },
];

function serviceText(backendOk: boolean | null) {
  if (backendOk === null) return "服务检查中";
  return backendOk ? "服务正常" : "服务异常";
}

export default function App() {
  const [page, setPage] = useState<NavPage>("run");
  const [activeDocId, setActiveDocId] = useState<number | null>(null);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  useEffect(() => {
    void checkHealth().then(setBackendOk);
  }, []);

  const activeItem = useMemo(() => NAV.find((item) => item.key === page) ?? NAV[0], [page]);

  return (
    <div className="app-shell app-shell-product">
      <aside className="sidebar product-sidebar">
        <div className="product-brand">
          <div className="brand-overline">本地工具</div>
          <h1 className="brand-title">日本大学募集要項抽取系统</h1>
          <p className="brand-subtitle">PDF 导入、人工复核、Excel 导出</p>
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
                  onClick={() => setPage(item.key)}
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

        <div className="sidebar-section sidebar-section-current">
          <div className="sidebar-section-label">当前工作</div>
          <div className="sidebar-card">
            <div className="sidebar-card-kicker">{activeItem.short}</div>
            <div className="sidebar-card-title">{activeItem.label}</div>
            <p className="sidebar-card-copy">{activeItem.hint}</p>
          </div>
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
            <div className="workspace-header-meta">中等宽度自动折叠</div>
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
          ) : (
            <RecordsPage />
          )}
        </main>
      </div>
    </div>
  );
}
