import type { NavPage } from "../types";

interface SidebarProps {
  page: NavPage;
  onChange: (page: NavPage) => void;
}

const items: Array<{ key: NavPage; label: string; sub?: string }> = [
  { key: "dashboard",  label: "概览" },
  { key: "upload",     label: "上传 PDF" },
  { key: "review",     label: "人工复查" },
  { key: "staging",    label: "待复核表格" },
  { key: "confirm",    label: "确认入库" },
  { key: "records",    label: "已确认记录" },
];

export default function Sidebar({ page, onChange }: SidebarProps) {
  return (
    <aside style={{
      width: 220,
      background: 'var(--surface)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      padding: '0',
      flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{padding: '28px 24px 20px', borderBottom: '1px solid var(--border)'}}>
        <div style={{
          fontFamily: "'Playfair Display', Georgia, serif",
          fontSize: 20,
          fontWeight: 700,
          lineHeight: 1.15,
          color: 'var(--ink)',
          letterSpacing: '-0.3px',
        }}>
          留学生<br/>
          <span style={{fontStyle:'italic', color:'var(--red)'}}>招生系统</span>
        </div>
        <div style={{marginTop: 8, fontSize: 11, letterSpacing: '0.12em', color: 'var(--ink3)', textTransform: 'uppercase'}}>
          admissions_v2
        </div>
      </div>

      {/* Nav */}
      <nav style={{padding: '12px 12px', flex: 1}}>
        {items.map((item) => {
          const active = page === item.key;
          return (
            <button
              key={item.key}
              onClick={() => onChange(item.key)}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                padding: '9px 14px',
                marginBottom: 2,
                borderRadius: 8,
                fontSize: 13,
                fontWeight: active ? 500 : 400,
                fontFamily: 'inherit',
                cursor: 'pointer',
                border: 'none',
                transition: 'background 0.15s, color 0.15s',
                background: active ? 'var(--ink)' : 'transparent',
                color: active ? '#fff' : 'var(--ink2)',
              }}
            >
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div style={{padding: '16px 24px', borderTop: '1px solid var(--border)'}}>
        <div style={{fontSize: 11, color: 'var(--ink3)', lineHeight: 1.6}}>
          <span style={{display:'inline-block', width:6, height:6, borderRadius:'50%', background:'#22c55e', marginRight:6, verticalAlign:'middle'}}/>
          系统运行中
        </div>
      </div>
    </aside>
  );
}
