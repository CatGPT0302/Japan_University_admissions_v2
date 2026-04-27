import { useRef, useState } from "react";
import { uploadPdf, extractPdf, toErrorMessage } from "../api/client";

interface Props { onDone: (docId: number) => void; }

type Step = "idle" | "uploading" | "extracting" | "done" | "error";

export default function RunPage({ onDone }: Props) {
  const [file, setFile]         = useState<File | null>(null);
  const [univ, setUniv]         = useState("");
  const [year, setYear]         = useState("2026");
  const [url, setUrl]           = useState("");
  const [step, setStep]         = useState<Step>("idle");
  const [result, setResult]     = useState<{ doc_id:number; records:number; failed:number } | null>(null);
  const [error, setError]       = useState("");
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFile(f: File | null) {
    if (!f || !f.name.endsWith(".pdf")) return;
    setFile(f);
    setStep("idle");
    setResult(null);
    setError("");
    // Auto-fill university from filename
    if (!univ) {
      const name = f.name.replace(/[_\-]/g, " ").replace(/\.pdf$/i, "").replace(/\d{4}/g, "").trim();
      if (name) setUniv(name);
    }
  }

  async function run() {
    if (!file || !univ) return;
    setError(""); setResult(null);
    try {
      setStep("uploading");
      const up = await uploadPdf(file);
      setStep("extracting");
      const ex = await extractPdf({ file_name: up.file_name, university: univ, year, url: url || undefined });
      setResult({ doc_id: ex.doc_id, records: ex.records, failed: ex.failed_pages?.length ?? 0 });
      setStep("done");
    } catch (e) {
      setError(toErrorMessage(e));
      setStep("error");
    }
  }

  const ready = file && univ && step !== "uploading" && step !== "extracting";

  const stepLabel = step === "uploading" ? "上传中…" : step === "extracting" ? "AI 抽取中，请稍候…" : step === "done" ? "完成" : "开始抽取";

  return (
    <div style={{ maxWidth:680 }}>
      {/* Header */}
      <div style={{ marginBottom:36 }}>
        <div style={{ fontSize:10, letterSpacing:"0.2em", textTransform:"uppercase", color:"var(--red)", marginBottom:10, fontWeight:500 }}>Step 1</div>
        <h1 style={{ fontFamily:"Georgia,serif", fontSize:34, fontStyle:"italic", fontWeight:400, letterSpacing:-0.5, lineHeight:1.1, marginBottom:10 }}>
          跑数据
        </h1>
        <p style={{ fontSize:14, color:"var(--ink2)", lineHeight:1.75 }}>
          上传招生简章 PDF，AI 自动提取结构化数据。<br/>
          完成后前往「复查」逐条核验。
        </p>
      </div>

      {/* Drop zone */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
        style={{
          border: `2px dashed ${dragging ? "var(--red)" : file ? "var(--green)" : "var(--border)"}`,
          borderRadius:12, padding:"40px 24px", textAlign:"center",
          background: dragging ? "#FEF2F2" : file ? "var(--green-soft)" : "var(--surface)",
          cursor:"pointer", transition:"all 0.2s", marginBottom:20,
        }}
      >
        <input ref={inputRef} type="file" accept=".pdf" style={{ display:"none" }} onChange={e => handleFile(e.target.files?.[0] ?? null)}/>
        <div style={{ fontSize:28, marginBottom:10 }}>{file ? "✅" : "📄"}</div>
        {file
          ? <div style={{ fontSize:14, fontWeight:500, color:"var(--green)" }}>{file.name}</div>
          : <><div style={{ fontSize:14, fontWeight:500, color:"var(--ink)", marginBottom:4 }}>拖放 PDF 到这里</div>
             <div style={{ fontSize:13, color:"var(--ink3)" }}>或点击选择文件</div></>
        }
      </div>

      {/* Form */}
      <div style={{ background:"var(--surface)", border:"1px solid var(--border)", borderRadius:12, padding:"24px", marginBottom:20 }}>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 100px", gap:"12px 14px" }}>
          <label>
            <div style={{ fontSize:11, color:"var(--ink3)", marginBottom:5, fontWeight:500 }}>大学名称 <span style={{ color:"var(--red)" }}>*</span></div>
            <input value={univ} onChange={e => setUniv(e.target.value)} placeholder="例：明治大学"
              style={{ width:"100%", height:38, padding:"0 12px", border:"1px solid var(--border)", borderRadius:8, fontSize:13, color:"var(--ink)", background:"var(--bg)", outline:"none" }}
              onFocus={e => e.target.style.borderColor="var(--red)"}
              onBlur={e  => e.target.style.borderColor="var(--border)"}
            />
          </label>
          <label>
            <div style={{ fontSize:11, color:"var(--ink3)", marginBottom:5, fontWeight:500 }}>年度</div>
            <input value={year} onChange={e => setYear(e.target.value)} placeholder="2026"
              style={{ width:"100%", height:38, padding:"0 12px", border:"1px solid var(--border)", borderRadius:8, fontSize:13, color:"var(--ink)", background:"var(--bg)", outline:"none" }}
              onFocus={e => e.target.style.borderColor="var(--red)"}
              onBlur={e  => e.target.style.borderColor="var(--border)"}
            />
          </label>
          <label style={{ gridColumn:"span 2" }}>
            <div style={{ fontSize:11, color:"var(--ink3)", marginBottom:5, fontWeight:500 }}>来源 URL（可选）</div>
            <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://..."
              style={{ width:"100%", height:38, padding:"0 12px", border:"1px solid var(--border)", borderRadius:8, fontSize:13, color:"var(--ink)", background:"var(--bg)", outline:"none" }}
              onFocus={e => e.target.style.borderColor="var(--red)"}
              onBlur={e  => e.target.style.borderColor="var(--border)"}
            />
          </label>
        </div>
      </div>

      {/* Action */}
      <button onClick={() => void run()} disabled={!ready}
        style={{ height:44, padding:"0 32px", background: ready ? "var(--ink)" : "var(--border)",
          color: ready ? "#fff" : "var(--ink3)", border:"none", borderRadius:10,
          fontSize:14, fontWeight:500, cursor: ready ? "pointer" : "not-allowed",
          fontFamily:"inherit", transition:"all 0.15s", marginBottom:20 }}>
        {step === "uploading" || step === "extracting"
          ? <span style={{ display:"flex", alignItems:"center", gap:8 }}>
              <span style={{ width:14, height:14, border:"2px solid rgba(255,255,255,0.4)", borderTopColor:"#fff", borderRadius:"50%", display:"inline-block", animation:"spin 0.7s linear infinite" }}/>
              {stepLabel}
            </span>
          : stepLabel}
      </button>

      {/* Result */}
      {step === "done" && result && (
        <div style={{ background:"var(--green-soft)", border:"1px solid #bbf7d0", borderRadius:10, padding:"20px 24px" }}>
          <div style={{ fontFamily:"Georgia,serif", fontSize:18, fontStyle:"italic", color:"var(--green)", marginBottom:8 }}>抽取完成</div>
          <div style={{ fontSize:13, color:"var(--ink2)", lineHeight:1.8, marginBottom:16 }}>
            文档 ID：<strong style={{ color:"var(--ink)" }}>#{result.doc_id}</strong>　
            提取记录：<strong style={{ color:"var(--ink)" }}>{result.records} 条</strong>　
            {result.failed > 0 && <span style={{ color:"var(--red)" }}>失败页：{result.failed}</span>}
          </div>
          <button onClick={() => onDone(result.doc_id)}
            style={{ height:38, padding:"0 20px", background:"var(--green)", color:"#fff", border:"none", borderRadius:8, fontSize:13, fontWeight:500, cursor:"pointer", fontFamily:"inherit" }}>
            前往复查 →
          </button>
        </div>
      )}

      {step === "error" && (
        <div style={{ background:"var(--red-soft)", border:"1px solid #fecaca", borderRadius:10, padding:"16px 20px", fontSize:13, color:"var(--red)" }}>
          {error || "抽取失败，请检查后端日志"}
        </div>
      )}

      <style>{`@keyframes spin { to { transform:rotate(360deg); } }`}</style>
    </div>
  );
}
