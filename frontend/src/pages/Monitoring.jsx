import { Gauge, HardDrive, Power, RefreshCcw, Server, Users, Wifi } from "lucide-react";
import { useEffect, useState } from "react";

import { analyticsApi, enterpriseApi } from "../api/services.js";
import Sparkline from "../components/dashboard/Sparkline.jsx";
import Badge from "../components/ui/Badge.jsx";
import Button from "../components/ui/Button.jsx";
import Page from "../components/ui/Page.jsx";
import StatCard from "../components/ui/StatCard.jsx";

export default function Monitoring() {
  const [data, setData] = useState(null);
  const [server, setServer] = useState(null);
  const [network, setNetwork] = useState(null);

  function load() {
    Promise.all([analyticsApi.performance(), enterpriseApi.serverLive(), enterpriseApi.networkLive()]).then(([performanceResponse, serverResponse, networkResponse]) => {
      setData(performanceResponse.data);
      setServer(serverResponse.data);
      setNetwork(networkResponse.data);
    });
  }

  async function controlServer(patch) {
    if (!server?.id) return;
    const { data } = await enterpriseApi.controlServer(server.id, patch);
    setServer(data);
  }

  useEffect(load, []);

  return (
    <Page title="Live Monitoring" subtitle="Server control, API latency, storage, active users, request speed, network throughput, and uptime." actions={<Button variant="secondary" onClick={load}><RefreshCcw size={16} />Refresh</Button>}>
      <div className="mb-6 overflow-hidden rounded-lg border border-white/10 bg-gradient-to-br from-cyan-300/15 via-teal-300/10 to-rose-300/10 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs uppercase tracking-[0.14em] text-slate-300"><Server size={14} />Server Command</div>
            <h1 className="mt-4 text-2xl font-semibold text-white">{server?.company_name || "Company"} infrastructure</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-300">Control server state, watch network health, and inspect live operational load from one monitoring surface.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => controlServer({ is_enabled: true })}><Power size={16} />ON</Button>
            <Button variant="secondary" onClick={() => controlServer({ is_enabled: false })}><Power size={16} />OFF</Button>
            <Button variant="ghost" onClick={() => controlServer({ scale_units: (server?.scale_units || 1) + 1 })}><Gauge size={16} />Scale</Button>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <StatCard label="Server Health" value={server?.health ?? "..."} icon={Server} />
        <StatCard label="Active Users" value={server?.active_users ?? "..."} icon={Users} />
        <StatCard label="Files" value={server?.file_count ?? "..."} icon={HardDrive} />
        <StatCard label="Scale Units" value={server?.scale_units ?? "..."} icon={Gauge} />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_0.8fr]">
        <div className="panel p-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Server Load</h2>
              <p className="mt-1 text-xs text-slate-500">Storage, uptime, requests, and control state.</p>
            </div>
            <Badge value={server?.is_enabled ? "ON" : "OFF"} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <MetricLine label="Storage" value={server?.storage_percent ?? 0} detail={`${server?.storage_used_gb ?? 0}/${server?.storage_total_gb ?? 0} GB`} />
            <MetricLine label="Load" value={Math.min(100, (server?.scale_units || 1) * 12 + (server?.active_users || 0))} detail={`${server?.scale_units ?? 1} units`} />
            <MetricLine label="Incoming" value={Math.min(100, (server?.incoming_requests || 0) / 20)} detail={`${server?.incoming_requests ?? 0} requests`} />
            <MetricLine label="Outgoing" value={Math.min(100, (server?.outgoing_requests || 0) / 18)} detail={`${server?.outgoing_requests ?? 0} responses`} />
          </div>
        </div>
        <div className="panel p-4">
          <div className="mb-4 flex items-center gap-2">
            <Wifi size={18} className="text-teal-200" />
            <h2 className="text-sm font-semibold text-white">Network Dashboard</h2>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <StatCard label="Download" value={`${network?.current?.download_mbps ?? "..."} Mbps`} />
            <StatCard label="Upload" value={`${network?.current?.upload_mbps ?? "..."} Mbps`} />
            <StatCard label="Ping" value={`${network?.current?.latency_ms ?? "..."} ms`} />
            <StatCard label="RPS" value={network?.current?.requests_per_second ?? "..."} />
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <StatCard label="Requests" value={data?.request_count ?? "..."} />
        <StatCard label="Avg Latency" value={`${data?.average_latency_ms ?? "..."} ms`} />
        <StatCard label="Errors" value={data?.error_count ?? "..."} />
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="panel p-4">
          <h2 className="text-sm font-semibold text-white">Daily Volume</h2>
          <Sparkline data={data?.by_day || []} color="#fbbf24" />
        </div>
        <div className="panel overflow-hidden">
          <div className="border-b border-white/10 p-4">
            <h2 className="text-sm font-semibold text-white">Slowest Requests</h2>
          </div>
          <div className="divide-y divide-white/10">
            {(data?.slowest_requests || []).map((item, index) => (
              <div key={`${item.path}-${index}`} className="flex items-center justify-between gap-4 p-4 text-sm">
                <span className="truncate text-slate-300">{item.method} {item.path}</span>
                <span className="text-amber-200">{item.duration_ms} ms</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Page>
  );
}

function MetricLine({ label, value, detail }) {
  const safeValue = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="text-slate-300">{label}</span>
        <span className="text-xs text-slate-500">{detail}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-teal-300" style={{ width: `${safeValue}%` }} />
      </div>
    </div>
  );
}
