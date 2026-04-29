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
import type { FetchPdfCandidate, FetchPdfProbeResponse, FetchPdfTarget } from "../types";

interface Props {
  onDone: (docId: number) => void;
}

type SourceMode = "upload" | "search" | "direct";
type Step = "idle" | "searching" | "downloading" | "uploading" | "extracting" | "done" | "error";

interface RunResult {
  doc_id: number;
  records: number;
  failed: number;
  university?: string;
  file_name?: string;
  source_url?: string;
}

const MODE_META: Record<SourceMode, { label: string; hint: string }> = {
  upload: { label: "本地上传", hint: "上传现有 PDF" },
  search: { label: "检索来源", hint: "查找候选 PDF" },
  direct: { label: "指定链接", hint: "直接处理地址" },
};

function stepText(step: Step) {
  if (step === "searching") return "检索中";
  if (step === "downloading") return "下载中";
  if (step === "uploading") return "上传中";
  if (step === "extracting") return "处理中";
  if (step === "done") return "已完成";
  if (step === "error") return "未完成";
  return "等待开始";
}

function stepProgress(step: Step) {
  if (step === "searching") return 20;
  if (step === "downloading") return 38;
  if (step === "uploading") return 32;
  if (step === "extracting") return 72;
  if (step === "done") return 100;
  if (step === "error") return 100;
  return 0;
}

function stepDetail(step: Step) {
  if (step === "searching") return "正在查找募集要項 PDF 候选。";
  if (step === "downloading") return "正在下载 PDF 并保存到本地数据目录。";
  if (step === "uploading") return "正在上传并登记 PDF 文件。";
  if (step === "extracting") return "AI 正在读取 PDF、抽取字段并写入待复核区。复杂 PDF 可能需要几分钟。";
  if (step === "done") return "处理完成，可以进入人工复核。";
  if (step === "error") return "处理未完成，请查看错误信息后重试。";
  return "选择来源后开始处理。";
}

function sourceKindText(candidate: FetchPdfCandidate) {
  if (candidate.source_kind === "registry_pdf") return "登记 PDF";
  if (candidate.source_kind === "registry_page_pdf") return "来源页 PDF";
  if (candidate.source_kind === "direct_pdf") return "直链";
  return "自动发现";
}

function sourceTrustText(candidate: FetchPdfCandidate) {
  if (candidate.source_origin === "maintained_registry") return "已维护";
  if (candidate.is_official) return "疑似官网";
  return "待确认";
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

  function clearAll() {
    setSelectedTarget("");
    setFile(null);
    setUniversity("");
    setYear("2026");
    setPageUrl("");
    setPdfUrl("");
    setProbeResult(null);
    resetRunState();
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
        setError("没有找到可用的 PDF 候选，请调整条件后重试。");
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

  const busy = step === "searching" || step === "downloading" || step === "uploading" || step === "extracting";
  const selectedCandidate = candidates.find((item) => item.pdf_url === selectedCandidateUrl) || null;
  const progress = stepProgress(step);

  const runSummary = useMemo(
    () => [
      { label: "来源", value: MODE_META[sourceMode].label },
      { label: "进度", value: stepText(step) },
      { label: "年份", value: year || "未填写" },
    ],
    [sourceMode, step, year],
  );

  return (
    <div className="page-shell">
      <section className="hero-panel">
        <div className="split-row split-row-start">
          <div>
            <div className="section-kicker">导入</div>
            <h2 className="section-title">整理新的招生来源</h2>
          <p className="section-copy">导入募集要项，整理完成后进入复核。</p>
          </div>
          <div className="hero-metrics">
            {runSummary.map((item) => (
              <div key={item.label} className="metric-card">
                <span className="metric-label">{item.label}</span>
                <strong className="metric-value">{item.value}</strong>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="content-grid">
        <aside className="sidebar-panel">
          <div className="toolbar-shell">
            <div className="sidebar-section-label">入口</div>
            <div className="split-row" style={{ marginBottom: 12 }}>
              <div>
                <h3 className="panel-title">导入方式</h3>
            <p className="panel-copy">选择一种导入方式。</p>
              </div>
              <button className="btn btn-ghost" onClick={clearAll} type="button">
                清空
              </button>
            </div>

            <div className="mode-switch">
              {(["upload", "search", "direct"] as SourceMode[]).map((mode) => (
                <button
                  key={mode}
                  className={`mode-tile${sourceMode === mode ? " is-active" : ""}`}
                  onClick={() => {
                    setSourceMode(mode);
                    resetRunState();
                  }}
                  type="button"
                >
                  <span className="mode-title">{MODE_META[mode].label}</span>
                  <span className="mode-copy">{MODE_META[mode].hint}</span>
                </button>
              ))}
            </div>

            <div className="list-stack section-stack">
              {sourceMode !== "upload" && (
                <label className="field-wrap">
                  <span className="field-label">学校名称</span>
                  <input
                    value={university}
                    onChange={(event) => {
                      setUniversity(event.target.value);
                      resetRunState();
                    }}
                    placeholder="例如：明治大学"
                    className="field"
                  />
                </label>
              )}

              <label className="field-wrap">
                <span className="field-label">招生年份</span>
                <input
                  value={year}
                  onChange={(event) => {
                    setYear(event.target.value);
                    resetRunState();
                  }}
                  placeholder="2026"
                  className="field"
                />
              </label>

              {sourceMode === "search" && (
                <>
                  <label className="field-wrap">
                    <span className="field-label">预设学校</span>
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
                      className="field field-select"
                    >
                      <option value="">可选</option>
                      {targets.map((target) => (
                        <option key={target.name} value={target.name}>
                          {target.name}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="field-wrap">
                    <span className="field-label">来源页</span>
                    <input
                      value={pageUrl}
                      onChange={(event) => {
                        setPageUrl(event.target.value);
                        resetRunState();
                      }}
                      placeholder="可选"
                      className="field"
                    />
                  </label>

                  <button className="btn btn-primary" disabled={!university || busy} onClick={() => void runSearch()} type="button">
                    {step === "searching" ? "检索中..." : "检索候选 PDF"}
                  </button>
                  <button className="btn btn-ghost" disabled={probeLoading || busy} onClick={() => void runProbe()} type="button">
                    {probeLoading ? "检查中..." : "检查来源"}
                  </button>
                </>
              )}

              {sourceMode === "direct" && (
                <>
                  <label className="field-wrap">
                    <span className="field-label">PDF 链接</span>
                    <input
                      value={pdfUrl}
                      onChange={(event) => {
                        setPdfUrl(event.target.value);
                        resetRunState();
                      }}
                      placeholder="https://.../guide.pdf"
                      className="field"
                    />
                  </label>
                  <label className="field-wrap">
                    <span className="field-label">来源页</span>
                    <input
                      value={pageUrl}
                      onChange={(event) => {
                        setPageUrl(event.target.value);
                        resetRunState();
                      }}
                      placeholder="可选"
                      className="field"
                    />
                  </label>
                  <button className="btn btn-primary" disabled={!university || !pdfUrl || busy} onClick={() => void runDirectPdf()} type="button">
                    {busy ? "处理中..." : "开始处理"}
                  </button>
                </>
              )}

              {sourceMode === "upload" && (
                <button className="btn btn-primary" disabled={!file || busy} onClick={() => void runUpload()} type="button">
                  {busy ? "处理中..." : "开始处理"}
                </button>
              )}
            </div>
          </div>
        </aside>

        <div className="item-detail">
          {(busy || step === "done" || step === "error") && (
            <section className={`progress-card${busy ? " is-running" : ""}${step === "error" ? " is-error" : ""}`}>
              <div className="split-row">
                <div>
                  <div className="card-kicker">处理进度</div>
                  <h3 className="panel-title">{stepText(step)}</h3>
                  <p className="panel-copy">{stepDetail(step)}</p>
                </div>
                <span className={step === "error" ? "badge badge-red" : step === "done" ? "badge badge-green" : "badge badge-blue"}>
                  {progress}%
                </span>
              </div>
              <div className="progress-track" aria-label="PDF 处理进度">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
            </section>
          )}

          {sourceMode === "upload" && (
            <section
              className={`dropzone${dragging ? " is-dragging" : ""}${file ? " is-filled" : ""}`}
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
            >
              <input
                ref={inputRef}
                type="file"
                accept=".pdf"
                style={{ display: "none" }}
                onChange={(event) => handleFile(event.target.files?.[0] ?? null)}
              />
              <div className="dropzone-badge">{file ? "已选择" : "PDF"}</div>
              <h3 className="dropzone-title">{file ? file.name : "投递招生 PDF"}</h3>
              <p className="dropzone-copy">{file ? "文件已就绪，可以开始处理。" : "拖入文件，或点按这里选择本地 PDF。"}</p>
            </section>
          )}

          {probeResult && sourceMode === "search" && (
            <section className="detail-shell">
              <div className="detail-header">
                <div>
              <div className="card-kicker">结果预览</div>
                  <h3 className="panel-title">已更新来源概况</h3>
                </div>
                <span className="badge badge-gray">{probeResult.checked_at}</span>
              </div>
              <div className="results-grid results-grid-quiet">
                <div className="result-card">
                  <span className="metric-label">目标学校</span>
                  <strong className="metric-value">{probeResult.target_count}</strong>
                </div>
                <div className="result-card">
                  <span className="metric-label">新增候选</span>
                  <strong className="metric-value">{probeResult.new_candidate_count}</strong>
                </div>
                <div className="result-card">
                  <span className="metric-label">异常</span>
                  <strong className="metric-value">{probeResult.error_count}</strong>
                </div>
              </div>
            </section>
          )}

          {searchQuery && <div className="message-box info">检索词：{searchQuery}</div>}

          {sourceMode === "search" && candidates.length > 0 && (
            <section className="detail-shell">
              <div className="detail-header">
                <div>
              <div className="card-kicker">可用文件</div>
                  <h3 className="panel-title">选择要处理的 PDF</h3>
                </div>
                <span className="badge badge-gray">{candidates.length} 条</span>
              </div>

              <div className="document-list">
                {candidates.map((candidate, index) => {
                  const active = selectedCandidateUrl === candidate.pdf_url;
                  return (
                    <button
                      key={candidate.pdf_url}
                      className={`item-card${active ? " is-active" : ""}`}
                      onClick={() => setSelectedCandidateUrl(candidate.pdf_url)}
                      type="button"
                    >
                      <div className="detail-header">
                        <div>
                          <h4 className="item-title">候选来源 {String(index + 1).padStart(2, "0")}</h4>
                          <p className="item-subtitle">{candidate.title || candidate.pdf_url}</p>
                        </div>
                        <div className="item-meta">
                          <span className={candidate.is_official ? "badge badge-green" : "badge badge-amber"}>
                            {sourceTrustText(candidate)}
                          </span>
                          <span className="badge badge-gray">{sourceKindText(candidate)}</span>
                        </div>
                      </div>

                      <div className="summary-box summary-box-inline">
                        <div className="field-label">PDF 地址</div>
                    <div className="secondary-note">点击后先预览，再开始整理。</div>
                      </div>

                      <div className="inline-actions">
                        <span className="badge badge-blue">分数 {candidate.score}</span>
                        {candidate.host && <span className="badge badge-gray">{candidate.host}</span>}
                      </div>
                    </button>
                  );
                })}
              </div>

              {selectedCandidate && (
                <div className="summary-box summary-box-feature">
                  <div className="field-label">已选来源</div>
                  <div className="summary-title">{selectedCandidate.title || "候选来源"}</div>
              <p className="secondary-note">确认无误后开始整理。</p>
                  <div className="inline-actions">
                    <button className="btn btn-primary" disabled={busy} onClick={() => void processPdfCandidate(selectedCandidate)} type="button">
                      {busy ? "处理中..." : "处理当前来源"}
                    </button>
                  </div>
                </div>
              )}
            </section>
          )}

          {step === "done" && result && (
            <section className="detail-shell detail-shell-feature">
              <div className="detail-header">
                <div>
                  <div className="card-kicker">处理完成</div>
                  <h3 className="panel-title">已整理出可复核内容</h3>
                  <p className="secondary-note">
                    共整理出 {result.records} 条记录
                    {result.university ? `，识别学校为 ${result.university}` : ""}
                    {result.failed > 0 ? `，其中 ${result.failed} 页建议重点复核。` : "。"}
                  </p>
                </div>
                <span className="badge badge-green">可进入人工复核</span>
              </div>

              <div className="results-grid">
                <div className="result-card">
                  <span className="metric-label">记录数</span>
                  <strong className="metric-value">{result.records}</strong>
                </div>
                <div className="result-card">
                  <span className="metric-label">重点页</span>
                  <strong className="metric-value">{result.failed}</strong>
                </div>
                <div className="result-card">
                  <span className="metric-label">状态</span>
                  <strong className="metric-value">已就绪</strong>
                </div>
              </div>

              <div className="inline-actions">
                <button className="btn btn-primary btn-prominent" onClick={() => onDone(result.doc_id)} type="button">
                  进入人工复核
                </button>
                {result.source_url && (
                  <a href={result.source_url} target="_blank" rel="noreferrer" className="btn btn-ghost">
                    打开来源
                  </a>
                )}
              </div>
            </section>
          )}

          {!result && !candidates.length && sourceMode !== "upload" && !error && (
            <div className="empty-state empty-state-quiet">
              <div className="card-kicker">等待导入</div>
              <h3 className="panel-title">从左侧选择一种入口</h3>
            <p className="panel-copy">导入文件后，这里会显示下一步。</p>
            </div>
          )}

          {step === "error" && <div className="message-box error">{error || "本次处理没有成功，请检查输入后重试。"}</div>}
        </div>
      </section>
    </div>
  );
}
