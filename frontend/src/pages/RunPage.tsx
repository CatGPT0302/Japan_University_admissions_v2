import { useRef, useState } from "react";
import { extractPdf, toErrorMessage, uploadPdf } from "../api/client";

interface Props {
  onDone: (docId: number) => void;
}

type Step = "idle" | "uploading" | "extracting" | "done" | "error";

function progress(step: Step) {
  if (step === "uploading") return 28;
  if (step === "extracting") return 72;
  if (step === "done") return 100;
  if (step === "error") return 100;
  return 0;
}

function stepTitle(step: Step) {
  if (step === "uploading") return "正在上传 PDF";
  if (step === "extracting") return "正在全卷视觉读取";
  if (step === "done") return "提取完成";
  if (step === "error") return "处理失败";
  return "等待开始";
}

export default function RunPage({ onDone }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [year, setYear] = useState("2027");
  const [university, setUniversity] = useState("");
  const [step, setStep] = useState<Step>("idle");
  const [message, setMessage] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [docId, setDocId] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFile(nextFile: File | null) {
    if (!nextFile || !nextFile.name.toLowerCase().endsWith(".pdf")) return;
    setFile(nextFile);
    setStep("idle");
    setMessage("");
    setWarnings([]);
    setError("");
    setDocId(null);
  }

  async function run() {
    if (!file) return;
    setError("");
    setMessage("");
    setWarnings([]);
    setDocId(null);
    try {
      setStep("uploading");
      const uploaded = await uploadPdf(file);
      setStep("extracting");
      const extracted = await extractPdf({
        file_name: uploaded.file_name,
        university,
        year,
      });
      setDocId(extracted.doc_id);
      setMessage(extracted.quality_message || `已生成 ${extracted.records} 条待复核记录。`);
      setWarnings(extracted.warnings || []);
      setStep("done");
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
            <div className="section-kicker">上传提取</div>
            <h2 className="section-title">上传 PDF，生成待复核初稿</h2>
            <p className="section-copy">系统会按整份 PDF 全卷阅读，不再切碎表格。结果只写入待复核区，不会直接进入正式库。</p>
          </div>
        </div>
      </section>

      <section className="content-grid">
        <aside className="sidebar-panel">
          <div className="toolbar-shell">
            <h3 className="panel-title">文件与基本信息</h3>
            <p className="panel-copy">大学名称可以留空，由模型识别；入学年度建议填写。</p>

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
              <h3 className="panel-title">{file ? file.name : "点击或拖拽上传招生要项 PDF"}</h3>
              <p className="panel-copy">只需要上传 PDF，系统会自动渲染页面并进行全卷视觉抽取。</p>
            </div>

            <div className="list-stack">
              <label className="field-wrap">
                <span className="field-label">大学名称（可选）</span>
                <input className="field" value={university} onChange={(event) => setUniversity(event.target.value)} placeholder="例如：早稲田大学" />
              </label>
              <label className="field-wrap">
                <span className="field-label">入学年度</span>
                <input className="field" value={year} onChange={(event) => setYear(event.target.value)} placeholder="2027" />
              </label>
              <button className="btn btn-primary" disabled={!file || step === "uploading" || step === "extracting"} onClick={() => void run()} type="button">
                {step === "extracting" ? "全卷读取中..." : "开始提取"}
              </button>
            </div>
          </div>
        </aside>

        <div className="item-detail">
          <div className={`progress-card${step === "extracting" || step === "uploading" ? " is-running" : ""}${step === "error" ? " is-error" : ""}`}>
            <div className="split-row">
              <div>
                <div className="card-kicker">当前状态</div>
                <h3 className="panel-title">{stepTitle(step)}</h3>
                <p className="panel-copy">
                  {step === "extracting"
                    ? "模型正在通读整份 PDF。复杂表格可能需要几分钟。"
                    : "质量问题会直接显示在这里，不额外生成诊断文件。"}
                </p>
              </div>
              <span className="badge badge-blue">{progress(step)}%</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${progress(step)}%` }} />
            </div>
          </div>

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
              <h3 className="panel-title">下一步：人工复核</h3>
              <p className="panel-copy">这份 PDF 的 AI 初稿已经进入待复核区。复核后再确认入库，随后可在主表导出页导出最新 Excel。</p>
              <button className="btn btn-green" onClick={() => onDone(docId)} type="button">
                去复核这份文档
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
