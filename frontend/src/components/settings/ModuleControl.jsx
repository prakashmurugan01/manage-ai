import { Activity, Clock3, ShieldCheck, ToggleLeft, ToggleRight } from "lucide-react";
import { useMemo, useState } from "react";

const moduleDescriptions = {
  TASKS: "Task management, Kanban workflows, approvals, and delivery tracking.",
  COLLABORATION: "Realtime channels, team messages, typing signals, and project communication.",
  TICKETS: "Support tickets, screenshots, comments, assignment, and service workflow.",
  NOTIFICATIONS: "Realtime alerts, dashboard badges, broadcast messages, and user notifications.",
  AI_CHATBOT: "AI task suggestions, assistant-ready workflows, and project intelligence.",
  MONITORING: "Operational dashboards, telemetry feeds, and service health indicators.",
  CONNECTION_ENGINE: "Universal connectors, sync events, API bridges, and integration health.",
  PROJECT_FILES: "Document upload, review, visibility control, and file approvals.",
  ANALYTICS: "Portfolio metrics, performance analytics, reports, and executive visibility.",
  AUDIT: "Immutable audit events for settings, API activity, deployments, and governance.",
};

export default function ModuleControl({ data = [], onToggle }) {
  const [filter, setFilter] = useState("all");
  const modules = useMemo(() => {
    if (filter === "enabled") return data.filter((module) => module.is_enabled);
    if (filter === "disabled") return data.filter((module) => !module.is_enabled);
    return data;
  }, [data, filter]);

  if (!data.length) return <EmptyModuleState />;

  const enabled = data.filter((module) => module.is_enabled).length;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4 lg:grid-cols-[1fr_auto] lg:items-center">
        <div>
          <div className="flex items-center gap-2 text-sm font-bold text-[color:var(--text-strong)]">
            <ShieldCheck size={17} />
            System Module Access
          </div>
          <p className="mt-1 text-sm text-[color:var(--text-muted)]">
            {enabled}/{data.length} modules enabled. Disabling a module immediately affects page access and is written to audit.
          </p>
        </div>
        <div className="flex rounded-lg border border-[color:var(--border)] bg-[color:var(--surface)] p-1">
          {["all", "enabled", "disabled"].map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setFilter(item)}
              className={`rounded-md px-3 py-1.5 text-xs font-bold capitalize transition ${
                filter === item ? "bg-[color:var(--surface-soft)] text-[color:var(--text-strong)]" : "text-[color:var(--text-muted)] hover:text-[color:var(--text-strong)]"
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4">
        {modules.map((module) => (
          <article
            key={module.id}
            className="grid gap-4 rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4 transition hover:border-[color:var(--border-strong)] lg:grid-cols-[1fr_auto] lg:items-center"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`h-2.5 w-2.5 rounded-full ${module.is_enabled ? "bg-emerald-300 shadow-[0_0_18px_rgba(52,211,153,0.58)]" : "bg-rose-300"}`} />
                <h3 className="text-sm font-bold text-[color:var(--text-strong)]">{labelize(module.module)}</h3>
                <span className={`rounded-full px-2 py-1 text-[11px] font-bold ${module.is_enabled ? "bg-emerald-400/12 text-emerald-200" : "bg-rose-400/12 text-rose-200"}`}>
                  {module.is_enabled ? "Enabled" : "Disabled"}
                </span>
              </div>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-[color:var(--text-muted)]">
                {module.description || moduleDescriptions[module.module] || "Enterprise module access control."}
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-[color:var(--text-muted)]">
                <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--border)] px-2 py-1">
                  <Activity size={12} />
                  Global page gate
                </span>
                <span className="inline-flex items-center gap-1 rounded-full border border-[color:var(--border)] px-2 py-1">
                  <Clock3 size={12} />
                  {module.changed_at ? new Date(module.changed_at).toLocaleString() : "Not changed yet"}
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => onToggle(module)}
              className={`inline-flex min-w-32 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-bold transition ${
                module.is_enabled ? "bg-emerald-500/15 text-emerald-200 hover:bg-emerald-500/20" : "bg-slate-500/15 text-slate-300 hover:bg-slate-500/20"
              }`}
            >
              {module.is_enabled ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
              {module.is_enabled ? "ON" : "OFF"}
            </button>
          </article>
        ))}
      </div>

      <div className="rounded-lg border border-blue-500/20 bg-blue-500/10 p-4 text-sm text-blue-300">
        Module changes are applied across navigation, settings telemetry, user access policy, and audit history.
      </div>
    </div>
  );
}

function EmptyModuleState() {
  return (
    <div className="rounded-lg border border-dashed border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-8 text-center">
      <p className="font-semibold text-[color:var(--text-strong)]">No modules configured</p>
      <p className="mt-1 text-sm text-[color:var(--text-muted)]">The settings dashboard will seed module controls from the backend defaults.</p>
    </div>
  );
}

function labelize(value) {
  return String(value || "Module").replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}
