import { useEffect, useRef, useState } from "react";
import {
  extractPdf,
  fetchPdf,
  getFetchTargets,
  toErrorMessage,
  uploadPdf,
} from "../api/client";
import type { FetchPdfTarget } from "../types";

interface Props {
  onDone: (docId: number) => void;
}

type SourceMode = "upload" | "crawl";
type Step = "idle" | "fetching" | "uploading" | "extracting" | "done" | "error";

export default function RunPage({ onDone }: Props) {
  const [sourceMode, setSourceMode] = useState<SourceMode>("upload");
  const [targets, setTargets] = useState<FetchPdfTarget[]>([]);
  const [selectedTarget, setSelectedTarget] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [univ, setUniv] = useState("");
  const [year, setYear] = useState("2026");
  const [url, setUrl] = useState("");
  const [step, setStep] = useState<Step>("idle");
  const [result, setResult] = useState<{
    doc_id: number;
    records: number;
    failed: number;
    file_name?: string;
    source_url?: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void loadTargets();
  }, []);

  async function loadTargets() {
    try {
      const data = await getFetchTargets();
      setTargets(data);
    } catch {
      setTargets([]);
    }
  }

  function resetStatus() {
    setStep("idle");
    setResult(null);
    setError("");
  }

  function handleFile(nextFile: File | null) {
    if (!nextFile || !nextFile.name.toLowerCase().endsWith(".pdf")) return;
    setFile(nextFile);
    resetStatus();
    if (!univ) {
      const name = nextFile.name
        .replace(/[_\-]/g, " ")
        .replace(/\.pdf$/i, "")
        .replace(/\d{4}/g, "")
        .trim();
      if (name) setUniv(name);
    }
  }

  async function runUpload() {
    if (!file || !univ) return;
    setError("");
    setResult(null);
    try {
      setStep("uploading");
      const up = await uploadPdf(file);
      setStep("extracting");
      const ex = await extractPdf({
        file_name: up.file_name,
        university: univ,
        year,
        url: url || undefined,
      });
      setResult({
        doc_id: ex.doc_id,
        records: ex.records,
        failed: ex.failed_pages?.length ?? 0,
        file_name: up.file_name,
        source_url: url || undefined,
      });
      setStep("done");
    } catch (e) {
      setError(toErrorMessage(e));
      setStep("error");
    }
  }

  async function runCrawl() {
    if (!univ) return;
    setError("");
    setResult(null);
    try {
      setStep("fetching");
      const fetched = await fetchPdf({
        university: univ,
        year,
        page_url: url || undefined,
      });
      setStep("extracting");
      const ex = await extractPdf({
        file_name: fetched.file_name,
        university: univ,
        year,
        url: fetched.source_url || url || undefined,
      });
      setResult({
        doc_id: ex.doc_id,
        records: ex.records,
        failed: ex.failed_pages?.length ?? 0,
        file_name: fetched.file_name,
        source_url: fetched.source_url || fetched.page_url,
      });
      setUrl(fetched.page_url || fetched.source_url || url);
      setStep("done");
    } catch (e) {
      setError(toErrorMessage(e));
      setStep("error");
    }
  }

  const busy = step === "fetching" || step === "uploading" || step === "extracting";
  const ready = sourceMode === "upload"
    ? Boolean(file && univ && !busy)
    : Boolean(univ && !busy);

  const stepLabel =
    step === "fetching"
      ? "自动抓取 PDF 中，请稍候…"
      : step === "uploading"
        ? "上传中…"
        : step === "extracting"
          ? "AI 抽取中，请稍候…"
          : step === "done"
            ? "完成"
            : sourceMode === "crawl"
              ? "自动抓取并抽取"
              : "开始抽取";

  return (
    <div style={{ maxWidth: 760 }}>
      <div style={{ marginBottom: 36 }}>
        <div style={{ fontSize: 10, letterSpacing: "0.2em", textTransform: "uppercase", color: "var(--red)", marginBottom: 10, fontWeight: 600 }}>Step 1</div>
        <h1 style={{ fontSize: 32, fontWeight: 700, letterSpacing: -0.4, lineHeight: 1.15, margin: "0 0 10px" }}>
          跑数据
        </h1>
        <p style={{ fontSize: 14, color: "var(--ink2)", lineHeight: 1.75, margin: 0 }}>
          可以直接上传本地 PDF，也可以先自动抓取学校招生页里的 PDF，再进入抽取和复查流程。
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
        {[
          {
            key: "upload" as SourceMode,
            title: "本地上传 PDF",
            desc: "你手里已经有文件，直接上传并抽取。",
          },
          {
            key: "crawl" as SourceMode,
            title: "自动爬取 PDF",
            desc: "从招生页自动找到 PDF，再继续抽取。",
          },
        ].map((item) => {
          const active = sourceMode === item.key;
          return (
            <button
              key={item.key}
              onClick={() => {
                setSourceMode(item.key);
                resetStatus();
              }}
              style={{
                textAlign: "left",
                padding: "16px 18px",
                borderRadius: 12,
                border: active ? "1px solid var(--ink)" : "1px solid var(--border)",
                background: active ? "var(--surface)" : "rgba(255,255,255,0.6)",
                boxShadow: active ? "0 8px 24px rgba(20,18,15,0.08)" : "none",
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)", marginBottom: 6 }}>{item.title}</div>
              <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.6 }}>{item.desc}</div>
            </button>
          );
        })}
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
            border: `2px dashed ${dragging ? "var(--red)" : file ? "var(--green)" : "var(--border)"}`,
            borderRadius: 12,
            padding: "40px 24px",
            textAlign: "center",
            background: dragging ? "#FEF2F2" : file ? "var(--green-soft)" : "var(--surface)",
            cursor: "pointer",
            transition: "all 0.2s",
            marginBottom: 20,
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            style={{ display: "none" }}
            onChange={(event) => handleFile(event.target.files?.[0] ?? null)}
          />
          <div style={{ fontSize: 28, marginBottom: 10 }}>{file ? "已选择" : "PDF"}</div>
          {file ? (
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--green)" }}>{file.name}</div>
          ) : (
            <>
              <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)", marginBottom: 4 }}>拖放 PDF 到这里</div>
              <div style={{ fontSize: 13, color: "var(--ink3)" }}>或者点击选择文件</div>
            </>
          )}
        </div>
      )}

      {sourceMode === "crawl" && (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", marginBottom: 10 }}>自动爬取入口</div>
          <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.7, marginBottom: 14 }}>
            可直接选择预设学校；如果学校不在预设里，就手动填招生页 URL。
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <label>
              <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>预设学校</div>
              <select
                value={selectedTarget}
                onChange={(event) => {
                  const next = event.target.value;
                  setSelectedTarget(next);
                  const target = targets.find((item) => item.name === next);
                  if (next) setUniv(next);
                  setUrl(target?.url || "");
                  resetStatus();
                }}
                style={{ width: "100%", height: 38, padding: "0 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, color: "var(--ink)", background: "var(--bg)", outline: "none", fontFamily: "inherit" }}
              >
                <option value="">选择学校</option>
                {targets.map((target) => (
                  <option key={target.name} value={target.name}>
                    {target.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>年度</div>
              <input
                value={year}
                onChange={(event) => {
                  setYear(event.target.value);
                  resetStatus();
                }}
                placeholder="2026"
                style={{ width: "100%", height: 38, padding: "0 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, color: "var(--ink)", background: "var(--bg)", outline: "none" }}
              />
            </label>
          </div>
        </div>
      )}

      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 24, marginBottom: 20 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 100px", gap: "12px 14px" }}>
          <label>
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>大学名称 <span style={{ color: "var(--red)" }}>*</span></div>
            <input
              value={univ}
              onChange={(event) => {
                setUniv(event.target.value);
                resetStatus();
              }}
              placeholder="例如：明治大学"
              style={{ width: "100%", height: 38, padding: "0 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, color: "var(--ink)", background: "var(--bg)", outline: "none" }}
            />
          </label>
          <label>
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>年度</div>
            <input
              value={year}
              onChange={(event) => {
                setYear(event.target.value);
                resetStatus();
              }}
              placeholder="2026"
              style={{ width: "100%", height: 38, padding: "0 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, color: "var(--ink)", background: "var(--bg)", outline: "none" }}
            />
          </label>
          <label style={{ gridColumn: "span 2" }}>
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>
              {sourceMode === "crawl" ? "招生页 URL（可选，手动指定时填写）" : "来源 URL（可选）"}
            </div>
            <input
              value={url}
              onChange={(event) => {
                setUrl(event.target.value);
                resetStatus();
              }}
              placeholder={sourceMode === "crawl" ? "https://..." : "https://..."}
              style={{ width: "100%", height: 38, padding: "0 12px", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, color: "var(--ink)", background: "var(--bg)", outline: "none" }}
            />
          </label>
        </div>
      </div>

      <button
        onClick={() => void (sourceMode === "crawl" ? runCrawl() : runUpload())}
        disabled={!ready}
        style={{
          height: 44,
          padding: "0 32px",
          background: ready ? "var(--ink)" : "var(--border)",
          color: ready ? "#fff" : "var(--ink3)",
          border: "none",
          borderRadius: 10,
          fontSize: 14,
          fontWeight: 600,
          cursor: ready ? "pointer" : "not-allowed",
          fontFamily: "inherit",
          transition: "all 0.15s",
          marginBottom: 20,
        }}
      >
        {busy ? (
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 14, height: 14, border: "2px solid rgba(255,255,255,0.4)", borderTopColor: "#fff", borderRadius: "50%", display: "inline-block", animation: "spin 0.7s linear infinite" }} />
            {stepLabel}
          </span>
        ) : (
          stepLabel
        )}
      </button>

      {step === "done" && result && (
        <div style={{ background: "var(--green-soft)", border: "1px solid #bbf7d0", borderRadius: 10, padding: "20px 24px" }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: "var(--green)", marginBottom: 8 }}>抽取完成</div>
          <div style={{ fontSize: 13, color: "var(--ink2)", lineHeight: 1.8, marginBottom: 16 }}>
            文档 ID：<strong style={{ color: "var(--ink)" }}>#{result.doc_id}</strong>。
            抽取记录：<strong style={{ color: "var(--ink)" }}>{result.records} 条</strong>。
            {result.file_name && <> 文件：<strong style={{ color: "var(--ink)" }}>{result.file_name}</strong>。</>}
            {result.failed > 0 && <span style={{ color: "var(--red)" }}> 失败页：{result.failed}</span>}
            {result.source_url && (
              <>
                {" "}
                <a href={result.source_url} target="_blank" rel="noreferrer" style={{ color: "var(--green)", textDecoration: "none" }}>
                  查看来源
                </a>
              </>
            )}
          </div>
          <button
            onClick={() => onDone(result.doc_id)}
            style={{ height: 38, padding: "0 20px", background: "var(--green)", color: "#fff", border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}
          >
            前往复查
          </button>
        </div>
      )}

      {step === "error" && (
        <div style={{ background: "var(--red-soft)", border: "1px solid #fecaca", borderRadius: 10, padding: "16px 20px", fontSize: 13, color: "var(--red)" }}>
          {error || "操作失败，请检查后端日志。"}
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
