import { useEffect, useMemo, useState } from "react";
import { getStaging, patchStaging, toErrorMessage } from "../api/client";
import type { StagingRecord } from "../types";

interface ReviewWorkspacePageProps {
  initialDocId?: string;
  onDocIdChange?: (docId: number | string) => void;
}

type FieldConfig = {
  key: keyof StagingRecord;
  label: string;
  multiline?: boolean;
};

const reviewFields: FieldConfig[] = [
  { key: "university",          label: "大学" },
  { key: "admission_year",      label: "年度" },
  { key: "faculty",             label: "学部" },
  { key: "department",          label: "学科" },
  { key: "application_period",  label: "出愿期间",     multiline: true },
  { key: "deadline_rule",       label: "必着/消印规则" },
  { key: "eju_session",         label: "EJU实施回" },
  { key: "eju_japanese",        label: "EJU日语" },
  { key: "eju_general",         label: "EJU综合科目" },
  { key: "eju_math",            label: "EJU数学" },
  { key: "english_requirement", label: "英语要求",     multiline: true },
  { key: "screening_method",    label: "选拔方式",     multiline: true },
  { key: "screening_schedule",  label: "选考日程",     multiline: true },
  { key: "result_date",         label: "合格发表日" },
  { key: "enrollment_period",   label: "入学手续期间", multiline: true },
  { key: "prefecture",          label: "都道府县" },
  { key: "campus",              label: "校区" },
];

function toEditableValues(row?: StagingRecord): Record<string, string> {
  const values: Record<string, string> = {};
  for (const f of reviewFields) {
    const raw = row?.[f.key];
    values[String(f.key)] = raw == null ? "" : String(raw);
  }
  return values;
}

function getStatus(row?: StagingRecord): { label: string; style: string } {
  if (!row) return { label: "未加载", style: "badge badge-gray" };
  if (Number(row.is_confirmed ?? 0) === 1) return { label: "已确认", style: "badge badge-green" };
  if (Number(row.needs_review ?? 0) === 1) return { label: "需复查", style: "badge badge-amber" };
  const conf = Number(row.confidence ?? 0);
  if (conf > 0 && conf < 0.75) return { label: "低置信度", style: "badge badge-red" };
  return { label: "待处理", style: "badge badge-gray" };
}

export default function ReviewWorkspacePage({ initialDocId = "", onDocIdChange }: ReviewWorkspacePageProps) {
  const [docId, setDocId] = useState(initialDocId);
  const [rows, setRows] = useState<StagingRecord[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => { setDocId(initialDocId); }, [initialDocId]);

  const current = rows[currentIndex];
  useEffect(() => { setValues(toEditableValues(current)); }, [current?.id]);

  const stats = useMemo(() => {
    const total = rows.length;
    const confirmed = rows.filter(r => Number(r.is_confirmed ?? 0) === 1).length;
    const needsReview = rows.filter(r => Number(r.needs_review ?? 0) === 1).length;
    return { total, confirmed, needsReview };
  }, [rows]);

  async function load() {
    const id = Number(docId);
    if (!id) return;
    setLoading(true); setError(""); setMessage("");
    try {
      const data = await getStaging(id);
      setRows(data); setCurrentIndex(0); onDocIdChange?.(id);
      setMessage(data.length ? `已加载 ${data.length} 条记录` : "没有找到待复查记录");
    } catch (err) { setError(toErrorMessage(err)); setRows([]); setCurrentIndex(0); }
    finally { setLoading(false); }
  }

  async function savePatch(patch: Record<string, unknown>, msg: string) {
    if (!current) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const updated = await patchStaging(current.id, patch);
      setRows(prev => prev.map(r => r.id === current.id ? { ...r, ...updated, ...patch } : r));
      setMessage(msg);
    } catch (err) { setError(toErrorMessage(err)); }
    finally { setSaving(false); }
  }

  function move(delta: number) {
    if (!rows.length) return;
    setCurrentIndex(idx => Math.min(Math.max(idx + delta, 0), rows.length - 1));
    setMessage(""); setError("");
  }

  const progress = rows.length ? Math.round((stats.confirmed / rows.length) * 100) : 0;
  const status = getStatus(current);

  return (
    <div style={{maxWidth: 1100}}>
      {/* Page header */}
      <div style={{marginBottom: 28}}>
        <div style={{fontSize:11, letterSpacing:'0.18em', textTransform:'uppercase', color:'var(--red)', marginBottom:8, fontWeight:500}}>Review Workspace</div>
        <div style={{display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:12}}>
          <h2 style={{fontFamily:"'Playfair Display', Georgia, serif", fontSize:32, fontWeight:700, lineHeight:1.1, letterSpacing:'-0.3px'}}>
            人工复查<span style={{fontStyle:'italic', color:'var(--ink2)'}}> 工作台</span>
          </h2>
          {rows.length > 0 && (
            <div style={{fontSize:13, color:'var(--ink3)'}}>
              第 <strong style={{color:'var(--ink)'}}>{currentIndex + 1}</strong> / {rows.length} 条
            </div>
          )}
        </div>
      </div>

      {/* Load bar */}
      <div className="card" style={{padding:'16px 20px', marginBottom:20, display:'flex', gap:10, alignItems:'center', flexWrap:'wrap'}}>
        <input
          value={docId}
          onChange={e => setDocId(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && load()}
          className="field"
          style={{width:140}}
          placeholder="文档 ID"
        />
        <button onClick={() => void load()} className="btn btn-primary" disabled={loading}>
          {loading ? '加载中…' : '加载'}
        </button>
        <div style={{width:1, height:24, background:'var(--border)', margin:'0 4px'}}/>
        <button onClick={() => move(-1)} className="btn" disabled={!rows.length || currentIndex === 0}>← 上一条</button>
        <button onClick={() => move(1)}  className="btn" disabled={!rows.length || currentIndex >= rows.length - 1}>下一条 →</button>

        {rows.length > 0 && (
          <div style={{marginLeft:'auto', display:'flex', alignItems:'center', gap:12}}>
            <div style={{width:120, height:4, background:'var(--border)', borderRadius:4, overflow:'hidden'}}>
              <div style={{width:`${progress}%`, height:'100%', background:'var(--green)', transition:'width 0.4s ease'}}/>
            </div>
            <span style={{fontSize:12, color:'var(--ink3)'}}>{progress}% 已确认</span>
          </div>
        )}
      </div>

      {/* Stats row */}
      <div style={{display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:12, marginBottom:20}}>
        {[
          {label:'总记录', value: stats.total,       color:'var(--ink)'},
          {label:'已确认', value: stats.confirmed,    color:'var(--green)'},
          {label:'需复查', value: stats.needsReview,  color:'var(--amber)'},
          {label:'当前状态', value: <span className={status.style}>{status.label}</span>, color:'var(--ink)'},
        ].map((c, i) => (
          <div key={i} className="card" style={{padding:'18px 20px'}}>
            <div style={{fontSize:11, color:'var(--ink3)', marginBottom:8, letterSpacing:'0.04em'}}>{c.label}</div>
            <div style={{fontSize:24, fontFamily:"'Playfair Display', serif", fontWeight:700, color: i < 3 ? c.color : 'inherit', lineHeight:1}}>
              {c.value}
            </div>
          </div>
        ))}
      </div>

      {/* Messages */}
      {error   && <div style={{marginBottom:16, padding:'10px 16px', background:'var(--red-soft)',   border:'1px solid #fecaca', borderRadius:8, fontSize:13, color:'var(--red)'}}>{error}</div>}
      {message && <div style={{marginBottom:16, padding:'10px 16px', background:'var(--blue-soft)', border:'1px solid #bfdbfe', borderRadius:8, fontSize:13, color:'var(--blue)'}}>{message}</div>}

      {!current && !loading && (
        <div className="card" style={{padding:'28px 24px', fontSize:14, color:'var(--ink3)', textAlign:'center'}}>
          输入文档 ID 并点击「加载」，开始逐条复查
        </div>
      )}

      {/* Main edit area */}
      {current && (
        <div style={{display:'grid', gridTemplateColumns:'1fr 300px', gap:20}}>

          {/* Edit form */}
          <div className="card" style={{padding:'28px'}}>
            <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:24}}>
              <div>
                <div style={{fontSize:15, fontWeight:500, color:'var(--ink)', marginBottom:3}}>抽取结果编辑</div>
                <div style={{fontSize:12, color:'var(--ink3)'}}>点击字段即可修改 · 记录ID {current.id}</div>
              </div>
              <span className={status.style}>{status.label}</span>
            </div>

            <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:'12px 16px', marginBottom:24}}>
              {reviewFields.map(field => {
                const key = String(field.key);
                const baseStyle = {
                  width: '100%',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  padding: '0 12px',
                  fontSize: 13,
                  fontFamily: 'inherit',
                  color: 'var(--ink)',
                  background: 'var(--surface)',
                  outline: 'none',
                };
                return (
                  <label key={key} style={field.multiline ? {gridColumn:'span 2'} : {}}>
                    <div style={{fontSize:11, fontWeight:500, color:'var(--ink3)', marginBottom:5, letterSpacing:'0.04em'}}>
                      {field.label}
                    </div>
                    {field.multiline ? (
                      <textarea
                        value={values[key] || ""}
                        onChange={e => setValues(p => ({...p, [key]: e.target.value}))}
                        style={{...baseStyle, minHeight:72, padding:'8px 12px', resize:'vertical'}}
                        onFocus={e => { e.target.style.borderColor='var(--red)'; e.target.style.boxShadow='0 0 0 3px rgba(185,28,28,0.08)'; }}
                        onBlur={e  => { e.target.style.borderColor='var(--border)'; e.target.style.boxShadow='none'; }}
                      />
                    ) : (
                      <input
                        value={values[key] || ""}
                        onChange={e => setValues(p => ({...p, [key]: e.target.value}))}
                        style={{...baseStyle, height:38}}
                        onFocus={e => { e.target.style.borderColor='var(--red)'; e.target.style.boxShadow='0 0 0 3px rgba(185,28,28,0.08)'; }}
                        onBlur={e  => { e.target.style.borderColor='var(--border)'; e.target.style.boxShadow='none'; }}
                      />
                    )}
                  </label>
                );
              })}
            </div>

            {/* Action buttons */}
            <div style={{display:'flex', gap:8, paddingTop:20, borderTop:'1px solid var(--border)'}}>
              <button onClick={() => void savePatch(values, "修改已保存")} disabled={saving} className="btn">
                保存修改
              </button>
              <button onClick={() => void savePatch({...values, needs_review:1, is_confirmed:0}, "已标记为需复查")} disabled={saving} className="btn btn-amber">
                标记复查
              </button>
              <button
                onClick={async () => {
                  await savePatch({...values, needs_review:0, is_confirmed:1}, "本条已确认 ✓");
                  if (currentIndex < rows.length - 1) move(1);
                }}
                disabled={saving}
                className="btn btn-green"
              >
                确认本条 →
              </button>
            </div>
          </div>

          {/* Right sidebar */}
          <div style={{display:'flex', flexDirection:'column', gap:16}}>
            {/* Meta info */}
            <div className="card" style={{padding:'20px 20px'}}>
              <div style={{fontSize:12, fontWeight:500, color:'var(--ink)', marginBottom:16, letterSpacing:'0.06em', textTransform:'uppercase'}}>
                辅助信息
              </div>
              {[
                {label:'页码',     value: current.page_number  || '未记录'},
                {label:'置信度',   value: current.confidence != null ? (
                  <span style={{color: Number(current.confidence) >= 0.85 ? 'var(--green)' : Number(current.confidence) >= 0.7 ? 'var(--amber)' : 'var(--red)', fontWeight:500}}>
                    {Number(current.confidence).toFixed(2)}
                  </span>
                ) : '未记录'},
                {label:'最后更新', value: current.updated_at   || '未记录'},
              ].map(item => (
                <div key={item.label} style={{marginBottom:14}}>
                  <div style={{fontSize:11, color:'var(--ink3)', marginBottom:4}}>{item.label}</div>
                  <div style={{fontSize:13, color:'var(--ink)', lineHeight:1.4}}>{item.value}</div>
                </div>
              ))}
            </div>

            {/* Navigation quick-jump */}
            <div className="card" style={{padding:'20px'}}>
              <div style={{fontSize:12, fontWeight:500, color:'var(--ink)', marginBottom:12, letterSpacing:'0.06em', textTransform:'uppercase'}}>
                快速跳转
              </div>
              <div style={{display:'flex', flexDirection:'column', gap:4, maxHeight:200, overflowY:'auto'}}>
                {rows.map((row, i) => {
                  const isConf = Number(row.is_confirmed ?? 0) === 1;
                  const isNR   = Number(row.needs_review ?? 0) === 1;
                  return (
                    <button
                      key={row.id}
                      onClick={() => { setCurrentIndex(i); setMessage(""); setError(""); }}
                      style={{
                        textAlign:'left',
                        padding:'6px 10px',
                        borderRadius:6,
                        fontSize:12,
                        border:'none',
                        cursor:'pointer',
                        fontFamily:'inherit',
                        background: i === currentIndex ? 'var(--ink)' : 'transparent',
                        color: i === currentIndex ? '#fff' : 'var(--ink2)',
                        display:'flex',
                        alignItems:'center',
                        gap:8,
                      }}
                    >
                      <span style={{width:6, height:6, borderRadius:'50%', flexShrink:0, background: isConf ? 'var(--green)' : isNR ? '#f59e0b' : 'var(--border)'}}/>
                      <span style={{overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>
                        {row.faculty || `记录 ${row.id}`}
                      </span>
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

interface ReviewWorkspacePageProps {
  initialDocId?: string;
  onDocIdChange?: (docId: number | string) => void;
}

type FieldConfig = {
  key: keyof StagingRecord;
  label: string;
  placeholder?: string;
  multiline?: boolean;
};

const reviewFields: FieldConfig[] = [
  { key: "university", label: "大学" },
  { key: "admission_year", label: "年度" },
  { key: "faculty", label: "学部" },
  { key: "department", label: "学科" },
  { key: "application_period", label: "出愿期间", multiline: true },
  { key: "deadline_rule", label: "必着/消印规则" },
  { key: "eju_session", label: "EJU实施回" },
  { key: "eju_japanese", label: "EJU日语" },
  { key: "eju_general", label: "EJU综合科目" },
  { key: "eju_math", label: "EJU数学" },
  { key: "english_requirement", label: "英语要求", multiline: true },
  { key: "screening_method", label: "选拔方式", multiline: true },
  { key: "screening_schedule", label: "选考日程", multiline: true },
  { key: "result_date", label: "合格发表日" },
  { key: "enrollment_period", label: "入学手续期间", multiline: true },
  { key: "prefecture", label: "都道府县" },
  { key: "campus", label: "校区" },
];

function toEditableValues(row?: StagingRecord): Record<string, string> {
  const values: Record<string, string> = {};
  for (const field of reviewFields) {
    const raw = row?.[field.key];
    values[String(field.key)] = raw == null ? "" : String(raw);
  }
  return values;
}

function statusText(row?: StagingRecord): string {
  if (!row) return "未加载";
  if (Number(row.is_confirmed ?? 0) === 1) return "已确认";
  if (Number(row.needs_review ?? 0) === 1) return "需复查";
  const confidence = Number(row.confidence ?? 0);
  if (confidence > 0 && confidence < 0.75) return "低置信度";
  return "待处理";
}

export default function ReviewWorkspacePage({ initialDocId = "", onDocIdChange }: ReviewWorkspacePageProps) {
  const [docId, setDocId] = useState(initialDocId);
  const [rows, setRows] = useState<StagingRecord[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    setDocId(initialDocId);
  }, [initialDocId]);

  const current = rows[currentIndex];

  useEffect(() => {
    setValues(toEditableValues(current));
  }, [current?.id]);

  const stats = useMemo(() => {
    const total = rows.length;
    const confirmed = rows.filter((r) => Number(r.is_confirmed ?? 0) === 1).length;
    const needsReview = rows.filter((r) => Number(r.needs_review ?? 0) === 1).length;
    return { total, confirmed, needsReview };
  }, [rows]);

  async function load(): Promise<void> {
    const id = Number(docId);
    if (!id) return;
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const data = await getStaging(id);
      setRows(data);
      setCurrentIndex(0);
      onDocIdChange?.(id);
      setMessage(data.length ? `已加载 ${data.length} 条待复查记录。` : "没有找到待复查记录。");
    } catch (err) {
      setError(toErrorMessage(err));
      setRows([]);
      setCurrentIndex(0);
    } finally {
      setLoading(false);
    }
  }

  async function savePatch(patch: Record<string, unknown>, successMessage: string): Promise<void> {
    if (!current) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const updated = await patchStaging(current.id, patch);
      setRows((prev) => prev.map((row) => (row.id === current.id ? { ...row, ...updated, ...patch } : row)));
      setMessage(successMessage);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function saveEdits(): Promise<void> {
    await savePatch(values, "修改已保存。");
  }

  async function confirmCurrent(): Promise<void> {
    await savePatch({ ...values, needs_review: 0, is_confirmed: 1 }, "本条已确认。后续可到“确认入库”页面批量写入正式记录。");
    if (currentIndex < rows.length - 1) setCurrentIndex((idx) => idx + 1);
  }

  async function markNeedsReview(): Promise<void> {
    await savePatch({ ...values, needs_review: 1, is_confirmed: 0 }, "已标记为需复查。");
  }

  function move(delta: number): void {
    if (!rows.length) return;
    setCurrentIndex((idx) => Math.min(Math.max(idx + delta, 0), rows.length - 1));
    setMessage("");
    setError("");
  }

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-[20px] font-semibold tracking-tight text-[#111827]">人工复查工作台</h2>
            <p className="mt-1 text-sm text-gray-500">逐条检查抽取结果，修改后确认，避免在大表格里横向滚动查错。</p>
          </div>
          <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
            当前 {rows.length ? currentIndex + 1 : 0} / {rows.length}
          </span>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <input
            value={docId}
            onChange={(e) => setDocId(e.target.value)}
            className="h-10 w-40 rounded-lg border border-gray-300 px-3 text-[13px] outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15"
            placeholder="文档ID"
          />
          <button onClick={() => void load()} className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-50">
            加载
          </button>
          <button
            onClick={() => move(-1)}
            disabled={!rows.length || currentIndex === 0}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            上一条
          </button>
          <button
            onClick={() => move(1)}
            disabled={!rows.length || currentIndex >= rows.length - 1}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            下一条
          </button>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
          <div className="text-xs text-gray-500">总记录数</div>
          <div className="mt-2 text-[24px] font-semibold text-gray-900">{stats.total}</div>
        </div>
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="text-xs text-emerald-700">已确认</div>
          <div className="mt-2 text-[24px] font-semibold text-emerald-900">{stats.confirmed}</div>
        </div>
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <div className="text-xs text-amber-700">需复查</div>
          <div className="mt-2 text-[24px] font-semibold text-amber-900">{stats.needsReview}</div>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
          <div className="text-xs text-gray-500">当前状态</div>
          <div className="mt-2 text-[24px] font-semibold text-gray-900">{statusText(current)}</div>
        </div>
      </section>

      {loading && <section className="rounded-2xl border border-gray-200 bg-white p-5 text-sm text-gray-500">加载中...</section>}
      {error && <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">操作失败：{error}</section>}
      {message && <section className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">{message}</section>}

      {!loading && !current && (
        <section className="rounded-2xl border border-gray-200 bg-white p-5 text-sm text-gray-500">
          请输入文档ID并点击“加载”，开始逐条复查。
        </section>
      )}

      {current && (
        <section className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_360px]">
          <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-[17px] font-semibold text-gray-900">抽取结果编辑</h3>
                <p className="mt-1 text-xs text-gray-500">点击文本框即可修改。保存后会写回待复核记录。</p>
              </div>
              <div className="text-xs text-gray-500">记录ID：{current.id}</div>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {reviewFields.map((field) => {
                const key = String(field.key);
                const commonClass = "w-full rounded-lg border border-gray-300 px-3 text-[13px] outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15";
                return (
                  <label key={key} className={field.multiline ? "md:col-span-2" : ""}>
                    <div className="mb-1 text-xs font-medium text-gray-500">{field.label}</div>
                    {field.multiline ? (
                      <textarea
                        value={values[key] || ""}
                        onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
                        className={`${commonClass} min-h-[72px] py-2`}
                      />
                    ) : (
                      <input
                        value={values[key] || ""}
                        onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
                        className={`${commonClass} h-10`}
                      />
                    )}
                  </label>
                );
              })}
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              <button
                onClick={() => void saveEdits()}
                disabled={saving}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                保存修改
              </button>
              <button
                onClick={() => void markNeedsReview()}
                disabled={saving}
                className="rounded-lg border border-amber-500 px-4 py-2 text-sm font-medium text-amber-700 hover:bg-amber-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                标记需复查
              </button>
              <button
                onClick={() => void confirmCurrent()}
                disabled={saving}
                className="rounded-lg border border-emerald-600 bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                确认本条
              </button>
            </div>
          </div>

          <aside className="space-y-4">
            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="text-[15px] font-semibold text-gray-900">复查辅助信息</h3>
              <dl className="mt-4 space-y-3 text-sm">
                <div>
                  <dt className="text-xs text-gray-500">页码</dt>
                  <dd className="mt-1 font-medium text-gray-900">{current.page_number || "未记录"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">置信度</dt>
                  <dd className="mt-1 font-medium text-gray-900">
                    {current.confidence == null ? "未记录" : Number(current.confidence).toFixed(2)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-gray-500">最后更新时间</dt>
                  <dd className="mt-1 font-medium text-gray-900">{current.updated_at || "未记录"}</dd>
                </div>
              </dl>
            </div>

            <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="text-[15px] font-semibold text-gray-900">原文证据</h3>
              <p className="mt-2 text-sm leading-6 text-gray-600">
                当前后端的 staging 接口尚未返回 source_snippet 字段，因此这里先显示页码和记录状态。
                下一步可以让后端把 trace_debug.json 中的 snippet 接到这里。
              </p>
            </div>
          </aside>
        </section>
      )}
    </div>
  );
}
