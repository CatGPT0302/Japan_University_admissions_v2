import { useMemo, useState, type ReactNode } from "react";

export interface ColumnDef {
  key: string;
  label: string;
  editable?: boolean;
  widthClass?: string;
  render?: (value: unknown, row: { id: number }) => ReactNode;
}

interface DataTableProps<T extends { id: number }> {
  rows: T[];
  columns: ColumnDef[];
  loading?: boolean;
  emptyText?: string;
  onSave?: (id: number, patch: Record<string, unknown>) => Promise<void>;
  onDelete?: (id: number) => Promise<void> | void;
  rowClassName?: (row: T) => string;
  cellClassName?: (row: T, columnKey: string) => string;
}

export default function DataTable<T extends { id: number }>({
  rows, columns, loading, emptyText = "暂无数据",
  onSave, onDelete, rowClassName, cellClassName,
}: DataTableProps<T>) {
  const [editing, setEditing] = useState<{ id: number; key: string } | null>(null);
  const [draft, setDraft] = useState("");
  const hasActions = useMemo(() => Boolean(onDelete), [onDelete]);

  async function commitEdit() {
    if (!editing || !onSave) return;
    await onSave(editing.id, { [editing.key]: draft });
    setEditing(null);
  }

  if (loading) return (
    <div className="card" style={{padding:'28px 24px', fontSize:13, color:'var(--ink3)'}}>加载中…</div>
  );

  if (!rows.length) return (
    <div className="card" style={{padding:'28px 24px', fontSize:13, color:'var(--ink3)', textAlign:'center'}}>{emptyText}</div>
  );

  return (
    <div style={{overflowX:'auto', borderRadius:12, border:'1px solid var(--border)', background:'var(--surface)'}}>
      <table style={{width:'100%', tableLayout:'fixed', borderCollapse:'collapse', fontSize:13}}>
        <thead>
          <tr style={{borderBottom:'1px solid var(--border)', background:'var(--bg)'}}>
            {columns.map(col => (
              <th key={col.key} className={col.widthClass}
                style={{padding:'10px 14px', textAlign:'left', fontSize:11, fontWeight:500,
                        letterSpacing:'0.08em', textTransform:'uppercase', color:'var(--ink3)',
                        fontFamily:'inherit'}}>
                {col.label}
              </th>
            ))}
            {hasActions && <th style={{width:64, padding:'10px 12px'}} />}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => {
            const rowId = Number(row.id ?? 0);
            const extra = rowClassName?.(row as T) || "";
            return (
              <tr key={rowId}
                style={{borderBottom:'1px solid var(--border)'}}
                className={`group ${extra}`}
                onMouseEnter={e => (e.currentTarget.style.background='var(--bg)')}
                onMouseLeave={e => (e.currentTarget.style.background='')}
              >
                {columns.map(col => {
                  const raw   = (row as Record<string, unknown>)[col.key];
                  const value = raw == null ? "" : String(raw);
                  const isEditing = editing?.id === rowId && editing?.key === col.key;
                  const extra = cellClassName?.(row as T, col.key) || "";
                  return (
                    <td key={col.key} title={value}
                      style={{padding:'10px 14px', verticalAlign:'top', color:'var(--ink)'}}
                      className={extra}
                    >
                      {isEditing ? (
                        <input autoFocus value={draft}
                          onChange={e => setDraft(e.target.value)}
                          onBlur={() => void commitEdit()}
                          onKeyDown={e => { if (e.key==='Enter') void commitEdit(); if (e.key==='Escape') setEditing(null); }}
                          style={{width:'100%', padding:'4px 8px', border:'1px solid var(--red)',
                                  borderRadius:6, fontSize:13, outline:'none', fontFamily:'inherit'}}
                        />
                      ) : (
                        <span
                          style={col.editable && onSave ? {cursor:'pointer'} : {}}
                          onClick={() => { if (!col.editable || !onSave) return; setEditing({id:rowId, key:col.key}); setDraft(value); }}
                        >
                          {col.render ? col.render(raw, row as T) : (value || <span style={{color:'var(--ink3)'}}>—</span>)}
                        </span>
                      )}
                    </td>
                  );
                })}
                {hasActions && (
                  <td style={{padding:'10px 12px', verticalAlign:'top'}}>
                    <button
                      onClick={() => onDelete?.(rowId)}
                      style={{opacity:0, fontSize:11, padding:'3px 10px', borderRadius:6,
                              border:'1px solid #fecaca', color:'var(--red)', background:'transparent',
                              cursor:'pointer', fontFamily:'inherit', transition:'opacity 0.15s'}}
                      className="group-hover:opacity-100"
                      onMouseEnter={e => { (e.target as HTMLElement).style.opacity='1'; }}
                    >
                      删除
                    </button>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}


export interface ColumnDef {
  key: string;
  label: string;
  editable?: boolean;
  widthClass?: string;
  render?: (value: unknown, row: { id: number }) => ReactNode;
}

interface DataTableProps<T extends { id: number }> {
  rows: T[];
  columns: ColumnDef[];
  loading?: boolean;
  emptyText?: string;
  onSave?: (id: number, patch: Record<string, unknown>) => Promise<void>;
  onDelete?: (id: number) => Promise<void> | void;
  rowClassName?: (row: T) => string;
  cellClassName?: (row: T, columnKey: string) => string;
}

export default function DataTable<T extends { id: number }>({
  rows,
  columns,
  loading,
  emptyText = "暂无数据",
  onSave,
  onDelete,
  rowClassName,
  cellClassName,
}: DataTableProps<T>) {
  const [editing, setEditing] = useState<{ id: number; key: string } | null>(null);
  const [draft, setDraft] = useState("");

  const hasActions = useMemo(() => Boolean(onDelete), [onDelete]);

  async function commitEdit(): Promise<void> {
    if (!editing || !onSave) return;
    await onSave(editing.id, { [editing.key]: draft });
    setEditing(null);
  }

  if (loading) {
    return <div className="rounded-2xl border border-gray-200 bg-white p-5 text-sm text-gray-500">加载中...</div>;
  }

  if (!rows.length) {
    return <div className="rounded-2xl border border-gray-200 bg-white p-5 text-sm text-gray-500">{emptyText}</div>;
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white shadow-sm">
      <table className="w-full table-fixed text-[13px]">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50/70">
            {columns.map((column) => (
              <th
                key={column.key}
                className={`px-3.5 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-gray-500 ${
                  column.widthClass || ""
                }`}
              >
                {column.label}
              </th>
            ))}
            {hasActions && <th className="w-16 px-3 py-2.5" />}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const rowId = Number(row.id ?? 0);
            return (
              <tr
                key={rowId}
                className={`group border-b border-gray-100 hover:bg-gray-50/80 ${rowClassName?.(row as T) || ""}`}
              >
                {columns.map((column) => {
                  const raw = (row as Record<string, unknown>)[column.key];
                  const value = raw == null ? "" : String(raw);
                  const isEditing = editing?.id === rowId && editing?.key === column.key;
                  const display = column.render ? column.render(raw, row as T) : value;
                  return (
                    <td
                      key={column.key}
                      className={`px-3.5 py-2.5 align-top ${cellClassName?.(row as T, column.key) || ""}`}
                      title={value}
                    >
                      {isEditing ? (
                        <input
                          autoFocus
                          value={draft}
                          onChange={(e) => setDraft(e.target.value)}
                          onBlur={() => void commitEdit()}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") void commitEdit();
                            if (e.key === "Escape") setEditing(null);
                          }}
                          className="w-full rounded border border-blue-500 px-2 py-1 text-[13px] outline-none"
                        />
                      ) : (
                        <span
                          className={column.editable && onSave ? "cursor-pointer hover:text-blue-600" : ""}
                          onClick={() => {
                            if (!column.editable || !onSave) return;
                            setEditing({ id: rowId, key: column.key });
                            setDraft(value);
                          }}
                        >
                          {display}
                        </span>
                      )}
                    </td>
                  );
                })}
                {hasActions && (
                  <td className="px-3 py-2.5 align-top">
                    <button
                      onClick={() => onDelete?.(rowId)}
                      className="rounded border border-red-200 px-2 py-1 text-xs text-red-600 opacity-0 transition hover:bg-red-50 group-hover:opacity-100"
                    >
                      删除
                    </button>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
