import { useEffect, useMemo, useRef, useState } from "react";
import {
  extractPdf,
  fetchPdf,
  getFetchTargets,
  searchFetchPdf,
  toErrorMessage,
  uploadPdf,
} from "../api/client";
import type { FetchPdfCandidate, FetchPdfTarget } from "../types";

interface Props {
  onDone: (docId: number) => void;
}

type SourceMode = "upload" | "search" | "direct";
type Step = "idle" | "searching" | "downloading" | "uploading" | "extracting" | "done" | "error";

interface RunResult {
  doc_id: number;
  records: number;
  failed: number;
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
  if (mode === "direct") return "用你给的 PDF 链接直接处理";
  return "准备上传并抽取";
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
    if (!university) {
      const inferredName = nextFile.name
        .replace(/[_-]/g, " ")
        .replace(/\.pdf$/i, "")
        .replace(/\d{4}/g, "")
        .trim();
      if (inferredName) setUniversity(inferredName);
    }
  }

  async function runUpload() {
    if (!file || !university) return;
    setError("");
    setResult(null);
    try {
      setStep("uploading");
      const uploaded = await uploadPdf(file);
      setStep("extracting");
      const extracted = await extractPdf({
        file_name: uploaded.file_name,
        university,
        year,
      });
      setResult({
        doc_id: extracted.doc_id,
        records: extracted.records,
        failed: extracted.failed_pages?.length ?? 0,
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
        setError("这次没有找到可用的募集要项 PDF。你可以改学校名、补来源页，或者直接走手动 PDF 链接。");
        setStep("error");
      }
    } catch (nextError) {
      setError(toErrorMessage(nextError));
      setStep("error");
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
        file_name: fetched.file_name,
        source_url: fetched.source_url || pdfUrl,
      });
      setStep("done");
    } catch (nextError) {
      setError(toErrorMessage(nextError));
      setStep("error");
    }
  }

  const busy = step === "searching" || step === "downloading" || step === "uploading" || step === "extracting";
  const readyToUpload = Boolean(file && university && !busy);
  const readyToSearch = Boolean(university && !busy);
  const selectedCandidate = candidates.find((item) => item.pdf_url === selectedCandidateUrl) || null;
  const readyToConfirmCandidate = Boolean(selectedCandidate && !busy);
  const readyToDirectRun = Boolean(university && pdfUrl && !busy);

  const statusBlock = useMemo(() => {
    if (step === "done" && result) {
      return {
        tone: "success" as const,
        title: `已经整理出 ${result.records} 条记录`,
        description:
          result.failed > 0
            ? `其中有 ${result.failed} 页没有顺利处理，进入复查后建议优先留意。`
            : "抽取已经完成，可以直接进入复查。",
      };
    }
    if (step === "error") {
      return {
        tone: "danger" as const,
        title: "这一步卡住了",
        description: "通常是来源页、PDF 链接或文件本身的问题。你可以换入口继续，不会影响别的流程。",
      };
    }
    if (step === "searching") {
      return {
        tone: "info" as const,
        title: "我正在帮你找候选 PDF",
        description: "这一步只负责找候选，不会直接入库。你确认之后我才会继续处理。",
      };
    }
    if (step === "downloading") {
      return {
        tone: "info" as const,
        title: "我正在获取你确认的 PDF",
        description: "拿到文件后会继续进入抽取。",
      };
    }
    if (step === "uploading") {
      return {
        tone: "info" as const,
        title: "PDF 已接收",
        description: "正在把文件送进系统准备抽取。",
      };
    }
    if (step === "extracting") {
      return {
        tone: "info" as const,
        title: "AI 正在读这份募集要项",
        description: "系统会把内容整理成可复查的 staging 记录。",
      };
    }
    return {
      tone: "neutral" as const,
      title: sourceMode === "search" ? "先找候选，再由你决定处理哪一份" : "准备开始",
      description:
        sourceMode === "upload"
          ? "适合你已经拿到 PDF 的情况。"
          : sourceMode === "direct"
            ? "适合你已经拿到直接 PDF 链接，不想再让系统搜索。"
            : "系统会优先用固定检索词搜索，例如：明治大学 外国人留学生募集要項 2026。",
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
    {
      key: "upload",
      title: "本地上传 PDF",
      desc: "你已经拿到文件时，用这条最快。",
    },
    {
      key: "search",
      title: "自动搜索募集要项",
      desc: "系统先搜候选 PDF，你看过再决定处理哪一份。",
    },
    {
      key: "direct",
      title: "手动填写 PDF 链接",
      desc: "你已经知道准确的 PDF 链接时，用这条最稳。",
    },
  ];

  return (
    <div style={{ maxWidth: 860 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 10, letterSpacing: "0.2em", textTransform: "uppercase", color: "var(--red)", marginBottom: 10, fontWeight: 600 }}>
          Step 1
        </div>
        <h1 style={{ fontSize: 32, fontWeight: 700, letterSpacing: -0.4, lineHeight: 1.15, margin: "0 0 10px" }}>跑数据</h1>
        <p style={{ fontSize: 14, color: "var(--ink2)", lineHeight: 1.75, margin: 0 }}>
          这里负责把 PDF 送进系统。你可以直接上传文件、让系统先搜索候选募集要项，或者自己贴准确的 PDF 链接。
        </p>
      </div>

      <div
        style={{
          background: statusStyle.background,
          border: statusStyle.border,
          borderRadius: 18,
          padding: "18px 20px",
          boxShadow: "0 10px 28px rgba(15, 23, 42, 0.05)",
          marginBottom: 18,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "flex-start" }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: statusStyle.accent, marginBottom: 6 }}>{statusBlock.title}</div>
            <div style={{ fontSize: 13, color: "var(--ink2)", lineHeight: 1.7 }}>{statusBlock.description}</div>
          </div>
          <div style={{ display: "grid", gap: 6, minWidth: 220 }}>
            <div className="badge badge-gray">模式：{modeTitle(sourceMode)}</div>
            <div className="badge badge-gray">大学：{university || "还没填写"}</div>
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
          <label>
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>大学名称</div>
            <input
              value={university}
              onChange={(event) => {
                setUniversity(event.target.value);
                resetRunState();
              }}
              placeholder="例如：明治大学"
              className="field"
              style={{ width: "100%" }}
            />
          </label>
          <label>
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>年度</div>
            <input
              value={year}
              onChange={(event) => {
                setYear(event.target.value);
                resetRunState();
              }}
              placeholder="2026"
              className="field"
              style={{ width: "100%" }}
            />
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
                    <option key={target.name} value={target.name}>
                      {target.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>募集页 URL</div>
                <input
                  value={pageUrl}
                  onChange={(event) => {
                    setPageUrl(event.target.value);
                    resetRunState();
                  }}
                  placeholder="可选，补充官网招生页会更稳"
                  className="field"
                  style={{ width: "100%" }}
                />
              </label>
            </>
          )}

          {sourceMode === "direct" && (
            <>
              <label style={{ gridColumn: "span 2" }}>
                <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>PDF 直链</div>
                <input
                  value={pdfUrl}
                  onChange={(event) => {
                    setPdfUrl(event.target.value);
                    resetRunState();
                  }}
                  placeholder="https://.../guideline.pdf"
                  className="field"
                  style={{ width: "100%" }}
                />
              </label>
              <label style={{ gridColumn: "span 2" }}>
                <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>来源页 URL（选填）</div>
                <input
                  value={pageUrl}
                  onChange={(event) => {
                    setPageUrl(event.target.value);
                    resetRunState();
                  }}
                  placeholder="可选，记录这份 PDF 是从哪个招生页来的"
                  className="field"
                  style={{ width: "100%" }}
                />
              </label>
            </>
          )}
        </div>
      </div>

      {sourceMode === "upload" && (
        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            handleFile(event.dataTransfer.files[0]);
          }}
          style={{
            border: `2px dashed ${dragging ? "#93c5fd" : file ? "#86efac" : "#d6d3d1"}`,
            borderRadius: 22,
            padding: "42px 24px",
            textAlign: "center",
            background: dragging ? "#eff6ff" : file ? "#f0fdf4" : "#ffffff",
            cursor: "pointer",
            transition: "all 0.2s",
            marginBottom: 20,
            boxShadow: "0 10px 22px rgba(15, 23, 42, 0.04)",
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            style={{ display: "none" }}
            onChange={(event) => handleFile(event.target.files?.[0] ?? null)}
          />
          <div style={{ fontSize: 28, marginBottom: 10 }}>{file ? "已就绪" : "PDF"}</div>
          {file ? (
            <>
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--green)" }}>{file.name}</div>
              <div style={{ marginTop: 6, fontSize: 12, color: "var(--ink2)" }}>确认后我会直接上传并开始抽取。</div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)", marginBottom: 4 }}>把 PDF 拖到这里</div>
              <div style={{ fontSize: 13, color: "var(--ink3)" }}>或者点一下，从本地挑一个文件</div>
            </>
          )}
        </div>
      )}

      {sourceMode === "search" && (
        <div className="card" style={{ padding: 22, borderRadius: 22, marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 14 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)", marginBottom: 6 }}>自动搜索候选 PDF</div>
              <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.7 }}>
                系统会优先用固定检索词搜索：<strong>{university || "大学名"} 外国人留学生募集要項 {year || "年份"}</strong>
              </div>
            </div>
            <button className="btn btn-primary" disabled={!readyToSearch} onClick={() => void runSearch()}>
              {step === "searching" ? "正在搜索..." : "先搜索候选"}
            </button>
          </div>

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
                      <input
                        type="radio"
                        name="pdf-candidate"
                        checked={active}
                        onChange={() => setSelectedCandidateUrl(candidate.pdf_url)}
                        style={{ marginTop: 3 }}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 6 }}>
                          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)" }}>
                            候选 {index + 1}：{candidate.title || candidate.pdf_url}
                          </div>
                          <div className="badge badge-gray">匹配分：{candidate.score}</div>
                        </div>
                        <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.7, wordBreak: "break-all" }}>
                          PDF：{candidate.pdf_url}
                        </div>
                        {candidate.page_url && candidate.page_url !== candidate.pdf_url && (
                          <div style={{ fontSize: 12, color: "var(--ink3)", lineHeight: 1.7, wordBreak: "break-all", marginTop: 4 }}>
                            来源页：{candidate.page_url}
                          </div>
                        )}
                      </div>
                    </div>
                  </label>
                );
              })}

              <div
                style={{
                  marginTop: 4,
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  flexWrap: "wrap",
                  alignItems: "center",
                  paddingTop: 8,
                }}
              >
                <div style={{ fontSize: 12, color: "var(--ink2)" }}>
                  先由你确认候选，再继续下载和抽取；不会因为自动搜索直接把结果写进去。
                </div>
                <button
                  className="btn btn-primary"
                  disabled={!readyToConfirmCandidate}
                  onClick={() => selectedCandidate && void processPdfCandidate(selectedCandidate)}
                >
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
            如果你已经知道准确的 PDF 链接，这条最稳，也能绕开自动搜索不准的问题。
          </div>
          <button className="btn btn-primary" disabled={!readyToDirectRun} onClick={() => void runDirectPdf()}>
            {step === "downloading" || step === "extracting" ? "正在处理..." : "用这份 PDF 直接处理"}
          </button>
        </div>
      )}

      {step === "done" && result && (
        <div
          style={{
            background: "#ffffff",
            border: "1px solid #d1fae5",
            borderRadius: 22,
            padding: "22px 24px",
            boxShadow: "0 12px 26px rgba(16, 185, 129, 0.08)",
          }}
        >
          <div style={{ fontSize: 18, fontWeight: 700, color: "var(--green)", marginBottom: 8 }}>这份结果已经可以开始复查了</div>
          <div style={{ fontSize: 13, color: "var(--ink2)", lineHeight: 1.8, marginBottom: 16 }}>
            这次一共整理出 <strong style={{ color: "var(--ink)" }}>{result.records}</strong> 条记录。
            {result.failed > 0 ? ` 其中有 ${result.failed} 页需要你额外留意。` : " 目前没有明显失败页。"}
            {result.file_name ? ` 文件名是 ${result.file_name}。` : ""}
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button className="btn btn-green" onClick={() => onDone(result.doc_id)}>
              前往复查
            </button>
            {result.source_url && (
              <a
                href={result.source_url}
                target="_blank"
                rel="noreferrer"
                className="btn"
                style={{ display: "inline-flex", alignItems: "center", textDecoration: "none" }}
              >
                查看来源
              </a>
            )}
          </div>
        </div>
      )}

      {step === "error" && (
        <div
          style={{
            background: "#fff7f7",
            border: "1px solid #fecaca",
            borderRadius: 20,
            padding: "16px 18px",
            fontSize: 13,
            color: "var(--red)",
            lineHeight: 1.7,
          }}
        >
          {error || "这次处理没有成功，请检查输入后再试一次。"}
        </div>
      )}

      <div style={{ marginTop: 18, fontSize: 12, color: "var(--ink3)", lineHeight: 1.8 }}>
        建议顺序：如果你手头已经有 PDF，就直接上传；如果没有，就先用“自动搜索募集要项”找候选，再确认；如果你已经知道准确 PDF 链接，就直接走手动通道。
      </div>
    </div>
  );
}
