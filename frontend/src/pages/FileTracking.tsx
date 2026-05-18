import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Database, FileClock, HardDrive, Network, Plus, RefreshCw } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { createFileTransfer, getFileTrackingDashboard } from "../api/fileTracking";
import { useRealtimeEvents } from "../hooks/useRealtimeEvents";

function formatBytes(value: unknown) {
  const bytes = Number(value || 0);
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function Metric({ icon: Icon, label, value }: { icon: typeof HardDrive; label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">{label}</p>
          <p className="mt-3 text-2xl font-semibold text-white">{value}</p>
        </div>
        <span className="rounded-lg bg-white/10 p-2 text-teal-200">
          <Icon size={20} />
        </span>
      </div>
    </div>
  );
}

export default function FileTracking() {
  useRealtimeEvents();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    source_path: "C:\\Finance\\backup.sql",
    destination_path: "D:\\Archive\\backup.sql",
    size_bytes: 2147483648,
    process_name: "manual-cli",
    status: "completed",
  });
  const dashboard = useQuery({ queryKey: ["file-tracking", "dashboard"], queryFn: getFileTrackingDashboard });
  const mutation = useMutation({
    mutationFn: createFileTransfer,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["file-tracking", "dashboard"] }),
  });

  const statusChart = useMemo(() => {
    const status = dashboard.data?.by_status ?? {};
    return Object.entries(status).map(([name, total]) => ({ name, total }));
  }, [dashboard.data]);

  const extensionChart = useMemo(() => dashboard.data?.by_extension?.map((row) => ({ name: row.file_extension || "none", bytes: row.bytes })) ?? [], [dashboard.data]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate(form);
  };

  return (
    <div className="space-y-5 p-4 lg:p-6">
      <section className="rounded-lg border border-white/10 bg-slate-950 p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-teal-200">Disk-to-Disk Engine</p>
            <h1 className="mt-2 text-2xl font-semibold text-white">File Tracking Control Center</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-400">Track C, D, USB, and network file movement in real time. AI can enhance detection later, but this engine runs fully without it.</p>
          </div>
          <button className="inline-flex items-center gap-2 rounded-md border border-white/10 px-3 py-2 text-sm text-white" onClick={() => dashboard.refetch()} type="button">
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-4">
        <Metric icon={FileClock} label="Transfers" value={dashboard.data?.totals.transfers ?? 0} />
        <Metric icon={Database} label="Bytes Moved" value={formatBytes(dashboard.data?.totals.bytes_moved)} />
        <Metric icon={AlertTriangle} label="Open Alerts" value={dashboard.data?.totals.open_alerts ?? 0} />
        <Metric icon={HardDrive} label="Volumes" value={dashboard.data?.totals.volumes ?? 0} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <section className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
          <h2 className="text-sm font-semibold text-white">Transfer Status</h2>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={statusChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.08)" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip />
                <Bar dataKey="total" fill="#2dd4bf" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
          <h2 className="text-sm font-semibold text-white">Bytes By Extension</h2>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={extensionChart}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.08)" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" tickFormatter={(value) => formatBytes(value)} />
                <Tooltip formatter={(value) => formatBytes(value)} />
                <Bar dataKey="bytes" fill="#38bdf8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <form onSubmit={submit} className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-white"><Plus size={16} /> Record Transfer</h2>
          {(["source_path", "destination_path", "size_bytes", "process_name", "status"] as const).map((key) => (
            <label className="mt-3 block text-xs uppercase tracking-[0.12em] text-slate-500" key={key}>
              {key.replace("_", " ")}
              <input
                className="mt-2 w-full rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-sm normal-case tracking-normal text-white outline-none"
                value={form[key]}
                onChange={(event) => setForm((current) => ({ ...current, [key]: key === "size_bytes" ? Number(event.target.value) : event.target.value }))}
              />
            </label>
          ))}
          <button className="mt-4 inline-flex items-center gap-2 rounded-md bg-teal-400 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-teal-300 disabled:opacity-50 transition-colors" type="submit" disabled={mutation.isPending}>
            <Plus size={16} />
            {mutation.isPending ? "Recording..." : "Record Transfer"}
          </button>
        </form>

        <section className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
          <h2 className="text-sm font-semibold text-white">Recent Transfers</h2>
          <div className="mt-4 overflow-auto">
            <table className="min-w-full text-left text-sm border-collapse">
              <thead className="text-xs uppercase tracking-[0.12em] text-slate-500 border-b border-white/10">
                <tr>
                  <th className="py-2 px-3 font-semibold">File</th>
                  <th className="py-2 px-3 font-semibold">Route</th>
                  <th className="py-2 px-3 font-semibold">Size</th>
                  <th className="py-2 px-3 font-semibold">Status</th>
                  <th className="py-2 px-3 font-semibold">Risk</th>
                </tr>
              </thead>
              <tbody>
                {(dashboard.data?.recent_transfers ?? []).map((row) => (
                  <tr className="border-t border-white/10 text-slate-300 hover:bg-white/5 transition-colors" key={String(row.id)}>
                    <td className="py-3 px-3 font-medium text-white truncate">{String(row.file_name)}</td>
                    <td className="py-3 px-3 text-xs text-slate-400 max-w-xs truncate" title={`${String(row.source_path)} → ${String(row.destination_path)}`}>{String(row.source_path)} → {String(row.destination_path)}</td>
                    <td className="py-3 px-3 whitespace-nowrap">{formatBytes(row.size_bytes)}</td>
                    <td className="py-3 px-3 whitespace-nowrap"><span className="px-2 py-1 rounded text-xs bg-white/10">{String(row.status)}</span></td>
                    <td className="py-3 px-3 whitespace-nowrap text-xs font-medium">{String(row.risk_score)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-white"><Network size={16} /> Volumes</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {(dashboard.data?.volume_usage ?? []).map((volume) => (
            <div className="rounded-lg border border-white/10 bg-slate-950 p-3" key={volume.id}>
              <p className="font-medium text-white">{volume.label}</p>
              <p className="mt-1 text-xs text-slate-500">{volume.mount_path} · {volume.disk_type}</p>
              <p className="mt-3 text-sm text-slate-300">{formatBytes(volume.used_bytes)} used / {formatBytes(volume.total_bytes)}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

