import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Line, LineChart, RadialBar, RadialBarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, listFrom } from "../api/client.js";

export default function DiskMonitor() {
  const [serverId, setServerId] = useState(null);
  const servers = useQuery({ queryKey: ["servers"], queryFn: () => api.get("/servers/").then(listFrom) });
  const disks = useQuery({ queryKey: ["disk-mounts", serverId], enabled: !!serverId, queryFn: () => api.get(`/disk-mounts/?server=${serverId}`).then(listFrom) });
  const selected = serverId || servers.data?.[0]?.id;
  const latest = useMemo(() => {
    const map = {};
    (disks.data || []).forEach((disk) => { if (!map[disk.mount_point]) map[disk.mount_point] = disk; });
    return Object.values(map);
  }, [disks.data]);
  return <div className="space-y-5"><h1 className="text-2xl font-semibold text-white">Disk Monitor</h1><div className="flex flex-wrap gap-2">{(servers.data || []).map((s) => <button key={s.id} onClick={() => setServerId(s.id)} className={`rounded-md px-3 py-2 text-sm ${selected === s.id ? "bg-cyan-400 text-slate-950" : "bg-white/10 text-white"}`}>{s.name}</button>)}</div><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{latest.map((disk) => <div key={disk.id} className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><h2 className="font-semibold text-white">{disk.mount_point}</h2><div className="h-44"><ResponsiveContainer><RadialBarChart innerRadius="65%" outerRadius="90%" data={[{ name: "usage", value: disk.usage_percent, fill: disk.usage_percent > disk.alert_threshold ? "#f87171" : "#67e8f9" }]}><RadialBar dataKey="value" cornerRadius={8} /></RadialBarChart></ResponsiveContainer></div><p className="text-sm text-slate-400">Threshold {disk.alert_threshold}%</p></div>)}</div><div className="h-72 rounded-lg border border-white/10 bg-white/[0.04] p-4"><ResponsiveContainer><LineChart data={disks.data || []}><XAxis dataKey="recorded_at" hide /><YAxis /><Tooltip /><Line dataKey="usage_percent" stroke="#67e8f9" dot={false} /></LineChart></ResponsiveContainer></div></div>;
}
