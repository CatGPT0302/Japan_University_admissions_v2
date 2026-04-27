import { useEffect, useMemo, useState } from "react";
import { getStaging, patchStaging, deleteStaging, confirmDoc, toErrorMessage } from "../api/client";
import type { StagingRecord } from "../types";

interface Props { onDone: () => void; }

const FIELDS = [
  { key:"university",          label:"大学",         span:1 },
  { key:"admission_year",      label:"年度",         span:1 },
  { key:"faculty",             label:"学部",         span:1 },
  { key:"department",          label:"学科",         span:1 },
  { key:"english_requirement", label:"英语要求",     span:2 },
  { key:"eju_japanese",        label:"EJU 日语",     span:1 },
  { key:"eju_math",            label:"EJU 数学",     span:1 },
  { key:"screening_method",    label:"选拔方式",     span:2 },
  { key:"application_period",  label:"出愿期间",     span:2 },
  { key:"result_date",         label:"合格发表日",   span:1 },
  { key:"campus",              label:"校区",         span:1 },
] as const;

function val(r: StagingRecord | undefined, k: string): string {
  if (!r) return "";
  return String((r as unknown as Record<string,unknown>)[k] ?? "");
}

function StatusBadge({ row }: { row: StagingRecord }) {
  const conf = Number(row.confidence ?? 0);
  if (Number(row.is_confirmed)) return <span style={{ fontSize:11, padding:"2px 9px", borderRadius:20, background:"#f0fdf4", color:"#166534", border:"1px solid #bbf7d0", fontWeight:500 }}>已确认</span>;
  if (Number(row.needs_review)) return <span style={{ fontSize:11, padding:"2px 9px", borderRadius:20, background:"#fffbeb", color:"#92400e", border:"1px solid #fde68a", fontWeight:500 }}>需复查</span>;
  if (conf > 0 && conf < 0.75)  return <span style={{ fontSize:11, padding:"2px 9px", borderRadius:20, background:"#fef2f2", color:"var(--red)", border:"1px solid #fecaca", fontWeight:500 }}>低置信度</span>;
  return <span style={{ fontSize:11, padding:"2px 9px", borderRadius:20, background:"var(--bg)", color:"var(--ink3)", border:"1px solid var(--border)", fontWeight:500 }}>待处理</span>;
}

export default function ReviewPage({ onDone }: Props) {
  const [docId,    setDocId]    = useState("");
  const [rows,     setRows]     = useState<StagingRecord[]>([]);
  const [idx,      setIdx]      = useState(0);
  const [draft,    setDraft]    = useState<Record<string,string>>({});
  const [loading,  setLoading]  = useState(false);
  const [saving,   setSaving]   = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [msg,      setMsg]      = useState("");
  const [err,      setErr]      = useState("");

  const row = rows[idx];

  useEffect(() => {
    if (!row) return;
    const d: Record<string,string> = {};
    FIELDS.forEach(f => { d[f.key] = val(row, f.key); });
    setDraft(d);
    setMsg(""); setErr("");
  }, [row?.id]);

  const stats = useMemo(() => ({
    total:     rows.length,
    confirmed: rows.filter(r => Number(r.is_confirmed)).length,
    review:    rows.filter(r => Number(r.needs_review)).length,
  }), [rows]);

  const progress = stats.total ? Math.round((stats.confirmed / stats.total) * 100) : 0;

  async function load() {
    const id = Number(docId);
    if (!id) return;
    setLoading(true); setErr(""); setMsg("");
    try {
      const data = await getStaging(id);
      setRows(data); setIdx(0);
      setMsg(data.length ? `加载了 ${data.length} 条` : "没有找到记录");
    } catch(e) { setErr(toErrorMessage(e)); }
    finally { setLoading(false); }
  }

  async function save(patch: Record<string,unknown>, label: string) {
    if (!row) return;
    setSaving(true); setErr(""); setMsg("");
    try {
      const updated = await patchStaging(row.id, patch);
      setRows(prev => prev.map(r => r.id === row.id ? {...r, ...updated, ...patch} : r));
      setMsg(label);
    } catch(e) { setErr(toErrorMessage(e)); }
    finally { setSaving(false); }
  }

  async function del() {
    if (!row || !confirm("确认删除这条记录？")) return;
    setSaving(true);
    try {
      await deleteStaging(row.id);
      const next = rows.filter(r => r.id !== row.id);
      setRows(next);
      setIdx(Math.min(idx, next.length - 1));
      setMsg("已删除");
    } catch(e) { setErr(toErrorMessage(e)); }
    finally { setSaving(false); }
  }

  async function confirmAll() {
    const id = Number(docId);
    if (!id) return;
    setConfirming(true); setErr(""); setMsg("");
    try {
      const res = await confirmDoc(id);
      setMsg(`确认完成：写入 ${res.confirmed} 条，跳过 ${res.skipped} 条`);
      setTimeout(onDone, 1500);
    } catch(e) { setErr(toErrorMessage(e)); }
    finally { setConfirming(false); }
  }

  function move(d: number) { setIdx(i => Math.min(Math.max(i+d, 0), rows.length-1)); setMsg(""); setErr(""); }

  return (
    <div style={{ maxWidth:960 }}>
      {/* Header */}
      <div style={{ marginBottom:28 }}>
        <div style={{ fontSize:10, letterSpacing:"0.2em", textTransform:"uppercase", color:"var(--red)", marginBottom:10, fontWeight:500 }}>Step 2</div>
        <div style={{ display:"flex", alignItems:"flex-end", justifyContent:"space-between", flexWrap:"wrap", gap:12 }}>
          <h1 style={{ fontFamily:"Georgia,serif", fontSize:34, fontStyle:"italic", fontWeight:400, letterSpacing:-0.5, lineHeight:1.1 }}>复查</h1>
          {rows.length > 0 && <span style={{ fontSize:13, color:"var(--ink3)" }}>第 {idx+1} / {rows.length} 条</span>}
        </div>
      </div>

      {/* Control bar */}
      <div style={{ background:"var(--surface)", border:"1px solid var(--border)", borderRadius:10, padding:"14px 16px", marginBottom:16, display:"flex", gap:10, alignItems:"center", flexWrap:"wrap" }}>
        <input value={docId} onChange={e=>setDocId(e.target.value)} onKeyDown={e=>e.key==="Enter"&&void load()}
          placeholder="文档 ID" style={{ height:36, width:110, padding:"0 12px", border:"1px solid var(--border)", borderRadius:8, fontSize:13, color:"var(--ink)", background:"var(--bg)", outline:"none" }}/>
        <button onClick={()=>void load()} disabled={loading} style={{ height:36, padding:"0 16px", background:"var(--ink)", color:"#fff", border:"none", borderRadius:8, fontSize:13, fontWeight:500, cursor:"pointer", fontFamily:"inherit" }}>
          {loading ? "加载中…" : "加载"}
        </button>
        <div style={{ width:1, height:20, background:"var(--border)" }}/>
        <button onClick={()=>move(-1)} disabled={!rows.length||idx===0} style={{ height:36, padding:"0 14px", background:"var(--surface)", border:"1px solid var(--border)", borderRadius:8, fontSize:13, cursor:"pointer", color:"var(--ink)", fontFamily:"inherit" }}>← 上一条</button>
        <button onClick={()=>move(1)}  disabled={!rows.length||idx>=rows.length-1} style={{ height:36, padding:"0 14px", background:"var(--surface)", border:"1px solid var(--border)", borderRadius:8, fontSize:13, cursor:"pointer", color:"var(--ink)", fontFamily:"inherit" }}>下一条 →</button>

        {rows.length > 0 && <>
          <div style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:10 }}>
            <div style={{ width:100, height:4, background:"var(--border)", borderRadius:4, overflow:"hidden" }}>
              <div style={{ width:`${progress}%`, height:"100%", background:"var(--green)", transition:"width 0.4s" }}/>
            </div>
            <span style={{ fontSize:11, color:"var(--ink3)", whiteSpace:"nowrap" }}>{progress}% 已确认</span>
          </div>
          <button onClick={()=>void confirmAll()} disabled={confirming}
            style={{ height:36, padding:"0 16px", background:"var(--green)", color:"#fff", border:"none", borderRadius:8, fontSize:13, fontWeight:500, cursor:"pointer", fontFamily:"inherit" }}>
            {confirming ? "写入中…" : "全部确认入库"}
          </button>
        </>}
      </div>

      {/* Stats */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:16 }}>
        {[
          { l:"总记录", v:stats.total,     c:"var(--ink)" },
          { l:"已确认", v:stats.confirmed, c:"var(--green)" },
          { l:"需复查", v:stats.review,    c:"var(--amber)" },
          { l:"当前", v: row ? <StatusBadge row={row}/> : "—", c:"var(--ink)" },
        ].map((c,i) => (
          <div key={i} style={{ background:"var(--surface)", border:"1px solid var(--border)", borderRadius:10, padding:"16px" }}>
            <div style={{ fontSize:10, color:"var(--ink3)", marginBottom:6 }}>{c.l}</div>
            <div style={{ fontFamily: i<3?"Georgia,serif":"inherit", fontSize:i<3?26:13, fontWeight:i<3?400:400, color:c.c, lineHeight:1 }}>{c.v}</div>
          </div>
        ))}
      </div>

      {msg && <div style={{ marginBottom:12, padding:"10px 16px", background:"var(--blue-soft)", border:"1px solid #bfdbfe", borderRadius:8, fontSize:13, color:"var(--blue)" }}>{msg}</div>}
      {err && <div style={{ marginBottom:12, padding:"10px 16px", background:"var(--red-soft)",  border:"1px solid #fecaca",  borderRadius:8, fontSize:13, color:"var(--red)"  }}>{err}</div>}

      {!row && !loading && (
        <div style={{ background:"var(--surface)", border:"1px solid var(--border)", borderRadius:10, padding:"32px 24px", fontSize:14, color:"var(--ink3)", textAlign:"center" }}>
          输入文档 ID 并点击「加载」开始复查
        </div>
      )}

      {row && (
        <div style={{ display:"grid", gridTemplateColumns:"1fr 240px", gap:16 }}>

          {/* Edit form */}
          <div style={{ background:"var(--surface)", border:"1px solid var(--border)", borderRadius:12, padding:"24px" }}>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:20 }}>
              <div>
                <div style={{ fontSize:14, fontWeight:500, marginBottom:2 }}>记录 #{row.id}</div>
                <div style={{ fontSize:11, color:"var(--ink3)" }}>
                  置信度：<span style={{ color: Number(row.confidence??0)>=0.85?"var(--green)":Number(row.confidence??0)>=0.7?"var(--amber)":"var(--red)", fontWeight:500 }}>
                    {Number(row.confidence??0).toFixed(2)}
                  </span>
                </div>
              </div>
              <StatusBadge row={row}/>
            </div>

            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"10px 14px", marginBottom:20 }}>
              {FIELDS.map(f => {
                const empty = !draft[f.key];
                const warn  = empty && (f.key === "english_requirement" || f.key === "faculty");
                return (
                  <label key={f.key} style={f.span===2?{gridColumn:"span 2"}:{}}>
                    <div style={{ fontSize:10, fontWeight:500, color: warn?"var(--red)":"var(--ink3)", marginBottom:4 }}>{f.label}{warn?" ⚠":""}</div>
                    <input value={draft[f.key]||""} onChange={e=>setDraft(p=>({...p,[f.key]:e.target.value}))}
                      style={{ width:"100%", height:36, padding:"0 12px",
                        border:`1px solid ${warn?"var(--red)":"var(--border)"}`,
                        borderRadius:8, fontSize:13, color:"var(--ink)",
                        background: warn?"var(--red-soft)":"var(--bg)", outline:"none" }}
                      onFocus={e=>{e.target.style.borderColor="var(--red)"; e.target.style.boxShadow="0 0 0 3px rgba(185,28,28,0.08)";}}
                      onBlur={e =>{e.target.style.borderColor=warn?"var(--red)":"var(--border)"; e.target.style.boxShadow="none";}}
                    />
                  </label>
                );
              })}
            </div>

            {/* Actions */}
            <div style={{ display:"flex", gap:8, paddingTop:16, borderTop:"1px solid var(--border)", flexWrap:"wrap" }}>
              <button onClick={()=>void save(draft,"已保存")} disabled={saving}
                style={{ height:36, padding:"0 16px", background:"var(--surface)", border:"1px solid var(--border)", borderRadius:8, fontSize:13, fontWeight:500, cursor:"pointer", fontFamily:"inherit", color:"var(--ink)" }}>
                保存
              </button>
              <button onClick={()=>void save({...draft,needs_review:1,is_confirmed:0},"已标记复查")} disabled={saving}
                style={{ height:36, padding:"0 16px", background:"transparent", border:"1px solid #fcd34d", borderRadius:8, fontSize:13, fontWeight:500, cursor:"pointer", fontFamily:"inherit", color:"var(--amber)" }}>
                标记复查
              </button>
              <button onClick={async()=>{ await save({...draft,needs_review:0,is_confirmed:1},"✓ 已确认"); if(idx<rows.length-1) move(1); }} disabled={saving}
                style={{ height:36, padding:"0 16px", background:"var(--green)", border:"none", borderRadius:8, fontSize:13, fontWeight:500, cursor:"pointer", fontFamily:"inherit", color:"#fff" }}>
                确认 →
              </button>
              <button onClick={()=>void del()} disabled={saving}
                style={{ height:36, padding:"0 14px", background:"transparent", border:"1px solid #fecaca", borderRadius:8, fontSize:13, cursor:"pointer", fontFamily:"inherit", color:"var(--red)", marginLeft:"auto" }}>
                删除
              </button>
            </div>
          </div>

          {/* Jump list */}
          <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
            <div style={{ background:"var(--surface)", border:"1px solid var(--border)", borderRadius:10, padding:"16px", flex:1, overflow:"hidden" }}>
              <div style={{ fontSize:10, fontWeight:500, color:"var(--ink3)", letterSpacing:"0.1em", textTransform:"uppercase", marginBottom:12 }}>快速跳转</div>
              <div style={{ display:"flex", flexDirection:"column", gap:3, maxHeight:400, overflowY:"auto" }}>
                {rows.map((r,i) => {
                  const isConf = Number(r.is_confirmed);
                  const isNR   = Number(r.needs_review);
                  const conf   = Number(r.confidence??0);
                  const dotColor = isConf?"#22c55e":isNR?"#f59e0b":conf<0.75?"var(--red)":"var(--border)";
                  return (
                    <button key={r.id} onClick={()=>{setIdx(i);setMsg("");setErr("");}}
                      style={{ textAlign:"left", padding:"7px 10px", borderRadius:6, fontSize:12, border:"none", cursor:"pointer", fontFamily:"inherit",
                        background: i===idx?"var(--ink)":"transparent",
                        color: i===idx?"#fff":"var(--ink2)",
                        display:"flex", alignItems:"center", gap:8 }}>
                      <span style={{ width:6, height:6, borderRadius:"50%", flexShrink:0, background:dotColor }}/>
                      <span style={{ overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{r.faculty||`#${r.id}`}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
