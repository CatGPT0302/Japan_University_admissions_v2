import { useState } from "react";
import RunPage    from "./pages/RunPage";
import ReviewPage from "./pages/ReviewPage";
import RecordsPage from "./pages/RecordsPage";
import type { NavPage } from "./types";

const NAV = [
  { key: "run"     as NavPage, label: "跑数据",  sub: "下载 · 抽取" },
  { key: "review"  as NavPage, label: "复查",    sub: "校对 · 入库" },
  { key: "records" as NavPage, label: "记录",    sub: "查询 · 导出" },
];

export default function App() {
  const [page, setPage] = useState<NavPage>("run");

  const content = page === "run" ? <RunPage onDone={() => setPage("review")} />
                : page === "review" ? <ReviewPage onDone={() => setPage("records")} />
                : <RecordsPage />;

  return (
    <div style={{ display:"flex", minHeight:"100vh", background:"var(--bg)", color:"var(--ink)", fontFamily:"'DM Sans',sans-serif", fontSize:14 }}>

      {/* Sidebar */}
      <aside style={{ width:200, background:"var(--surface)", borderRight:"1px solid var(--border)", display:"flex", flexDirection:"column", flexShrink:0 }}>
        {/* Logo */}
        <div style={{ padding:"28px 22px 24px", borderBottom:"1px solid var(--border)" }}>
          <div style={{ fontFamily:"Georgia,serif", fontSize:18, lineHeight:1.15, letterSpacing:-0.3 }}>
            留学生<br/><em style={{ color:"var(--red)", fontStyle:"italic" }}>招生系统</em>
          </div>
          <div style={{ marginTop:8, fontSize:10, letterSpacing:"0.14em", color:"var(--ink3)", textTransform:"uppercase" }}>admissions_v2</div>
        </div>

        {/* Nav */}
        <nav style={{ padding:"16px 10px", flex:1 }}>
          {NAV.map((item, i) => {
            const active = page === item.key;
            return (
              <button key={item.key} onClick={() => setPage(item.key)} style={{
                display:"block", width:"100%", textAlign:"left",
                padding:"10px 13px", marginBottom:4,
                borderRadius:8, border:"none", cursor:"pointer", fontFamily:"inherit",
                background: active ? "var(--ink)" : "transparent",
                color: active ? "#fff" : "var(--ink2)",
                transition:"background 0.15s, color 0.15s",
              }}>
                <div style={{ display:"flex", alignItems:"center", gap:10 }}>
                  <span style={{ width:20, height:20, borderRadius:6, background: active ? "rgba(255,255,255,0.15)" : "var(--border)", display:"flex", alignItems:"center", justifyContent:"center", fontSize:11, fontWeight:600, flexShrink:0 }}>{i+1}</span>
                  <div>
                    <div style={{ fontSize:13, fontWeight: active ? 500 : 400, lineHeight:1.2 }}>{item.label}</div>
                    <div style={{ fontSize:10, opacity:0.55, letterSpacing:"0.04em" }}>{item.sub}</div>
                  </div>
                </div>
              </button>
            );
          })}
        </nav>

        {/* Status */}
        <div style={{ padding:"16px 22px", borderTop:"1px solid var(--border)" }}>
          <div style={{ fontSize:11, color:"var(--ink3)", display:"flex", alignItems:"center", gap:6 }}>
            <span style={{ width:6, height:6, borderRadius:"50%", background:"#22c55e", flexShrink:0 }}/>
            后端已连接
          </div>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex:1, padding:"40px 48px", overflowY:"auto", minWidth:0 }}>
        {content}
      </main>
    </div>
  );
}
