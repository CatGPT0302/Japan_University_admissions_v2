import type { StatsResponse } from "../types";

interface StatsBarProps {
  stats: StatsResponse | null;
}

function Card({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</div>
      <div className="mt-3 text-[26px] font-semibold leading-none text-[#111827]">{value}</div>
    </div>
  );
}

export default function StatsBar({ stats }: StatsBarProps) {
  if (!stats) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Card label="已确认记录" value="--" />
        <Card label="待复核记录" value="--" />
        <Card label="高校数量" value="--" />
        <Card label="平均置信度" value="--" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Card label="已确认记录" value={stats.total_records} />
      <Card label="待复核记录" value={stats.staging_records} />
      <Card label="高校数量" value={stats.universities} />
      <Card label="平均置信度" value={stats.avg_confidence.toFixed(2)} />
    </div>
  );
}
