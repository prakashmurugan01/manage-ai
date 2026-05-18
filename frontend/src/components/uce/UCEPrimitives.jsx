import { Bell, Server, Shield, Globe2 } from "lucide-react";

export function StatCard({ title, value, detail, icon: Icon = Shield, tone = "cyan" }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4 shadow-xl shadow-black/10">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">{title}</p>
        <Icon className={`h-5 w-5 text-${tone}-300`} />
      </div>
      <div className="mt-3 text-3xl font-semibold text-white">{value}</div>
      <p className="mt-1 text-sm text-slate-400">{detail}</p>
    </div>
  );
}

export function StatusBadge({ value }) {
  const map = { active: "bg-emerald-400/15 text-emerald-200", live: "bg-emerald-400/15 text-emerald-200", down: "bg-red-400/15 text-red-200", expired: "bg-red-500/20 text-red-200", warning: "bg-amber-400/15 text-amber-100", maintenance: "bg-sky-400/15 text-sky-200", suspended: "bg-slate-400/15 text-slate-200" };
  return <span className={`rounded-full px-2 py-1 text-xs font-medium ${map[value] || "bg-white/10 text-slate-200"}`}>{value}</span>;
}

export function Meter({ label, value }) {
  const tone = value > 85 ? "bg-red-400" : value > 70 ? "bg-amber-300" : "bg-emerald-300";
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-400"><span>{label}</span><span>{Math.round(value || 0)}%</span></div>
      <div className="h-2 rounded-full bg-white/10"><div className={`h-2 rounded-full ${tone}`} style={{ width: `${Math.min(100, value || 0)}%` }} /></div>
    </div>
  );
}

export function ServerCard({ server, onToggle }) {
  const metrics = server.latest_metrics || {};
  return (
    <div className="rounded-lg border border-white/10 bg-slate-950/70 p-4">
      <div className="flex items-start justify-between gap-3">
        <div><h3 className="font-semibold text-white">{server.name || `Server ${server.id}`}</h3><p className="text-sm text-slate-400">{server.ip_address || "metrics stream"}</p></div>
        <StatusBadge value={server.status || "active"} />
      </div>
      <div className="mt-4 space-y-3">
        <Meter label="CPU" value={metrics.cpu_percent} />
        <Meter label="RAM" value={metrics.memory_percent} />
        <Meter label="Disk" value={metrics.disk_percent} />
      </div>
      <div className="mt-4 flex items-center justify-between text-sm text-slate-400">
        <span>{formatUptime(metrics.uptime_seconds || 0)}</span>
        <button onClick={() => onToggle?.(server)} className={`rounded-full px-3 py-1 text-xs ${server.is_enabled === false ? "bg-slate-700" : "bg-emerald-500/20 text-emerald-100"}`}>{server.is_enabled === false ? "OFF" : "ON"}</button>
      </div>
    </div>
  );
}

export function formatUptime(seconds) {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${d}d ${h}h ${m}m`;
}

export const icons = { Bell, Server, Shield, Globe2 };
