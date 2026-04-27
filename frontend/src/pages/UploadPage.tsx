import { useState } from "react";
import { extractPdf, toErrorMessage, uploadPdf } from "../api/client";
import type { ExtractResponse, UploadResponse } from "../types";

interface UploadPageProps {
  onExtractionDone?: (docId: number) => void;
  onReviewStaging?: (docId: number) => void;
}

export default function UploadPage({ onExtractionDone, onReviewStaging }: UploadPageProps) {
  const [file, setFile] = useState<File | null>(null);
  const [university, setUniversity] = useState("");
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [extractResult, setExtractResult] = useState<ExtractResponse | null>(null);
  const [error, setError] = useState("");

  async function handleRun(): Promise<void> {
    if (!file) return;
    setLoading(true);
    setError("");
    setUploadResult(null);
    setExtractResult(null);
    try {
      const uploaded = await uploadPdf(file);
      setUploadResult(uploaded);
      const extracted = await extractPdf({ file_name: uploaded.file_name, university, year, url: url || undefined });
      setExtractResult(extracted);
      onExtractionDone?.(extracted.doc_id);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-[20px] font-semibold tracking-tight text-[#111827]">上传 PDF</h2>
        <p className="mt-1 text-sm text-gray-500">上传募集要项 PDF 并开始抽取。</p>
      </section>
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-gray-500">PDF 文件</label>
        <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-5">
          <input type="file" accept=".pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} className="text-[13px]" />
          <div className="mt-2 text-xs text-gray-500">{file ? file.name : "选择一个 PDF 文件。"}</div>
        </div>
        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
          <label><div className="mb-1 text-xs text-gray-500">大学</div><input value={university} onChange={(e) => setUniversity(e.target.value)} className="h-10 w-full rounded-lg border border-gray-300 px-3 text-[13px] outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15" placeholder="例：明治大学" /></label>
          <label><div className="mb-1 text-xs text-gray-500">年份</div><input value={year} onChange={(e) => setYear(e.target.value)} className="h-10 w-full rounded-lg border border-gray-300 px-3 text-[13px] outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15" placeholder="2026" /></label>
          <label><div className="mb-1 text-xs text-gray-500">来源链接（可选）</div><input value={url} onChange={(e) => setUrl(e.target.value)} className="h-10 w-full rounded-lg border border-gray-300 px-3 text-[13px] outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15" placeholder="https://..." /></label>
        </div>
        <button onClick={() => void handleRun()} disabled={!file || loading} className="mt-5 rounded-lg border border-blue-600 bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60">{loading ? "抽取中..." : "开始抽取"}</button>
      </section>
      {(uploadResult || extractResult || error) && (
        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          {uploadResult && <div className="mb-4"><div className="text-xs font-medium uppercase tracking-wide text-gray-500">已上传文件</div><div className="mt-1 text-sm font-medium text-gray-800">{uploadResult.file_name}</div></div>}
          {extractResult && <div className="space-y-4"><div className="rounded-xl border border-blue-200 bg-blue-50 p-4"><div className="text-xs font-medium uppercase tracking-wide text-blue-700">抽取完成</div><div className="mt-2 text-3xl font-semibold leading-none text-blue-900">doc_id {extractResult.doc_id}</div><div className="mt-2 text-sm text-blue-800">{extractResult.records} 条记录抽取成功{extractResult.failed_pages.length ? `（${extractResult.failed_pages.length} 页失败）` : ""}</div></div><button onClick={() => onReviewStaging?.(extractResult.doc_id)} className="rounded-lg border border-gray-900 bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-black">进入人工复查</button></div>}
          {error && <div className="text-sm text-amber-700">无法完成抽取，请检查 API 服务并重试。</div>}
        </section>
      )}
    </div>
  );
}
