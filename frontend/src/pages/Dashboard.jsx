import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bell,
  Boxes,
  Cable,
  CheckCircle2,
  Clock,
  Cloud,
  Database,
  ExternalLink,
  FileStack,
  Gauge,
  KeyRound,
  LifeBuoy,
  Loader2,
  Network,
  RefreshCcw,
  Server,
  ShieldCheck,
  Wifi,
  WifiOff
} from "lucide-react";
import { Link } from "react-router-dom";

import { api, apiErrorMessage } from "../api/client.js";

const cardMotion = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.32, ease: "easeInOut" } }
};

export default function Dashboard() {
  const [selectedQuery, setSelectedQuery] = useState(null);
  const engine = useQuery({
    queryKey: ["management-engine-dashboard"],
    queryFn: () => api.get("/management-engine/dashboard/").then((res) => res.data.data),
    refetchInterval: 5000
  });

  const data = engine.data || {};
  const summary = data.summary || {};
  const hosting = data.hosting || [];
  const projects = data.projects || [];
  const tickets = data.tickets || [];
  const servers = data.servers || [];
  const apiQueries = data.api_queries || [];
  const transfers = data.file_transfers || [];
  const notifications = data.notifications || [];
  const expiryAlerts = data.expiry_alerts || [];

  const health = useMemo(() => {
    const critical = (summary.hosting_down || 0) + (summary.servers_down || 0) + expiryAlerts.filter((item) => item.level === "critical" || item.level === "expired").length;
    if (critical > 0) return { label: "Action Required", tone: "rose", icon: AlertTriangle };
    if ((summary.tickets_open || 0) > 0) return { label: "Operational", tone: "amber", icon: Clock };
    return { label: "Stable", tone: "emerald", icon: CheckCircle2 };
  }, [expiryAlerts, summary.hosting_down, summary.servers_down, summary.tickets_open]);

  if (engine.isLoading) {
    return <DashboardSkeleton />;
  }

  if (engine.error) {
    return (
      <EngineCard className="border-rose-400/35 bg-rose-500/10">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-1 text-rose-300" />
          <div>
            <h1 className="text-xl font-semibold text-[color:var(--text-strong)]">Management Engine unavailable</h1>
            <p className="mt-1 text-sm text-[color:var(--text-muted)]">{apiErrorMessage(engine.error)}</p>
          </div>
        </div>
      </EngineCard>
    );
  }

  return (
    <motion.div variants={cardMotion} initial="initial" animate="animate" className="space-y-6 text-[color:var(--text)]">
      <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm font-semibold text-[color:var(--primary)]">Enterprise Management Engine</p>
          <h1 className="mt-1 text-3xl font-semibold text-[color:var(--text-strong)]">Central Control Dashboard</h1>
          <p className="mt-2 max-w-3xl text-sm text-[color:var(--text-muted)]">Hosting, projects, tickets, API intake, remote connections, file transfer, and live server health in one operational view.</p>
        </div>
        <div className="flex items-center gap-2 rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] px-4 py-3">
          <health.icon className={toneText(health.tone)} size={18} />
          <div>
            <p className="text-xs text-[color:var(--text-muted)]">Engine Status</p>
            <p className="text-sm font-semibold text-[color:var(--text-strong)]">{health.label}</p>
          </div>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Metric title="Hosting Links" value={summary.hosting_total || 0} detail={`${summary.hosting_down || 0} down, ${summary.hosting_expiring || 0} expiring`} icon={Cloud} tone="cyan" to="/hosting" />
        <Metric title="Projects" value={summary.projects_total || 0} detail={`${summary.projects_active || 0} active projects`} icon={Boxes} tone="emerald" to="/projects" />
        <Metric title="Tickets" value={summary.tickets_open || 0} detail="Open courier queue" icon={LifeBuoy} tone="amber" to="/tickets" />
        <Metric title="Server Risk" value={summary.servers_down || 0} detail={`${servers.length} monitored servers`} icon={Server} tone={summary.servers_down ? "rose" : "emerald"} to="/server-monitor" />
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,.65fr)]">
        <div className="space-y-5">
          <EngineCard>
            <SectionHeader icon={Cloud} title="Hosting Control" action="/hosting" />
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {hosting.slice(0, 6).map((item) => (
                <Link key={item.id} to={`/hosting/${providerRoute(item.provider)}`} className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4 transition hover:border-[color:var(--primary)]">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-[color:var(--text-strong)]">{item.name}</p>
                      <p className="mt-1 truncate text-xs text-[color:var(--text-muted)]">{item.domain || item.live_url || "No live URL"}</p>
                    </div>
                    <StatusBadge value={item.status === "offline" ? "Down" : "Active"} tone={item.status === "offline" ? "rose" : "emerald"} />
                  </div>
                  <div className="mt-4 grid grid-cols-3 gap-2">
                    <Mini label="Provider" value={pretty(item.provider)} />
                    <Mini label="Uptime" value={`${Math.round(item.uptime || 0)}%`} />
                    <Mini label="Expiry" value={item.days_remaining == null ? "n/a" : `${item.days_remaining}d`} />
                  </div>
                </Link>
              ))}
            </div>
          </EngineCard>

          <div className="grid gap-5 xl:grid-cols-2">
            <EngineCard>
              <SectionHeader icon={Boxes} title="Project Operations" action="/projects" />
              <Rows
                items={projects.slice(0, 6)}
                empty="No projects found"
                render={(item) => (
                  <Row key={item.id} title={item.name} detail={`${item.connection_status || "DISCONNECTED"} · ${item.progress || 0}% progress`} badge={item.status} tone={item.status === "ACTIVE" ? "emerald" : item.connection_status === "ERROR" ? "rose" : "cyan"} />
                )}
              />
            </EngineCard>

            <EngineCard>
              <SectionHeader icon={LifeBuoy} title="Ticket Processing" action="/tickets" />
              <Rows
                items={tickets.slice(0, 6)}
                empty="No active tickets"
                render={(item) => (
                  <Row key={item.id} title={item.title} detail={`${item.ticket_id} · ${item.project || "Unassigned"} · ${item.source}`} badge={item.status} tone={["CLOSED", "RESOLVED"].includes(item.status) ? "emerald" : item.priority === "P1" ? "rose" : "amber"} />
                )}
              />
            </EngineCard>
          </div>

          <EngineCard>
            <SectionHeader icon={KeyRound} title="API Query Intake" action="/api-keys" />
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {apiQueries.slice(0, 8).map((item) => (
                <button key={item.id} type="button" onClick={() => setSelectedQuery(item)} className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4 text-left transition hover:border-[color:var(--primary)]">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-[color:var(--text-strong)]">{item.endpoint}</p>
                      <p className="mt-1 text-xs text-[color:var(--text-muted)]">{item.source_platform} · {item.project || "No project"} · {formatMs(item.response_time_ms)}</p>
                    </div>
                    <StatusBadge value={String(item.response_code)} tone={item.response_code >= 400 ? "rose" : "emerald"} />
                  </div>
                </button>
              ))}
              {!apiQueries.length && <EmptyLine text="No API queries received yet" />}
            </div>
          </EngineCard>
        </div>

        <aside className="space-y-5">
          <EngineCard>
            <SectionHeader icon={Activity} title="Live Server Monitoring" action="/server-monitor" />
            <Rows
              items={servers.slice(0, 5)}
              empty="No servers connected"
              render={(item) => (
                <div key={item.id} className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-[color:var(--text-strong)]">{item.name}</p>
                      <p className="text-xs text-[color:var(--text-muted)]">{item.ip_address}</p>
                    </div>
                    {item.status === "down" ? <WifiOff className="text-rose-300" /> : <Wifi className="text-emerald-300" />}
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <Mini label="CPU" value={`${Math.round(item.cpu || 0)}%`} />
                    <Mini label="Down" value={formatBytes(item.download_bytes)} />
                    <Mini label="Up" value={formatBytes(item.upload_bytes)} />
                  </div>
                </div>
              )}
            />
          </EngineCard>

          <EngineCard>
            <SectionHeader icon={Cable} title="Desk / Disk Connections" action="/enterprise" />
            <div className="mt-4 grid gap-3">
              <ConnectionLine icon={ShieldCheck} title="Desk-to-Desk Access" detail="Secure key, admin approval, permission boundary" />
              <ConnectionLine icon={FileStack} title="Disk-to-Disk Transfer" detail={`${summary.file_transfers || 0} transfers tracked`} />
              <ConnectionLine icon={Network} title="Network Telemetry" detail="Router/server status, latency, WiFi/Ethernet speed" />
            </div>
          </EngineCard>

          <EngineCard>
            <SectionHeader icon={Database} title="Recent File Transfers" action="/file-tracking" />
            <Rows
              items={transfers.slice(0, 5)}
              empty="No file transfers detected"
              render={(item) => (
                <Row key={item.id} title={item.file_name} detail={`${formatBytes(item.size_bytes)} · ${item.source} → ${item.destination}`} badge={item.status} tone={item.risk_score > 70 ? "rose" : item.status === "completed" ? "emerald" : "cyan"} />
              )}
            />
          </EngineCard>
        </aside>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <EngineCard>
          <SectionHeader icon={AlertTriangle} title="Expiry & Risk Alerts" action="/notifications" />
          <Rows
            items={expiryAlerts.slice(0, 8)}
            empty="No expiry risk inside 60 days"
            render={(item, index) => (
              <Row key={`${item.domain}-${index}`} title={item.project} detail={`${item.domain || "No domain"} · ${item.days_remaining} days remaining`} badge={item.level} tone={item.level === "critical" || item.level === "expired" ? "rose" : "amber"} />
            )}
          />
        </EngineCard>

        <EngineCard>
          <SectionHeader icon={Bell} title="Persistent Notifications" action="/notifications" />
          <Rows
            items={notifications.slice(0, 8)}
            empty="No notifications"
            render={(item) => (
              <Row key={item.id} title={item.title} detail={item.message} badge={item.is_read ? "read" : item.urgency || item.type} tone={item.is_read ? "cyan" : item.urgency === "critical" ? "rose" : "amber"} />
            )}
          />
        </EngineCard>
      </section>

      {selectedQuery && <QueryModal query={selectedQuery} onClose={() => setSelectedQuery(null)} />}
    </motion.div>
  );
}

function Metric({ title, value, detail, icon: Icon, tone, to }) {
  return (
    <Link to={to} className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--card-bg)] p-5 shadow-sm transition hover:-translate-y-1 hover:border-[color:var(--primary)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm text-[color:var(--text-muted)]">{title}</p>
          <p className="mt-2 text-3xl font-semibold text-[color:var(--text-strong)]">{value}</p>
          <p className="mt-1 text-xs text-[color:var(--text-muted)]">{detail}</p>
        </div>
        <div className={`grid size-11 place-items-center rounded-xl ${toneBg(tone)}`}>
          <Icon size={20} />
        </div>
      </div>
    </Link>
  );
}

function EngineCard({ children, className = "" }) {
  return <motion.section variants={cardMotion} className={`rounded-2xl border border-[color:var(--border)] bg-[color:var(--card-bg)] p-5 shadow-sm ${className}`}>{children}</motion.section>;
}

function SectionHeader({ icon: Icon, title, action }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <div className="grid size-10 place-items-center rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] text-[color:var(--primary)]">
          <Icon size={18} />
        </div>
        <h2 className="font-semibold text-[color:var(--text-strong)]">{title}</h2>
      </div>
      {action && <Link to={action} className="inline-flex items-center gap-1 text-xs font-semibold text-[color:var(--primary)]">Open <ArrowRight size={14} /></Link>}
    </div>
  );
}

function Rows({ items, render, empty }) {
  if (!items.length) return <EmptyLine text={empty} />;
  return <div className="mt-4 space-y-3">{items.map(render)}</div>;
}

function Row({ title, detail, badge, tone }) {
  return (
    <div className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-[color:var(--text-strong)]">{title}</p>
          <p className="mt-1 line-clamp-2 text-xs text-[color:var(--text-muted)]">{detail}</p>
        </div>
        <StatusBadge value={badge} tone={tone} />
      </div>
    </div>
  );
}

function Mini({ label, value }) {
  return (
    <div className="rounded-lg border border-[color:var(--border)] bg-[color:var(--card-bg)] px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-[color:var(--text-faint)]">{label}</p>
      <p className="mt-1 truncate text-xs font-semibold text-[color:var(--text-strong)]">{value}</p>
    </div>
  );
}

function ConnectionLine({ icon: Icon, title, detail }) {
  return (
    <div className="flex gap-3 rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
      <Icon className="mt-0.5 text-[color:var(--primary)]" size={18} />
      <div>
        <p className="text-sm font-semibold text-[color:var(--text-strong)]">{title}</p>
        <p className="mt-1 text-xs text-[color:var(--text-muted)]">{detail}</p>
      </div>
    </div>
  );
}

function QueryModal({ query, onClose }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 backdrop-blur-sm">
      <motion.div initial={{ opacity: 0, y: 20, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} className="w-full max-w-2xl rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-strong)] p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-[color:var(--primary)]">API Query Details</p>
            <h3 className="mt-1 text-xl font-semibold text-[color:var(--text-strong)]">{query.endpoint}</h3>
            <p className="mt-1 text-sm text-[color:var(--text-muted)]">{query.source_platform} · {query.project || "No project"} · {query.method}</p>
          </div>
          <button onClick={onClose} className="rounded-xl border border-[color:var(--border)] px-3 py-2 text-sm text-[color:var(--text-muted)]">Close</button>
        </div>
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <Mini label="Status" value={query.response_code} />
          <Mini label="Response" value={formatMs(query.response_time_ms)} />
          <Mini label="Time" value={formatDate(query.timestamp)} />
        </div>
        <div className="mt-5 rounded-xl border border-[color:var(--border)] bg-[color:var(--card-bg)] p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-[color:var(--text-faint)]">Full Issue / Request Context</p>
          <p className="mt-2 break-words text-sm text-[color:var(--text-muted)]">{query.endpoint}</p>
        </div>
      </motion.div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-24 rounded-2xl bg-[color:var(--surface-soft)] animate-pulse" />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => <div key={index} className="h-32 rounded-2xl bg-[color:var(--surface-soft)] animate-pulse" />)}
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <div className="h-96 rounded-2xl bg-[color:var(--surface-soft)] animate-pulse" />
        <div className="h-96 rounded-2xl bg-[color:var(--surface-soft)] animate-pulse" />
      </div>
    </div>
  );
}

function EmptyLine({ text }) {
  return <div className="mt-4 rounded-xl border border-dashed border-[color:var(--border)] bg-[color:var(--surface-soft)] p-5 text-center text-sm text-[color:var(--text-muted)]">{text}</div>;
}

function StatusBadge({ value, tone = "cyan" }) {
  return <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${badgeClass(tone)}`}>{pretty(value)}</span>;
}

function providerRoute(provider) {
  if (["s3", "cloudfront", "aws_s3", "aws_cloudfront"].includes(provider)) return "aws";
  if (["custom", "cloudflare", "dns"].includes(provider)) return "dns";
  return provider || "aws";
}

function pretty(value) {
  return String(value || "unknown").replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const power = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** power).toFixed(power ? 1 : 0)} ${units[power]}`;
}

function formatMs(value) {
  return `${Number(value || 0)} ms`;
}

function formatDate(value) {
  if (!value) return "n/a";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return String(value);
  }
}

function badgeClass(tone) {
  return {
    emerald: "bg-emerald-500/12 text-emerald-300 ring-1 ring-emerald-400/25",
    rose: "bg-rose-500/12 text-rose-300 ring-1 ring-rose-400/25",
    amber: "bg-amber-500/12 text-amber-300 ring-1 ring-amber-400/25",
    cyan: "bg-cyan-500/12 text-cyan-300 ring-1 ring-cyan-400/25"
  }[tone] || "bg-cyan-500/12 text-cyan-300 ring-1 ring-cyan-400/25";
}

function toneBg(tone) {
  return {
    emerald: "bg-emerald-500/12 text-emerald-300",
    rose: "bg-rose-500/12 text-rose-300",
    amber: "bg-amber-500/12 text-amber-300",
    cyan: "bg-cyan-500/12 text-cyan-300"
  }[tone] || "bg-cyan-500/12 text-cyan-300";
}

function toneText(tone) {
  return {
    emerald: "text-emerald-300",
    rose: "text-rose-300",
    amber: "text-amber-300",
    cyan: "text-cyan-300"
  }[tone] || "text-cyan-300";
}
