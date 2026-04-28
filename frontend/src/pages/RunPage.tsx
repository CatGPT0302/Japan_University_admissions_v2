import { useEffect, useMemo, useRef, useState } from "react";
import {
  extractPdf,
  fetchPdf,
  getFetchTargets,
  probeFetchSources,
  searchFetchPdf,
  toErrorMessage,
  uploadPdf,
} from "../api/client";
import type {
  FetchPdfCandidate,
  FetchPdfProbeResponse,
  FetchPdfTarget,
} from "../types";

interface Props {
  onDone: (docId: number) => void;
}

type SourceMode = "upload" | "search" | "direct";
type Step =
  | "idle"
  | "searching"
  | "downloading"
  | "uploading"
  | "extracting"
  | "done"
  | "error";

interface RunResult {
  doc_id: number;
  records: number;
  failed: number;
  university?: string;
  file_name?: string;
  source_url?: string;
}

function modeTitle(mode: SourceMode): string {
  if (mode === "upload") return "本地上传 PDF";
  if (mode === "search") return "自动搜索募集要项";
  return "手动填写 PDF 链接";
}

function stepLabel(step: Step, mode: SourceMode): string {
  if (step === "searching") return "正在搜索候选 PDF";
  if (step === "downloading") return "正在获取 PDF";
  if (step === "uploading") return "正在上传文件";
  if (step === "extracting") return "正在抽取内容";
  if (step === "done") return "抽取完成";
  if (step === "error") return "处理遇到问题";
  if (mode === "search") return "先搜索候选，再由你确认";
  if (mode === "direct") return "按你给的 PDF 链接直接处理";
  return "准备上传并抽取";
}

function candidateKindLabel(candidate: FetchPdfCandidate): string {
  if (candidate.source_kind === "registry_pdf") return "维护表直链";
  if (candidate.source_kind === "registry_page_pdf") return "维护表来源页";
  if (candidate.source_kind === "direct_pdf") return "直链 PDF";
  return "来源页发现";
}

function candidateTrustLabel(candidate: FetchPdfCandidate): string {
  if (candidate.source_origin === "maintained_registry") return "维护来源";
  if (candidate.is_official) return "疑似官网";
  return "需人工确认";
}

export default function RunPage({ onDone }: Props) {
  const [sourceMode, setSourceMode] = useState<SourceMode>("upload");
  const [targets, setTargets] = useState<FetchPdfTarget[]>([]);
  const [selectedTarget, setSelectedTarget] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [university, setUniversity] = useState("");
  const [year, setYear] = useState("2026");
  const [pageUrl, setPageUrl] = useState("");
  const [pdfUrl, setPdfUrl] = useState("");
  const [step, setStep] = useState<Step>("idle");
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [candidates, setCandidates] = useState<FetchPdfCandidate[]>([]);
  const [selectedCandidateUrl, setSelectedCandidateUrl] = useState("");
  const [probeResult, setProbeResult] = useState<FetchPdfProbeResponse | null>(null);
  const [probeLoading, setProbeLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void loadTargets();
  }, []);

  async function loadTargets() {
    try {
      setTargets(await getFetchTargets());
    } catch {
      setTargets([]);
    }
  }

  function resetRunState(options?: { keepCandidates?: boolean }) {
    setStep("idle");
    setResult(null);
    setError("");
    if (!options?.keepCandidates) {
      setCandidates([]);
      setSelectedCandidateUrl("");
      setSearchQuery("");
    }
  }

  function handleFile(nextFile: File | null) {
    if (!nextFile || !nextFile.name.toLowerCase().endsWith(".pdf")) return;
    setFile(nextFile);
    resetRunState();
  }

  async function runUpload() {
    if (!file) return;
    setError("");
    setResult(null);
    try {
      setStep("uploading");
      const uploaded = await uploadPdf(file);
      setStep("extracting");
      const extracted = await extractPdf({
        file_name: uploaded.file_name,
        university: "",
        year,
      });
      setResult({
        doc_id: extracted.doc_id,
        records: extracted.records,
        failed: extracted.failed_pages?.length ?? 0,
        university: extracted.university || "",
        file_name: uploaded.file_name,
      });
      setStep("done");
    } catch (nextError) {
      setError(toErrorMessage(nextError));
      setStep("error");
    }
  }

  async function runSearch() {
    if (!university) return;
    setError("");
    setResult(null);
    setCandidates([]);
    setSelectedCandidateUrl("");
    try {
      setStep("searching");
      const searched = await searchFetchPdf({
        university,
        year,
        page_url: pageUrl || undefined,
      });
      setSearchQuery(searched.query);
      setCandidates(searched.candidates || []);
      if (searched.candidates?.length) {
        setSelectedCandidateUrl(searched.candidates[0].pdf_url);
        setStep("idle");
      } else {
        setError("本次没有找到可用募集要项 PDF。可改学校名、补来源页，或改走手动 PDF 链接。");
        setStep("error");
      }
    } catch (nextError) {
      setError(toErrorMessage(nextError));
      setStep("error");
    }
  }

  async function runProbe() {
    setProbeLoading(true);
    setError("");
    try {
      const probe = await probeFetchSources(Number(year) || 2026);
      setProbeResult(probe);
    } catch (nextError) {
      setError(toErrorMessage(nextError));
    } finally {
      setProbeLoading(false);
    }
  }

  async function processPdfCandidate(candidate: FetchPdfCandidate) {
    setError("");
    setResult(null);
    try {
      setStep("downloading");
      const fetched = await fetchPdf({
        university,
        year,
        page_url: candidate.page_url || pageUrl || undefined,
        pdf_url: candidate.pdf_url,
      });
      setStep("extracting");
      const extracted = await extractPdf({
        file_name: fetched.file_name,
        university,
        year,
        url: fetched.source_url || candidate.pdf_url,
      });
      setResult({
        doc_id: extracted.doc_id,
        records: extracted.records,
        failed: extracted.failed_pages?.length ?? 0,
        university: extracted.university || university,
        file_name: fetched.file_name,
        source_url: fetched.source_url || candidate.pdf_url,
      });
      setStep("done");
    } catch (nextError) {
      setError(toErrorMessage(nextError));
      setStep("error");
    }
  }

  async function runDirectPdf() {
    if (!university || !pdfUrl) return;
    setError("");
    setResult(null);
    try {
      setStep("downloading");
      const fetched = await fetchPdf({
        university,
        year,
        page_url: pageUrl || undefined,
        pdf_url: pdfUrl,
      });
      setStep("extracting");
      const extracted = await extractPdf({
        file_name: fetched.file_name,
        university,
        year,
        url: fetched.source_url || pdfUrl,
      });
      setResult({
        doc_id: extracted.doc_id,
        records: extracted.records,
        failed: extracted.failed_pages?.length ?? 0,
        university: extracted.university || university,
        file_name: fetched.file_name,
        source_url: fetched.source_url || pdfUrl,
      });
      setStep("done");
    } catch (nextError) {
      setError(toErrorMessage(nextError));
      setStep("error");
    }
  }

  const busy =
    step === "searching" ||
    step === "downloading" ||
    step === "uploading" ||
    step === "extracting";
  const readyToUpload = Boolean(file && !busy);
  const readyToSearch = Boolean(university && !busy);
  const selectedCandidate =
    candidates.find((item) => item.pdf_url === selectedCandidateUrl) || null;
  const readyToConfirmCandidate = Boolean(selectedCandidate && !busy);
  const readyToDirectRun = Boolean(university && pdfUrl && !busy);

  const statusBlock = useMemo(() => {
    if (step === "done" && result) {
      return {
        tone: "success" as const,
        title: `已整理出 ${result.records} 条记录`,
        description:
          result.failed > 0
            ? `系统识别到大学 ${result.university || "待人工确认"}。有 ${result.failed} 页未顺利处理，建议复查时优先关注。`
            : `系统识别到大学 ${result.university || "待人工确认"}。可以进入复查继续确认。`,
      };
    }
    if (step === "error") {
      return {
        tone: "danger" as const,
        title: "这一步卡住了",
        description: "通常是来源页、PDF 链接或文件本身问题。可以切换入口继续处理。",
      };
    }
    if (step === "searching") {
      return {
        tone: "info" as const,
        title: "正在搜索候选 PDF",
        description: "搜索阶段不会入库，仍由你人工确认候选后再处理。",
      };
    }
    if (step === "downloading") {
      return {
        tone: "info" as const,
        title: "正在获取 PDF",
        description: "拿到文件后会自动进入抽取。",
      };
    }
    if (step === "uploading") {
      return {
        tone: "info" as const,
        title: "PDF 已接收",
        description: "正在上传并准备抽取。",
      };
    }
    if (step === "extracting") {
      return {
        tone: "info" as const,
        title: "AI 正在抽取内容",
        description: "系统会把内容整理成可复查记录。",
      };
    }
    return {
      tone: "neutral" as const,
      title: sourceMode === "search" ? "先找候选，再由你决定处理哪一份" : "准备开始",
      description:
        sourceMode === "upload"
          ? "适合你已经拿到 PDF 的情况。"
          : sourceMode === "direct"
            ? "适合你已经有准确 PDF 链接，不想再搜索。"
            : "系统优先走维护来源，未命中再用固定检索词搜索。",
    };
  }, [result, sourceMode, step]);

  const statusStyle =
    statusBlock.tone === "success"
      ? { background: "#f0fdf4", border: "1px solid #bbf7d0", accent: "#166534" }
      : statusBlock.tone === "danger"
        ? { background: "#fef2f2", border: "1px solid #fecaca", accent: "#b91c1c" }
        : statusBlock.tone === "info"
          ? { background: "#eff6ff", border: "1px solid #bfdbfe", accent: "#1d4ed8" }
          : { background: "#ffffff", border: "1px solid #e5e7eb", accent: "#111827" };

  const modeCards: Array<{ key: SourceMode; title: string; desc: string }> = [
    { key: "upload", title: "本地上传 PDF", desc: "你已经有文件时，这条最快。" },
    { key: "search", title: "自动搜索募集要项", desc: "系统先找候选 PDF，你确认后再处理。" },
    { key: "direct", title: "手动填写 PDF 链接", desc: "你已知准确 PDF 链接时最稳。" },
  ];

  return (
    <div style={{ maxWidth: 860 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 10, letterSpacing: "0.2em", textTransform: "uppercase", color: "var(--red)", marginBottom: 10, fontWeight: 600 }}>
          Step 1
        </div>
        <h1 style={{ fontSize: 32, fontWeight: 700, letterSpacing: -0.4, lineHeight: 1.15, margin: "0 0 10px" }}>跑数据</h1>
        <p style={{ fontSize: 14, color: "var(--ink2)", lineHeight: 1.75, margin: 0 }}>
          这里负责把 PDF 送进系统。你可以上传文件、先搜索候选，再确认处理。
        </p>
      </div>

      <div style={{ background: statusStyle.background, border: statusStyle.border, borderRadius: 18, padding: "18px 20px", boxShadow: "0 10px 28px rgba(15, 23, 42, 0.05)", marginBottom: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "flex-start" }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: statusStyle.accent, marginBottom: 6 }}>{statusBlock.title}</div>
            <div style={{ fontSize: 13, color: "var(--ink2)", lineHeight: 1.7 }}>{statusBlock.description}</div>
          </div>
          <div style={{ display: "grid", gap: 6, minWidth: 220 }}>
            <div className="badge badge-gray">模式：{modeTitle(sourceMode)}</div>
            <div className="badge badge-gray">大学：{sourceMode === "upload" ? result?.university || "将从 PDF 自动识别" : university || "未填写"}</div>
            <div className="badge badge-gray">年度：{year || "未设置"}</div>
            <div className="badge badge-gray">状态：{stepLabel(step, sourceMode)}</div>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12, marginBottom: 18 }}>
        {modeCards.map((item) => {
          const active = sourceMode === item.key;
          return (
            <button
              key={item.key}
              onClick={() => {
                setSourceMode(item.key);
                resetRunState();
              }}
              style={{
                textAlign: "left",
                padding: "18px 18px",
                borderRadius: 18,
                border: active ? "1px solid #cbd5e1" : "1px solid #e5e7eb",
                background: "#ffffff",
                boxShadow: active ? "0 12px 24px rgba(15, 23, 42, 0.08)" : "0 6px 16px rgba(15, 23, 42, 0.04)",
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)", marginBottom: 6 }}>{item.title}</div>
              <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.7 }}>{item.desc}</div>
            </button>
          );
        })}
      </div>

      <div className="card" style={{ padding: 22, borderRadius: 22, marginBottom: 18 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 120px", gap: "12px 14px" }}>
          {sourceMode === "upload" ? (
            <div style={{ border: "1px solid #e5e7eb", borderRadius: 16, padding: "12px 14px", background: "#fafaf9" }}>
              <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>大学名称</div>
              <div style={{ fontSize: 13, color: "var(--ink)", fontWeight: 600, marginBottom: 4 }}>将从 PDF 自动识别</div>
              <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.7 }}>上传模式不需要手填大学名。系统会先识别，后续仍需人工复查确认。</div>
            </div>
          ) : (
            <label>
              <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>大学名称</div>
              <input value={university} onChange={(event) => { setUniversity(event.target.value); resetRunState(); }} placeholder="例如：明治大学" className="field" style={{ width: "100%" }} />
            </label>
          )}
          <label>
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>年度</div>
            <input value={year} onChange={(event) => { setYear(event.target.value); resetRunState(); }} placeholder="2026" className="field" style={{ width: "100%" }} />
          </label>

          {sourceMode === "search" && (
            <>
              <label>
                <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>预设学校</div>
                <select
                  value={selectedTarget}
                  onChange={(event) => {
                    const next = event.target.value;
                    const matched = targets.find((item) => item.name === next);
                    setSelectedTarget(next);
                    if (next) setUniversity(next);
                    setPageUrl(matched?.url || "");
                    resetRunState();
                  }}
                  className="field"
                  style={{ width: "100%" }}
                >
                  <option value="">可选，不填也行</option>
                  {targets.map((target) => (
                    <option key={target.name} value={target.name}>{target.name}</option>
                  ))}
                </select>
              </label>
              <label>
                <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>募集页 URL</div>
                <input value={pageUrl} onChange={(event) => { setPageUrl(event.target.value); resetRunState(); }} placeholder="可选，补充官网招生页会更稳" className="field" style={{ width: "100%" }} />
              </label>
            </>
          )}

          {sourceMode === "direct" && (
            <>
              <label style={{ gridColumn: "span 2" }}>
                <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>PDF 直链</div>
                <input value={pdfUrl} onChange={(event) => { setPdfUrl(event.target.value); resetRunState(); }} placeholder="https://.../guideline.pdf" className="field" style={{ width: "100%" }} />
              </label>
              <label style={{ gridColumn: "span 2" }}>
                <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>来源页 URL（可选）</div>
                <input value={pageUrl} onChange={(event) => { setPageUrl(event.target.value); resetRunState(); }} placeholder="可选，记录这份 PDF 的来源页" className="field" style={{ width: "100%" }} />
              </label>
            </>
          )}
        </div>
      </div>

      {sourceMode === "upload" && (
        <>
          <div
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => { event.preventDefault(); setDragging(false); handleFile(event.dataTransfer.files[0]); }}
            style={{
              border: `2px dashed ${dragging ? "#93c5fd" : file ? "#86efac" : "#d6d3d1"}`,
              borderRadius: 22,
              padding: "42px 24px",
              textAlign: "center",
              background: dragging ? "#eff6ff" : file ? "#f0fdf4" : "#ffffff",
              cursor: "pointer",
              transition: "all 0.2s",
              marginBottom: 16,
              boxShadow: "0 10px 22px rgba(15, 23, 42, 0.04)",
            }}
          >
            <input ref={inputRef} type="file" accept=".pdf" style={{ display: "none" }} onChange={(event) => handleFile(event.target.files?.[0] ?? null)} />
            <div style={{ fontSize: 28, marginBottom: 10 }}>{file ? "已就绪" : "PDF"}</div>
            {file ? (
              <>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--green)" }}>{file.name}</div>
                <div style={{ marginTop: 6, fontSize: 12, color: "var(--ink2)" }}>文件已选好。点下面按钮才会正式开始处理。</div>
              </>
            ) : (
              <>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)", marginBottom: 4 }}>把 PDF 拖到这里</div>
                <div style={{ fontSize: 13, color: "var(--ink3)" }}>或者点一下，从本地选择文件</div>
              </>
            )}
          </div>

          <div className="card" style={{ padding: 20, borderRadius: 22, marginBottom: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)", marginBottom: 6 }}>本地 PDF 处理</div>
                <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.7 }}>
                  {file ? `将使用 ${file.name} 抽取，大学名会由系统自动识别。` : "先选一份 PDF，再从这里开始处理。"}
                </div>
              </div>
              <button className="btn btn-primary" disabled={!readyToUpload} onClick={() => void runUpload()}>
                {step === "uploading" || step === "extracting" ? "正在处理..." : "用这份 PDF 开始处理"}
              </button>
            </div>
          </div>
        </>
      )}

      {sourceMode === "search" && (
        <div className="card" style={{ padding: 22, borderRadius: 22, marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)", marginBottom: 6 }}>自动搜索候选 PDF</div>
              <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.7 }}>
                固定检索词：<strong>{university || "大学名"} 外国人留学生募集要项 {year || "年份"}</strong>
              </div>
            </div>
            <button className="btn btn-primary" disabled={!readyToSearch} onClick={() => void runSearch()}>
              {step === "searching" ? "正在搜索..." : "先搜索候选"}
            </button>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
            <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.7 }}>
              来源巡检会提醒你“目标官网里出现了疑似新 PDF 链接”，便于及时更新维护注册表。
            </div>
            <button className="btn" disabled={probeLoading || busy} onClick={() => void runProbe()}>
              {probeLoading ? "检查中..." : "检查来源更新"}
            </button>
          </div>

          {probeResult && (
            <div style={{ marginBottom: 12, padding: "12px 14px", border: "1px solid #e5e7eb", borderRadius: 12, background: "#fafaf9" }}>
              <div style={{ fontSize: 12, color: "var(--ink2)", marginBottom: 6 }}>
                巡检时间：{probeResult.checked_at} · 目标 {probeResult.target_count} · 新候选 {probeResult.new_candidate_count} · 错误 {probeResult.error_count}
              </div>
              <div style={{ display: "grid", gap: 6 }}>
                {probeResult.probes
                  .filter((item) => item.is_new_pdf_candidate || item.status === "error")
                  .slice(0, 8)
                  .map((item) => (
                    <div key={`${item.university}-${item.seed_url}`} style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.6, wordBreak: "break-all" }}>
                      <span>[{item.university}] {item.status}</span>
                      {item.top_candidate_pdf && (
                        <>
                          {" · "}
                          <a href={item.top_candidate_pdf} target="_blank" rel="noreferrer" style={{ color: "var(--red)" }}>
                            open candidate pdf
                          </a>
                        </>
                      )}
                    </div>
                  ))}
                {probeResult.probes.every((item) => !item.is_new_pdf_candidate && item.status !== "error") && (
                  <div style={{ fontSize: 12, color: "var(--ink3)" }}>本次未发现明显新链接。</div>
                )}
              </div>
            </div>
          )}

          {searchQuery && (
            <div style={{ marginBottom: 12, fontSize: 12, color: "var(--ink2)" }}>
              本次搜索词：<code>{searchQuery}</code>
            </div>
          )}

          {candidates.length > 0 && (
            <div style={{ display: "grid", gap: 12 }}>
              {candidates.map((candidate, index) => {
                const active = selectedCandidateUrl === candidate.pdf_url;
                return (
                  <label
                    key={candidate.pdf_url}
                    style={{
                      display: "block",
                      border: active ? "1px solid #cbd5e1" : "1px solid #e5e7eb",
                      background: active ? "#f8fafc" : "#ffffff",
                      borderRadius: 16,
                      padding: 16,
                      cursor: "pointer",
                    }}
                  >
                    <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                      <input type="radio" name="pdf-candidate" checked={active} onChange={() => setSelectedCandidateUrl(candidate.pdf_url)} style={{ marginTop: 3 }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 6 }}>
                          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)" }}>
                            候选 {index + 1}：{candidate.title || candidate.pdf_url}
                          </div>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            <div className={candidate.is_official ? "badge badge-green" : "badge badge-amber"}>{candidateTrustLabel(candidate)}</div>
                            <div className="badge badge-gray">{candidateKindLabel(candidate)}</div>
                            <div className="badge badge-gray">匹配分：{candidate.score}</div>
                          </div>
                        </div>
                        {candidate.host && <div style={{ fontSize: 12, color: "var(--ink3)", lineHeight: 1.7, marginBottom: 4 }}>域名：{candidate.host}</div>}
                        <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.7, wordBreak: "break-all" }}>PDF：{candidate.pdf_url}</div>
                        {candidate.page_url && candidate.page_url !== candidate.pdf_url && <div style={{ fontSize: 12, color: "var(--ink3)", lineHeight: 1.7, wordBreak: "break-all", marginTop: 4 }}>来源页：{candidate.page_url}</div>}
                        {candidate.registry_note && <div style={{ fontSize: 12, color: "var(--ink3)", lineHeight: 1.7, marginTop: 4 }}>维护说明：{candidate.registry_note}</div>}
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
                          <a href={candidate.pdf_url} target="_blank" rel="noreferrer" className="btn" style={{ display: "inline-flex", alignItems: "center", textDecoration: "none" }} onClick={(event) => event.stopPropagation()}>
                            预览 PDF
                          </a>
                          {candidate.page_url && candidate.page_url !== candidate.pdf_url && (
                            <a href={candidate.page_url} target="_blank" rel="noreferrer" className="btn" style={{ display: "inline-flex", alignItems: "center", textDecoration: "none" }} onClick={(event) => event.stopPropagation()}>
                              查看来源页
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  </label>
                );
              })}

              <div style={{ marginTop: 4, display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center", paddingTop: 8 }}>
                <div style={{ fontSize: 12, color: "var(--ink2)" }}>
                  必须先由你确认候选，系统才会继续下载和抽取，不会自动入库。
                </div>
                <button className="btn btn-primary" disabled={!readyToConfirmCandidate} onClick={() => selectedCandidate && void processPdfCandidate(selectedCandidate)}>
                  {step === "downloading" || step === "extracting" ? "正在处理..." : "确认这份并开始处理"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {sourceMode === "direct" && (
        <div className="card" style={{ padding: 22, borderRadius: 22, marginBottom: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)", marginBottom: 8 }}>手动 PDF 处理通道</div>
          <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.7, marginBottom: 14 }}>
            当你手里已有准确 PDF 链接时，优先走这条，最稳。
          </div>
          <button className="btn btn-primary" disabled={!readyToDirectRun} onClick={() => void runDirectPdf()}>
            {step === "downloading" || step === "extracting" ? "正在处理..." : "用这份 PDF 直接处理"}
          </button>
        </div>
      )}

      {step === "done" && result && (
        <div style={{ background: "#ffffff", border: "1px solid #d1fae5", borderRadius: 22, padding: "22px 24px", boxShadow: "0 12px 26px rgba(16, 185, 129, 0.08)" }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: "var(--green)", marginBottom: 8 }}>结果已可进入复查</div>
          <div style={{ fontSize: 13, color: "var(--ink2)", lineHeight: 1.8, marginBottom: 16 }}>
            共整理出 <strong style={{ color: "var(--ink)" }}>{result.records}</strong> 条记录。
            {result.university ? ` 系统识别大学为 ${result.university}。` : " 大学名需你在复查页人工确认。"}
            {result.failed > 0 ? ` 其中有 ${result.failed} 页需要额外留意。` : " 当前没有明显失败页。"}
            {result.file_name ? ` 文件：${result.file_name}。` : ""}
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button className="btn btn-green" onClick={() => onDone(result.doc_id)}>前往复查</button>
            {result.source_url && (
              <a href={result.source_url} target="_blank" rel="noreferrer" className="btn" style={{ display: "inline-flex", alignItems: "center", textDecoration: "none" }}>
                查看来源
              </a>
            )}
          </div>
        </div>
      )}

      {step === "error" && (
        <div style={{ background: "#fff7f7", border: "1px solid #fecaca", borderRadius: 20, padding: "16px 18px", fontSize: 13, color: "var(--red)", lineHeight: 1.7 }}>
          {error || "本次处理未成功，请检查输入后重试。"}
        </div>
      )}

      <div style={{ marginTop: 18, fontSize: 12, color: "var(--ink3)", lineHeight: 1.8 }}>
        建议顺序：已有 PDF 就直接上传；没有就先搜索候选再确认；已知准确链接就走手动通道。
      </div>
    </div>
  );
}
