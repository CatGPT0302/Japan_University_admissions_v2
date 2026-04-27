import { useEffect, useMemo, useRef, useState } from "react";
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

function stepDescription(step: Step, sourceMode: SourceMode): string {
  if (step === "fetching") return "我正在帮你从招生页里寻找 PDF，找到后会直接继续抽取。";
  if (step === "uploading") return "文件已经接收，正在把 PDF 送进系统。";
  if (step === "extracting") return "AI 正在读取 PDF 内容并整理成可复查记录。";
  if (step === "done") return "抽取已经完成，可以直接进入复查。";
  if (step === "error") return "这次处理没有成功，建议先看报错，再重新运行。";
  return sourceMode === "crawl"
    ? "你可以先让我自动去找 PDF，也可以手动指定招生页地址。"
    : "你可以直接上传现成 PDF，系统会自动完成抽取。";
}

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
  const ready = sourceMode === "upload" ? Boolean(file && univ && !busy) : Boolean(univ && !busy);

  const primaryActionLabel =
    step === "fetching"
      ? "正在寻找 PDF…"
      : step === "uploading"
        ? "正在上传…"
        : step === "extracting"
          ? "正在抽取…"
          : step === "done"
            ? "抽取完成"
            : sourceMode === "crawl"
              ? "自动抓取并抽取"
              : "开始抽取";

  const topStatus = useMemo(() => {
    if (step === "done" && result) {
      return {
        tone: "success",
        title: `已经整理出 ${result.records} 条记录`,
        description: result.failed > 0
          ? `其中有 ${result.failed} 页没有顺利处理，建议在复查时优先留意。`
          : "抽取过程很顺，下一步直接去复查就可以了。",
      };
    }
    if (step === "error") {
      return {
        tone: "danger",
        title: "这一步卡住了",
        description: "别担心，通常是来源页或文件格式问题，改一下后重新跑就行。",
      };
    }
    if (busy) {
      return {
        tone: "info",
        title: "系统正在处理",
        description: stepDescription(step, sourceMode),
      };
    }
    return {
      tone: "neutral",
      title: sourceMode === "crawl" ? "可以先帮你找 PDF" : "可以直接开始抽取",
      description: stepDescription(step, sourceMode),
    };
  }, [result, sourceMode, step]);

  const statusStyle =
    topStatus.tone === "success"
      ? { background: "#f0fdf4", border: "1px solid #bbf7d0", accent: "#166534" }
      : topStatus.tone === "danger"
        ? { background: "#fef2f2", border: "1px solid #fecaca", accent: "#b91c1c" }
        : topStatus.tone === "info"
          ? { background: "#eff6ff", border: "1px solid #bfdbfe", accent: "#1d4ed8" }
          : { background: "#ffffff", border: "1px solid #e5e7eb", accent: "#111827" };

  return (
    <div style={{ maxWidth: 780 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 10, letterSpacing: "0.2em", textTransform: "uppercase", color: "var(--red)", marginBottom: 10, fontWeight: 600 }}>Step 1</div>
        <h1 style={{ fontSize: 32, fontWeight: 700, letterSpacing: -0.4, lineHeight: 1.15, margin: "0 0 10px" }}>
          跑数据
        </h1>
        <p style={{ fontSize: 14, color: "var(--ink2)", lineHeight: 1.75, margin: 0 }}>
          这一步更像把原始 PDF 交给助手。你给我文件或来源页，我先帮你整理出一版可复查结果。
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
            <div style={{ fontSize: 14, fontWeight: 700, color: statusStyle.accent, marginBottom: 6 }}>{topStatus.title}</div>
            <div style={{ fontSize: 13, color: "var(--ink2)", lineHeight: 1.7 }}>{topStatus.description}</div>
          </div>
          <div style={{ display: "grid", gap: 6, minWidth: 180 }}>
            <div className="badge badge-gray">模式：{sourceMode === "crawl" ? "自动抓取 PDF" : "本地上传 PDF"}</div>
            <div className="badge badge-gray">大学：{univ || "还没填写"}</div>
            <div className="badge badge-gray">年度：{year || "未设置"}</div>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 18 }}>
        {[
          {
            key: "upload" as SourceMode,
            title: "本地上传 PDF",
            desc: "适合你已经拿到文件的情况，步骤最短。",
          },
          {
            key: "crawl" as SourceMode,
            title: "自动抓取 PDF",
            desc: "适合你只有招生页地址，想让我先帮你把 PDF 找出来。",
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

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 12,
          marginBottom: 20,
        }}
      >
        <div className="card" style={{ padding: 16, borderRadius: 18 }}>
          <div style={{ fontSize: 12, color: "var(--ink3)", marginBottom: 6 }}>当前状态</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink)" }}>{primaryActionLabel}</div>
        </div>
        <div className="card" style={{ padding: 16, borderRadius: 18 }}>
          <div style={{ fontSize: 12, color: "var(--ink3)", marginBottom: 6 }}>已选文件</div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)" }}>{file?.name || "还没有"}</div>
        </div>
        <div className="card" style={{ padding: 16, borderRadius: 18 }}>
          <div style={{ fontSize: 12, color: "var(--ink3)", marginBottom: 6 }}>操作建议</div>
          <div style={{ fontSize: 13, color: "var(--ink2)", lineHeight: 1.65 }}>
            {sourceMode === "crawl" ? "先选学校，再决定是否补招生页 URL。" : "上传后先不要急着关页，等抽取完成再去复查。"}
          </div>
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
              <div style={{ marginTop: 6, fontSize: 12, color: "var(--ink2)" }}>我会用这个文件开始抽取。</div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)", marginBottom: 4 }}>把 PDF 拖到这里</div>
              <div style={{ fontSize: 13, color: "var(--ink3)" }}>或者点一下，从本地挑一个文件</div>
            </>
          )}
        </div>
      )}

      {sourceMode === "crawl" && (
        <div className="card" style={{ padding: 22, borderRadius: 22, marginBottom: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ink)", marginBottom: 8 }}>自动抓取入口</div>
          <div style={{ fontSize: 12, color: "var(--ink2)", lineHeight: 1.7, marginBottom: 14 }}>
            这里更像“让我先去找文件”。如果预设学校够用，你几乎不用再手动处理。
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
                className="field"
                style={{ width: "100%" }}
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
                className="field"
                style={{ width: "100%" }}
              />
            </label>
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 24, borderRadius: 22, marginBottom: 20 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 100px", gap: "12px 14px" }}>
          <label>
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>大学名称</div>
            <input
              value={univ}
              onChange={(event) => {
                setUniv(event.target.value);
                resetStatus();
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
                resetStatus();
              }}
              placeholder="2026"
              className="field"
              style={{ width: "100%" }}
            />
          </label>
          <label style={{ gridColumn: "span 2" }}>
            <div style={{ fontSize: 11, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>
              {sourceMode === "crawl" ? "招生页 URL（选填）" : "来源 URL（选填）"}
            </div>
            <input
              value={url}
              onChange={(event) => {
                setUrl(event.target.value);
                resetStatus();
              }}
              placeholder="https://..."
              className="field"
              style={{ width: "100%" }}
            />
          </label>
        </div>
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 20 }}>
        <button
          onClick={() => void (sourceMode === "crawl" ? runCrawl() : runUpload())}
          disabled={!ready}
          style={{
            height: 46,
            padding: "0 32px",
            background: ready ? "#111827" : "#d6d3d1",
            color: ready ? "#fff" : "#78716c",
            border: "none",
            borderRadius: 14,
            fontSize: 14,
            fontWeight: 700,
            cursor: ready ? "pointer" : "not-allowed",
            fontFamily: "inherit",
            boxShadow: ready ? "0 12px 22px rgba(17,24,39,0.12)" : "none",
          }}
        >
          {busy ? (
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 14, height: 14, border: "2px solid rgba(255,255,255,0.4)", borderTopColor: "#fff", borderRadius: "50%", display: "inline-block", animation: "spin 0.7s linear infinite" }} />
              {primaryActionLabel}
            </span>
          ) : (
            primaryActionLabel
          )}
        </button>
        <div style={{ fontSize: 12, color: "var(--ink3)" }}>
          建议先把大学名和年度填准，这样后面的复查会轻松很多。
        </div>
      </div>

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
            我一共整理出了 <strong style={{ color: "var(--ink)" }}>{result.records}</strong> 条记录。
            {result.failed > 0 ? ` 其中有 ${result.failed} 页需要你额外留意。` : " 目前没有明显失败页。"}
            {result.file_name ? ` 文件名是 ${result.file_name}。` : ""}
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button
              onClick={() => onDone(result.doc_id)}
              style={{
                height: 40,
                padding: "0 20px",
                background: "var(--green)",
                color: "#fff",
                border: "none",
                borderRadius: 12,
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              前往复查
            </button>
            {result.source_url && (
              <a
                href={result.source_url}
                target="_blank"
                rel="noreferrer"
                style={{
                  height: 40,
                  padding: "0 18px",
                  display: "inline-flex",
                  alignItems: "center",
                  borderRadius: 12,
                  border: "1px solid var(--border)",
                  textDecoration: "none",
                  color: "var(--ink)",
                  background: "#fff",
                  fontSize: 13,
                  fontWeight: 600,
                }}
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

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
