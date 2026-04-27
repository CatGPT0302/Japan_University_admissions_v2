import { useEffect, useState } from "react";
import { getStats, toErrorMessage } from "../api/client";
import type { StatsResponse } from "../types";

export default function DashboardPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getStats().then(d => { if (active) setStats(d); }).catch(e => { if (active) setError(toErrorMessage(e)); });
    return () => { active = false; };
  }, []);

  const statCards = [
    { label: "已确认记录", value: stats?.total_records ?? "—", accent: 'var(--red)' },
    { label: "覆盖大学数", value: stats?.universities ?? "—", accent: 'var(--gold)' },
    { label: "平均置信度", value: stats ? stats.avg_confidence.toFixed(2) : "—", accent: 'var(--green)' },
  ];

  return (
    <div style={{maxWidth: 860}}>
      {/* Header */}
      <div style={{marginBottom: 36}}>
        <div style={{fontSize:11, letterSpacing:'0.18em', textTransform:'uppercase', color:'var(--red)', marginBottom:10, fontWeight:500}}>
          Dashboard
        </div>
        <h1 style={{fontFamily:"'Playfair Display', Georgia, serif", fontSize:38, fontWeight:700, lineHeight:1.1, letterSpacing:'-0.5px', color:'var(--ink)', marginBottom:12}}>
          招生信息<br/><span style={{fontStyle:'italic', color:'var(--ink2)'}}>工作台</span>
        </h1>
        <p style={{fontSize:15, color:'var(--ink2)', lineHeight:1.75, maxWidth:480}}>
          PDF 自动抽取 · 人工核验 · 结构化入库。<br/>
          把散落在各大学官网的招生简章，变成可以直接使用的数据。
        </p>
      </div>

      {/* Stats */}
      <div style={{display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:16, marginBottom:32}}>
        {statCards.map(c => (
          <div key={c.label} className="card" style={{padding:'28px 24px', position:'relative', overflow:'hidden'}}>
            <div style={{position:'absolute', top:0, left:0, right:0, height:3, background:c.accent, borderRadius:'12px 12px 0 0'}}/>
            <div style={{fontFamily:"'Playfair Display', serif", fontSize:44, fontWeight:700, lineHeight:1, color:'var(--ink)', letterSpacing:'-1px', marginBottom:8}}>
              {c.value}
            </div>
            <div style={{fontSize:12, color:'var(--ink3)', letterSpacing:'0.05em'}}>{c.label}</div>
          </div>
        ))}
      </div>

      {/* Flow */}
      <div className="card" style={{padding:'32px 28px', marginBottom:24}}>
        <div style={{fontSize:12, letterSpacing:'0.12em', textTransform:'uppercase', color:'var(--ink3)', marginBottom:20, fontWeight:500}}>处理流程</div>
        <div style={{display:'flex', gap:0, alignItems:'stretch'}}>
          {[
            {n:'01', title:'下载 PDF', desc:'自动爬取各大学官网'},
            {n:'02', title:'AI 抽取', desc:'GPT-5.4-mini 结构化'},
            {n:'03', title:'人工核验', desc:'逐条确认修改'},
            {n:'04', title:'确认入库', desc:'写入正式数据库'},
            {n:'05', title:'检索导出', desc:'筛选 + Excel 导出'},
          ].map((step, i) => (
            <div key={i} style={{flex:1, padding:'16px 14px', borderRight: i<4?'1px solid var(--border)':'none'}}>
              <div style={{fontSize:11, color:'var(--red)', fontWeight:500, marginBottom:8, letterSpacing:'0.08em'}}>{step.n}</div>
              <div style={{fontSize:13, fontWeight:500, color:'var(--ink)', marginBottom:4}}>{step.title}</div>
              <div style={{fontSize:12, color:'var(--ink3)', lineHeight:1.5}}>{step.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div style={{padding:'12px 16px', background:'var(--red-soft)', border:'1px solid #fecaca', borderRadius:8, fontSize:13, color:'var(--red)'}}>
          服务暂不可用，请检查后端状态。
        </div>
      )}
    </div>
  );
}
