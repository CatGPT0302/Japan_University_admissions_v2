import { useEffect, useMemo, useState } from "react";
import { checkHealth } from "./api/client";
import RunPage from "./pages/RunPage";
import RecordsPage from "./pages/RecordsPage";
import ReviewPage from "./pages/ReviewPage";
import type { NavPage } from "./types";

const NAV: Array<{
  key: NavPage;
  label: string;
  caption: string;
  short: string;
}> = [
  { key: "run", label: "Run Intake", caption: "Collect and extract source PDFs", short: "Run" },
  { key: "review", label: "Review Queue", caption: "Resolve risk before confirmation", short: "Review" },
  { key: "records", label: "Records Hub", caption: "Search, audit, and export confirmed data", short: "Records" },
];

export default function App() {
  const [page, setPage] = useState<NavPage>("run");
  const [activeDocId, setActiveDocId] = useState<number | null>(null);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  useEffect(() => {
    void checkHealth().then(setBackendOk);
  }, []);

  const activeNav = useMemo(
    () => NAV.find((item) => item.key === page) ?? NAV[0],
    [page],
  );

  const content =
    page === "run" ? (
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
    );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-panel">
          <div className="brand-mark">A2</div>
          <div>
            <div className="brand-overline">Admissions_v2</div>
            <h1 className="brand-title">Admissions Ops</h1>
            <p className="brand-subtitle">Internal review workspace for intake, validation, and records quality.</p>
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-label">Workflow</div>
          <nav className="sidebar-nav" aria-label="Primary">
            {NAV.map((item, index) => {
              const active = page === item.key;
              return (
                <button
                  key={item.key}
                  className={`nav-card${active ? " is-active" : ""}`}
                  onClick={() => setPage(item.key)}
                  type="button"
                >
                  <span className="nav-index">{index + 1}</span>
                  <span className="nav-copy">
                    <span className="nav-label">{item.label}</span>
                    <span className="nav-caption">{item.caption}</span>
                  </span>
                </button>
              );
            })}
          </nav>
        </div>

        <div className="workflow-rail">
          {NAV.map((item, index) => {
            const active = item.key === page;
            const completed = NAV.findIndex((nav) => nav.key === page) > index;
            return (
              <div key={item.key} className={`workflow-step${active ? " is-active" : ""}${completed ? " is-complete" : ""}`}>
                <div className="workflow-dot">{index + 1}</div>
                <div>
                  <div className="workflow-label">{item.short}</div>
                  <div className="workflow-meta">{completed ? "Complete" : active ? "Current" : "Pending"}</div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="sidebar-footer">
          <div className={`health-pill${backendOk === false ? " is-down" : ""}`}>
            <span className="health-dot" />
            {backendOk === null ? "Checking backend" : backendOk ? "Backend connected" : "Backend unavailable"}
          </div>
          <div className="sidebar-footnote">
            Current view
            <strong>{activeNav.label}</strong>
          </div>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <div className="topbar-overline">Professional review dashboard</div>
            <div className="topbar-title">{activeNav.label}</div>
          </div>
          <div className="topbar-badges">
            <span className="badge badge-gray">Run → Review → Records</span>
            <span className={`badge ${backendOk === false ? "badge-red" : "badge-green"}`}>
              {backendOk === false ? "System attention" : "System ready"}
            </span>
          </div>
        </header>

        <main className="workspace-body">{content}</main>
      </div>
    </div>
  );
}
