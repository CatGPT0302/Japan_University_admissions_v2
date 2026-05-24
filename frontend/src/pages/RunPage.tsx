import { useRef, useState } from "react";
import { runAgentWorkflow, toErrorMessage, uploadPdf } from "../api/client";
import type { AgentRunResponse, FetchPdfCandidate } from "../types";

interface Props {
  onDone: (docId: number) => void;
}

type Step = "idle" | "uploading" | "running" | "needs_source" | "done" | "error";

function progress(step: Step) {
  if (step === "uploading") return 24;
  if (step === "running") return 68;
  if (step === "needs_source") return 38;
  if (step === "done") return 100;
  if (step === "error") return 100;
  return 0;
}

function stepTitle(step: Step) {
  if (step === "uploading") return "正在上传 PDF";
  if (step === "running") return "正在整理资料";
  if (step === "needs_source") return "需要确认 PDF 来源";
  if (step === "done") return "已送去核对";
  if (step === "error") return "处理失败";
  return "等待开始";
}

function candidateTitle(candidate: FetchPdfCandidate, index: number) {
  return candidate.title || candidate.pdf_url || `候选 ${index + 1}`;
}

function isConfirmation(result: AgentRunResponse): result is Extract<AgentRunResponse, { status: "needs_source_confirmation" }> {
  return result.status === "needs_source_confirmation";
}

export default function RunPage({ onDone }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [year, setYear] = useState("2027");
  const [university, setUniversity] = useState("");
  const [pdfUrl, setPdfUrl] = useState("");
  const [pageUrl, setPageUrl] = useState("");
  const [step, setStep] = useState<Step>("idle");
  const [message, setMessage] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [docId, setDocId] = useState<number | null>(null);
  const [candidates, setCandidates] = useState<FetchPdfCandidate[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const canRun = Boolean(file || pdfUrl.trim() || pageUrl.trim() || university.trim());
  const isBusy = step === "uploading" || step === "running";

  function resetResult() {
    setStep("idle");
    setMessage("");
    setWarnings([]);
    setError("");
    setDocId(null);
    setCandidates([]);
  }

  function handleFile(nextFile: File | null) {
    if (!nextFile || !nextFile.name.toLowerCase().endsWith(".pdf")) return;
    setFile(nextFile);
    resetResult();
  }

  function applyResult(result: AgentRunResponse) {
    if (isConfirmation(result)) {
      setCandidates(result.candidates || []);
      setWarnings(["来源候选接近，请先确认要读取的 PDF。"]);
      setMessage("");
      setStep("needs_source");
      return;
    }
    setDocId(result.doc_id);
    setMessage(result.quality_message || `已整理出 ${result.records} 条待核对内容。`);
    setWarnings(result.warnings || []);
    setCandidates([]);
    setStep("done");
  }

  async function run(selected?: FetchPdfCandidate) {
    setError("");
    setMessage("");
    setWarnings([]);
    setDocId(null);
    try {
      let fileName = "";
      if (file && !selected && !pdfUrl.trim() && !pageUrl.trim()) {
        setStep("uploading");
        const uploaded = await uploadPdf(file);
        fileName = uploaded.file_name;
      }

      setStep("running");
      const result = await runAgentWorkflow({
        file_name: fileName,
        pdf_url: selected?.pdf_url || pdfUrl.trim(),
        page_url: selected?.page_url || pageUrl.trim(),
        university: university.trim(),
        year,
      });
      applyResult(result);
    } catch (nextError) {
      setError(toErrorMessage(nextError));
      setStep("error");
    }
  }

  return (
    <div className="page-shell">
      <section className="hero-panel">
        <div className="split-row split-row-start">
          <div>
            <div className="section-kicker">资料整理</div>
            <h2 className="section-title">收集招生资料，整理待核对内容</h2>
            <p className="section-copy">上传 PDF，或输入来源信息让系统自动查找。整理结果会先送去核对，确认后再保存为正式资料。</p>
          </div>
        </div>
      </section>

      <nav className="local-secondary-nav" aria-label="资料整理步骤">
        <button className="is-active" type="button">
          <strong>导入资料</strong>
          <span>上传 PDF 或填写来源</span>
        </button>
        <button type="button">
          <strong>整理初稿</strong>
          <span>页面会先整理成可核对内容</span>
        </button>
        <button type="button">
          <strong>确认保存</strong>
          <span>核对后进入正式资料</span>
        </button>
      </nav>

      <section className="content-grid">
        <aside className="sidebar-panel">
          <div className="toolbar-shell">
            <h3 className="panel-title">来源</h3>
            <p className="panel-copy">可以上传本地 PDF，也可以贴 PDF 地址、官网页面地址，或输入大学和年度让系统查找。</p>

            <div
              className="dropzone"
              onClick={() => inputRef.current?.click()}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                handleFile(event.dataTransfer.files?.[0] ?? null);
              }}
              role="button"
              tabIndex={0}
            >
              <input
                ref={inputRef}
                hidden
                type="file"
                accept="application/pdf"
                onChange={(event) => handleFile(event.target.files?.[0] ?? null)}
              />
              <div className="card-kicker">PDF</div>
              <h3 className="panel-title">{file ? file.name : "点击或拖拽上传 PDF"}</h3>
              <p className="panel-copy">已有 PDF 时会直接读取这份文件。</p>
            </div>

            <div className="list-stack">
              <label className="field-wrap">
                <span className="field-label">大学名称</span>
                <input className="field" value={university} onChange={(event) => setUniversity(event.target.value)} placeholder="例如：早稻田大学" />
              </label>
              <label className="field-wrap">
                <span className="field-label">入学年度</span>
                <input className="field" value={year} onChange={(event) => setYear(event.target.value)} placeholder="2027" />
              </label>
              <label className="field-wrap">
                <span className="field-label">PDF 地址</span>
                <input className="field" value={pdfUrl} onChange={(event) => setPdfUrl(event.target.value)} placeholder="https://.../admission.pdf" />
              </label>
              <label className="field-wrap">
                <span className="field-label">官网页面地址</span>
                <input className="field" value={pageUrl} onChange={(event) => setPageUrl(event.target.value)} placeholder="https://.../admissions" />
              </label>
              <button className="btn btn-primary" disabled={!canRun || isBusy} onClick={() => void run()} type="button">
                {isBusy ? "正在整理..." : "开始整理资料"}
              </button>
            </div>
          </div>
        </aside>

        <div className="item-detail">
          <div className={`progress-card${isBusy ? " is-running" : ""}${step === "error" ? " is-error" : ""}`}>
            <div className="split-row">
              <div>
                <div className="card-kicker">当前状态</div>
                <h3 className="panel-title">{stepTitle(step)}</h3>
                <p className="panel-copy">
                  {step === "needs_source"
                    ? "多个来源都可能匹配，请选择一个候选 PDF 后继续。"
                    : "系统会处理来源、整理内容，并把初稿送去人工核对。"}
                </p>
              </div>
              <span className="badge badge-blue">{progress(step)}%</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${progress(step)}%` }} />
            </div>
          </div>

          {candidates.length > 0 && (
            <div className="summary-box">
              <h3 className="panel-title">确认 PDF 来源</h3>
              <div className="list-stack">
                {candidates.map((candidate, index) => (
                  <button className="queue-item" key={`${candidate.pdf_url}-${index}`} onClick={() => void run(candidate)} type="button">
                    <div>
                      <strong>{candidateTitle(candidate, index)}</strong>
                      <p>{candidate.pdf_url}</p>
                    </div>
                    <span className="badge badge-gray">匹配度 {candidate.score ?? 0}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {message && (
            <div className="message-box">
              <strong>{message}</strong>
              {warnings.length > 0 && (
                <ul>
                  {warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {error && <div className="message-box error">{error}</div>}

          {docId && (
            <div className="summary-box">
              <h3 className="panel-title">下一步：人工核对</h3>
              <p className="panel-copy">初稿已经送去核对。确认后才会保存为正式资料，并用于 Excel 表。</p>
              <button className="btn btn-green" onClick={() => onDone(docId)} type="button">
                去核对这份资料
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
