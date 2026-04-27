import { useEffect, useMemo, useState } from "react";
import { createManualStaging, deleteStaging, getStaging, patchStaging, toErrorMessage } from "../api/client";
import DataTable, { type ColumnDef } from "../components/DataTable";
import EditModal from "../components/EditModal";
import type { StagingRecord } from "../types";

function StatusBadge({ text, tone }: { text: string; tone: "amber" | "emerald" | "slate" | "rose" }) {
  const toneClass = tone === "amber" ? "border-amber-200 bg-amber-50 text-amber-700" : tone === "emerald" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : tone === "rose" ? "border-rose-200 bg-rose-50 text-rose-700" : "border-slate-200 bg-slate-100 text-slate-700";
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${toneClass}`}>{text}</span>;
}

const columns: ColumnDef[] = [
  { key: "id", label: "ID", widthClass: "w-16" },
  { key: "university", label: "大学", editable: true, widthClass: "w-40" },
  { key: "faculty", label: "学部", editable: true, widthClass: "w-36" },
  { key: "department", label: "学科", editable: true, widthClass: "w-44" },
  { key: "application_period", label: "出愿期限", editable: true, widthClass: "w-40" },
  { key: "eju_japanese", label: "EJU", editable: true, widthClass: "w-32" },
  { key: "english_requirement", label: "英语要求", editable: true, widthClass: "w-48" },
  { key: "screening_method", label: "选拔方式", editable: true, widthClass: "w-40" },
  { key: "confidence", label: "置信度", widthClass: "w-28", render: (value) => { const num = Number(value ?? 0); return Number.isNaN(num) ? "-" : num.toFixed(2); } },
  { key: "status", label: "状态", widthClass: "w-44", render: (_, row) => { const data = row as StagingRecord; const confidence = Number(data.confidence ?? 0); const needsReview = Number(data.needs_review ?? 0) === 1; const confirmed = Number(data.is_confirmed ?? 0) === 1; return <div className="flex flex-wrap gap-1">{confirmed && <StatusBadge text="已确认" tone="emerald" />}{needsReview && <StatusBadge text="需复核" tone="amber" />}{confidence > 0 && confidence < 0.75 && <StatusBadge text="低置信度" tone="rose" />}{!confirmed && !needsReview && !(confidence > 0 && confidence < 0.75) && <StatusBadge text="正常" tone="slate" />}</div>; } },
];

const manualFields = [
  { key: "university", label: "大学" }, { key: "admission_year", label: "年度" }, { key: "faculty", label: "学部" }, { key: "department", label: "学科" }, { key: "application_period", label: "出愿期限" }, { key: "eju_japanese", label: "EJU日语" }, { key: "english_requirement", label: "英语要求" }, { key: "screening_method", label: "选拔方式" }, { key: "confidence", label: "置信度" },
];

interface StagingPageProps { initialDocId?: string; onDocIdChange?: (docId: number | string) => void; }

export default function StagingPage({ initialDocId = "", onDocIdChange }: StagingPageProps) {
  const [docId, setDocId] = useState(initialDocId);
  const [rows, setRows] = useState<StagingRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);

  useEffect(() => { setDocId(initialDocId); }, [initialDocId]);
  const reviewCount = useMemo(() => rows.filter((r) => Number(r.needs_review ?? 0) === 1).length, [rows]);
  const lowConfidence = useMemo(() => rows.filter((r) => Number(r.confidence ?? 0) < 0.75).length, [rows]);

  async function load(): Promise<void> { const id = Number(docId); if (!id) return; setLoading(true); setError(""); try { setRows(await getStaging(id)); onDocIdChange?.(id); } catch (err) { setError(toErrorMessage(err)); setRows([]); } finally { setLoading(false); } }
  async function onSave(id: number, patch: Record<string, unknown>): Promise<void> { await patchStaging(id, patch); setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r))); }
  async function onDelete(id: number): Promise<void> { if (!window.confirm(`删除待复核记录 ${id}?`)) return; await deleteStaging(id); setRows((prev) => prev.filter((r) => r.id !== id)); }
  async function onCreateManual(data: Record<string, string>): Promise<void> { const id = Number(docId); await createManualStaging({ document_id: id, data }); await load(); }

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-[20px] font-semibold tracking-tight text-[#111827]">待复核表格</h2>
        <div className="mt-4 flex flex-wrap items-center gap-2"><input value={docId} onChange={(e) => setDocId(e.target.value)} className="h-10 w-40 rounded-lg border border-gray-300 px-3 text-[13px] outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15" placeholder="文档ID" /><button onClick={() => void load()} className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-50">加载</button><button onClick={() => setShowModal(true)} className="rounded-lg border border-blue-600 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50">手动添加记录</button></div>
      </section>
      <section className="grid grid-cols-1 gap-3 sm:grid-cols-3"><div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm"><div className="text-xs text-gray-500">总记录数</div><div className="mt-2 text-2xl font-semibold text-gray-900">{rows.length}</div></div><div className="rounded-2xl border border-amber-200 bg-amber-50 p-4"><div className="text-xs text-amber-700">需复核</div><div className="mt-2 text-2xl font-semibold text-amber-900">{reviewCount}</div></div><div className="rounded-2xl border border-rose-200 bg-rose-50 p-4"><div className="text-xs text-rose-700">低置信度 (&lt; 0.75)</div><div className="mt-2 text-2xl font-semibold text-rose-900">{lowConfidence}</div></div></section>
      {error && <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">无法加载待复核记录，请检查文档ID和后端状态。</section>}
      <DataTable rows={rows} columns={columns} loading={loading} emptyText="暂无待复核记录。" onSave={onSave} onDelete={onDelete} rowClassName={(row) => (Number(row.needs_review ?? 0) === 1 ? "bg-amber-50/40" : "")} />
      <EditModal open={showModal} title={`手动添加记录${docId ? ` (文档ID=${docId})` : ""}`} fields={manualFields} onClose={() => setShowModal(false)} onSubmit={onCreateManual} />
    </div>
  );
}
