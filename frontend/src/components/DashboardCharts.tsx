interface PieDatum {
  label: string;
  value: number;
  color: string;
}

interface TreemapDatum {
  label: string;
  value: number;
  color: string;
  note?: string;
}

function polarToCartesian(cx: number, cy: number, radius: number, angle: number) {
  const radians = ((angle - 90) * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(radians),
    y: cy + radius * Math.sin(radians),
  };
}

function describeArc(cx: number, cy: number, radius: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(cx, cy, radius, endAngle);
  const end = polarToCartesian(cx, cy, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
}

export function PieSummary({
  title,
  subtitle,
  totalLabel,
  totalValue,
  data,
}: {
  title: string;
  subtitle?: string;
  totalLabel?: string;
  totalValue?: string;
  data: PieDatum[];
}) {
  const total = data.reduce((sum, item) => sum + Math.max(item.value, 0), 0);
  let current = 0;

  return (
    <div className="chart-panel chart-panel-subtle">
      <div className="split-row split-row-start" style={{ marginBottom: 14 }}>
        <div>
          <div className="card-kicker">概览</div>
          <h3 className="panel-title">{title}</h3>
          {subtitle && <p className="panel-copy">{subtitle}</p>}
        </div>
      </div>

      <div className="pie-layout">
        <div className="pie-visual">
          <svg viewBox="0 0 120 120" className="pie-svg" aria-hidden="true">
            <circle cx="60" cy="60" r="38" fill="none" stroke="rgba(148, 163, 184, 0.18)" strokeWidth="14" />
            {data.map((item) => {
              if (!total || item.value <= 0) return null;
              const startAngle = (current / total) * 360;
              current += item.value;
              const endAngle = (current / total) * 360;
              return (
                <path
                  key={item.label}
                  d={describeArc(60, 60, 38, startAngle, endAngle)}
                  fill="none"
                  stroke={item.color}
                  strokeWidth="14"
                  strokeLinecap="round"
                />
              );
            })}
          </svg>
          <div className="pie-center">
            <div className="pie-total-label">{totalLabel || "总数"}</div>
            <div className="pie-total-value">{totalValue || String(total)}</div>
          </div>
        </div>

        <div className="pie-legend">
          {data.map((item) => {
            const percentage = total ? Math.round((item.value / total) * 100) : 0;
            return (
              <div key={item.label} className="legend-row">
                <div className="legend-label-wrap">
                  <span className="legend-dot" style={{ background: item.color }} />
                  <span className="legend-label">{item.label}</span>
                </div>
                <div className="legend-value">
                  <strong>{percentage}%</strong>
                  <span>{item.value}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function TreemapSummary({
  title,
  subtitle,
  data,
}: {
  title: string;
  subtitle?: string;
  data: TreemapDatum[];
}) {
  const total = data.reduce((sum, item) => sum + Math.max(item.value, 0), 0) || 1;

  return (
    <div className="chart-panel chart-panel-subtle">
      <div className="split-row split-row-start" style={{ marginBottom: 14 }}>
        <div>
          <div className="card-kicker">分布</div>
          <h3 className="panel-title">{title}</h3>
          {subtitle && <p className="panel-copy">{subtitle}</p>}
        </div>
      </div>

      <div className="treemap-grid">
        {data.map((item) => {
          const basis = `${Math.max((item.value / total) * 100, 18)}%`;
          return (
            <div
              key={item.label}
              className="treemap-tile"
              style={{
                flexBasis: basis,
                background: item.color,
              }}
            >
              <div className="treemap-label">{item.label}</div>
              <div className="treemap-value">{item.value}</div>
              {item.note && <div className="treemap-note">{item.note}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
