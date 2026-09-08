import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { getPublicProgram, getPublicPrograms, getPublicRecommendations, toErrorMessage } from "../api/client";
import type { PublicProgram, StudentProfile } from "../types";
import "../student-discovery.css";

const assets = import.meta.glob("../assets/admissions-icons/*.svg", { eager: true, query: "?url", import: "default" });
function Icon({ name }: { name: string }) {
  return <img className="ad-icon" src={assets[`../assets/admissions-icons/${name}.svg`] as string} alt="" aria-hidden="true" />;
}
const text = (value?: string) => value?.trim() || "待补充";
const terms = (value: string) => value.split(/[,，、;；\n]+/).map(s => s.trim()).filter(Boolean);
const fold = (value: string) => value.normalize("NFKC").toLowerCase().replace(/东京/g, "東京").replace(/经济/g, "経済");
function sourceUrl(program: PublicProgram) {
  try { const url = new URL(program.source_document?.pdf_url || ""); return ["https:", "http:"].includes(url.protocol) ? url.href : ""; }
  catch { return ""; }
}
function ejuRows(p: PublicProgram) {
  const e = p.requirements?.eju || {};
  return [["有效场次", e.session], ["日本语", e.japanese], ["综合科目", e.general], ["数学", e.math], ["物理", e.physics], ["化学", e.chemistry], ["生物", e.biology]];
}
function ejuSummary(p: PublicProgram) {
  const groups = new Map<string, string[]>();
  for (const [label, value] of ejuRows(p).slice(1)) {
    if (value?.trim()) groups.set(value, [...(groups.get(value) || []), label!]);
  }
  return [...groups].map(([value, labels]) => `${labels.join(" / ")}：${value}`).join("；");
}
function Datum({ label, value }: { label: string; value?: string }) {
  return <div className="ad-datum"><dt>{label}</dt><dd className={!value?.trim() ? "ad-missing" : undefined}>{text(value)}</dd></div>;
}

export default function StudentApp() {
  const [programs, setPrograms] = useState<PublicProgram[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [query, setQuery] = useState("");
  const [year, setYear] = useState("");
  const [region, setRegion] = useState("");
  const [faculty, setFaculty] = useState("");
  const [selected, setSelected] = useState<PublicProgram | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [copyMessage, setCopyMessage] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);
  const [matching, setMatching] = useState(false);
  const [matchIds, setMatchIds] = useState<number[] | null>(null);
  const requestId = useRef(0);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true); setError("");
      try {
        const all: PublicProgram[] = [];
        for (let offset = 0; active; offset += 100) {
          const batch = await getPublicPrograms({ limit: 100, offset });
          all.push(...batch);
          if (batch.length < 100) break;
        }
        if (active) setPrograms([...new Map(all.map(p => [p.id, p])).values()]);
      } catch (err) { if (active) setError(toErrorMessage(err)); }
      finally { if (active) setLoading(false); }
    }
    void load();
    return () => { active = false; };
  }, [reload]);
  useEffect(() => () => { requestId.current++; }, []);

  const choices = (key: "admission_year" | "prefecture" | "faculty") => [...new Set(programs.map(p => p[key]).filter((v): v is string => Boolean(v)))].sort();
  const filtered = useMemo(() => programs.filter(p => {
    const content = fold([p.school_name, p.faculty, p.department, p.prefecture, p.campus, p.admission_period, p.exam_method, p.requirements?.english?.raw_text, ...ejuRows(p).map(row => row[1])].join(" "));
    return (!year || p.admission_year === year) && (!region || p.prefecture === region) && (!faculty || p.faculty === faculty)
      && fold(query).split(/\s+/).filter(Boolean).every(term => content.includes(term)) && (matchIds === null || matchIds.includes(p.id));
  }).sort((a, b) => a.school_name.localeCompare(b.school_name, "ja") || a.faculty.localeCompare(b.faculty, "ja") || a.id - b.id), [programs, query, year, region, faculty, matchIds]);
  const hasFilters = Boolean(query || year || region || faculty || matchIds !== null);
  function reset() { setQuery(""); setYear(""); setRegion(""); setFaculty(""); setMatchIds(null); }
  function back() { requestId.current++; setSelected(null); setDetailBusy(false); setDetailError(""); setCopyMessage(""); }
  async function open(p: PublicProgram) {
    const id = ++requestId.current;
    setSelected(p); setDetailBusy(true); setDetailError(""); setCopyMessage("");
    window.scrollTo({ top: 0, behavior: "instant" });
    try { const result = await getPublicProgram(p.id); if (id === requestId.current) setSelected(result); }
    catch (err) { if (id === requestId.current) setDetailError(toErrorMessage(err)); }
    finally { if (id === requestId.current) { setDetailBusy(false); heading.current?.focus(); } }
  }
  async function match(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    const value = (key: string) => String(data.get(key) || "");
    const profile: StudentProfile = { target_year: value("year"), desired_fields: terms(value("fields")), preferred_prefectures: terms(value("regions")), english_tests: terms(value("english")), eju_subjects: terms(value("eju")), japanese_level: value("japanese"), notes: value("notes") };
    setMatching(true); setError("");
    try { const response = await getPublicRecommendations(profile); reset(); setMatchIds(response.results.map(r => r.program.id)); setProfileOpen(false); }
    catch (err) { setError(toErrorMessage(err)); }
    finally { setMatching(false); }
  }
  async function copy() {
    if (!selected) return;
    const p = selected;
    try {
      await navigator.clipboard.writeText([`${p.school_name} · ${p.admission_year} · ${p.faculty} ${p.department}`, `入试方式：${text(p.admission_period)}`, `出愿：${text(p.application_period)}`, `截止规则：${text(p.deadline_rule)}`, ...ejuRows(p).map(([key, value]) => `EJU ${key}：${text(value)}`), `英语：${text(p.requirements?.english?.raw_text)}`, `选考：${text(p.exam_method)}`, `考试：${text(p.exam_date)}`, `合格发表：${text(p.result_date)}`, `入学手续：${text(p.enrollment_period)}`, `资格：${text(p.requirements?.eligibility)}`, `材料：${p.requirements?.required_documents?.join("；") || "待补充"}`, `来源：${sourceUrl(p) || "待补充"}`].join("\n"));
      setCopyMessage("已复制报考信息");
    } catch { setCopyMessage("复制失败，请选择页面文字复制。"); }
  }

  return <div className="ad-student">
    <header className="ad-topbar"><div className="ad-topbar-inner">
      <a className="ad-brand" href="#/student" onClick={back}><span className="ad-brand-symbol"><Icon name="GraduationCap" /></span><span>日本大学申请<span className="ad-brand-sub">ADMISSIONS GUIDE</span></span></a>
      <nav aria-label="学生端导航"><button className={!profileOpen ? "ad-nav-active" : undefined} onClick={() => { back(); setProfileOpen(false); }}>学校查询</button><button className={profileOpen ? "ad-nav-active" : undefined} onClick={() => { back(); setProfileOpen(v => !v); }}>按条件选校</button></nav>
      <a className="ad-account" href="#/account" aria-label="登录 / 我的账号" title="登录 / 我的账号"><Icon name="UserRound" /><span>我的账号</span></a>
    </div></header>
    <main className="ad-main">
      {!selected ? <>
        <section className="ad-intro"><div><p className="ad-eyebrow">留学生入试 · 募集要项</p><h1>学校与报考信息</h1><p className="ad-subtitle">出愿时间、考试要求、官方原文。</p></div><div className="ad-publication"><span /> 人工复核后发布</div></section>
        <section className="ad-search-area" aria-label="学校查询条件">
          <label className="ad-search"><Icon name="Search" /><input aria-label="搜索学校或条件" value={query} onChange={e => setQuery(e.target.value)} placeholder="搜索大学、学部或考试要求" />{query && <button title="清空搜索" aria-label="清空搜索" onClick={() => setQuery("")}>×</button>}</label>
          <div className="ad-filters">{([['入学年度', year, setYear, choices('admission_year')], ['地区', region, setRegion, choices('prefecture')], ['学部 / 方向', faculty, setFaculty, choices('faculty')]] as const).map(([label, value, setter, options]) => <label key={label}><span>{label}</span><select aria-label={label} value={value} onChange={e => setter(e.target.value)}><option value="">全部</option>{options.map(v => <option key={v}>{v}</option>)}</select></label>)}<button className="ad-reset" onClick={reset} disabled={!hasFilters}><Icon name="RotateCcw" />重置</button></div>
        </section>
        {profileOpen && <section className="ad-profile"><h2>按已有条件筛选</h2><p>仅按公开要求整理候选，不代表录取概率。</p><form onSubmit={e => void match(e)}><div className="ad-profile-fields">{[["year", "目标年度"], ["fields", "专业方向"], ["regions", "希望地区"], ["english", "英语考试"], ["eju", "EJU 科目"], ["japanese", "日语情况"], ["notes", "补充条件"]].map(([name, label]) => <label key={name}>{label}<input name={name} /></label>)}</div><button className="ad-primary" disabled={matching}>{matching ? "筛选中…" : "查看候选学校"}</button><button type="button" className="ad-text-button" onClick={() => setProfileOpen(false)}>收起</button></form></section>}
        {error ? <div className="ad-alert" role="alert">读取失败：{error} <button onClick={() => setReload(v => v + 1)}>重新加载</button></div> : null}
        <section className="ad-results" aria-label="学校查询结果"><div className="ad-results-heading"><h2>{matchIds !== null ? "条件筛选结果" : "招生信息"}<span>{loading ? "读取中" : `${new Set(filtered.map(p => p.school_name)).size} 所大学 · ${filtered.length} 个招生项目`}</span></h2><span className="ad-muted">以大学最新公告为准</span></div>
          {loading ? <div className="ad-loading" role="status">正在读取已发布资料…<div /><div /><div /></div> : error ? null : filtered.length ? <div className="ad-program-list">{filtered.map(p => <article className="ad-program" key={p.id}>
            <div className="ad-program-title"><span className="ad-school-mark" aria-hidden="true">{p.school_name.slice(0, 1)}</span><div><span className="ad-meta">{text(p.admission_year)} 年度 · {text(p.prefecture)}</span><h3><button onClick={() => void open(p)}>{p.school_name}<Icon name="ChevronRight" /></button></h3><p>{[p.faculty, p.department].filter(Boolean).join(" / ") || "学部待补充"}</p><span className="ad-route">{text(p.admission_period)}</span></div></div>
            <dl className="ad-program-facts"><Datum label="出愿期间" value={p.application_period} /><Datum label="EJU 要求" value={ejuSummary(p)} /><Datum label="英语要求" value={p.requirements?.english?.raw_text} /></dl>
            <div className="ad-program-footer"><span>{p.deadline_rule || "截止规则待补充"}</span><button onClick={() => void open(p)}>查看报考详情<Icon name="ArrowUpRight" /></button></div>
          </article>)}</div> : <div className="ad-empty"><div className="ad-empty-art"><Icon name={programs.length ? "Search" : "FileSearch"} /></div><p className="ad-eyebrow">{programs.length ? "没有匹配结果" : "资料准备中"}</p><h2>{programs.length ? "换一组条件，再看看" : "下一份报考信息，正在核对"}</h2><p>{programs.length ? "可以减少关键词，或取消年度、地区与学部限制。" : "已整理的资料完成复核后，会出现在这里。尚未确认的内容暂不公开。"}</p>{hasFilters && <button className="ad-primary" onClick={reset}>清除筛选条件</button>}<div className="ad-empty-boundary"><Icon name="BookOpen" /><span>不确定的信息不作结论<br /><small>“待补充”不等于“不要求”</small></span></div></div>}
        </section>
      </> : <>
        <button className="ad-back" onClick={back}><Icon name="ArrowLeft" />学校查询</button>
        <section className="ad-detail-heading"><div><p className="ad-eyebrow">{text(selected.admission_year)} 年度 · {text(selected.admission_period)}</p><h1 ref={heading} tabIndex={-1}>{selected.school_name}</h1><p>{[selected.faculty, selected.department].filter(Boolean).join(" / ")}</p><span className="ad-muted">{[selected.prefecture, selected.campus].filter(Boolean).join(" · ")}</span></div><div className="ad-detail-actions">{sourceUrl(selected) && <a className="ad-primary" href={sourceUrl(selected)} target="_blank" rel="noreferrer">募集要项原文<Icon name="ArrowUpRight" /></a>}<button className="ad-icon-button" onClick={() => void copy()} aria-label="复制报考信息" title="复制报考信息"><Icon name="Copy" /></button></div></section>
        {copyMessage && <p role="status">{copyMessage}</p>}{detailBusy && <p role="status">正在更新详情…</p>}{detailError && <div className="ad-alert" role="alert">详情更新失败，以下为列表快照。<button onClick={() => void open(selected)}>重试</button></div>}
        <div className="ad-detail-grid"><div>
          <section className="ad-detail-section"><h2><Icon name="CalendarDays" />申请时间线</h2><ol className="ad-timeline">{[["出愿期间", selected.application_period], ["考试 / 选考", selected.exam_date], ["合格发表", selected.result_date], ["入学手续", selected.enrollment_period]].map(([label, value], i) => <li key={label}><span className="ad-step">0{i + 1}</span><div><h3>{label}</h3><p>{text(value)}</p>{i === 0 && <small>{text(selected.deadline_rule)}</small>}</div></li>)}</ol></section>
          <section className="ad-detail-section"><h2><Icon name="BookOpen" />考试与出愿条件</h2><h3 className="ad-group-title">EJU 日本留学试验</h3><dl className="ad-requirements">{ejuRows(selected).map(([label, value]) => <Datum key={label} label={label!} value={value} />)}</dl><dl className="ad-requirements ad-other-requirements"><Datum label="英语要求" value={selected.requirements?.english?.raw_text} /><Datum label="JLPT 要求" value={selected.requirements?.jlpt?.raw_text} /><Datum label="选考方式" value={selected.exam_method} /><Datum label="出愿资格" value={selected.requirements?.eligibility} /></dl></section>
          <section className="ad-detail-section"><h2>出愿材料</h2>{selected.requirements?.required_documents?.length ? <ul className="ad-documents">{selected.requirements.required_documents.map((item, i) => <li key={i}>{item}</li>)}</ul> : <p className="ad-muted">材料清单待补充，请核对募集要项原文。</p>}</section>
        </div><aside className="ad-source"><span className="ad-eyebrow">SOURCE</span><h2>回到官方资料</h2><Icon name="FileSearch" /><p>{selected.source_document?.file_name || "来源文件名待补充"}</p>{sourceUrl(selected) ? <a href={sourceUrl(selected)} target="_blank" rel="noreferrer">打开募集要项<Icon name="ArrowUpRight" /></a> : <p>原文链接待补充</p>}<small>证据页码暂未提供</small><hr /><h3>报考前再确认</h3><p>截止日的必着 / 消印规则、EJU 选科组合与有效场次，以及大学后续发布的更正公告。</p><p className="ad-muted">空白字段标为“待补充”；原文明确写“不要求”或“未记载”的内容按原文保留。</p></aside></div>
      </>}
      <footer className="ad-footer"><span>日本大学申请 / Admissions Guide</span><span>公开资料整理 · 人工复核发布</span></footer>
    </main>
  </div>;
}
