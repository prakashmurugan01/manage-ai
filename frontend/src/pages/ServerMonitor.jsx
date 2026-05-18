import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, listFrom } from "../api/client.js";
import { Meter, ServerCard, StatusBadge } from "../components/uce/UCEPrimitives.jsx";

export default function ServerMonitor() {
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState(null);
  const servers = useQuery({ queryKey: ["servers", status], queryFn: () => api.get(`/servers/${status ? `?status=${status}` : ""}`).then(listFrom) });
  const metrics = useQuery({ queryKey: ["server-metrics", selected?.id], enabled: !!selected, queryFn: () => api.get(`/servers/${selected.id}/metrics/`).then((r) => r.data) });
  const disks = useQuery({ queryKey: ["server-disks", selected?.id], enabled: !!selected, queryFn: () => api.get(`/servers/${selected.id}/disks/`).then((r) => r.data) });
  const createServer = useMutation({ mutationFn: (payload) => api.post("/servers/", payload), onSuccess: () => qc.invalidateQueries({ queryKey: ["servers"] }) });
  const filtered = useMemo(() => (servers.data || []).filter((s) => `${s.name} ${s.ip_address}`.toLowerCase().includes(query.toLowerCase())), [servers.data, query]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-2xl font-semibold text-white">Server Monitor</h1><AddServer onSubmit={(payload) => createServer.mutate(payload)} /></div>
      <div className="flex gap-3"><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search servers" className="rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white" /><select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-md border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white"><option value="">All</option><option value="active">Active</option><option value="down">Down</option><option value="maintenance">Maintenance</option></select></div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{filtered.map((server) => <button key={server.id} onClick={() => setSelected(server)} className="text-left"><ServerCard server={server} /></button>)}</div>
      {selected && <aside className="fixed inset-y-0 right-0 z-40 w-full max-w-xl overflow-y-auto border-l border-white/10 bg-slate-950 p-6 shadow-2xl"><button onClick={() => setSelected(null)} className="float-right text-slate-400">Close</button><h2 className="text-xl font-semibold text-white">{selected.name}</h2><StatusBadge value={selected.status} /><div className="mt-6 h-64"><ResponsiveContainer><LineChart data={metrics.data || []}><XAxis dataKey="recorded_at" hide /><YAxis /><Tooltip /><Line dataKey="cpu_percent" stroke="#67e8f9" dot={false} /><Line dataKey="memory_percent" stroke="#a7f3d0" dot={false} /></LineChart></ResponsiveContainer></div><h3 className="mt-5 font-semibold text-white">Disk mounts</h3><div className="mt-2 space-y-2">{(disks.data || []).slice(0, 10).map((disk) => <div key={disk.id} className="rounded-md bg-white/5 p-3"><div className="mb-2 flex justify-between text-sm text-slate-300"><span>{disk.mount_point}</span><span>{disk.used_gb}/{disk.total_gb} GB</span></div><Meter label="Usage" value={disk.usage_percent} /></div>)}</div><h3 className="mt-5 font-semibold text-white">Maintenance</h3><input type="datetime-local" className="mt-2 rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white" /></aside>}
    </div>
  );
}

function AddServer({ onSubmit }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", ip_address: "", ssh_port: 22, status: "active" });
  return <><button onClick={() => setOpen(true)} className="rounded-md bg-cyan-400 px-3 py-2 text-sm font-medium text-slate-950">Add server</button>{open && <div className="fixed inset-0 z-50 grid place-items-center bg-black/60"><form onSubmit={(e) => { e.preventDefault(); onSubmit(form); setOpen(false); }} className="w-full max-w-md rounded-lg border border-white/10 bg-slate-950 p-5"><h2 className="mb-4 font-semibold text-white">Add server</h2>{["name", "ip_address", "ssh_port"].map((key) => <input key={key} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} placeholder={key} className="mb-3 w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-white" />)}<button className="rounded-md bg-cyan-400 px-3 py-2 text-slate-950">Save</button></form></div>}</>;
}
