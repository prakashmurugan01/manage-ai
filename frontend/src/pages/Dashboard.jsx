import {
  Activity,
  AlertTriangle,
  BellRing,
  Boxes,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  ClipboardList,
  Clock3,
  Code2,
  Download,
  FileArchive,
  FileCheck2,
  FileClock,
  FileText,
  Gauge,
  GitBranch,
  Headphones,
  LifeBuoy,
  MessageSquareWarning,
  Power,
  Rocket,
  Server,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  UploadCloud,
  UserCheck,
  Users,
  Wifi,
  Workflow
} from "lucide-react";
import { motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";

import { listFrom } from "../api/client.js";
import {
  analyticsApi,
  deploymentsApi,
  documentsApi,
  notificationsApi,
  projectsApi,
  tasksApi,
  ticketsApi
} from "../api/services.js";
import Sparkline from "../components/dashboard/Sparkline.jsx";
import StatusBars from "../components/dashboard/StatusBars.jsx";
import Badge from "../components/ui/Badge.jsx";
import Button from "../components/ui/Button.jsx";
import Page from "../components/ui/Page.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { bytes, pct } from "../utils/format.js";
import { ROLES } from "../utils/rbac.js";

const roleSkins = {
  [ROLES.SUPER_ADMIN]: {
    eyebrow: "System Command",
    title: "Super Admin Control Tower",
    subtitle: "System governance, users, audit posture, critical tickets, server health, and platform-wide operations.",
    icon: ShieldCheck,
    accent: "#2dd4bf",
    accent2: "#38bdf8",
    accent3: "#fb7185",
    className: "dashboard-super-admin"
  },
  [ROLES.ADMIN]: {
    eyebrow: "Delivery Operations",
    title: "Admin Mission Control",
    subtitle: "Projects, approvals, deployment stages, ticket routing, file review, and performance visibility.",
    icon: Rocket,
    accent: "#fbbf24",
    accent2: "#2dd4bf",
    accent3: "#60a5fa",
    className: "dashboard-admin"
  },
  [ROLES.DEVELOPER]: {
    eyebrow: "Build Workspace",
    title: "Developer Flow Console",
    subtitle: "Assigned work, day-by-day workflow, blocked items, Git activity, logs, and upload readiness.",
    icon: Code2,
    accent: "#38bdf8",
    accent2: "#34d399",
    accent3: "#fbbf24",
    className: "dashboard-developer"
  },
  [ROLES.CLIENT]: {
    eyebrow: "Client Portal",
    title: "Project Transparency Hub",
    subtitle: "Project progress, deployment readiness, shared documents, support requests, and update history.",
    icon: FileCheck2,
    accent: "#a78bfa",
    accent2: "#2dd4bf",
    accent3: "#fb7185",
    className: "dashboard-client"
  }
};

const openTicketStatuses = new Set(["OPEN", "TRIAGED", "IN_PROGRESS"]);
const stageLabels = {
  development: "Development",
  staging: "Staging",
  production: "Production"
};

const tileMotion = {
  hidden: { opacity: 0, y: 14 },
  show: (index = 0) => ({ opacity: 1, y: 0, transition: { delay: index * 0.045, duration: 0.28 } })
};

function asNumber(value, fallback = 0) {
  const next = Number(value);
  return Number.isFinite(next) ? next : fallback;
}

function ratio(part, total) {
  const safeTotal = asNumber(total);
  if (!safeTotal) return 0;
  return Math.round((asNumber(part) / safeTotal) * 100);
}

function mean(items, key) {
  if (!items.length) return 0;
  return Math.round(items.reduce((total, item) => total + asNumber(item[key]), 0) / items.length);
}

function firstFulfilled(result, fallback) {
  return result.status === "fulfilled" ? result.value : fallback;
}

function responseData(result, fallback = {}) {
  const response = firstFulfilled(result, null);
  return response?.data ?? fallback;
}

function responseList(result) {
  const response = firstFulfilled(result, null);
  return response ? listFrom(response) : [];
}

function formatEnv(value) {
  return stageLabels[value] || String(value || "Unknown").replace("_", " ");
}

function pickProjectUrl(project) {
  return project?.hosted_url || project?.local_url || project?.repository_url || "";
}

function buildFallbackOps(snapshot) {
  const { analytics, performance, projects, tasks, tickets, documents, deployments } = snapshot;
  const totals = analytics?.totals || {};
  const activeProjects = asNumber(totals.active_projects, projects.filter((project) => project.status === "ACTIVE").length);
  const openTasks = asNumber(totals.open_tasks, tasks.filter((task) => task.status !== "DONE").length);
  const blockedTasks = asNumber(totals.blocked_tasks, tasks.filter((task) => task.status === "BLOCKED").length);
  const criticalTickets = tickets.filter((ticket) => ticket.priority === "CRITICAL" && openTicketStatuses.has(ticket.status)).length;
  const pendingDocuments = documents.filter((document) => document.review_status === "PENDING").length;
  const liveDeployments = deployments.filter((deployment) => deployment.is_enabled).length;
  const avgHealth = mean(projects, "health_score") || Math.max(58, 96 - blockedTasks * 9 - criticalTickets * 6);
  const latency = asNumber(performance?.average_latency_ms, 88 + blockedTasks * 12);
  const responseScore = Math.max(52, 100 - Math.round(latency / 18) - asNumber(performance?.error_count) * 5);

  return {
    server_health: {
      status: criticalTickets > 1 ? "DEGRADED" : "HEALTHY",
      uptime_percent: Math.min(99.99, 99.82 - criticalTickets * 0.04),
      response_time_ms: latency,
      cpu_percent: Math.min(96, 38 + openTasks * 2 + blockedTasks * 7),
      memory_percent: Math.min(96, 45 + activeProjects * 4),
      storage_percent: Math.min(92, 40 + pendingDocuments * 3 + asNumber(totals.documents) * 0.8),
      health_score: avgHealth,
      websocket_clients: Math.max(1, asNumber(totals.developers) + asNumber(totals.clients)),
      incidents: criticalTickets + blockedTasks
    },
    network: {
      speed_mbps: Math.max(72, 260 - blockedTasks * 8),
      latency_ms: Math.max(18, Math.round(latency / 3)),
      api_success_rate: Math.max(88, responseScore),
      packet_loss: criticalTickets ? 0.08 : 0.01
    },
    approvals: {
      tasks: asNumber(totals.pending_approvals),
      files: pendingDocuments,
      projects: projects.filter((project) => project.approval_status === "IN_REVIEW").length
    },
    deployment_stages: ["development", "staging", "production"].map((environment) => {
      const scoped = deployments.filter((deployment) => deployment.environment === environment);
      return {
        environment,
        total: scoped.length,
        enabled: scoped.filter((deployment) => deployment.is_enabled).length,
        healthy: scoped.filter((deployment) => deployment.status === "HEALTHY").length,
        latest: scoped[0] || null
      };
    }),
    workload_health: {
      active_projects: activeProjects,
      open_tasks: openTasks,
      blocked_tasks: blockedTasks,
      live_deployments: liveDeployments,
      critical_tickets: criticalTickets
    }
  };
}

function useDashboardSnapshot(user) {
  const [snapshot, setSnapshot] = useState({
    loading: true,
    analytics: null,
    performance: null,
    projects: [],
    tasks: [],
    tickets: [],
    documents: [],
    deployments: [],
    notifications: [],
    error: ""
  });

  useEffect(() => {
    let mounted = true;
    const taskRequest = user?.role === ROLES.DEVELOPER ? tasksApi.my() : tasksApi.list();

    Promise.allSettled([
      analyticsApi.dashboard(),
      analyticsApi.performance(7),
      projectsApi.list(),
      taskRequest,
      ticketsApi.list(),
      documentsApi.list(),
      deploymentsApi.list(),
      notificationsApi.list()
    ])
      .then((results) => {
        if (!mounted) return;
        const next = {
          loading: false,
          analytics: responseData(results[0], {}),
          performance: responseData(results[1], {}),
          projects: responseList(results[2]),
          tasks: responseList(results[3]),
          tickets: responseList(results[4]),
          documents: responseList(results[5]),
          deployments: responseList(results[6]),
          notifications: responseList(results[7]),
          error: ""
        };
        setSnapshot(next);
      })
      .catch((error) => {
        if (!mounted) return;
        setSnapshot((current) => ({ ...current, loading: false, error: error?.message || "Dashboard data failed to load." }));
      });

    return () => {
      mounted = false;
    };
  }, [user?.role]);

  return snapshot;
}

function useDashboardSummary(snapshot) {
  return useMemo(() => {
    const ops = snapshot.analytics?.ops || buildFallbackOps(snapshot);
    const totals = snapshot.analytics?.totals || {};
    const tasksByStatus = snapshot.analytics?.tasks_by_status || {};
    const projectsByStatus = snapshot.analytics?.projects_by_status || {};
    const ticketsByStatus = snapshot.analytics?.tickets_by_status || {};
    const completion = ratio(asNumber(totals.tasks) - asNumber(totals.open_tasks), totals.tasks);
    const projectHealth = mean(snapshot.projects, "health_score") || asNumber(ops.server_health?.health_score, 94);
    const activeProject = snapshot.projects.find((project) => project.status === "ACTIVE") || snapshot.projects[0] || null;
    const pendingFiles = snapshot.documents.filter((document) => document.review_status === "PENDING");
    const approvedFiles = snapshot.documents.filter((document) => document.review_status === "APPROVED");
    const openTickets = snapshot.tickets.filter((ticket) => openTicketStatuses.has(ticket.status));
    const criticalTickets = openTickets.filter((ticket) => ticket.priority === "CRITICAL");
    const blockedTasks = snapshot.tasks.filter((task) => task.status === "BLOCKED");
    const reviewTasks = snapshot.tasks.filter((task) => task.status === "REVIEW" || task.approval_status === "PENDING");
    const developerTasks = snapshot.tasks.filter((task) => task.assignee_detail?.id === snapshot.userId || task.assignee === snapshot.userId);
    const liveDeployments = snapshot.deployments.filter((deployment) => deployment.is_enabled);
    const recentUpdates = [
      ...snapshot.notifications.slice(0, 4).map((item) => ({
        id: `notification-${item.id}`,
        title: item.title,
        detail: item.message,
        time: item.created_at,
        type: item.type || "INFO"
      })),
      ...(snapshot.analytics?.recent_activity || []).slice(0, 4).map((item, index) => ({
        id: `activity-${item.entity_id || index}`,
        title: `${item.action} ${item.entity_type}`,
        detail: item.actor__email || "System",
        time: item.created_at,
        type: item.entity_type || "EVENT"
      }))
    ].slice(0, 6);

    return {
      ops,
      totals,
      tasksByStatus,
      projectsByStatus,
      ticketsByStatus,
      completion,
      projectHealth,
      activeProject,
      pendingFiles,
      approvedFiles,
      openTickets,
      criticalTickets,
      blockedTasks,
      reviewTasks,
      developerTasks,
      liveDeployments,
      recentUpdates
    };
  }, [snapshot]);
}

function DashboardFrame({ skin, children }) {
  return (
    <div
      className={`enterprise-dashboard ${skin.className} space-y-5`}
      style={{ "--role-accent": skin.accent, "--role-accent-2": skin.accent2, "--role-accent-3": skin.accent3 }}
    >
      {children}
    </div>
  );
}

function CommandHero({ skin, user, summary, events = [], actions = [] }) {
  const Icon = skin.icon;
  const serverStatus = summary.ops.server_health?.status || "HEALTHY";

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="role-command-hero relative overflow-hidden rounded-lg border border-white/10 p-5"
    >
      <div className="absolute inset-0 opacity-90" />
      <div className="relative grid gap-5 xl:grid-cols-[1fr_360px] xl:items-center">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.14em] text-slate-200">
            <Icon size={14} />
            {skin.eyebrow}
          </div>
          <h1 className="mt-4 max-w-4xl text-3xl font-semibold text-white sm:text-4xl">{skin.title}</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">{skin.subtitle}</p>
          <div className="mt-5 flex flex-wrap gap-2">
            {actions.map((action) => {
              const ActionIcon = action.icon;
              return (
                <Link key={action.label} to={action.to}>
                  <Button variant={action.primary ? "primary" : "secondary"}>
                    <ActionIcon size={16} />
                    {action.label}
                  </Button>
                </Link>
              );
            })}
          </div>
        </div>
        <div className="rounded-lg border border-white/10 bg-black/20 p-4 backdrop-blur">
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Live Operations</p>
              <p className="mt-2 truncate text-sm font-medium text-white">{user?.full_name || user?.email}</p>
            </div>
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1 text-xs font-medium text-emerald-200">
              <span className="h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_18px_rgba(52,211,153,0.75)]" />
              {serverStatus}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <MiniPulse label="Projects" value={summary.totals.projects || 0} />
            <MiniPulse label="Open Tasks" value={summary.totals.open_tasks || 0} />
            <MiniPulse label="Alerts" value={events.length + summary.criticalTickets.length} danger={summary.criticalTickets.length > 0} />
          </div>
        </div>
      </div>
    </motion.section>
  );
}

function MiniPulse({ label, value, danger = false }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.055] p-3 text-center">
      <p className={`text-xl font-semibold ${danger ? "text-rose-200" : "text-white"}`}>{value}</p>
      <p className="mt-1 text-[11px] uppercase tracking-[0.12em] text-slate-500">{label}</p>
    </div>
  );
}

function MetricTile({ icon: Icon, label, value, detail, tone = "text-white", index = 0 }) {
  return (
    <motion.div
      variants={tileMotion}
      initial="hidden"
      animate="show"
      custom={index}
      whileHover={{ y: -4, scale: 1.01 }}
      className="panel relative overflow-hidden p-4"
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[color:var(--role-accent)] to-transparent" />
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">{label}</p>
          <p className={`mt-3 text-3xl font-semibold ${tone}`}>{value}</p>
          <p className="mt-2 text-sm text-slate-400">{detail}</p>
        </div>
        <span className="grid h-10 w-10 place-items-center rounded-lg border border-white/10 bg-white/10 text-[color:var(--role-accent)]">
          <Icon size={20} />
        </span>
      </div>
    </motion.div>
  );
}

function SectionPanel({ title, subtitle, icon: Icon, action, children, className = "" }) {
  return (
    <section className={`panel overflow-hidden p-4 ${className}`}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {Icon && <Icon size={17} className="text-[color:var(--role-accent)]" />}
            <h2 className="text-sm font-semibold text-white">{title}</h2>
          </div>
          {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function ProgressLine({ label, value, detail, color = "var(--role-accent)" }) {
  const safeValue = Math.max(0, Math.min(100, asNumber(value)));
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3 text-sm">
        <span className="font-medium text-slate-200">{label}</span>
        <span className="text-xs text-slate-500">{detail || `${safeValue}%`}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/8">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${safeValue}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ background: color }}
        />
      </div>
    </div>
  );
}

function HealthDial({ label, value, icon: Icon, color = "var(--role-accent)" }) {
  const safeValue = Math.max(0, Math.min(100, Math.round(asNumber(value))));
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (safeValue / 100) * circumference;

  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
      <div className="relative mx-auto h-28 w-28">
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle cx="50" cy="50" r={radius} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" />
          <motion.circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 0.85, ease: "easeOut" }}
          />
        </svg>
        <div className="absolute inset-0 grid place-items-center text-center">
          {Icon ? <Icon size={18} className="mx-auto mb-1 text-slate-400" /> : null}
          <span className="text-xl font-semibold text-white">{safeValue}%</span>
        </div>
      </div>
      <p className="mt-3 text-center text-xs uppercase tracking-[0.14em] text-slate-400">{label}</p>
    </div>
  );
}

function ServerMatrix({ summary }) {
  const server = summary.ops.server_health || {};
  const network = summary.ops.network || {};

  return (
    <SectionPanel title="Server And Network Fabric" subtitle="Uptime, latency, storage, CPU, memory, sockets, and response posture." icon={Server}>
      <div className="grid gap-3 sm:grid-cols-2">
        <ProgressLine label="CPU Load" value={server.cpu_percent} detail={`${Math.round(asNumber(server.cpu_percent))}%`} color="#38bdf8" />
        <ProgressLine label="Memory" value={server.memory_percent} detail={`${Math.round(asNumber(server.memory_percent))}%`} color="#34d399" />
        <ProgressLine label="Storage" value={server.storage_percent} detail={`${Math.round(asNumber(server.storage_percent))}%`} color="#fbbf24" />
        <ProgressLine label="API Success" value={network.api_success_rate} detail={`${Math.round(asNumber(network.api_success_rate))}%`} color="#fb7185" />
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-4">
        <MiniPulse label="Uptime" value={`${asNumber(server.uptime_percent, 99.9).toFixed(2)}%`} />
        <MiniPulse label="Latency" value={`${Math.round(asNumber(network.latency_ms))}ms`} />
        <MiniPulse label="Network" value={`${Math.round(asNumber(network.speed_mbps))} Mbps`} />
        <MiniPulse label="Sockets" value={server.websocket_clients || 0} />
      </div>
    </SectionPanel>
  );
}

function DeploymentBoard({ deployments, stages = [] }) {
  const fallbackStages = ["development", "staging", "production"].map((environment) => ({
    environment,
    total: deployments.filter((deployment) => deployment.environment === environment).length,
    enabled: deployments.filter((deployment) => deployment.environment === environment && deployment.is_enabled).length,
    healthy: deployments.filter((deployment) => deployment.environment === environment && deployment.status === "HEALTHY").length,
    latest: deployments.find((deployment) => deployment.environment === environment) || null
  }));
  const items = stages.length ? stages : fallbackStages;

  return (
    <SectionPanel title="Deployment Stage Control" subtitle="Development, staging, and production readiness across connected projects." icon={Power}>
      <div className="grid gap-3 md:grid-cols-3">
        {items.map((stage) => {
          const enabled = asNumber(stage.enabled);
          const total = asNumber(stage.total);
          const percentage = total ? ratio(enabled, total) : 0;
          return (
            <div key={stage.environment} className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-white">{formatEnv(stage.environment)}</p>
                  <p className="mt-1 text-xs text-slate-500">{enabled}/{total || deployments.length || 0} enabled</p>
                </div>
                <span className={`relative h-7 w-12 rounded-full border ${enabled ? "border-emerald-300/30 bg-emerald-300/20" : "border-white/10 bg-white/10"}`}>
                  <span className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition ${enabled ? "left-6" : "left-1"}`} />
                </span>
              </div>
              <div className="mt-4">
                <ProgressLine label="Stage coverage" value={percentage} detail={`${percentage}%`} color="var(--role-accent-2)" />
              </div>
              <p className="mt-3 text-xs text-slate-500">
                {stage.latest?.project_name || "No project attached"} {stage.latest?.status ? `- ${stage.latest.status}` : ""}
              </p>
            </div>
          );
        })}
      </div>
    </SectionPanel>
  );
}

function ApprovalQueue({ summary }) {
  const approvals = summary.ops.approvals || {};
  const rows = [
    { label: "Task approvals", value: approvals.tasks || summary.reviewTasks.length, icon: ClipboardCheck, to: "/tasks" },
    { label: "File reviews", value: approvals.files || summary.pendingFiles.length, icon: FileClock, to: "/files" },
    { label: "Project reviews", value: approvals.projects || 0, icon: Boxes, to: "/projects" }
  ];

  return (
    <SectionPanel title="Approval Command Queue" subtitle="Admin-controlled gates for work completion, server uploads, and project signoff." icon={UserCheck}>
      <div className="space-y-3">
        {rows.map((row) => {
          const Icon = row.icon;
          return (
            <Link key={row.label} to={row.to} className="group flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.035] p-3 transition hover:border-[color:var(--role-accent)]/50 hover:bg-white/[0.075]">
              <span className="inline-flex items-center gap-3 text-sm font-medium text-slate-200">
                <span className="grid h-9 w-9 place-items-center rounded-lg bg-white/10 text-[color:var(--role-accent)]"><Icon size={16} /></span>
                {row.label}
              </span>
              <span className="inline-flex items-center gap-2 text-sm text-white">
                {row.value}
                <ChevronRight size={15} className="text-slate-500 transition group-hover:text-white" />
              </span>
            </Link>
          );
        })}
      </div>
    </SectionPanel>
  );
}

function EscalationPanel({ tickets = [] }) {
  const items = tickets.slice(0, 4);

  return (
    <SectionPanel title="Critical Client Requests" subtitle="Escalations and support tickets that need the fastest operational response." icon={LifeBuoy}>
      <div className="space-y-3">
        {items.map((ticket) => (
          <Link key={ticket.id} to="/tickets" className="block rounded-lg border border-rose-300/20 bg-rose-300/10 p-3 transition hover:bg-rose-300/15">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-white">{ticket.title}</p>
                <p className="mt-1 truncate text-xs text-rose-100/75">{ticket.project_name || "Project"} - {ticket.status}</p>
              </div>
              <Badge value={ticket.priority} />
            </div>
          </Link>
        ))}
        {!items.length && <p className="rounded-lg border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-500">No critical escalations are open.</p>}
      </div>
    </SectionPanel>
  );
}

function ProjectCommandList({ projects = [], adminView = false }) {
  const items = projects.slice(0, 5);

  return (
    <SectionPanel
      title={adminView ? "Project Command Stack" : "Project Portfolio"}
      subtitle={adminView ? "Delivery progress, project health, client visibility, and connected resources." : "Visible projects and live delivery status."}
      icon={Boxes}
      action={<Link to="/projects" className="text-xs font-medium text-[color:var(--role-accent)]">Open all</Link>}
    >
      <div className="space-y-3">
        {items.map((project) => (
          <Link key={project.id} to={`/projects/${project.id}`} className="block rounded-lg border border-white/10 bg-white/[0.035] p-3 transition hover:border-[color:var(--role-accent)]/40 hover:bg-white/[0.075]">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{project.name}</p>
                <p className="mt-1 truncate text-xs text-slate-500">{project.client_detail?.full_name || project.client_detail?.email || "Internal project"}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge value={project.status} />
                <Badge value={project.connection_type} />
              </div>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto] sm:items-center">
              <ProgressLine label="Progress" value={project.progress} detail={pct(project.progress)} color="var(--role-accent)" />
              <span className="text-xs text-slate-500">{project.open_task_count || 0} open tasks</span>
            </div>
          </Link>
        ))}
        {!items.length && <p className="rounded-lg border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-500">No projects in this view.</p>}
      </div>
    </SectionPanel>
  );
}

function TeamPerformance({ items = [] }) {
  return (
    <SectionPanel title="Team Performance Grid" subtitle="Developer throughput, blocked work, and pending approval pressure." icon={Users}>
      <div className="grid gap-3 md:grid-cols-2">
        {items.slice(0, 8).map((item) => {
          const name = `${item.assignee__first_name || ""} ${item.assignee__last_name || ""}`.trim() || item.assignee__email;
          const completion = ratio(item.completed, item.total);
          return (
            <div key={item.assignee__id} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-white">{name}</p>
                  <p className="mt-1 font-mono text-xs text-slate-500">{item.assignee__secret_id || item.assignee__role_title || "Team member"}</p>
                </div>
                {item.blocked ? <AlertTriangle size={16} className="text-amber-200" /> : <CheckCircle2 size={16} className="text-emerald-300" />}
              </div>
              <div className="mt-3">
                <ProgressLine label="Done" value={completion} detail={`${item.completed}/${item.total}`} color="var(--role-accent-2)" />
              </div>
              <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                <span>{item.pending_approval} approvals</span>
                <span>{item.blocked} blocked</span>
              </div>
            </div>
          );
        })}
        {!items.length && <p className="rounded-lg border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-500">No team activity yet.</p>}
      </div>
    </SectionPanel>
  );
}

function ActivityTimeline({ items = [], title = "Activity Timeline", subtitle = "Realtime and audited operational events." }) {
  return (
    <SectionPanel title={title} subtitle={subtitle} icon={Activity}>
      <div className="space-y-3">
        {items.map((item, index) => (
          <motion.div
            key={item.id || index}
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.04 }}
            className="relative rounded-lg border border-white/10 bg-white/[0.035] p-3"
          >
            <span className="absolute -left-px top-4 h-8 w-px bg-[color:var(--role-accent)]" />
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-white">{item.title}</p>
                <p className="mt-1 truncate text-xs text-slate-500">{item.detail}</p>
              </div>
              <Badge value={item.type || "Event"} />
            </div>
            {item.time && <p className="mt-2 text-[11px] uppercase tracking-[0.12em] text-slate-500">{new Date(item.time).toLocaleString()}</p>}
          </motion.div>
        ))}
        {!items.length && <p className="rounded-lg border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-500">No activity yet.</p>}
      </div>
    </SectionPanel>
  );
}

function DeveloperWorkflow({ tasks = [] }) {
  const days = [1, 2, 3].map((day) => {
    const scoped = tasks.filter((task) => asNumber(task.workflow_day, 1) === day);
    return {
      day,
      total: scoped.length,
      done: scoped.filter((task) => task.status === "DONE").length,
      active: scoped.filter((task) => task.status === "IN_PROGRESS").length,
      blocked: scoped.filter((task) => task.status === "BLOCKED").length,
      tasks: scoped.slice(0, 2)
    };
  });

  return (
    <SectionPanel title="Day 1 / Day 2 / Day 3 Workflow" subtitle="Structured execution loop for assigned project work." icon={Workflow}>
      <div className="grid gap-3 md:grid-cols-3">
        {days.map((item) => (
          <div key={item.day} className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-white">Day {item.day}</p>
              <Badge value={`${item.done}/${item.total || 0}`} />
            </div>
            <div className="mt-4">
              <ProgressLine label="Completion" value={ratio(item.done, item.total)} detail={`${ratio(item.done, item.total)}%`} color="var(--role-accent)" />
            </div>
            <div className="mt-3 space-y-2">
              {item.tasks.map((task) => (
                <Link key={task.id} to="/tasks" className="block rounded-lg bg-white/[0.04] px-3 py-2 text-xs text-slate-300">
                  <span className="block truncate font-medium text-white">{task.title}</span>
                  <span className="mt-1 block text-slate-500">{task.status}</span>
                </Link>
              ))}
              {!item.tasks.length && <p className="text-xs text-slate-500">No work assigned.</p>}
            </div>
          </div>
        ))}
      </div>
    </SectionPanel>
  );
}

function DeveloperFocusList({ tasks = [] }) {
  const items = tasks.filter((task) => task.status !== "DONE").slice(0, 5);

  return (
    <SectionPanel title="Assigned Work Queue" subtitle="Priority tasks, blockers, review states, and completion updates." icon={ClipboardList}>
      <div className="space-y-3">
        {items.map((task) => (
          <Link key={task.id} to="/tasks" className="block rounded-lg border border-white/10 bg-white/[0.035] p-3 transition hover:bg-white/[0.075]">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-white">{task.title}</p>
                <p className="mt-1 truncate text-xs text-slate-500">{task.project_name} - Day {task.workflow_day || 1}</p>
              </div>
              <div className="flex flex-wrap justify-end gap-2">
                <Badge value={task.status} />
                <Badge value={task.priority} />
              </div>
            </div>
            {task.delay_reason && (
              <p className="mt-2 inline-flex items-center gap-2 rounded-lg bg-amber-300/10 px-2 py-1 text-xs text-amber-100">
                <MessageSquareWarning size={13} />
                {task.delay_reason}
              </p>
            )}
          </Link>
        ))}
        {!items.length && <p className="rounded-lg border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-500">No open assigned tasks.</p>}
      </div>
    </SectionPanel>
  );
}

function GitOpsPanel({ projects = [] }) {
  const connected = projects.filter((project) => project.connection_type === "GITHUB" || project.repository_url);

  return (
    <SectionPanel title="Git And Redeploy Track" subtitle="Repository, commit, branch, and push visibility for connected projects." icon={GitBranch}>
      <div className="space-y-3">
        {connected.slice(0, 4).map((project) => (
          <Link key={project.id} to={`/projects/${project.id}`} className="block rounded-lg border border-white/10 bg-white/[0.035] p-3 transition hover:bg-white/[0.075]">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-white">{project.name}</p>
                <p className="mt-1 truncate font-mono text-xs text-slate-500">{project.github_owner && project.github_repo ? `${project.github_owner}/${project.github_repo}` : project.repository_url || "Repository pending"}</p>
              </div>
              <Badge value={project.selected_branch || project.github_default_branch || "main"} />
            </div>
            <p className="mt-2 truncate text-xs text-slate-400">{project.last_commit_message || "No commit synced yet."}</p>
          </Link>
        ))}
        {!connected.length && <p className="rounded-lg border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-500">No GitHub projects are connected yet.</p>}
      </div>
    </SectionPanel>
  );
}

function FileOpsPanel({ files = [], developerMode = false }) {
  const items = files.slice(0, 5);

  return (
    <SectionPanel
      title={developerMode ? "Upload And Approval Status" : "Project File Review"}
      subtitle={developerMode ? "Server upload state and admin review feedback." : "Project ZIPs, documents, client resources, and review decisions."}
      icon={developerMode ? UploadCloud : FileArchive}
      action={<Link to="/files" className="text-xs font-medium text-[color:var(--role-accent)]">Files</Link>}
    >
      <div className="space-y-3">
        {items.map((file) => (
          <Link key={file.id} to="/files" className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.035] p-3 transition hover:bg-white/[0.075]">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-white">{file.title}</p>
              <p className="mt-1 truncate text-xs text-slate-500">{file.project_name} - {bytes(file.file_size)}</p>
            </div>
            <Badge value={file.review_status} />
          </Link>
        ))}
        {!items.length && <p className="rounded-lg border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-500">No project files in this view.</p>}
      </div>
    </SectionPanel>
  );
}

function ClientProjectCards({ projects = [], deployments = [] }) {
  const items = projects.slice(0, 3);

  return (
    <SectionPanel title="Live Project Status" subtitle="Progress, production readiness, and visible project resources." icon={TrendingUp}>
      <div className="grid gap-3 lg:grid-cols-3">
        {items.map((project) => {
          const deployment = deployments.find((item) => item.project === project.id);
          const url = pickProjectUrl(project);
          return (
            <article key={project.id} className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">{project.name}</p>
                  <p className="mt-1 text-xs text-slate-500">{project.status}</p>
                </div>
                <Badge value={deployment?.is_enabled ? "PRODUCTION ON" : "NOT LIVE"} />
              </div>
              <div className="mt-4">
                <ProgressLine label="Progress" value={project.progress} detail={pct(project.progress)} color="var(--role-accent-2)" />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link to={`/projects/${project.id}`}>
                  <Button variant="secondary"><Boxes size={16} />Details</Button>
                </Link>
                {url && (
                  <a href={url} target="_blank" rel="noreferrer">
                    <Button variant="ghost"><Rocket size={16} />Live</Button>
                  </a>
                )}
              </div>
            </article>
          );
        })}
        {!items.length && <p className="rounded-lg border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-500">No projects are shared with this account.</p>}
      </div>
    </SectionPanel>
  );
}

function SuperAdminDashboard({ user, snapshot, summary, events }) {
  const metrics = [
    { label: "Projects", value: summary.totals.projects || 0, detail: `${summary.totals.active_projects || 0} active`, icon: Boxes },
    { label: "Users", value: (summary.totals.developers || 0) + (summary.totals.clients || 0), detail: `${summary.totals.developers || 0} devs / ${summary.totals.clients || 0} clients`, icon: Users },
    { label: "System Health", value: `${summary.projectHealth}%`, detail: `${summary.ops.server_health?.status || "HEALTHY"} platform`, icon: Gauge, tone: "text-emerald-200" },
    { label: "Critical Alerts", value: summary.criticalTickets.length + summary.blockedTasks.length, detail: `${summary.blockedTasks.length} blocked tasks`, icon: AlertTriangle, tone: summary.criticalTickets.length ? "text-rose-200" : "text-emerald-200" }
  ];

  return (
    <DashboardFrame skin={roleSkins[ROLES.SUPER_ADMIN]}>
      <CommandHero
        skin={roleSkins[ROLES.SUPER_ADMIN]}
        user={user}
        summary={summary}
        events={events}
        actions={[
          { label: "Users", to: "/users", icon: Users, primary: true },
          { label: "Audit Logs", to: "/logs", icon: ShieldCheck },
          { label: "Monitoring", to: "/monitoring", icon: Gauge },
          { label: "Tickets", to: "/tickets", icon: LifeBuoy }
        ]}
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric, index) => <MetricTile key={metric.label} {...metric} index={index} />)}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <ServerMatrix summary={summary} />
        <EscalationPanel tickets={summary.criticalTickets} />
      </div>
      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <ApprovalQueue summary={summary} />
        <DeploymentBoard deployments={snapshot.deployments} stages={summary.ops.deployment_stages} />
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <TeamPerformance items={snapshot.analytics?.team_performance || []} />
        <ActivityTimeline items={summary.recentUpdates} title="Audit And Notification Stream" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <StatusBars title="Projects" data={summary.projectsByStatus} />
        <StatusBars title="Tasks" data={summary.tasksByStatus} />
        <StatusBars title="Tickets" data={summary.ticketsByStatus} />
      </div>
    </DashboardFrame>
  );
}

function AdminDashboard({ user, snapshot, summary, events }) {
  const deploymentCoverage = ratio(summary.liveDeployments.length, Math.max(snapshot.deployments.length, snapshot.projects.length));
  const metrics = [
    { label: "Active Projects", value: summary.totals.active_projects || 0, detail: `${summary.totals.projects || 0} total`, icon: Boxes },
    { label: "Progress", value: `${summary.completion}%`, detail: "Task completion", icon: TrendingUp, tone: "text-emerald-200" },
    { label: "Approvals", value: summary.reviewTasks.length + summary.pendingFiles.length, detail: "Tasks and file uploads", icon: UserCheck, tone: summary.pendingFiles.length ? "text-amber-200" : "text-emerald-200" },
    { label: "Deployment ON", value: `${deploymentCoverage}%`, detail: `${summary.liveDeployments.length} active controls`, icon: Power }
  ];

  return (
    <DashboardFrame skin={roleSkins[ROLES.ADMIN]}>
      <CommandHero
        skin={roleSkins[ROLES.ADMIN]}
        user={user}
        summary={summary}
        events={events}
        actions={[
          { label: "New Project", to: "/projects", icon: Boxes, primary: true },
          { label: "Assign Tasks", to: "/tasks", icon: ClipboardList },
          { label: "Review Files", to: "/files", icon: FileArchive },
          { label: "Tickets", to: "/tickets", icon: LifeBuoy }
        ]}
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric, index) => <MetricTile key={metric.label} {...metric} index={index} />)}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <ProjectCommandList projects={snapshot.projects} adminView />
        <ApprovalQueue summary={summary} />
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <DeploymentBoard deployments={snapshot.deployments} stages={summary.ops.deployment_stages} />
        <ServerMatrix summary={summary} />
      </div>
      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <FileOpsPanel files={snapshot.documents} />
        <ActivityTimeline items={summary.recentUpdates} title="Delivery Timeline" subtitle="Project updates, ticket movement, and admin approvals." />
      </div>
      <div className="panel p-4">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Completion Velocity</h2>
            <p className="mt-1 text-xs text-slate-500">Completed work over the last 14 days.</p>
          </div>
          <Badge value="Live" />
        </div>
        <Sparkline data={snapshot.analytics?.velocity || []} />
      </div>
    </DashboardFrame>
  );
}

function DeveloperDashboard({ user, snapshot, summary, events }) {
  const activeTasks = summary.developerTasks.length ? summary.developerTasks : snapshot.tasks;
  const done = activeTasks.filter((task) => task.status === "DONE").length;
  const metrics = [
    { label: "Assigned Work", value: activeTasks.filter((task) => task.status !== "DONE").length, detail: `${done} completed`, icon: ClipboardList },
    { label: "In Review", value: activeTasks.filter((task) => task.status === "REVIEW" || task.approval_status === "PENDING").length, detail: "Waiting for admin", icon: Clock3, tone: "text-amber-200" },
    { label: "Blocked", value: activeTasks.filter((task) => task.status === "BLOCKED").length, detail: "Needs escalation", icon: AlertTriangle, tone: activeTasks.some((task) => task.status === "BLOCKED") ? "text-rose-200" : "text-emerald-200" },
    { label: "Connected Projects", value: summary.totals.connected_projects || 0, detail: `${summary.totals.github_projects || 0} GitHub`, icon: GitBranch }
  ];

  return (
    <DashboardFrame skin={roleSkins[ROLES.DEVELOPER]}>
      <CommandHero
        skin={roleSkins[ROLES.DEVELOPER]}
        user={user}
        summary={summary}
        events={events}
        actions={[
          { label: "My Tasks", to: "/tasks", icon: ClipboardCheck, primary: true },
          { label: "Upload Files", to: "/files", icon: UploadCloud },
          { label: "Bugs", to: "/tickets", icon: LifeBuoy },
          { label: "Projects", to: "/projects", icon: Boxes }
        ]}
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric, index) => <MetricTile key={metric.label} {...metric} index={index} />)}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <DeveloperWorkflow tasks={activeTasks} />
        <DeveloperFocusList tasks={activeTasks} />
      </div>
      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <GitOpsPanel projects={snapshot.projects} />
        <FileOpsPanel files={snapshot.documents} developerMode />
      </div>
      <div className="grid gap-4 lg:grid-cols-4">
        <HealthDial label="Delivery" value={summary.completion} icon={TrendingUp} color="#38bdf8" />
        <HealthDial label="Server" value={summary.ops.server_health?.health_score || summary.projectHealth} icon={Server} color="#34d399" />
        <HealthDial label="Network" value={summary.ops.network?.api_success_rate || 96} icon={Wifi} color="#fbbf24" />
        <HealthDial label="Debug Lane" value={Math.max(0, 100 - summary.blockedTasks.length * 16)} icon={BrainCircuit} color="#fb7185" />
      </div>
      <ActivityTimeline items={summary.recentUpdates} title="Logs And Update History" subtitle="Realtime notifications, Git pushes, task movement, and debug events." />
    </DashboardFrame>
  );
}

function ClientDashboard({ user, snapshot, summary, events }) {
  const metrics = [
    { label: "Project Progress", value: `${summary.completion}%`, detail: "Completed work", icon: TrendingUp, tone: "text-emerald-200" },
    { label: "Live Projects", value: summary.liveDeployments.length, detail: "Production-ready controls", icon: Rocket },
    { label: "Open Tickets", value: summary.openTickets.length, detail: "Support requests", icon: Headphones, tone: summary.openTickets.length ? "text-amber-200" : "text-emerald-200" },
    { label: "Shared Files", value: summary.approvedFiles.length, detail: "Approved resources", icon: Download }
  ];

  return (
    <DashboardFrame skin={roleSkins[ROLES.CLIENT]}>
      <CommandHero
        skin={roleSkins[ROLES.CLIENT]}
        user={user}
        summary={summary}
        events={events}
        actions={[
          { label: "Projects", to: "/projects", icon: Boxes, primary: true },
          { label: "Raise Ticket", to: "/tickets", icon: LifeBuoy },
          { label: "Documents", to: "/files", icon: FileText },
          { label: "Updates", to: "/notifications", icon: BellRing }
        ]}
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric, index) => <MetricTile key={metric.label} {...metric} index={index} />)}
      </div>
      <ClientProjectCards projects={snapshot.projects} deployments={snapshot.deployments} />
      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <FileOpsPanel files={summary.approvedFiles} />
        <ActivityTimeline items={summary.recentUpdates} title="Update History" subtitle="Shared delivery changes, approvals, documents, and responses." />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <StatusBars title="Projects" data={summary.projectsByStatus} />
        <StatusBars title="Tickets" data={summary.ticketsByStatus} />
        <SectionPanel title="Support Access" subtitle="Create a ticket with screenshots and track every response." icon={LifeBuoy}>
          <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
            <p className="text-sm text-slate-300">Support requests are routed to the assigned admin and developer team with screenshot evidence and status history.</p>
            <Link to="/tickets" className="mt-4 inline-flex">
              <Button><LifeBuoy size={16} />Open Tickets</Button>
            </Link>
          </div>
        </SectionPanel>
      </div>
    </DashboardFrame>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const outlet = useOutletContext();
  const snapshot = useDashboardSnapshot(user);
  const summary = useDashboardSummary({ ...snapshot, userId: user?.id });
  const events = outlet?.events || [];

  if (snapshot.loading) {
    return (
      <Page title="" subtitle="">
        <div className="grid min-h-[55vh] place-items-center">
          <div className="panel w-full max-w-md p-6 text-center">
            <Sparkles className="mx-auto text-[color:var(--accent)]" size={28} />
            <p className="mt-4 text-sm font-medium text-white">Loading operations dashboard</p>
            <p className="mt-2 text-sm text-slate-500">Preparing projects, tickets, files, servers, and realtime signals.</p>
          </div>
        </div>
      </Page>
    );
  }

  return (
    <Page title="" subtitle="">
      {snapshot.error && (
        <div className="mb-4 rounded-lg border border-amber-300/20 bg-amber-300/10 p-3 text-sm text-amber-100">
          {snapshot.error}
        </div>
      )}
      {user?.role === ROLES.SUPER_ADMIN && <SuperAdminDashboard user={user} snapshot={snapshot} summary={summary} events={events} />}
      {user?.role === ROLES.ADMIN && <AdminDashboard user={user} snapshot={snapshot} summary={summary} events={events} />}
      {user?.role === ROLES.DEVELOPER && <DeveloperDashboard user={user} snapshot={snapshot} summary={summary} events={events} />}
      {(!user?.role || user?.role === ROLES.CLIENT) && <ClientDashboard user={user} snapshot={snapshot} summary={summary} events={events} />}
    </Page>
  );
}
