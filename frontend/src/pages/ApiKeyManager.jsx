import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate, useParams } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BellRing,
  Bot,
  BrainCircuit,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Copy,
  DatabaseZap,
  Download,
  Eye,
  FileJson,
  Filter,
  Globe2,
  KeyRound,
  Lock,
  MessageSquareWarning,
  Network,
  Play,
  RefreshCw,
  Search,
  ServerCog,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  TerminalSquare,
  Users,
  Webhook,
  X,
  Zap
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import { api, apiErrorMessage } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

const WS_BASE = import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000/ws";

const centers = [
  { id: "overview", label: "Overview", icon: Sparkles },
  { id: "chatbot", label: "Chatbot Complaints", icon: MessageSquareWarning },
  { id: "erp", label: "ERP Center", icon: DatabaseZap },
  { id: "webhooks", label: "Webhooks", icon: Webhook },
  { id: "security", label: "Security", icon: ShieldCheck },
  { id: "playground", label: "Playground", icon: TerminalSquare }
];

const keyTypes = [
  { value: "chatbot", label: "Chatbot", icon: Bot, scopes: ["complaints:write", "tickets:create", "customers:read"] },
  { value: "crm", label: "CRM", icon: BriefcaseBusiness, scopes: ["customers:sync", "deals:read", "tickets:create"] },
  { value: "erp", label: "ERP", icon: DatabaseZap, scopes: ["erp:sync", "inventory:read", "orders:read"] },
  { value: "webhook", label: "Webhook", icon: Webhook, scopes: ["webhooks:write", "events:read", "retries:manage"] },
  { value: "ai_agent", label: "AI Agent", icon: BrainCircuit, scopes: ["ai:classify", "tickets:create", "events:read"] }
];

const roles = ["viewer", "editor", "admin"];
const environments = ["local", "staging", "production"];
const statuses = ["all", "OPEN", "NEW", "ASSIGNED", "IN_PROGRESS", "PENDING", "RESOLVED", "CLOSED"];
const fieldClass = "h-11 w-full rounded-[8px] border border-white/10 bg-[#070d19] px-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/60";

const emptyDashboard = {
  summary: {},
  projects: [],
  api_keys: [],
  complaints: [],
  complaint_events: [],
  erp: { summary: {}, customers: [], inventory: [], sync_logs: [] },
  webhooks: { events: [], local_events: [], production_events: [], event_types: [] },
  traffic: [],
  security: { top_ips: [], recent_failures: [] },
  anomalies: []
};

function dateTime(value) {
  if (!value) return "Never";
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function numberCompact(value) {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(Number(value || 0));
}

function money(value) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Number(value || 0));
}

function normalize(value) {
  return String(value || "").toLowerCase();
}

function statusTone(value) {
  const v = normalize(value);
  if (["healthy", "active", "resolved", "closed", "success", "production"].some((item) => v.includes(item))) {
    return "border-emerald-300/30 bg-emerald-300/10 text-emerald-200";
  }
  if (["warning", "pending", "progress", "staging", "triaged"].some((item) => v.includes(item))) {
    return "border-amber-300/30 bg-amber-300/10 text-amber-100";
  }
  if (["degraded", "down", "critical", "disabled", "failed", "expired"].some((item) => v.includes(item))) {
    return "border-rose-300/30 bg-rose-300/10 text-rose-200";
  }
  return "border-cyan-300/30 bg-cyan-300/10 text-cyan-200";
}

function downloadCsv(filename, rows) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const escape = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;
  const csv = [headers.join(","), ...rows.map((row) => headers.map((header) => escape(row[header])).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function useLiveApiMonitor() {
  const [live, setLive] = useState({ connected: false, points: [], stats: null });

  useEffect(() => {
    const token = localStorage.getItem("accessToken") || "";
    let socket;
    try {
      socket = new WebSocket(`${WS_BASE}/api-monitor/?token=${encodeURIComponent(token)}`);
    } catch {
      return undefined;
    }

    socket.onopen = () => setLive((state) => ({ ...state, connected: true }));
    socket.onclose = () => setLive((state) => ({ ...state, connected: false }));
    socket.onerror = () => setLive((state) => ({ ...state, connected: false }));
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLive((state) => ({
        connected: true,
        stats: data,
        points: [...state.points.slice(-59), { label: new Date().toLocaleTimeString(), rps: data.requests_per_sec || 0 }]
      }));
    };
    return () => socket?.close();
  }, []);

  return live;
}

export default function ApiKeyManager() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { center } = useParams();
  const { user } = useAuth();
  const live = useLiveApiMonitor();
  const activeCenter = centers.some((item) => item.id === center) ? center : "overview";
  const canManage = String(user?.role || user?.user_type || "super_admin").toLowerCase().includes("admin")
    || String(user?.role || "").toLowerCase().includes("super");

  const [filters, setFilters] = useState({ project: "all", source: "all", status: "all", window_hours: 24 });
  const [search, setSearch] = useState("");
  const [selectedKey, setSelectedKey] = useState(null);
  const [selectedComplaint, setSelectedComplaint] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [newKey, setNewKey] = useState(null);
  const [ipList, setIpList] = useState("");
  const [debugResult, setDebugResult] = useState(null);
  const [debugForm, setDebugForm] = useState({
    method: "POST",
    endpoint: "/api/external/issues/",
    response_code: 200,
    payload: "{\n  \"type\": \"complaint\",\n  \"customer_name\": \"\",\n  \"message\": \"\",\n  \"priority\": \"HIGH\"\n}"
  });
  const [form, setForm] = useState({
    project: "",
    name: "",
    key_type: "chatbot",
    environment: "production",
    role: "viewer",
    rate_limit_per_minute: 1000,
    expires_at: "",
    allowed_scopes: keyTypes[0].scopes
  });

  const dashboardQuery = useQuery({
    queryKey: ["api-intelligence-dashboard", filters],
    queryFn: () => api.get("/api-intelligence/dashboard/", { params: filters }).then((response) => response.data),
    refetchInterval: 5000
  });

  const keyDetails = useQuery({
    queryKey: ["api-intelligence-key-details", selectedKey?.id],
    queryFn: () => api.get(`/uce-api-keys/${selectedKey.id}/details/`).then((response) => response.data),
    enabled: Boolean(selectedKey?.id),
    refetchInterval: selectedKey ? 5000 : false
  });

  const create = useMutation({
    mutationFn: (payload) => api.post("/uce-api-keys/", payload).then((response) => response.data),
    onSuccess: (data) => {
      setNewKey(data.plaintext_key);
      setForm((current) => ({ ...current, name: "", expires_at: "" }));
      setIpList("");
      qc.invalidateQueries({ queryKey: ["api-intelligence-dashboard"] });
    }
  });

  const toggle = useMutation({
    mutationFn: (key) => api.post(`/uce-api-keys/${key.id}/toggle/`).then((response) => response.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-intelligence-dashboard"] })
  });

  const regenerate = useMutation({
    mutationFn: (key) => api.post(`/uce-api-keys/${key.id}/regenerate/`).then((response) => response.data),
    onSuccess: (data) => {
      setNewKey(data.plaintext_key);
      qc.invalidateQueries({ queryKey: ["api-intelligence-dashboard"] });
    }
  });

  const debug = useMutation({
    mutationFn: (payload) => api.post(`/uce-api-keys/${payload.keyId}/test/`, payload.body).then((response) => response.data),
    onSuccess: (data) => {
      setDebugResult(data);
      qc.invalidateQueries({ queryKey: ["api-intelligence-dashboard"] });
      qc.invalidateQueries({ queryKey: ["api-intelligence-key-details", selectedKey?.id] });
    }
  });

  const dashboard = dashboardQuery.data || emptyDashboard;
  const summary = dashboard.summary || {};
  const projects = dashboard.projects || [];
  const keys = dashboard.api_keys || [];
  const complaints = dashboard.complaints || [];
  const erp = dashboard.erp || emptyDashboard.erp;
  const webhooks = dashboard.webhooks || emptyDashboard.webhooks;
  const traffic = dashboard.traffic || [];
  const security = dashboard.security || emptyDashboard.security;
  const anomalies = dashboard.anomalies || [];
  const selectedDebugKey = selectedKey || keys.find((key) => key.is_active) || keys[0];

  const sourceOptions = useMemo(() => {
    const values = new Set(["all"]);
    [...(webhooks.events || []), ...(dashboard.complaint_events || [])].forEach((item) => {
      if (item.source_module) values.add(item.source_module);
      if (item.payload?.source_platform) values.add(item.payload.source_platform);
    });
    return [...values];
  }, [dashboard.complaint_events, webhooks.events]);

  const searchedComplaints = complaints.filter((item) => {
    const text = [item.ticket_id, item.project_name, item.customer_name, item.customer_email, item.category, item.summary, item.description]
      .join(" ")
      .toLowerCase();
    return !search || text.includes(search.toLowerCase());
  });

  const searchedEvents = (webhooks.events || []).filter((item) => {
    const text = [item.event_type, item.source_module, item.project_name, JSON.stringify(item.payload || {})].join(" ").toLowerCase();
    return !search || text.includes(search.toLowerCase());
  });

  function setCenter(id) {
    navigate(id === "overview" ? "/api-keys" : `/api-keys/${id}`);
  }

  async function copy(text) {
    if (text) await navigator.clipboard?.writeText(text);
  }

  function updateKeyType(value) {
    const type = keyTypes.find((item) => item.value === value);
    setForm((current) => ({ ...current, key_type: value, allowed_scopes: type?.scopes || [] }));
  }

  function submitKey(event) {
    event.preventDefault();
    const payload = {
      ...form,
      ip_whitelist: ipList.split(",").map((item) => item.trim()).filter(Boolean),
      metadata: { created_from: "api_intelligence_platform" }
    };
    if (!payload.expires_at) delete payload.expires_at;
    create.mutate(payload);
  }

  function runDebug() {
    if (!selectedDebugKey?.id) return;
    let payload = {};
    try {
      payload = JSON.parse(debugForm.payload || "{}");
    } catch {
      setDebugResult({ success: false, message: "Payload JSON is invalid." });
      return;
    }
    debug.mutate({
      keyId: selectedDebugKey.id,
      body: {
        method: debugForm.method,
        endpoint: debugForm.endpoint,
        response_code: Number(debugForm.response_code),
        payload
      }
    });
  }

  const pageError = dashboardQuery.isError ? apiErrorMessage(dashboardQuery.error, "API intelligence data could not be loaded.") : "";

  return (
    <div className="min-h-screen space-y-5 text-slate-200">
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-[8px] border border-white/10 bg-[#08101d] p-5 shadow-[0_24px_90px_rgba(0,0,0,0.34)]"
      >
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_12%_10%,rgba(34,211,238,0.16),transparent_28%),radial-gradient(circle_at_86%_16%,rgba(139,92,246,0.16),transparent_30%)]" />
        <div className="relative grid gap-5 xl:grid-cols-[1fr_520px] xl:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1 text-xs font-black uppercase tracking-[0.18em] text-cyan-200">
                <Sparkles size={14} />
                Enterprise API Intelligence
              </span>
              <StatusPill value={live.connected ? "live websocket" : "polling"} />
              <StatusPill value={`${dashboard.window_hours || filters.window_hours}h window`} />
            </div>
            <h1 className="mt-4 max-w-5xl text-3xl font-black tracking-tight text-white md:text-5xl">
              API Operations, Complaint Automation, ERP Sync, and Webhook Intelligence
            </h1>
            <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-400">
              Centralized command surface for project-scoped credentials, external complaint intake, live usage telemetry, sync health, audit visibility, and response automation.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <MetricCard icon={KeyRound} label="Active keys" value={summary.active_keys} />
            <MetricCard icon={Activity} label="Requests" value={numberCompact(summary.requests)} />
            <MetricCard icon={MessageSquareWarning} label="Open complaints" value={summary.open_complaints} tone="amber" />
            <MetricCard icon={ClipboardCheck} label="AI tickets" value={summary.ai_tickets} tone="violet" />
            <MetricCard icon={Webhook} label="Webhook events" value={summary.webhook_events} tone="cyan" />
            <MetricCard icon={Zap} label="Avg latency" value={`${summary.avg_latency_ms || live.stats?.avg_response_time_ms || 0}ms`} tone={summary.failure_rate > 5 ? "rose" : "emerald"} />
          </div>
        </div>
      </motion.section>

      <div className="sticky top-0 z-20 rounded-[8px] border border-white/10 bg-[#080f1d]/95 p-2 backdrop-blur-xl">
        <div className="flex gap-2 overflow-x-auto">
          {centers.map((item) => {
            const Icon = item.icon;
            const active = activeCenter === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setCenter(item.id)}
                className={`inline-flex h-11 shrink-0 items-center gap-2 rounded-[8px] px-3 text-sm font-bold transition ${
                  active ? "bg-cyan-300 text-slate-950" : "border border-white/10 bg-white/[0.035] text-slate-300 hover:border-cyan-300/40 hover:text-white"
                }`}
              >
                <Icon size={16} />
                {item.label}
              </button>
            );
          })}
        </div>
      </div>

      <ControlBar
        filters={filters}
        setFilters={setFilters}
        projects={projects}
        sourceOptions={sourceOptions}
        search={search}
        setSearch={setSearch}
        loading={dashboardQuery.isFetching}
      />

      {pageError && <Notice tone="rose" title="API intelligence unavailable" detail={pageError} />}
      {create.isError && <Notice tone="rose" title="Key generation failed" detail={apiErrorMessage(create.error, "Could not generate API key.")} />}

      <AnimatePresence>
        {newKey && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="rounded-[8px] border border-amber-300/30 bg-amber-300/10 p-4 text-amber-50"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="font-bold">New API key generated. This secret is shown once.</p>
                <code className="mt-2 block break-all rounded-[8px] bg-black/35 px-3 py-2 text-xs text-amber-100">{newKey}</code>
              </div>
              <div className="flex gap-2">
                <button onClick={() => copy(newKey)} className="inline-flex h-10 items-center gap-2 rounded-[8px] border border-amber-200/30 px-3 text-sm font-bold text-amber-100 hover:bg-amber-200/10">
                  <Copy size={15} />
                  Copy
                </button>
                <button onClick={() => setNewKey(null)} className="grid h-10 w-10 place-items-center rounded-[8px] border border-amber-200/30 text-amber-100 hover:bg-amber-200/10" aria-label="Dismiss API key">
                  <X size={16} />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {activeCenter === "overview" && (
        <OverviewCenter
          traffic={traffic}
          live={live}
          projects={projects}
          anomalies={anomalies}
          onSelectProject={(project) => setFilters((current) => ({ ...current, project: String(project.id) }))}
          form={form}
          setForm={setForm}
          ipList={ipList}
          setIpList={setIpList}
          create={create}
          submitKey={submitKey}
          updateKeyType={updateKeyType}
        />
      )}

      {activeCenter === "chatbot" && (
        <ChatbotCenter
          complaints={searchedComplaints}
          events={dashboard.complaint_events || []}
          onOpen={setSelectedComplaint}
          onExport={() => downloadCsv("chatbot-complaints.csv", searchedComplaints.map(flattenComplaint))}
        />
      )}

      {activeCenter === "erp" && (
        <ErpCenter
          erp={erp}
          onExportCustomers={() => downloadCsv("erp-customers.csv", erp.customers || [])}
          onExportInventory={() => downloadCsv("erp-inventory.csv", erp.inventory || [])}
        />
      )}

      {activeCenter === "webhooks" && (
        <WebhookCenter
          webhooks={webhooks}
          projects={projects}
          events={searchedEvents}
          onOpen={setSelectedEvent}
          onExport={() => downloadCsv("webhook-events.csv", searchedEvents.map(flattenEvent))}
        />
      )}

      {activeCenter === "security" && (
        <SecurityCenter
          keys={keys}
          security={security}
          canManage={canManage}
          onView={setSelectedKey}
          onToggle={(key) => toggle.mutate(key)}
          onRegenerate={(key) => regenerate.mutate(key)}
        />
      )}

      {activeCenter === "playground" && (
        <PlaygroundCenter
          selectedKey={selectedDebugKey}
          keys={keys}
          setSelectedKey={setSelectedKey}
          debugForm={debugForm}
          setDebugForm={setDebugForm}
          runDebug={runDebug}
          debug={debug}
          debugResult={debugResult}
        />
      )}

      <AnimatePresence>
        {selectedKey && (
          <KeyModal
            selectedKey={selectedKey}
            keyDetails={keyDetails}
            canManage={canManage}
            onClose={() => setSelectedKey(null)}
            onCopy={copy}
          />
        )}
        {selectedComplaint && (
          <ComplaintModal complaint={selectedComplaint} onClose={() => setSelectedComplaint(null)} />
        )}
        {selectedEvent && (
          <EventModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}

function ControlBar({ filters, setFilters, projects, sourceOptions, search, setSearch, loading }) {
  return (
    <section className="grid gap-3 rounded-[8px] border border-white/10 bg-white/[0.04] p-3 lg:grid-cols-[1fr_auto]">
      <div className="grid gap-3 md:grid-cols-4">
        <select value={filters.project} onChange={(event) => setFilters({ ...filters, project: event.target.value })} className="h-11 rounded-[8px] border border-white/10 bg-[#070d19] px-3 text-sm text-white outline-none focus:border-cyan-300/60">
          <option value="all">All projects</option>
          {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>
        <select value={filters.source} onChange={(event) => setFilters({ ...filters, source: event.target.value })} className="h-11 rounded-[8px] border border-white/10 bg-[#070d19] px-3 text-sm text-white outline-none focus:border-cyan-300/60">
          {sourceOptions.map((source) => <option key={source} value={source}>{source}</option>)}
        </select>
        <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })} className="h-11 rounded-[8px] border border-white/10 bg-[#070d19] px-3 text-sm text-white outline-none focus:border-cyan-300/60">
          {statuses.map((status) => <option key={status} value={status}>{status}</option>)}
        </select>
        <select value={filters.window_hours} onChange={(event) => setFilters({ ...filters, window_hours: Number(event.target.value) })} className="h-11 rounded-[8px] border border-white/10 bg-[#070d19] px-3 text-sm text-white outline-none focus:border-cyan-300/60">
          <option value={1}>1 hour</option>
          <option value={24}>24 hours</option>
          <option value={168}>7 days</option>
          <option value={720}>30 days</option>
        </select>
      </div>
      <div className="flex min-w-0 items-center gap-2">
        <div className="relative min-w-0 flex-1 lg:w-80">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search tickets, events, customers" className="h-11 w-full rounded-[8px] border border-white/10 bg-[#070d19] pl-9 pr-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/60" />
        </div>
        <button type="button" className="grid h-11 w-11 place-items-center rounded-[8px] border border-white/10 bg-white/[0.04] text-slate-300" aria-label="Refresh status">
          <RefreshCw size={16} className={loading ? "animate-spin text-cyan-300" : ""} />
        </button>
      </div>
    </section>
  );
}

function OverviewCenter({ traffic, live, projects, anomalies, onSelectProject, form, setForm, ipList, setIpList, create, submitKey, updateKeyType }) {
  return (
    <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_480px]">
      <div className="space-y-5">
        <Panel>
          <PanelHeader icon={Activity} title="Realtime API Traffic" action={<StatusPill value={live.connected ? "websocket connected" : "polling active"} />} />
          <div className="mt-4 h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={traffic}>
                <defs>
                  <linearGradient id="trafficRequests" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.36} />
                    <stop offset="95%" stopColor="#22d3ee" stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="trafficTickets" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#a78bfa" stopOpacity={0.32} />
                    <stop offset="95%" stopColor="#a78bfa" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
                <XAxis dataKey="label" stroke="#64748b" fontSize={12} />
                <YAxis stroke="#64748b" fontSize={12} />
                <Tooltip contentStyle={{ background: "#07101d", border: "1px solid rgba(148,163,184,0.22)", borderRadius: 8 }} />
                <Area type="monotone" dataKey="requests" stroke="#22d3ee" fill="url(#trafficRequests)" strokeWidth={2} />
                <Area type="monotone" dataKey="tickets" stroke="#a78bfa" fill="url(#trafficTickets)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel>
          <PanelHeader icon={Globe2} title="Multi-Project API Health" />
          <div className="mt-4 grid gap-3 xl:grid-cols-2">
            {projects.map((project) => (
              <button key={project.id} type="button" onClick={() => onSelectProject(project)} className="rounded-[8px] border border-white/10 bg-[#07101d] p-4 text-left transition hover:border-cyan-300/40">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-black text-white">{project.name}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">{project.environment} - {project.connection_status}</p>
                  </div>
                  <StatusPill value={project.api_status} />
                </div>
                <div className="mt-4 grid grid-cols-4 gap-2 text-center">
                  <MiniStat label="Keys" value={project.key_count} />
                  <MiniStat label="Events" value={project.event_count} />
                  <MiniStat label="24h req" value={project.request_count_24h} />
                  <MiniStat label="Health" value={`${project.health_score || 0}%`} />
                </div>
              </button>
            ))}
            {!projects.length && <EmptyState icon={Globe2} title="No visible projects" text="Create or assign a project before issuing integration credentials." />}
          </div>
        </Panel>
      </div>

      <div className="space-y-5">
        <KeyFactory form={form} setForm={setForm} ipList={ipList} setIpList={setIpList} submitKey={submitKey} create={create} updateKeyType={updateKeyType} projects={projects} />
        <Panel>
          <PanelHeader icon={BrainCircuit} title="AI Risk & Automation Signals" />
          <div className="mt-4 space-y-3">
            {anomalies.map((item) => <SignalCard key={`${item.title}-${item.severity}`} item={item} />)}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function KeyFactory({ form, setForm, ipList, setIpList, submitKey, create, updateKeyType, projects }) {
  return (
    <Panel>
      <PanelHeader icon={KeyRound} title="Generate Integration Key" action={<StatusPill value="scoped credential" />} />
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {keyTypes.map((type) => {
          const Icon = type.icon;
          const active = form.key_type === type.value;
          return (
            <button
              key={type.value}
              type="button"
              onClick={() => updateKeyType(type.value)}
              className={`rounded-[8px] border p-3 text-left transition ${active ? "border-cyan-300/50 bg-cyan-300/12" : "border-white/10 bg-[#07101d] hover:border-cyan-300/30"}`}
            >
              <Icon className={active ? "text-cyan-200" : "text-slate-400"} size={18} />
              <p className="mt-2 text-sm font-black text-white">{type.label}</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">{type.scopes.join(", ")}</p>
            </button>
          );
        })}
      </div>
      <form onSubmit={submitKey} className="mt-4 space-y-3">
        <select required value={form.project} onChange={(event) => setForm({ ...form, project: event.target.value })} className={fieldClass}>
          <option value="">Select project</option>
          {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>
        <input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder={`${keyTypes.find((item) => item.value === form.key_type)?.label} integration name`} className={fieldClass} />
        <div className="grid gap-3 sm:grid-cols-2">
          <select value={form.environment} onChange={(event) => setForm({ ...form, environment: event.target.value })} className={fieldClass}>
            {environments.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })} className={fieldClass}>
            {roles.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <input type="number" min="10" max="100000" value={form.rate_limit_per_minute} onChange={(event) => setForm({ ...form, rate_limit_per_minute: Number(event.target.value) })} className={fieldClass} />
          <input type="datetime-local" value={form.expires_at} onChange={(event) => setForm({ ...form, expires_at: event.target.value })} className={fieldClass} />
        </div>
        <input value={ipList} onChange={(event) => setIpList(event.target.value)} placeholder="IP allowlist, comma separated" className={fieldClass} />
        <button disabled={create.isPending} className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-[8px] bg-cyan-300 px-4 text-sm font-black text-slate-950 transition hover:bg-cyan-200 disabled:cursor-wait disabled:opacity-60">
          {create.isPending ? <RefreshCw className="animate-spin" size={16} /> : <KeyRound size={16} />}
          Generate Secure Key
        </button>
      </form>
    </Panel>
  );
}

function ChatbotCenter({ complaints, events, onOpen, onExport }) {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      <Panel>
        <PanelHeader icon={MessageSquareWarning} title="Chatbot Complaint Center" action={<ExportButton onClick={onExport} />} />
        <div className="mt-4 overflow-hidden rounded-[8px] border border-white/10">
          <div className="grid grid-cols-[1fr_170px_130px_130px] bg-white/[0.04] px-4 py-3 text-xs font-black uppercase tracking-[0.14em] text-slate-500 max-lg:hidden">
            <span>Customer and ticket</span>
            <span>Project</span>
            <span>Priority</span>
            <span>Status</span>
          </div>
          <div className="divide-y divide-white/10">
            {complaints.map((item) => (
              <button key={item.id} onClick={() => onOpen(item)} className="grid w-full gap-3 px-4 py-4 text-left transition hover:bg-white/[0.035] lg:grid-cols-[1fr_170px_130px_130px]">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-black text-white">{item.ticket_id}</p>
                    <StatusPill value={item.category} />
                    <StatusPill value={item.sentiment} />
                  </div>
                  <p className="mt-1 truncate text-sm text-slate-300">{item.customer_name} {item.customer_email ? `- ${item.customer_email}` : ""}</p>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{item.summary || item.description}</p>
                </div>
                <span className="text-sm text-slate-300">{item.project_name}</span>
                <span><StatusPill value={item.priority} /></span>
                <span><StatusPill value={item.status} /></span>
              </button>
            ))}
            {!complaints.length && <EmptyState icon={Filter} title="No matching complaints" text="Complaint intake records will appear after authenticated external issue ingestion." />}
          </div>
        </div>
      </Panel>

      <Panel>
        <PanelHeader icon={BrainCircuit} title="AI Complaint Intake" />
        <div className="mt-4 space-y-3">
          {events.slice(0, 12).map((event) => (
            <div key={event.id} className="rounded-[8px] border border-white/10 bg-[#07101d] p-3">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-bold text-white">{event.payload?.title || event.event_type}</p>
                <StatusPill value={event.payload?.status || "open"} />
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-500">{event.payload?.ai?.summary || event.payload?.description || "Event received"}</p>
              <p className="mt-2 text-xs text-slate-600">{dateTime(event.created_at)}</p>
            </div>
          ))}
          {!events.length && <EmptyState icon={BrainCircuit} title="No intake events" text="External chatbot and AI-agent payloads will be indexed here." />}
        </div>
      </Panel>
    </div>
  );
}

function ErpCenter({ erp, onExportCustomers, onExportInventory }) {
  const summary = erp.summary || {};
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard icon={Users} label="Customers" value={summary.customers} />
        <MetricCard icon={BarChart3} label="Revenue" value={money(summary.revenue)} tone="emerald" />
        <MetricCard icon={ClipboardCheck} label="Pending orders" value={summary.pending_orders} tone="amber" />
        <MetricCard icon={DatabaseZap} label="Available stock" value={numberCompact(summary.available_stock)} tone="cyan" />
        <MetricCard icon={AlertTriangle} label="Low stock" value={summary.low_stock_products} tone={summary.low_stock_products ? "rose" : "emerald"} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[1fr_1fr]">
        <Panel>
          <PanelHeader icon={Users} title="Customer Data Explorer" action={<ExportButton onClick={onExportCustomers} />} />
          <DataRows rows={(erp.customers || []).slice(0, 12)} emptyIcon={Users} render={(item) => (
            <div className="grid gap-2 rounded-[8px] border border-white/10 bg-[#07101d] p-3 md:grid-cols-[1fr_auto]">
              <div>
                <p className="font-bold text-white">{item.name}</p>
                <p className="mt-1 text-xs text-slate-500">{item.company || "No company"} - {item.email}</p>
              </div>
              <div className="text-right text-sm text-slate-300">
                <p>{money(item.total_spend)}</p>
                <StatusPill value={item.lifecycle_stage} />
              </div>
            </div>
          )} />
        </Panel>
        <Panel>
          <PanelHeader icon={DatabaseZap} title="Inventory Data Explorer" action={<ExportButton onClick={onExportInventory} />} />
          <DataRows rows={(erp.inventory || []).slice(0, 12)} emptyIcon={DatabaseZap} render={(item) => (
            <div className="grid gap-2 rounded-[8px] border border-white/10 bg-[#07101d] p-3 md:grid-cols-[1fr_auto]">
              <div>
                <p className="font-bold text-white">{item.product}</p>
                <p className="mt-1 text-xs text-slate-500">{item.sku} - {item.warehouse}</p>
              </div>
              <div className="text-right text-sm text-slate-300">
                <p>{item.available_qty} available</p>
                <StatusPill value={item.status} />
              </div>
            </div>
          )} />
        </Panel>
      </div>
      <Panel>
        <PanelHeader icon={RefreshCw} title="Real-Time Synchronization Logs" />
        <DataRows rows={(erp.sync_logs || []).slice(0, 16)} emptyIcon={RefreshCw} render={(item) => (
          <div className="grid gap-2 rounded-[8px] border border-white/10 bg-[#07101d] px-3 py-3 text-sm md:grid-cols-[1fr_auto_auto]">
              <span className="text-white">{item.source_module} {"->"} {item.target_module}</span>
            <StatusPill value={item.conflict_detected ? "conflict" : "synced"} />
            <span className="text-slate-500">{dateTime(item.created_at)}</span>
          </div>
        )} />
      </Panel>
    </div>
  );
}

function WebhookCenter({ webhooks, projects, events, onOpen, onExport }) {
  const eventTypes = webhooks.event_types || [];
  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[1fr_420px]">
        <Panel>
          <PanelHeader icon={Globe2} title="Connected Project Monitor" />
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {projects.map((project) => (
              <div key={project.id} className="rounded-[8px] border border-white/10 bg-[#07101d] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-black text-white">{project.name}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.14em] text-slate-500">{project.environment}</p>
                  </div>
                  <StatusPill value={project.api_status} />
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2">
                  <MiniStat label="Events" value={project.event_count} />
                  <MiniStat label="Requests" value={project.request_count_24h} />
                  <MiniStat label="Failures" value={project.failure_count_24h} />
                </div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel>
          <PanelHeader icon={BarChart3} title="Event Type Distribution" />
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={eventTypes}>
                <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
                <XAxis dataKey="event_type" stroke="#64748b" fontSize={11} tick={{ width: 90 }} />
                <YAxis stroke="#64748b" fontSize={12} />
                <Tooltip contentStyle={{ background: "#07101d", border: "1px solid rgba(148,163,184,0.22)", borderRadius: 8 }} />
                <Bar dataKey="count" fill="#22d3ee" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>
      <Panel>
        <PanelHeader icon={Webhook} title="Real-Time Webhook Event Stream" action={<ExportButton onClick={onExport} />} />
        <div className="mt-4 space-y-2">
          {events.slice(0, 80).map((event) => (
            <button key={event.id} type="button" onClick={() => onOpen(event)} className="grid w-full gap-3 rounded-[8px] border border-white/10 bg-[#07101d] px-4 py-3 text-left transition hover:border-cyan-300/40 md:grid-cols-[1fr_150px_140px_120px]">
              <span className="truncate font-bold text-white">{event.event_type}</span>
              <span className="text-sm text-slate-400">{event.source_module}</span>
              <StatusPill value={event.payload?.environment || "workspace"} />
              <span className="text-sm text-slate-500">{dateTime(event.created_at)}</span>
            </button>
          ))}
          {!events.length && <EmptyState icon={Webhook} title="No webhook events" text="Authenticated webhook and module events will stream here." />}
        </div>
      </Panel>
    </div>
  );
}

function SecurityCenter({ keys, security, canManage, onView, onToggle, onRegenerate }) {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      <Panel>
        <PanelHeader icon={Lock} title="API Key Vault & Access Governance" />
        <div className="mt-4 space-y-3">
          {keys.map((key) => (
            <div key={key.id} className="grid gap-3 rounded-[8px] border border-white/10 bg-[#07101d] p-4 lg:grid-cols-[1fr_auto]">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-black text-white">{key.name}</p>
                  <StatusPill value={key.key_type} />
                  <StatusPill value={key.environment} />
                  <StatusPill value={key.is_active ? key.role : "disabled"} />
                </div>
                <p className="mt-2 text-sm text-slate-400">{key.project_name} - prefix <span className="font-mono text-cyan-200">{key.key_prefix}****</span></p>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
                  <span>Rate {key.rate_limit_per_minute}/min</span>
                  <span>Last used {dateTime(key.last_used_at)}</span>
                  <span>Expires {dateTime(key.expires_at)}</span>
                  <span>{key.ip_whitelist?.length ? `${key.ip_whitelist.length} allowed IPs` : "No IP allowlist"}</span>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <IconButton label="View key details" icon={Eye} onClick={() => onView(key)} />
                <IconButton label="Regenerate key" icon={RefreshCw} disabled={!canManage} onClick={() => onRegenerate(key)} />
                <button disabled={!canManage} onClick={() => onToggle(key)} className="h-10 rounded-[8px] border border-white/10 px-3 text-sm font-bold text-slate-300 transition hover:border-rose-300/40 hover:text-rose-200 disabled:cursor-not-allowed disabled:opacity-40">
                  {key.is_active ? "Disable" : "Enable"}
                </button>
              </div>
            </div>
          ))}
          {!keys.length && <EmptyState icon={KeyRound} title="No API keys" text="Generate project-scoped keys from the Overview center." />}
        </div>
      </Panel>
      <div className="space-y-5">
        <Panel>
          <PanelHeader icon={ShieldAlert} title="Security Posture" />
          <div className="mt-4 grid gap-3">
            <MetricLine label="Disabled keys" value={security.disabled_keys} />
            <MetricLine label="Expired keys" value={security.expired_keys} />
            <MetricLine label="Unrestricted keys" value={security.unrestricted_keys} />
          </div>
        </Panel>
        <Panel>
          <PanelHeader icon={Network} title="Top Request Origins" />
          <DataRows rows={security.top_ips || []} emptyIcon={Network} render={(item) => (
            <div className="flex items-center justify-between rounded-[8px] border border-white/10 bg-[#07101d] px-3 py-2 text-sm">
              <span className="text-white">{item.ip_address}</span>
              <span className="text-cyan-200">{item.count}</span>
            </div>
          )} />
        </Panel>
        <Panel>
          <PanelHeader icon={AlertTriangle} title="Recent Failures" />
          <DataRows rows={(security.recent_failures || []).slice(0, 12)} emptyIcon={AlertTriangle} render={(item) => (
            <div className="rounded-[8px] border border-white/10 bg-[#07101d] px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="truncate text-white">{item.http_method} {item.endpoint}</span>
                <StatusPill value={item.response_code} />
              </div>
              <p className="mt-1 text-xs text-slate-500">{item.project_name} - {dateTime(item.timestamp)}</p>
            </div>
          )} />
        </Panel>
      </div>
    </div>
  );
}

function PlaygroundCenter({ selectedKey, keys, setSelectedKey, debugForm, setDebugForm, runDebug, debug, debugResult }) {
  const sdk = useMemo(() => buildSdkSnippets(selectedKey, debugForm.endpoint), [selectedKey, debugForm.endpoint]);
  const [sdkTab, setSdkTab] = useState("javascript");
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_460px]">
      <Panel>
        <PanelHeader icon={TerminalSquare} title="API Playground" action={<StatusPill value={selectedKey?.key_type || "select key"} />} />
        <div className="mt-4 grid gap-3 md:grid-cols-[1fr_150px_150px]">
          <select value={selectedKey?.id || ""} onChange={(event) => setSelectedKey(keys.find((key) => String(key.id) === event.target.value) || null)} className={fieldClass}>
            <option value="">Select active key</option>
            {keys.map((key) => <option key={key.id} value={key.id}>{key.project_name} - {key.name}</option>)}
          </select>
          <select value={debugForm.method} onChange={(event) => setDebugForm({ ...debugForm, method: event.target.value })} className={fieldClass}>
            {["POST", "GET", "PATCH", "DELETE"].map((method) => <option key={method}>{method}</option>)}
          </select>
          <input type="number" min="100" max="599" value={debugForm.response_code} onChange={(event) => setDebugForm({ ...debugForm, response_code: Number(event.target.value) })} className={fieldClass} />
        </div>
        <input value={debugForm.endpoint} onChange={(event) => setDebugForm({ ...debugForm, endpoint: event.target.value })} className={`${fieldClass} mt-3`} />
        <textarea value={debugForm.payload} onChange={(event) => setDebugForm({ ...debugForm, payload: event.target.value })} rows={14} className="mt-3 w-full resize-y rounded-[8px] border border-white/10 bg-[#070d19] p-4 font-mono text-xs leading-6 text-cyan-100 outline-none focus:border-cyan-300/60" />
        <button disabled={!selectedKey?.id || debug.isPending} onClick={runDebug} className="mt-3 inline-flex h-11 items-center gap-2 rounded-[8px] bg-cyan-300 px-4 text-sm font-black text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50">
          {debug.isPending ? <RefreshCw className="animate-spin" size={16} /> : <Play size={16} />}
          Run Request
        </button>
        {debugResult && (
          <div className={`mt-4 rounded-[8px] border p-3 text-sm ${debugResult.success === false ? "border-rose-300/25 bg-rose-300/10 text-rose-100" : "border-emerald-300/25 bg-emerald-300/10 text-emerald-100"}`}>
            {debugResult.message}
          </div>
        )}
      </Panel>
      <Panel>
        <PanelHeader icon={FileJson} title="SDK Generator" />
        <div className="mt-4 grid grid-cols-3 gap-2">
          {Object.keys(sdk).map((tab) => (
            <button key={tab} onClick={() => setSdkTab(tab)} className={`h-10 rounded-[8px] border text-xs font-bold capitalize transition ${sdkTab === tab ? "border-cyan-300 bg-cyan-300 text-slate-950" : "border-white/10 text-slate-300 hover:border-cyan-300/40"}`}>
              {tab}
            </button>
          ))}
        </div>
        <pre className="mt-3 max-h-[520px] overflow-auto rounded-[8px] border border-white/10 bg-black/35 p-4 text-xs leading-6 text-cyan-100">{sdk[sdkTab]}</pre>
      </Panel>
    </div>
  );
}

function KeyModal({ selectedKey, keyDetails, canManage, onClose, onCopy }) {
  const details = keyDetails.data || {};
  const visibleKey = details.plaintext_key || details.api_key || `${selectedKey.key_prefix || "sk"}************************`;
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[9999] grid place-items-center overflow-y-auto bg-black/75 p-4 backdrop-blur-[8px]">
      <motion.div initial={{ scale: 0.96 }} animate={{ scale: 1 }} exit={{ scale: 0.96 }} className="w-full max-w-6xl rounded-[8px] border border-white/10 bg-[#08101d] p-5 shadow-2xl">
        <ModalHeader title={selectedKey.name} subtitle={`${selectedKey.project_name} - ${selectedKey.key_type} - ${selectedKey.environment}`} onClose={onClose} />
        <div className="mt-5 rounded-[8px] border border-cyan-300/20 bg-cyan-300/10 p-4">
          <p className="text-xs font-black uppercase tracking-[0.16em] text-cyan-200">Protected key</p>
          <code className={`mt-2 block break-all rounded-[8px] bg-black/35 px-3 py-2 text-xs ${canManage ? "text-cyan-100" : "text-slate-500 blur-sm"}`}>{visibleKey}</code>
          <button disabled={!canManage} onClick={() => onCopy(visibleKey)} className="mt-3 inline-flex h-10 items-center gap-2 rounded-[8px] border border-cyan-200/30 px-3 text-sm font-bold text-cyan-100 disabled:cursor-not-allowed disabled:opacity-40">
            <Copy size={15} />
            Copy
          </button>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-4">
          <MetricCard icon={Activity} label="24h requests" value={details.usage?.summary?.requests_24h || 0} />
          <MetricCard icon={ShieldAlert} label="Error rate" value={`${details.usage?.summary?.error_rate_percent || 0}%`} tone="rose" />
          <MetricCard icon={Zap} label="Avg latency" value={`${details.usage?.summary?.avg_response_time_ms || 0}ms`} tone="cyan" />
          <MetricCard icon={Network} label="Systems" value={details.connected_systems?.length || 0} tone="violet" />
        </div>
        <div className="mt-5 grid gap-4 xl:grid-cols-3">
          <DetailList title="Request Logs" rows={details.request_logs || []} />
          <DetailList title="Error Logs" rows={details.error_logs || []} />
          <TicketList rows={details.tickets || []} />
        </div>
      </motion.div>
    </motion.div>
  );
}

function ComplaintModal({ complaint, onClose }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[9999] grid place-items-center overflow-y-auto bg-black/75 p-4 backdrop-blur-[8px]">
      <motion.div initial={{ scale: 0.96 }} animate={{ scale: 1 }} exit={{ scale: 0.96 }} className="w-full max-w-5xl rounded-[8px] border border-white/10 bg-[#08101d] p-5 shadow-2xl">
        <ModalHeader title={complaint.ticket_id} subtitle={`${complaint.project_name} - ${complaint.category} - ${complaint.status}`} onClose={onClose} />
        <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_0.8fr]">
          <Panel tight>
            <PanelHeader icon={Users} title="Customer" />
            <div className="mt-4 grid gap-2 text-sm text-slate-300">
              <Info label="Name" value={complaint.customer_name} />
              <Info label="Email" value={complaint.customer_email || "Not provided"} />
              <Info label="Phone" value={complaint.customer_phone || "Not provided"} />
              <Info label="Customer ID" value={complaint.customer_id || "Not provided"} />
              <Info label="Source" value={complaint.source_platform} />
            </div>
          </Panel>
          <Panel tight>
            <PanelHeader icon={BrainCircuit} title="AI Summary" />
            <p className="mt-4 text-sm leading-6 text-slate-300">{complaint.summary || complaint.description}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <StatusPill value={complaint.sentiment} />
              <StatusPill value={complaint.priority} />
              {complaint.confidence && <StatusPill value={`AI ${complaint.confidence}%`} />}
            </div>
          </Panel>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <JsonBlock title="Conversation History" value={complaint.conversation} />
          <JsonBlock title="Order, Product, and Attachments" value={{ order: complaint.order, product: complaint.product, attachments: complaint.attachments }} />
        </div>
      </motion.div>
    </motion.div>
  );
}

function EventModal({ event, onClose }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[9999] grid place-items-center overflow-y-auto bg-black/75 p-4 backdrop-blur-[8px]">
      <motion.div initial={{ scale: 0.96 }} animate={{ scale: 1 }} exit={{ scale: 0.96 }} className="w-full max-w-5xl rounded-[8px] border border-white/10 bg-[#08101d] p-5 shadow-2xl">
        <ModalHeader title={event.event_type} subtitle={`${event.source_module} - ${dateTime(event.created_at)}`} onClose={onClose} />
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <JsonBlock title="Request Payload" value={event.payload} />
          <JsonBlock title="Event Metadata" value={{ id: event.id, entity_type: event.entity_type, entity_id: event.entity_id, processed_at: event.processed_at }} />
        </div>
      </motion.div>
    </motion.div>
  );
}

function buildSdkSnippets(key, endpoint) {
  const url = endpoint || "/api/external/issues/";
  const auth = "process.env.MANAGEAI_API_KEY";
  return {
    javascript: `const response = await fetch("${url}", {
  method: "POST",
  headers: {
    "Authorization": \`API_KEY \${${auth}}\`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    type: "complaint",
    customer_name: "Customer Name",
    message: "Customer issue details",
    priority: "HIGH"
  })
});

const result = await response.json();`,
    python: `import os
import requests

response = requests.post(
    "${url}",
    headers={"Authorization": f"API_KEY {os.environ['MANAGEAI_API_KEY']}"},
    json={
        "type": "complaint",
        "customer_name": "Customer Name",
        "message": "Customer issue details",
        "priority": "HIGH",
    },
    timeout=20,
)
response.raise_for_status()
print(response.json())`,
    curl: `curl -X POST "${url}" \\
  -H "Authorization: API_KEY $MANAGEAI_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"type":"complaint","customer_name":"Customer Name","message":"Customer issue details","priority":"HIGH"}'`
  };
}

function flattenComplaint(item) {
  return {
    ticket_id: item.ticket_id,
    project_name: item.project_name,
    customer_name: item.customer_name,
    customer_email: item.customer_email,
    customer_phone: item.customer_phone,
    customer_id: item.customer_id,
    category: item.category,
    priority: item.priority,
    status: item.status,
    sentiment: item.sentiment,
    created_at: item.created_at,
    updated_at: item.updated_at
  };
}

function flattenEvent(item) {
  return {
    id: item.id,
    event_type: item.event_type,
    source_module: item.source_module,
    project_name: item.project_name || item.payload?.project_name,
    environment: item.payload?.environment,
    created_at: item.created_at
  };
}

function Panel({ children, tight = false }) {
  return <section className={`rounded-[8px] border border-white/10 bg-white/[0.045] shadow-[0_18px_70px_rgba(0,0,0,0.24)] ${tight ? "p-4" : "p-5"}`}>{children}</section>;
}

function PanelHeader({ icon: Icon, title, action }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2">
        <Icon className="shrink-0 text-cyan-200" size={19} />
        <h2 className="truncate text-lg font-black text-white">{title}</h2>
      </div>
      {action}
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, tone = "cyan" }) {
  const tones = {
    cyan: "text-cyan-200 bg-cyan-300/10 border-cyan-300/20",
    violet: "text-violet-200 bg-violet-300/10 border-violet-300/20",
    amber: "text-amber-100 bg-amber-300/10 border-amber-300/20",
    emerald: "text-emerald-200 bg-emerald-300/10 border-emerald-300/20",
    rose: "text-rose-200 bg-rose-300/10 border-rose-300/20"
  };
  return (
    <div className="rounded-[8px] border border-white/10 bg-white/[0.045] p-4">
      <div className={`grid h-10 w-10 place-items-center rounded-[8px] border ${tones[tone] || tones.cyan}`}>
        <Icon size={18} />
      </div>
      <p className="mt-3 text-2xl font-black text-white">{value ?? 0}</p>
      <p className="mt-1 text-xs uppercase tracking-[0.14em] text-slate-500">{label}</p>
    </div>
  );
}

function StatusPill({ value }) {
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold ${statusTone(value)}`}>{String(value || "unknown")}</span>;
}

function MiniStat({ label, value }) {
  return (
    <div className="rounded-[8px] border border-white/10 bg-white/[0.035] px-2 py-2">
      <p className="text-sm font-black text-white">{value ?? 0}</p>
      <p className="mt-1 text-[10px] uppercase tracking-[0.14em] text-slate-500">{label}</p>
    </div>
  );
}

function SignalCard({ item }) {
  return (
    <div className="rounded-[8px] border border-white/10 bg-[#07101d] p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="font-black text-white">{item.title}</p>
        <StatusPill value={item.severity} />
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-400">{item.detail}</p>
      <p className="mt-3 text-xs leading-5 text-cyan-200">{item.recommendation}</p>
    </div>
  );
}

function Notice({ tone = "cyan", title, detail }) {
  const cls = tone === "rose" ? "border-rose-300/25 bg-rose-300/10 text-rose-100" : "border-cyan-300/25 bg-cyan-300/10 text-cyan-100";
  return (
    <div className={`rounded-[8px] border px-4 py-3 ${cls}`}>
      <p className="font-bold">{title}</p>
      {detail && <p className="mt-1 text-sm opacity-80">{detail}</p>}
    </div>
  );
}

function EmptyState({ icon: Icon, title, text }) {
  return (
    <div className="rounded-[8px] border border-dashed border-white/10 bg-[#07101d] p-8 text-center">
      <Icon className="mx-auto text-cyan-300" size={24} />
      <p className="mt-3 font-bold text-white">{title}</p>
      <p className="mt-1 text-sm leading-6 text-slate-500">{text}</p>
    </div>
  );
}

function ExportButton({ onClick }) {
  return (
    <button onClick={onClick} className="inline-flex h-9 items-center gap-2 rounded-[8px] border border-white/10 px-3 text-xs font-bold text-slate-300 transition hover:border-cyan-300/40 hover:text-cyan-200">
      <Download size={14} />
      Export
    </button>
  );
}

function IconButton({ label, icon: Icon, onClick, disabled }) {
  return (
    <button aria-label={label} title={label} disabled={disabled} onClick={onClick} className="grid h-10 w-10 place-items-center rounded-[8px] border border-white/10 text-slate-300 transition hover:border-cyan-300/40 hover:text-cyan-200 disabled:cursor-not-allowed disabled:opacity-40">
      <Icon size={15} />
    </button>
  );
}

function DataRows({ rows, render, emptyIcon }) {
  if (!rows.length) return <EmptyState icon={emptyIcon} title="No records" text="Records will appear as connected systems send data." />;
  return <div className="mt-4 space-y-2">{rows.map((item) => <div key={item.id || `${item.ip_address}-${item.count}`}>{render(item)}</div>)}</div>;
}

function MetricLine({ label, value }) {
  return (
    <div className="flex items-center justify-between rounded-[8px] border border-white/10 bg-[#07101d] px-3 py-3">
      <span className="text-sm text-slate-400">{label}</span>
      <span className="text-lg font-black text-white">{value || 0}</span>
    </div>
  );
}

function ModalHeader({ title, subtitle, onClose }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <h3 className="truncate text-2xl font-black text-white">{title}</h3>
        {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
      </div>
      <button onClick={onClose} className="grid h-10 w-10 place-items-center rounded-[8px] border border-white/10 text-slate-300 transition hover:border-cyan-300/40 hover:text-white" aria-label="Close dialog">
        <X size={18} />
      </button>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-[8px] border border-white/10 bg-[#07101d] px-3 py-2">
      <span className="text-slate-500">{label}</span>
      <span className="text-right text-white">{value}</span>
    </div>
  );
}

function JsonBlock({ title, value }) {
  return (
    <Panel tight>
      <PanelHeader icon={FileJson} title={title} />
      <pre className="mt-4 max-h-80 overflow-auto rounded-[8px] border border-white/10 bg-black/35 p-4 text-xs leading-6 text-cyan-100">
        {JSON.stringify(value || {}, null, 2)}
      </pre>
    </Panel>
  );
}

function DetailList({ title, rows }) {
  return (
    <Panel tight>
      <h4 className="mb-3 font-black text-white">{title}</h4>
      <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
        {rows.slice(0, 20).map((row) => (
          <div key={row.id} className="rounded-[8px] bg-[#07101d] px-3 py-2 text-sm">
            <p className="truncate text-slate-200">{row.http_method} {row.endpoint}</p>
            <p className="mt-1 text-xs text-slate-500">{row.response_code} - {row.response_time_ms}ms - {dateTime(row.timestamp)}</p>
          </div>
        ))}
        {!rows.length && <p className="rounded-[8px] border border-dashed border-white/10 p-4 text-sm text-slate-500">No records yet.</p>}
      </div>
    </Panel>
  );
}

function TicketList({ rows }) {
  return (
    <Panel tight>
      <h4 className="mb-3 font-black text-white">Automated Tickets</h4>
      <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
        {rows.slice(0, 20).map((ticket) => (
          <div key={ticket.id} className="rounded-[8px] bg-[#07101d] px-3 py-2 text-sm">
            <div className="flex items-start justify-between gap-3">
              <p className="text-slate-200">{ticket.title}</p>
              <StatusPill value={ticket.status} />
            </div>
            <p className="mt-1 text-xs text-slate-500">{ticket.ticket_id || ticket.id} - {ticket.priority}</p>
          </div>
        ))}
        {!rows.length && <p className="rounded-[8px] border border-dashed border-white/10 p-4 text-sm text-slate-500">No API-created tickets yet.</p>}
      </div>
    </Panel>
  );
}
