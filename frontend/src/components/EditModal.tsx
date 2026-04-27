import { useState } from "react";

interface EditModalProps {
  open: boolean;
  title: string;
  initialData?: Record<string, string>;
  fields: Array<{ key: string; label: string }>;
  onClose: () => void;
  onSubmit: (data: Record<string, string>) => Promise<void>;
}

export default function EditModal({ open, title, initialData, fields, onClose, onSubmit }: EditModalProps) {
  const [saving, setSaving] = useState(false);
  const [values, setValues] = useState<Record<string, string>>(initialData || {});

  if (!open) return null;

  async function handleSubmit(): Promise<void> {
    setSaving(true);
    try {
      await onSubmit(values);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/25 p-4">
      <div className="w-full max-w-2xl rounded-xl border border-gray-200 bg-white p-5">
        <div className="mb-4 text-[16px] font-medium text-[#1C1C1C]">{title}</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {fields.map((f) => (
            <label key={f.key} className="block">
              <div className="mb-1 text-xs text-gray-500">{f.label}</div>
              <input
                value={values[f.key] || ""}
                onChange={(e) => setValues((prev) => ({ ...prev, [f.key]: e.target.value }))}
                className="h-9 w-full rounded border border-gray-300 px-3 text-[13px] outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              />
            </label>
          ))}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50">
            取消
          </button>
          <button
            onClick={() => void handleSubmit()}
            disabled={saving}
            className="rounded border border-blue-600 bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
