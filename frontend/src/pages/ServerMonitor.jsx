import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Cpu,
  HardDrive,
  Network,
  PlugZap,
  RefreshCw,
  Server,
  ShieldCheck,
  TerminalSquare,
  Wifi,
  WifiOff,
} from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api, apiErrorMessage, listFrom } from "../api/client.js";
import useServerWebSocket from "../hooks/useServerWebSocket.js";

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function formatSpeed(value) {
  return `${formatBytes(value)}/s`;
}

export default function ServerMonitor() {
  const qc = useQueryClient();
  const live = useServerWebSocket();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [selectedId, setSelectedId] = useState(null);

  const serversQuery = useQuery({
    queryKey: ["servers", status],
    queryFn: () => api.get(`/servers/${status ? `?status=${status}` : ""}`).then(listFrom),
    refetchInterval: 10000,
  });
  const summaryQuery = useQuery({
    queryKey: ["servers", "summary"],
    queryFn: () => api.get("/servers/summary/").then((response) => response.data),
    refetchInterval: 10000,
  });

  const discoverLocal = useMutation({
    mutationFn: () => api.post("/servers/discover-local/"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["servers"] }),
  });
  const collectNow = useMutation({
    mutationFn: () => api.post("/servers/collect-now/"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["servers"] }),
  });
  const createServer = useMutation({
    mutationFn: (payload) => api.post("/servers/", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["servers"] }),
  });

  const liveById = useMemo(() => Object.fromEntries(live.servers.map((server) => [server.id, server])), [live.servers]);
  const servers = useMemo(
    () =>
      (serversQuery.data || [])
        .map((server) => ({ ...server, ...(liveById[server.id] || {}) }))
        .filter((server) => `${server.name} ${server.ip_address} ${server.hostname || ""}`.toLowerCase().includes(query.toLowerCase())),
    [liveById, query, serversQuery.data],
  );
  const selected = servers.find((server) => server.id === selectedId) || servers[0] || null;
  const metricsQuery = useQuery({
    queryKey: ["server-metrics", selected?.id],
    enabled: !!selected,
    queryFn: () => api.get(`/servers/${selected.id}/metrics/?hours=2`).then((response) => response.data),
    refetchInterval: 5000,
  });
  const disksQuery = useQuery({
    queryKey: ["server-disks", selected?.id],
    enabled: !!selected,
    queryFn: () => api.get(`/servers/${selected.id}/disks/`).then((response) => response.data),
    refetchInterval: 10000,
  });

  const latest = selected?.latest_metrics || metricsQuery.data?.[metricsQuery.data.length - 1] || null;
  const summary = summaryQuery.data || {};
  const error = apiErrorMessage(serversQuery.error, "");

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-white/10 bg-slate-950/80 p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-200">Enterprise Server Management</p>
            <h1 className="mt-2 text-2xl font-semibold text-white">Real-Time Server Monitor</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-400">
              Real servers only. Local machines use a psutil collector; remote hosts show reachability until an authenticated agent posts live metrics.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="btn-secondary" onClick={() => collectNow.mutate()} disabled={collectNow.isPending}>
              <RefreshCw size={16} className={collectNow.isPending ? "animate-spin" : ""} /> Collect Now
            </button>
            <button className="btn-primary" onClick={() => discoverLocal.mutate()} disabled={discoverLocal.isPending}>
              <PlugZap size={16} /> Discover Local Server
            </button>
            <AddServer onSubmit={(payload) => createServer.mutate(payload)} busy={createServer.isPending} />
          </div>
        </div>
      </section>

      <div className="grid gap-3 md:grid-cols-4">
        <Metric icon={Server} label="Registered Servers" value={summary.servers ?? servers.length} />
        <Metric icon={Wifi} label="Connected" value={summary.connected ?? 0} tone="emerald" />
        <Metric icon={WifiOff} label="Offline" value={summary.offline ?? 0} tone={(summary.offline ?? 0) ? "rose" : "slate"} />
        <Metric icon={Activity} label="WebSocket" value={live.isConnected ? "Live" : "Disconnected"} tone={live.isConnected ? "emerald" : "amber"} />
      </div>

      <div className="flex flex-col gap-3 rounded-lg border border-white/10 bg-white/[.035] p-3 md:flex-row">
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search servers" className="form-control md:max-w-xs" />
        <select value={status} onChange={(event) => setStatus(event.target.value)} className="form-control md:max-w-[180px]">
          <option value="">All statuses</option>
          <option value="active">Connected</option>
          <option value="down">Offline</option>
          <option value="maintenance">Maintenance</option>
          <option value="inactive">Inactive</option>
        </select>
        <span className="ml-auto self-center text-xs text-slate-400">
          Last heartbeat: {live.lastUpdate ? live.lastUpdate.toLocaleTimeString() : "waiting"}
        </span>
      </div>

      {error && <div className="rounded-lg border border-rose-300/20 bg-rose-500/10 p-4 text-sm text-rose-100">{error}</div>}

      {!serversQuery.isLoading && !servers.length ? (
        <ServerNotFound onDiscover={() => discoverLocal.mutate()} busy={discoverLocal.isPending} />
      ) : (
        <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
          <section className="space-y-3">
            {servers.map((server) => (
              <button
                key={server.id}
                onClick={() => setSelectedId(server.id)}
                className={`w-full rounded-lg border p-4 text-left transition ${selected?.id === server.id ? "border-cyan-300/45 bg-cyan-300/10" : "border-white/10 bg-white/[.04] hover:border-white/20"}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="font-semibold text-white">{server.name}</h2>
                    <p className="mt-1 text-xs text-slate-400">{server.ip_address} · {server.connection_method}</p>
                  </div>
                  <StatusBadge server={server} />
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                  <Mini label="CPU" value={`${Math.round(server.latest_metrics?.cpu_percent || 0)}%`} />
                  <Mini label="RAM" value={`${Math.round(server.latest_metrics?.memory_percent || 0)}%`} />
                  <Mini label="Health" value={server.health_score || 0} />
                </div>
              </button>
            ))}
          </section>

          <section className="space-y-5">
            <ServerDetail server={selected} latest={latest} metrics={metricsQuery.data || []} disks={disksQuery.data || []} />
          </section>
        </div>
      )}
    </div>
  );
}

function ServerDetail({ server, latest, metrics, disks }) {
  if (!server) return null;
  const chart = metrics.slice(-120);
  return (
    <>
      <section className="rounded-lg border border-white/10 bg-white/[.04] p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200">{server.server_type}</p>
            <h2 className="mt-2 text-xl font-semibold text-white">{server.hostname || server.name}</h2>
            <p className="mt-1 text-sm text-slate-400">{server.os_name || "OS pending"} {server.os_version || ""}</p>
          </div>
          <StatusBadge server={server} large />
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-4">
          <Metric icon={Cpu} label="CPU" value={`${Math.round(latest?.cpu_percent || 0)}%`} />
          <Metric icon={Activity} label="RAM" value={`${Math.round(latest?.memory_percent || 0)}%`} />
          <Metric icon={HardDrive} label="Disk" value={`${Math.round(latest?.disk_percent || 0)}%`} />
          <Metric icon={ShieldCheck} label="Health Score" value={server.health_score || 0} />
        </div>
        {server.status === "down" && (
          <div className="mt-4 rounded-lg border border-amber-300/20 bg-amber-400/10 p-4 text-sm text-amber-100">
            <p className="font-semibold">Diagnostics</p>
            <p className="mt-1">{server.last_error || "No heartbeat received. Check network route, firewall, agent service, and connection port."}</p>
          </div>
        )}
      </section>

      <section className="grid gap-5 xl:grid-cols-[1fr_320px]">
        <div className="rounded-lg border border-white/10 bg-white/[.04] p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-white"><Activity size={16} /> Live Metrics</h3>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart}>
                <XAxis dataKey="recorded_at" hide />
                <YAxis stroke="#94a3b8" domain={[0, 100]} />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,.12)", borderRadius: 8 }} />
                <Line dataKey="cpu_percent" stroke="#22d3ee" dot={false} />
                <Line dataKey="memory_percent" stroke="#34d399" dot={false} />
                <Line dataKey="disk_percent" stroke="#f59e0b" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-lg border border-white/10 bg-white/[.04] p-4">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-white"><Network size={16} /> Network</h3>
          <div className="mt-4 space-y-3 text-sm">
            <Info label="Upload" value={formatSpeed(latest?.upload_bytes_per_sec)} />
            <Info label="Download" value={formatSpeed(latest?.download_bytes_per_sec)} />
            <Info label="Total Sent" value={formatBytes(latest?.network_bytes_sent)} />
            <Info label="Total Received" value={formatBytes(latest?.network_bytes_recv)} />
            <Info label="Latency" value={`${latest?.latency_ms || 0} ms`} />
            <Info label="Packet Loss" value={`${latest?.packet_loss_percent || 0}%`} />
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-white/10 bg-white/[.04] p-4">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-white"><TerminalSquare size={16} /> Disks</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {disks.slice(0, 12).map((disk) => (
            <div key={`${disk.mount_point}-${disk.recorded_at}`} className="rounded-lg border border-white/10 bg-slate-950/70 p-3">
              <div className="flex justify-between gap-3 text-sm text-white"><span>{disk.mount_point}</span><span>{Math.round(disk.usage_percent)}%</span></div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full bg-cyan-300" style={{ width: `${Math.min(100, disk.usage_percent)}%` }} /></div>
              <p className="mt-2 text-xs text-slate-400">{disk.used_gb} GB used / {disk.total_gb} GB</p>
            </div>
          ))}
          {!disks.length && <p className="text-sm text-slate-400">No disk telemetry has been received for this server yet.</p>}
        </div>
      </section>
    </>
  );
}

function ServerNotFound({ onDiscover, busy }) {
  return (
    <section className="grid min-h-[420px] place-items-center rounded-lg border border-amber-300/20 bg-slate-950/70 p-8 text-center">
      <div className="max-w-xl">
        <div className="mx-auto grid size-20 place-items-center rounded-2xl border border-amber-300/20 bg-amber-300/10 text-amber-100">
          <AlertTriangle size={38} />
        </div>
        <h2 className="mt-5 text-3xl font-semibold text-white">SERVER NOT FOUND</h2>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          No real server has been registered in the backend. Add a remote endpoint or discover this machine to begin collecting real telemetry.
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <button className="btn-primary" onClick={onDiscover} disabled={busy}>
            <PlugZap size={16} /> Discover Local Server
          </button>
          <button className="btn-secondary" onClick={() => window.location.reload()}>
            <RefreshCw size={16} /> Reconnect
          </button>
        </div>
      </div>
    </section>
  );
}

function AddServer({ onSubmit, busy }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", ip_address: "", ssh_port: 22, server_type: "linux", connection_method: "ssh", status: "active" });
  return (
    <>
      <button onClick={() => setOpen(true)} className="btn-secondary" type="button"><Server size={16} /> Add Server</button>
      {open && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              onSubmit(form);
              setOpen(false);
            }}
            className="w-full max-w-lg rounded-lg border border-white/10 bg-slate-950 p-5"
          >
            <h2 className="text-lg font-semibold text-white">Register Real Server</h2>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <Field label="Name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} required />
              <Field label="IP Address" value={form.ip_address} onChange={(value) => setForm({ ...form, ip_address: value })} required />
              <Field label="Port" type="number" value={form.ssh_port} onChange={(value) => setForm({ ...form, ssh_port: Number(value) })} />
              <label className="grid gap-2 text-xs uppercase tracking-[0.12em] text-slate-400">
                Method
                <select className="form-control normal-case tracking-normal" value={form.connection_method} onChange={(event) => setForm({ ...form, connection_method: event.target.value })}>
                  {["ssh", "sftp", "smb", "winrm", "rest", "websocket", "agent"].map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button className="btn-secondary" type="button" onClick={() => setOpen(false)}>Cancel</button>
              <button className="btn-primary" disabled={busy} type="submit">Save Server</button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}

function Field({ label, value, onChange, type = "text", required = false }) {
  return (
    <label className="grid gap-2 text-xs uppercase tracking-[0.12em] text-slate-400">
      {label}
      <input required={required} type={type} value={value} onChange={(event) => onChange(event.target.value)} className="form-control normal-case tracking-normal" />
    </label>
  );
}

function StatusBadge({ server, large = false }) {
  const active = server.status === "active";
  const classes = active ? "bg-emerald-400/10 text-emerald-100" : server.status === "down" ? "bg-rose-400/10 text-rose-100" : "bg-amber-400/10 text-amber-100";
  return <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 font-semibold ${large ? "text-sm" : "text-xs"} ${classes}`}>{active ? <Wifi size={14} /> : <WifiOff size={14} />}{active ? "Connected" : server.status}</span>;
}

function Metric({ icon: Icon, label, value, tone = "cyan" }) {
  const toneClass = tone === "emerald" ? "text-emerald-200" : tone === "rose" ? "text-rose-200" : tone === "amber" ? "text-amber-200" : "text-cyan-200";
  return (
    <div className="rounded-lg border border-white/10 bg-white/[.04] p-4">
      <Icon size={18} className={toneClass} />
      <p className="mt-3 text-xs uppercase tracking-[0.14em] text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function Mini({ label, value }) {
  return <div className="rounded-md bg-white/[.05] p-2"><p className="text-slate-500">{label}</p><p className="mt-1 font-semibold text-white">{value}</p></div>;
}

function Info({ label, value }) {
  return <div className="flex justify-between gap-3 border-b border-white/10 pb-2 last:border-b-0"><span className="text-slate-400">{label}</span><span className="font-semibold text-white">{value}</span></div>;
}
