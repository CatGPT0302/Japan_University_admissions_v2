import { useEffect, useState } from "react";
import { getRecords, getStats, downloadExcel, toErrorMessage } from "../api/client";
import type { ConfirmedRecord, StatsResponse } from "../types";

const COLS: Array<{ key: keyof ConfirmedRecord; label: string; w?: number }> = [
  { key:"university",          label:"大学",       w:140 },
  { key:"faculty",             label:"学部",       w:120 },
  { key:"department",          label:"学科",       w:130 },
  { key:"admission_year",      label:"年度",       w:60  },
  { key:"application_period",  label:"出愿期间",   w:160 },
  { key:"deadline_rule",       label:"必着/消印",  w:90  },
  { key:"eju_session",         label:"EJU实施回",  w:90  },
  { key:"eju_japanese",        label:"EJU日本语",  w:90  },
  { key:"english_requirement", label:"英语要求",   w:160 },
  { key:"screening_method",    label:"选拔方式",   w:120 },
  { key:"result_date",         label:"结果日期",   w:100 },
];

export default function RecordsPage() {
  const [rows,    setRows]    = useState<ConfirmedRecord[]>([]);
  const [stats,   setStats]   = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err,     setErr]     = useState("");
  const [univ,    setUniv]    = useState("");
  const [fac,     setFac]     = useState("");
  const [yr,      setYr]      = useState("");

  async function load() {
    setLoading(true); setErr("");
    try {
      const data = await getRecords({ university:univ||undefined, faculty:fac||undefined, year:yr?Number(yr):undefined, limit:1000 });
      setRows(data);
    } catch(e) { setErr(toErrorMessage(e)); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    void load();
    void getStats().then(setStats).catch(()=>setStats(null));
  }, []);

  return (
    <div style={{ maxWidth:1100 }}>
      {/* Header */}
      <div style={{ marginBottom:28 }}>
        <div style={{ fontSize:10, letterSpacing:"0.2em", textTransform:"uppercase", color:"var(--red)", marginBottom:10, fontWeight:500 }}>Step 3</div>
        <div style={{ display:"flex", alignItems:"flex-end", justifyContent:"space-between", flexWrap:"wrap", gap:12 }}>
          <h1 style={{ fontFamily:"Georgia,serif", fontSize:34, fontStyle:"italic", fontWeight:400, letterSpacing:-0.5, lineHeight:1.1 }}>记录</h1>
          <button onClick={()=>downloadExcel({university:univ||undefined,year:yr?Number(yr):undefined,faculty:fac||undefined})}
            style={{ height:38, padding:"0 18px", background:"var(--ink)", color:"#fff", border:"none", borderRadius:8, fontSize:13, fontWeight:500, cursor:"pointer", fontFamily:"inherit" }}>
            导出 Excel
          </button>
        </div>
      </div>

      {/* Stats */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:12, marginBottom:20 }}>
        {[
          { l:"覆盖大学",   v: stats?.universities   ?? "—" },
          { l:"已确认总数", v: stats?.total_records   ?? "—" },
          { l:"平均置信度", v: stats ? stats.avg_confidence.toFixed(2) : "—" },
        ].map(c => (
          <div key={c.l} style={{ background:"var(--surface)", border:"1px solid var(--border)", borderRadius:10, padding:"20px" }}>
            <div style={{ fontSize:10, color:"var(--ink3)", marginBottom:6 }}>{c.l}</div>
            <div style={{ fontFamily:"Georgia,serif", fontSize:30, fontWeight:400, color:"var(--ink)", lineHeight:1 }}>{c.v}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ background:"var(--surface)", border:"1px solid var(--border)", borderRadius:10, padding:"14px 16px", marginBottom:16, display:"flex", gap:10, flexWrap:"wrap", alignItems:"center" }}>
        {[
          { val:univ, set:setUniv, ph:"大学",   w:140 },
          { val:fac,  set:setFac,  ph:"学部",   w:130 },
          { val:yr,   set:setYr,   ph:"年度",   w:90  },
        ].map(f => (
          <input key={f.ph} value={f.val} onChange={e=>f.set(e.target.value)} onKeyDown={e=>e.key==="Enter"&&void load()}
            placeholder={f.ph} style={{ height:36, width:f.w, padding:"0 12px", border:"1px solid var(--border)", borderRadius:8, fontSize:13, color:"var(--ink)", background:"var(--bg)", outline:"none" }}/>
        ))}
        <button onClick={()=>void load()} style={{ height:36, padding:"0 16px", background:"var(--ink)", color:"#fff", border:"none", borderRadius:8, fontSize:13, fontWeight:500, cursor:"pointer", fontFamily:"inherit" }}>
          搜索
        </button>
        <span style={{ fontSize:12, color:"var(--ink3)", marginLeft:4 }}>{loading ? "加载中…" : `${rows.length} 条`}</span>
      </div>

      {err && <div style={{ marginBottom:16, padding:"10px 16px", background:"var(--red-soft)", border:"1px solid #fecaca", borderRadius:8, fontSize:13, color:"var(--red)" }}>{err}</div>}

      {/* Table */}
      {rows.length === 0 && !loading ? (
        <div style={{ background:"var(--surface)", border:"1px solid var(--border)", borderRadius:10, padding:"32px", fontSize:14, color:"var(--ink3)", textAlign:"center" }}>
          暂无已确认记录
        </div>
      ) : (
        <div style={{ overflowX:"auto", background:"var(--surface)", border:"1px solid var(--border)", borderRadius:10 }}>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
            <thead>
              <tr style={{ background:"var(--bg)", borderBottom:"1px solid var(--border)" }}>
                {COLS.map(c => (
                  <th key={c.key} style={{ padding:"10px 14px", textAlign:"left", fontSize:10, fontWeight:500, letterSpacing:"0.08em", textTransform:"uppercase", color:"var(--ink3)", whiteSpace:"nowrap", width:c.w }}>
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.id} style={{ borderBottom:"1px solid var(--border)", background: i%2===0?"var(--surface)":"var(--bg)" }}
                  onMouseEnter={e=>(e.currentTarget.style.background="var(--bg)")}
                  onMouseLeave={e=>(e.currentTarget.style.background=i%2===0?"var(--surface)":"var(--bg)")}>
                  {COLS.map(c => (
                    <td key={c.key} style={{ padding:"10px 14px", color: c.key==="university"?"var(--ink)":"var(--ink2)", maxWidth:c.w, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}
                      title={String(r[c.key]??"")}
                    >
                      {r[c.key] || <span style={{ color:"var(--ink3)" }}>—</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
