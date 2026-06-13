import { useEffect, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { StatCard } from "../components/uce/UCEPrimitives.jsx";

const WS_BASE = import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000/ws";

export default function ApiMonitor() {
  const [points, setPoints] = useState([]);
  const [stats, setStats] = useState({ top_endpoints: [], recent_logs: [] });
  useEffect(() => {
    const token = localStorage.getItem("accessToken") || "";
    const ws = new WebSocket(`${WS_BASE}/api-monitor/?token=${encodeURIComponent(token)}`);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setStats(data);
      setPoints((rows) => [...rows.slice(-59), { time: new Date().toLocaleTimeString(), rps: data.requests_per_sec }]);
    };
    return () => ws.close();
  }, []);
  return <div className="space-y-5"><h1 className="text-2xl font-semibold text-white">API Monitor</h1><div className="grid gap-4 md:grid-cols-3"><StatCard title="Requests / sec" value={stats.requests_per_sec || 0} detail="Last 60 seconds" /><StatCard title="Average response" value={`${stats.avg_response_time_ms || 0}ms`} detail="API key traffic" /><StatCard title="Error rate" value={`${stats.error_rate_percent || 0}%`} detail="4xx and 5xx responses" /></div><div className="h-72 rounded-lg border border-white/10 bg-white/[0.04] p-4"><ResponsiveContainer><AreaChart data={points}><XAxis dataKey="time" hide /><YAxis /><Tooltip /><Area dataKey="rps" stroke="#67e8f9" fill="#164e63" /></AreaChart></ResponsiveContainer></div><div className="grid gap-4 xl:grid-cols-2"><Panel title="Top endpoints" rows={stats.top_endpoints || []} /><Panel title="Live request log" rows={stats.recent_logs || []} /></div></div>;
}

function Panel({ title, rows }) {
  return <section className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><h2 className="mb-3 font-semibold text-white">{title}</h2><div className="space-y-2">{rows.map((row, index) => <div key={index} className="grid grid-cols-[1fr_auto_auto] gap-3 rounded-md bg-slate-950/60 p-3 text-sm"><span className="truncate text-slate-200">{row.endpoint}</span><span>{row.count || row.response_code}</span><span>{row.avg_response_ms || row.response_time_ms || 0}ms</span></div>)}</div></section>;
}
