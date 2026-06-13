import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  Bot,
  Box,
  Braces,
  Copy,
  Cpu,
  Download,
  Eye,
  Filter,
  GitBranch,
  Globe2,
  KeyRound,
  Laptop,
  Layers3,
  Network,
  Play,
  RefreshCw,
  RotateCcw,
  Search,
  Server,
  ShieldAlert,
  ShieldCheck,
  TerminalSquare,
  Webhook,
  X,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api, apiErrorMessage } from "../api/client.js";

const environmentOptions = ["all", "localhost", "development", "qa", "staging", "production"];
const statusOptions = ["all", "running", "degraded", "error", "stopped", "unknown"];
const windowOptions = [1, 6, 24, 72, 168];
const fieldClass =
  "theme-input px-3 text-sm placeholder:text-[color:var(--text-muted)]";
const secondaryButtonClass =
  "theme-secondary-button inline-flex h-11 items-center gap-2 rounded-[8px] px-3 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-45";
const iconButtonClass =
  "theme-icon-button grid h-11 w-11 place-items-center rounded-[8px] transition disabled:cursor-not-allowed disabled:opacity-40";
const compactIconButtonClass =
  "theme-icon-button grid h-10 w-10 place-items-center rounded-[8px] transition disabled:cursor-not-allowed disabled:opacity-40";
const chart = {
  grid: "var(--chart-grid)",
  axis: "var(--chart-axis)",
  cpu: "var(--chart-cpu)",
  memory: "var(--chart-memory)",
  error: "var(--chart-error)",
  tooltip: {
    background: "var(--tooltip-bg)",
    border: "1px solid var(--tooltip-border)",
    borderRadius: 8,
    color: "var(--text-primary)",
  },
};

const emptyDashboard = {
  generated_at: "",
  window_hours: 24,
  summary: {},
  agents: [],
  projects: [],
  traffic: [],
  webhooks: [],
  logs: [],
  deployments: [],
  topology: { nodes: [], links: [] },
  anomalies: [],
};

function resolveWsBase() {
  if (import.meta.env.VITE_WS_BASE_URL) return import.meta.env.VITE_WS_BASE_URL.replace(/\/$/, "");
  if (typeof window === "undefined") return "ws://127.0.0.1:8001/ws";
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws`;
}

function formatNumber(value, options = {}) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, ...options }).format(Number(value || 0));
}

function formatDate(value) {
  if (!value) return "Never";
  return new Date(value).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function normalize(value) {
  return String(value || "").toLowerCase();
}

function statusTone(value) {
  const text = normalize(value);
  if (["online", "running", "passing", "ready", "deployed", "success", "healthy", "processed", "valid"].some((item) => text.includes(item))) {
    return "theme-status-success";
  }
  if (["building", "pending", "retried", "warning", "risky", "staging", "qa"].some((item) => text.includes(item))) {
    return "theme-status-warning";
  }
  if (["failed", "blocked", "error", "critical", "degraded", "revoked", "offline"].some((item) => text.includes(item))) {
    return "theme-status-danger";
  }
  return "theme-status-info";
}

function useProjectIntelligenceSocket(onEvent) {
  const [state, setState] = useState({ connected: false, lastEvent: null });

  useEffect(() => {
    const token = localStorage.getItem("accessToken") || "";
    if (!token) return undefined;
    const socket = new WebSocket(`${resolveWsBase()}/project-intelligence/?token=${encodeURIComponent(token)}`);

    socket.onopen = () => setState((current) => ({ ...current, connected: true }));
    socket.onclose = () => setState((current) => ({ ...current, connected: false }));
    socket.onerror = () => setState((current) => ({ ...current, connected: false }));
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setState({ connected: true, lastEvent: data });
      onEvent?.(data);
    };
    return () => socket.close();
  }, [onEvent]);

  return state;
}

export default function ProjectIntelligence() {
  const qc = useQueryClient();
  const [filters, setFilters] = useState({ environment: "all", status: "all", window_hours: 24 });
  const [search, setSearch] = useState("");
  const [selectedProject, setSelectedProject] = useState(null);
  const [selectedWebhook, setSelectedWebhook] = useState(null);
  const [agentToken, setAgentToken] = useState(null);
  const [registerForm, setRegisterForm] = useState({
    name: "",
    machine_id: "",
    hostname: "",
    os_name: "",
    environment: "development",
  });

  const handleSocketEvent = useCallback(() => {
    qc.invalidateQueries({ queryKey: ["project-intelligence-dashboard"] });
  }, [qc]);
  const socket = useProjectIntelligenceSocket(handleSocketEvent);

  const dashboardQuery = useQuery({
    queryKey: ["project-intelligence-dashboard", filters],
    queryFn: () => api.get("/project-intelligence/dashboard/", { params: filters }).then((response) => response.data),
    refetchInterval: 5000,
  });

  const registerAgent = useMutation({
    mutationFn: (payload) => api.post("/project-intelligence/agents/register/", payload).then((response) => response.data),
    onSuccess: (data) => {
      setAgentToken(data.plaintext_token);
      setRegisterForm((current) => ({ ...current, name: "", machine_id: "", hostname: "", os_name: "" }));
      qc.invalidateQueries({ queryKey: ["project-intelligence-dashboard"] });
    },
  });

  const commandProject = useMutation({
    mutationFn: ({ projectId, command_type, payload }) =>
      api.post(`/project-intelligence/projects/${projectId}/command/`, { command_type, payload }).then((response) => response.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["project-intelligence-dashboard"] });
      if (selectedProject?.id) qc.invalidateQueries({ queryKey: ["project-intelligence-workspace", selectedProject.id] });
    },
  });

  const retryWebhook = useMutation({
    mutationFn: (eventId) => api.post(`/project-intelligence/webhooks/${eventId}/retry/`).then((response) => response.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project-intelligence-dashboard"] }),
  });

  const revokeAgent = useMutation({
    mutationFn: (agentId) => api.post(`/project-agents/${agentId}/revoke/`).then((response) => response.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project-intelligence-dashboard"] }),
  });

  const dashboard = dashboardQuery.data || emptyDashboard;
  const summary = dashboard.summary || {};
  const projects = dashboard.projects || [];
  const webhooks = dashboard.webhooks || [];
  const agents = dashboard.agents || [];
  const logs = dashboard.logs || [];
  const deployments = dashboard.deployments || [];
  const anomalies = dashboard.anomalies || [];
  const traffic = dashboard.traffic || [];

  const searchedProjects = useMemo(() => {
    const q = search.toLowerCase().trim();
    if (!q) return projects;
    return projects.filter((project) =>
      [project.name, project.framework, project.environment, project.current_branch, project.repository_url, project.agent_name]
        .join(" ")
        .toLowerCase()
        .includes(q),
    );
  }, [projects, search]);

  const pageError = dashboardQuery.isError ? apiErrorMessage(dashboardQuery.error, "Project intelligence data could not be loaded.") : "";

  function submitAgent(event) {
    event.preventDefault();
    registerAgent.mutate({
      ...registerForm,
      machine_id: registerForm.machine_id || `${registerForm.name || "machine"}-${Date.now()}`,
      capabilities: { project_discovery: true, websocket: true, runtime_metrics: true },
      metadata: { registered_from: "project_intelligence_dashboard" },
    });
  }

  async function copy(value) {
    if (value) await navigator.clipboard?.writeText(value);
  }

  return (
    <div className="project-intelligence-page min-h-screen space-y-5 text-[color:var(--text-primary)]">
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="theme-hero-panel overflow-hidden rounded-[8px] p-5"
      >
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_540px] xl:items-center">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill value={socket.connected ? "live websocket" : "polling"} />
              <StatusPill value={`${dashboard.window_hours || filters.window_hours}h window`} />
              <StatusPill value={`${agents.filter((agent) => agent.status === "online").length}/${agents.length} agents online`} />
            </div>
            <h1 className="theme-title mt-4 text-3xl font-black md:text-5xl">Project Intelligence Command Center</h1>
            <p className="theme-muted mt-3 max-w-4xl text-sm leading-6">
              Fleet visibility for developer machines, localhost apps, cloud workloads, deployments, runtime signals, logs, and webhook execution.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <MetricCard icon={Laptop} label="Online agents" value={summary.agents_online} tone="emerald" />
            <MetricCard icon={Layers3} label="Projects" value={summary.projects_total} />
            <MetricCard icon={Activity} label="Running" value={summary.projects_running} tone="emerald" />
            <MetricCard icon={AlertTriangle} label="Degraded" value={summary.projects_degraded} tone="amber" />
            <MetricCard icon={Webhook} label="Webhook failures" value={summary.webhook_failures} tone={summary.webhook_failures ? "rose" : "cyan"} />
            <MetricCard icon={Zap} label="Error rate" value={`${formatNumber(summary.error_rate)}%`} tone={summary.error_rate > 3 ? "rose" : "cyan"} />
          </div>
        </div>
      </motion.section>

      <section className="theme-toolbar grid gap-3 rounded-[8px] p-3 lg:grid-cols-[1fr_auto]">
        <div className="grid gap-3 md:grid-cols-[1fr_160px_150px_130px]">
          <label className="relative block">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[color:var(--text-muted)]" size={16} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className={`${fieldClass} pl-9`}
              placeholder="Search projects, frameworks, branches, agents"
            />
          </label>
          <select value={filters.environment} onChange={(event) => setFilters((current) => ({ ...current, environment: event.target.value }))} className={fieldClass} aria-label="Environment">
            {environmentOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))} className={fieldClass} aria-label="Runtime status">
            {statusOptions.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={filters.window_hours} onChange={(event) => setFilters((current) => ({ ...current, window_hours: Number(event.target.value) }))} className={fieldClass} aria-label="Telemetry window">
            {windowOptions.map((item) => <option key={item} value={item}>{item}h</option>)}
          </select>
        </div>
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => dashboardQuery.refetch()}
            className={secondaryButtonClass}
          >
            <RefreshCw size={16} className={dashboardQuery.isFetching ? "animate-spin" : ""} />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => setFilters({ environment: "all", status: "all", window_hours: 24 })}
            className={iconButtonClass}
            aria-label="Reset filters"
            title="Reset filters"
          >
            <Filter size={16} />
          </button>
        </div>
      </section>

      {pageError && <Notice tone="rose" title="Project intelligence unavailable" detail={pageError} />}
      {registerAgent.isError && <Notice tone="rose" title="Agent registration failed" detail={apiErrorMessage(registerAgent.error, "Could not register machine agent.")} />}
      {commandProject.isError && <Notice tone="rose" title="Command was not queued" detail={apiErrorMessage(commandProject.error, "Project command could not be queued.")} />}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.65fr)]">
        <div className="space-y-5">
          <TrafficPanel traffic={traffic} summary={summary} />
          <ProjectsPanel projects={searchedProjects} onOpen={setSelectedProject} />
          <WebhookPanel webhooks={webhooks} onOpen={setSelectedWebhook} retryWebhook={retryWebhook} />
          <LogsPanel logs={logs} />
        </div>

        <div className="space-y-5">
          <AgentRegistrationPanel form={registerForm} setForm={setRegisterForm} submit={submitAgent} loading={registerAgent.isPending} />
          <AgentsPanel agents={agents} revokeAgent={revokeAgent} />
          <TopologyPanel topology={dashboard.topology || emptyDashboard.topology} />
          <SignalsPanel anomalies={anomalies} deployments={deployments} />
        </div>
      </div>

      <AnimatePresence>
        {selectedProject && (
          <ProjectWorkspace
            project={selectedProject}
            onClose={() => setSelectedProject(null)}
            commandProject={commandProject}
          />
        )}
        {selectedWebhook && (
          <WebhookInspector
            event={selectedWebhook}
            onClose={() => setSelectedWebhook(null)}
            onRetry={() => retryWebhook.mutate(selectedWebhook.id)}
            retrying={retryWebhook.isPending}
          />
        )}
        {agentToken && <AgentTokenModal token={agentToken} onClose={() => setAgentToken(null)} onCopy={copy} />}
      </AnimatePresence>
    </div>
  );
}

function TrafficPanel({ traffic, summary }) {
  return (
    <Panel>
      <PanelHeader icon={Activity} title="Realtime Runtime Fabric" action={<StatusPill value={`${formatNumber(summary.requests_per_second)} rps`} />} />
      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <MiniStat label="Avg CPU" value={`${formatNumber(summary.avg_cpu)}%`} />
        <MiniStat label="Avg memory" value={`${formatNumber(summary.avg_memory)}%`} />
        <MiniStat label="Errors" value={`${formatNumber(summary.error_rate)}%`} />
        <MiniStat label="Critical logs" value={summary.critical_logs || 0} />
      </div>
      <div className="mt-4 h-72 min-h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={traffic}>
            <defs>
              <linearGradient id="piCpu" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={chart.cpu} stopOpacity={0.32} />
                <stop offset="95%" stopColor={chart.cpu} stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="piMemory" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={chart.memory} stopOpacity={0.28} />
                <stop offset="95%" stopColor={chart.memory} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={chart.grid} vertical={false} />
            <XAxis dataKey="label" tick={{ fill: chart.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: chart.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={chart.tooltip} />
            <Area type="monotone" dataKey="cpu" name="CPU" stroke={chart.cpu} fill="url(#piCpu)" strokeWidth={2} />
            <Area type="monotone" dataKey="memory" name="Memory" stroke={chart.memory} fill="url(#piMemory)" strokeWidth={2} />
            <Line type="monotone" dataKey="errors" name="Errors" stroke={chart.error} dot={false} strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}

function ProjectsPanel({ projects, onOpen }) {
  return (
    <Panel>
      <PanelHeader icon={Layers3} title="Discovered Projects" action={<StatusPill value={`${projects.length} visible`} />} />
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[920px] border-separate border-spacing-y-2 text-left text-sm">
          <thead className="theme-faint text-xs">
            <tr>
              <th className="px-3 py-2 font-bold">Project</th>
              <th className="px-3 py-2 font-bold">Developer</th>
              <th className="px-3 py-2 font-bold">Environment</th>
              <th className="px-3 py-2 font-bold">Runtime</th>
              <th className="px-3 py-2 font-bold">Branch</th>
              <th className="px-3 py-2 font-bold">Build</th>
              <th className="px-3 py-2 font-bold">Health</th>
              <th className="px-3 py-2 font-bold">Open</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((project) => (
              <tr key={project.id} className="theme-table-row rounded-[8px]">
                <td className="rounded-l-[8px] px-3 py-3">
                  <p className="theme-title max-w-56 truncate font-black">{project.name}</p>
                  <p className="theme-faint mt-1 text-xs">{project.framework || "Unknown"} {project.port ? `: ${project.port}` : ""}</p>
                </td>
                <td className="theme-muted px-3 py-3">{project.developer_name || project.agent_name || "Unassigned"}</td>
                <td className="px-3 py-3"><StatusPill value={project.environment} /></td>
                <td className="px-3 py-3"><StatusPill value={project.runtime_status} /></td>
                <td className="px-3 py-3">
                  <span className="theme-muted inline-flex max-w-36 items-center gap-2 truncate">
                    <GitBranch size={14} />
                    {project.current_branch || "unknown"}
                  </span>
                </td>
                <td className="px-3 py-3"><StatusPill value={project.build_status} /></td>
                <td className="px-3 py-3">
                  <HealthBar value={project.health_score} />
                </td>
                <td className="rounded-r-[8px] px-3 py-3">
                  <IconButton label={`Open ${project.name}`} icon={Eye} onClick={() => onOpen(project)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!projects.length && <EmptyState icon={Layers3} title="No discovered projects" detail="Connected agents will stream project inventory here." />}
    </Panel>
  );
}

function WebhookPanel({ webhooks, onOpen, retryWebhook }) {
  return (
    <Panel>
      <PanelHeader icon={Webhook} title="Webhook Command Center" action={<StatusPill value={`${webhooks.length} events`} />} />
      <div className="mt-4 space-y-2">
        {webhooks.slice(0, 14).map((event) => (
          <div key={event.id} className="theme-row grid gap-3 rounded-[8px] p-3 md:grid-cols-[1fr_auto] md:items-center">
            <div className="min-w-0">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <p className="theme-title truncate font-black">{event.event_type}</p>
                <StatusPill value={event.status} />
                <StatusPill value={event.direction} />
                {!event.signature_valid && <StatusPill value="signature failed" />}
              </div>
              <p className="theme-faint mt-1 truncate text-xs">
                {event.project_name || "Unlinked event"} - {event.integration || "internal"} - {event.processing_time_ms || 0}ms - {formatDate(event.occurred_at)}
              </p>
              {event.ai_analysis?.recommendation && <p className="theme-accent mt-2 line-clamp-2 text-xs leading-5">{event.ai_analysis.recommendation}</p>}
            </div>
            <div className="flex items-center gap-2">
              <IconButton label="Inspect payload" icon={Braces} onClick={() => onOpen(event)} />
              <IconButton label="Retry webhook" icon={RotateCcw} onClick={() => retryWebhook.mutate(event.id)} disabled={retryWebhook.isPending || !event.agent} />
            </div>
          </div>
        ))}
      </div>
      {!webhooks.length && <EmptyState icon={Webhook} title="No webhook events" detail="Webhook executions will appear as agents and integrations stream events." />}
    </Panel>
  );
}

function LogsPanel({ logs }) {
  return (
    <Panel>
      <PanelHeader icon={TerminalSquare} title="Runtime Logs" action={<StatusPill value={`${logs.length} entries`} />} />
      <div className="mt-4 max-h-[420px] space-y-2 overflow-auto pr-1">
        {logs.slice(0, 80).map((entry) => (
          <div key={entry.id} className="theme-code-row rounded-[8px] px-3 py-2 font-mono text-xs leading-5">
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill value={entry.level} />
              <span className="theme-muted">{entry.project_name || "project"}</span>
              <span className="theme-faint">{formatDate(entry.timestamp)}</span>
            </div>
            <p className="theme-muted mt-2 whitespace-pre-wrap break-words">{entry.message}</p>
          </div>
        ))}
        {!logs.length && <EmptyState icon={TerminalSquare} title="No runtime logs" detail="Agent log collectors have not reported entries for this window." />}
      </div>
    </Panel>
  );
}

function AgentRegistrationPanel({ form, setForm, submit, loading }) {
  return (
    <Panel>
      <PanelHeader icon={KeyRound} title="Register Machine Agent" action={<StatusPill value="JWT issued token" />} />
      <form onSubmit={submit} className="mt-4 space-y-3">
        <input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} className={fieldClass} placeholder="Agent display name" />
        <input value={form.machine_id} onChange={(event) => setForm({ ...form, machine_id: event.target.value })} className={fieldClass} placeholder="Machine ID (optional)" />
        <div className="grid gap-3 sm:grid-cols-2">
          <input value={form.hostname} onChange={(event) => setForm({ ...form, hostname: event.target.value })} className={fieldClass} placeholder="Hostname" />
          <input value={form.os_name} onChange={(event) => setForm({ ...form, os_name: event.target.value })} className={fieldClass} placeholder="OS name" />
        </div>
        <select value={form.environment} onChange={(event) => setForm({ ...form, environment: event.target.value })} className={fieldClass}>
          {environmentOptions.filter((item) => item !== "all").map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <button disabled={loading} className="theme-primary-action inline-flex h-11 w-full items-center justify-center gap-2 rounded-[8px] px-4 text-sm font-black transition disabled:cursor-not-allowed disabled:opacity-50">
          {loading ? <RefreshCw className="animate-spin" size={16} /> : <KeyRound size={16} />}
          Generate Agent Token
        </button>
      </form>
    </Panel>
  );
}

function AgentsPanel({ agents, revokeAgent }) {
  return (
    <Panel>
      <PanelHeader icon={Laptop} title="Distributed Agents" action={<StatusPill value={`${agents.length} registered`} />} />
      <div className="mt-4 space-y-2">
        {agents.slice(0, 12).map((agent) => (
          <div key={agent.id} className="theme-row rounded-[8px] p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="theme-title truncate font-black">{agent.name}</p>
                <p className="theme-faint mt-1 truncate text-xs">{agent.hostname || agent.machine_id} - {agent.os_name || "OS unknown"}</p>
              </div>
              <StatusPill value={agent.status} />
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <MiniStat label="Projects" value={agent.project_count || 0} />
              <MiniStat label="Env" value={agent.environment} />
              <MiniStat label="Seen" value={formatDate(agent.last_seen_at)} />
            </div>
            {agent.status !== "revoked" && (
              <button
                type="button"
                onClick={() => revokeAgent.mutate(agent.id)}
                disabled={revokeAgent.isPending}
                className="theme-danger-button mt-3 inline-flex h-9 items-center gap-2 rounded-[8px] px-3 text-xs font-bold transition disabled:cursor-not-allowed disabled:opacity-50"
              >
                <ShieldAlert size={14} />
                Revoke
              </button>
            )}
          </div>
        ))}
        {!agents.length && <EmptyState icon={Laptop} title="No agents registered" detail="Issued agent tokens will create secure machine identities." />}
      </div>
    </Panel>
  );
}

function TopologyPanel({ topology }) {
  const nodes = topology.nodes || [];
  const links = topology.links || [];
  const agents = nodes.filter((node) => node.type === "agent");
  const projects = nodes.filter((node) => node.type === "project");
  return (
    <Panel>
      <PanelHeader icon={Network} title="Topology Map" action={<StatusPill value={`${links.length} links`} />} />
      <div className="theme-code-row mt-4 min-h-64 rounded-[8px] p-4">
        <div className="grid gap-4">
          {agents.slice(0, 8).map((agent) => {
            const childIds = links.filter((link) => link.source === agent.id).map((link) => link.target);
            const children = projects.filter((project) => childIds.includes(project.id));
            return (
              <div key={agent.id} className="theme-row rounded-[8px] p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="theme-title min-w-0 truncate font-black">{agent.label}</span>
                  <StatusPill value={agent.status} />
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {children.slice(0, 10).map((project) => (
                    <span key={project.id} className="theme-mini-card inline-flex items-center gap-2 rounded-[8px] px-2.5 py-1 text-xs">
                      <Box size={13} />
                      {project.label}
                    </span>
                  ))}
                  {!children.length && <span className="theme-faint text-xs">No linked projects</span>}
                </div>
              </div>
            );
          })}
          {!agents.length && <EmptyState icon={Network} title="No topology" detail="Agent-to-project links will render after the first snapshot." />}
        </div>
      </div>
    </Panel>
  );
}

function SignalsPanel({ anomalies, deployments }) {
  return (
    <Panel>
      <PanelHeader icon={Bot} title="AI Operations Signals" action={<StatusPill value={`${anomalies.length} findings`} />} />
      <div className="mt-4 space-y-3">
        {anomalies.map((item) => (
          <div key={`${item.title}-${item.severity}`} className="theme-row rounded-[8px] p-3">
            <div className="flex items-start justify-between gap-3">
              <p className="theme-title font-black">{item.title}</p>
              <StatusPill value={item.severity} />
            </div>
            <p className="theme-muted mt-2 text-sm leading-6">{item.detail}</p>
            <p className="theme-accent mt-2 text-xs leading-5">{item.recommendation}</p>
          </div>
        ))}
      </div>
      <div className="mt-5 space-y-2">
        <p className="theme-title text-sm font-black">Deployment Timeline</p>
        {deployments.slice(0, 8).map((item) => (
          <div key={item.id} className="theme-code-row rounded-[8px] px-3 py-2 text-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="theme-title truncate">{item.project_name || item.signal_type}</span>
              <StatusPill value={item.status} />
            </div>
            <p className="theme-faint mt-1 text-xs">{item.version || item.release_id || "release"} - risk {item.risk_score || 0}% - {formatDate(item.created_at)}</p>
          </div>
        ))}
        {!deployments.length && <p className="theme-faint rounded-[8px] border border-dashed border-[color:var(--border-color)] p-3 text-sm">No deployment signals in this window.</p>}
      </div>
    </Panel>
  );
}

function ProjectWorkspace({ project, onClose, commandProject }) {
  const workspaceQuery = useQuery({
    queryKey: ["project-intelligence-workspace", project.id],
    queryFn: () => api.get(`/project-intelligence/projects/${project.id}/workspace/`).then((response) => response.data),
    enabled: Boolean(project?.id),
    refetchInterval: 5000,
  });

  useEffect(() => {
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = original;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const data = workspaceQuery.data || {};
  const metrics = data.metrics || [];
  const logs = data.logs || [];
  const webhooks = data.webhooks || [];
  const deployments = data.deployments || [];
  const commands = data.commands || [];

  function queue(command_type) {
    commandProject.mutate({ projectId: project.id, command_type, payload: { source: "project_workspace" } });
  }

  return (
    <motion.div
      className="theme-modal-backdrop fixed inset-0 z-[9999] grid place-items-center overflow-y-auto p-4 backdrop-blur-[8px]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      role="dialog"
      aria-modal="true"
      aria-label={`${project.name} workspace`}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <motion.div
        className="theme-modal w-full max-w-7xl rounded-[8px] p-5"
        initial={{ opacity: 0, scale: 0.96, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 10 }}
        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      >
        <ModalHeader title={project.name} subtitle={`${project.framework || "Unknown"} - ${project.environment} - ${project.agent_name || "unassigned agent"}`} onClose={onClose} />

        <div className="mt-5 grid gap-3 md:grid-cols-5">
          <MetricCard icon={Activity} label="Health" value={`${project.health_score || 0}%`} tone={project.health_score < 60 ? "rose" : "emerald"} />
          <MetricCard icon={Cpu} label="Runtime" value={project.runtime_status} />
          <MetricCard icon={GitBranch} label="Branch" value={project.current_branch || "unknown"} tone="violet" />
          <MetricCard icon={Server} label="Build" value={project.build_status} tone={project.build_status === "failing" ? "rose" : "cyan"} />
          <MetricCard icon={Globe2} label="Deploy" value={project.deployment_status} tone="amber" />
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          {[
            ["refresh_discovery", RefreshCw, "Refresh"],
            ["collect_logs", Download, "Collect Logs"],
            ["build", Play, "Build"],
            ["deploy", Zap, "Deploy"],
            ["rollback", RotateCcw, "Rollback"],
          ].map(([type, Icon, label]) => (
            <button
              key={type}
              type="button"
              onClick={() => queue(type)}
              disabled={commandProject.isPending || !project.agent}
              className={secondaryButtonClass.replace("h-11", "h-10")}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </div>

        <div className="mt-5 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
          <Panel tight>
            <PanelHeader icon={Activity} title="Runtime Metrics" />
            <div className="mt-4 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={metrics.slice().reverse()}>
                  <CartesianGrid stroke={chart.grid} vertical={false} />
                  <XAxis dataKey="recorded_at" hide />
                  <YAxis tick={{ fill: chart.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={chart.tooltip} />
                  <Line type="monotone" dataKey="cpu_percent" name="CPU" stroke={chart.cpu} dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="memory_percent" name="Memory" stroke={chart.memory} dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="error_rate_percent" name="Error rate" stroke={chart.error} dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Panel>
          <Panel tight>
            <PanelHeader icon={ShieldCheck} title="Command History" />
            <div className="mt-4 max-h-64 space-y-2 overflow-auto pr-1">
              {commands.map((command) => (
                <div key={command.id} className="theme-code-row rounded-[8px] px-3 py-2 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="theme-title font-bold">{command.command_type}</span>
                    <StatusPill value={command.status} />
                  </div>
                  <p className="theme-faint mt-1 text-xs">{formatDate(command.created_at)}</p>
                </div>
              ))}
              {!commands.length && <p className="theme-faint rounded-[8px] border border-dashed border-[color:var(--border-color)] p-3 text-sm">No commands queued yet.</p>}
            </div>
          </Panel>
        </div>

        <div className="mt-5 grid gap-5 xl:grid-cols-3">
          <CompactRows title="Webhook Events" icon={Webhook} rows={webhooks} render={(item) => (
            <RowLine title={item.event_type} detail={`${item.status} - ${item.processing_time_ms || 0}ms - ${formatDate(item.occurred_at)}`} />
          )} />
          <CompactRows title="Runtime Logs" icon={TerminalSquare} rows={logs} render={(item) => (
            <RowLine title={item.level} detail={item.message} />
          )} />
          <CompactRows title="Deployments" icon={Server} rows={deployments} render={(item) => (
            <RowLine title={item.signal_type} detail={`${item.status} - risk ${item.risk_score || 0}% - ${formatDate(item.created_at)}`} />
          )} />
        </div>
      </motion.div>
    </motion.div>
  );
}

function WebhookInspector({ event, onClose, onRetry, retrying }) {
  useEffect(() => {
    const onKey = (keyEvent) => {
      if (keyEvent.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <motion.div
      className="theme-modal-backdrop fixed inset-0 z-[9999] grid place-items-center overflow-y-auto p-4 backdrop-blur-[8px]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      role="dialog"
      aria-modal="true"
      aria-label="Webhook payload inspector"
      onMouseDown={(click) => {
        if (click.target === click.currentTarget) onClose();
      }}
    >
      <motion.div className="theme-modal w-full max-w-6xl rounded-[8px] p-5" initial={{ scale: 0.96 }} animate={{ scale: 1 }} exit={{ scale: 0.96 }}>
        <ModalHeader title={event.event_type} subtitle={`${event.project_name || "Unlinked"} - ${event.integration || "internal"} - ${formatDate(event.occurred_at)}`} onClose={onClose} />
        <div className="mt-4 flex flex-wrap gap-2">
          <StatusPill value={event.status} />
          <StatusPill value={event.direction} />
          <StatusPill value={`${event.processing_time_ms || 0}ms`} />
          <StatusPill value={event.signature_valid ? "signature valid" : "signature failed"} />
          <StatusPill value={`threat ${event.threat_score || 0}`} />
        </div>
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <JsonBlock title="Request Headers" value={event.request_headers} />
          <JsonBlock title="Request Body" value={event.request_body} />
          <JsonBlock title="Response Body" value={event.response_body} />
          <JsonBlock title="AI Analysis" value={event.ai_analysis} />
          <JsonBlock title="Retry History" value={event.retry_history} />
          <JsonBlock title="Execution Trace" value={event.execution_trace} />
        </div>
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying || !event.agent}
          className="theme-primary-action mt-5 inline-flex h-11 items-center gap-2 rounded-[8px] px-4 text-sm font-black transition disabled:cursor-not-allowed disabled:opacity-50"
        >
          {retrying ? <RefreshCw className="animate-spin" size={16} /> : <RotateCcw size={16} />}
          Retry Event
        </button>
      </motion.div>
    </motion.div>
  );
}

function AgentTokenModal({ token, onClose, onCopy }) {
  const command = `python backend/agents/project_intelligence_agent.py --server ws://127.0.0.1:8001 --token ${token} --environment development --roots .`;
  return (
    <motion.div className="theme-modal-backdrop fixed inset-0 z-[9999] grid place-items-center overflow-y-auto p-4 backdrop-blur-[8px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} role="dialog" aria-modal="true" aria-label="Agent token">
      <motion.div className="theme-modal w-full max-w-3xl rounded-[8px] p-5" initial={{ scale: 0.96 }} animate={{ scale: 1 }} exit={{ scale: 0.96 }}>
        <ModalHeader title="Agent Token Issued" subtitle="Shown once. Store it in the machine agent runtime secret store." onClose={onClose} />
        <div className="theme-status-warning mt-5 rounded-[8px] p-4">
          <p className="text-sm font-bold">Token</p>
          <code className="theme-code-block mt-2 block break-all rounded-[8px] px-3 py-2 text-xs">{token}</code>
          <button onClick={() => onCopy(token)} className="theme-secondary-button mt-3 inline-flex h-10 items-center gap-2 rounded-[8px] px-3 text-sm font-bold">
            <Copy size={15} />
            Copy Token
          </button>
        </div>
        <JsonBlock title="Agent Start Command" value={{ command }} />
      </motion.div>
    </motion.div>
  );
}

function Panel({ children, tight = false }) {
  return <section className={`theme-panel rounded-[8px] ${tight ? "p-4" : "p-5"}`}>{children}</section>;
}

function PanelHeader({ icon: Icon, title, action }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2">
        <Icon className="theme-accent shrink-0" size={19} />
        <h2 className="theme-title min-w-0 text-lg font-black leading-tight">{title}</h2>
      </div>
      {action}
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, tone = "cyan" }) {
  const tones = {
    cyan: "theme-tone-cyan",
    violet: "theme-tone-violet",
    amber: "theme-tone-amber",
    emerald: "theme-tone-emerald",
    rose: "theme-tone-rose",
  };
  return (
    <div className="theme-mini-card rounded-[8px] p-4">
      <div className={`grid h-10 w-10 place-items-center rounded-[8px] border ${tones[tone] || tones.cyan}`}>
        <Icon size={18} />
      </div>
      <p className="theme-title mt-3 truncate text-2xl font-black">{value ?? 0}</p>
      <p className="theme-faint mt-1 text-xs">{label}</p>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div className="theme-mini-card rounded-[8px] px-3 py-2">
      <p className="theme-title truncate text-sm font-black">{value ?? 0}</p>
      <p className="theme-faint mt-1 text-xs">{label}</p>
    </div>
  );
}

function StatusPill({ value }) {
  return <span className={`inline-flex max-w-full items-center rounded-full border px-2.5 py-1 text-xs font-bold ${statusTone(value)}`}>{String(value || "unknown")}</span>;
}

function HealthBar({ value }) {
  const percent = Math.max(0, Math.min(100, Number(value || 0)));
  const color = percent < 50 ? "theme-progress-fill--danger" : percent < 75 ? "theme-progress-fill--warning" : "theme-progress-fill--success";
  return (
    <div className="w-28">
      <div className="theme-progress-track h-2 rounded-full">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${percent}%` }} />
      </div>
      <p className="theme-faint mt-1 text-xs">{percent}%</p>
    </div>
  );
}

function IconButton({ label, icon: Icon, onClick, disabled }) {
  return (
    <button
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className={compactIconButtonClass}
      type="button"
    >
      <Icon size={15} />
    </button>
  );
}

function EmptyState({ icon: Icon, title, detail }) {
  return (
    <div className="theme-row mt-4 rounded-[8px] border-dashed p-8 text-center">
      <Icon className="theme-accent mx-auto" size={24} />
      <p className="theme-title mt-3 font-bold">{title}</p>
      <p className="theme-faint mt-1 text-sm leading-6">{detail}</p>
    </div>
  );
}

function Notice({ tone = "cyan", title, detail }) {
  const cls = tone === "rose" ? "theme-notice-rose" : "theme-notice-cyan";
  return (
    <div className={`theme-notice rounded-[8px] px-4 py-3 ${cls}`}>
      <p className="font-bold">{title}</p>
      {detail && <p className="mt-1 text-sm opacity-80">{detail}</p>}
    </div>
  );
}

function ModalHeader({ title, subtitle, onClose }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <h3 className="theme-title truncate text-2xl font-black">{title}</h3>
        {subtitle && <p className="theme-muted mt-1 text-sm">{subtitle}</p>}
      </div>
      <button onClick={onClose} className={compactIconButtonClass} aria-label="Close dialog" type="button">
        <X size={18} />
      </button>
    </div>
  );
}

function JsonBlock({ title, value }) {
  return (
    <Panel tight>
      <PanelHeader icon={Braces} title={title} />
      <pre className="theme-code-block mt-4 max-h-80 overflow-auto rounded-[8px] p-4 text-xs leading-6">
        {JSON.stringify(value || {}, null, 2)}
      </pre>
    </Panel>
  );
}

function CompactRows({ title, icon, rows, render }) {
  return (
    <Panel tight>
      <PanelHeader icon={icon} title={title} />
      <div className="mt-4 max-h-80 space-y-2 overflow-auto pr-1">
        {rows.map((item) => <div key={item.id}>{render(item)}</div>)}
        {!rows.length && <p className="theme-faint rounded-[8px] border border-dashed border-[color:var(--border-color)] p-3 text-sm">No records.</p>}
      </div>
    </Panel>
  );
}

function RowLine({ title, detail }) {
  return (
    <div className="theme-code-row rounded-[8px] px-3 py-2 text-sm">
      <p className="theme-title truncate font-bold">{title}</p>
      <p className="theme-faint mt-1 line-clamp-2 text-xs leading-5">{detail}</p>
    </div>
  );
}
