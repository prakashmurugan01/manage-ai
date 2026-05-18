import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, Copy, Eye, Filter, KeyRound, Lock, RefreshCw, ShieldCheck, Slash, Zap } from "lucide-react";

import { api, apiErrorMessage, listFrom } from "../api/client.js";

const roles = ["viewer", "editor", "admin"];
const allStatuses = ["all", "open", "in_progress", "closed", "resolved", "pending"];

function envelope(response) {
  return response?.data?.data ?? response?.data ?? {};
}

function shortDate(value) {
  if (!value) return "Never";
  return new Date(value).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function normalizeStatus(value) {
  return String(value || "open").toLowerCase();
}

function StatusPill({ value }) {
  const status = normalizeStatus(value);
  const tone = status.includes("closed") || status.includes("resolved")
    ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
    : status.includes("progress")
      ? "border-cyan-400/30 bg-cyan-400/10 text-cyan-200"
      : status.includes("disabled")
        ? "border-slate-400/25 bg-slate-400/10 text-slate-300"
        : "border-amber-400/30 bg-amber-400/10 text-amber-200";
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${tone}`}>{value || "Open"}</span>;
}

export default function ApiKeyManager() {
  const qc = useQueryClient();
  const [newKey, setNewKey] = useState(null);
  const [selectedQuery, setSelectedQuery] = useState(null);
  const [filters, setFilters] = useState({ project: "all", status: "all", source: "all" });
  const [form, setForm] = useState({ project: "", name: "", role: "viewer", rate_limit_per_minute: 100, expires_at: "" });

  const keys = useQuery({ queryKey: ["uce-api-keys"], queryFn: () => api.get("/uce-api-keys/").then(listFrom), refetchInterval: 5000 });
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api.get("/projects/").then(listFrom) });
  const logs = useQuery({ queryKey: ["uce-api-key-logs"], queryFn: () => api.get("/uce-api-key-logs/").then(listFrom), refetchInterval: 5000 });
  const engine = useQuery({ queryKey: ["management-engine-dashboard"], queryFn: () => api.get("/management-engine/dashboard/").then(envelope), refetchInterval: 5000 });

  const create = useMutation({
    mutationFn: (payload) => api.post("/uce-api-keys/", payload).then((r) => r.data),
    onSuccess: (data) => {
      setNewKey(data.plaintext_key);
      setForm((current) => ({ ...current, name: "", expires_at: "" }));
      qc.invalidateQueries({ queryKey: ["uce-api-keys"] });
    }
  });

  const toggle = useMutation({
    mutationFn: (key) => api.post(`/uce-api-keys/${key.id}/toggle/`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["uce-api-keys"] })
  });

  const regenerate = useMutation({
    mutationFn: (key) => api.post(`/uce-api-keys/${key.id}/regenerate/`).then((r) => r.data),
    onSuccess: (data) => {
      setNewKey(data.plaintext_key);
      qc.invalidateQueries({ queryKey: ["uce-api-keys"] });
    }
  });

  const keyRows = keys.data || [];
  const projectRows = projects.data || [];
  const logRows = logs.data || [];
  const dashboard = engine.data || {};
  const eventRows = dashboard.external_events || [];
  const ticketRows = dashboard.tickets || [];

  const queryRows = useMemo(() => {
    const ticketById = new Map(ticketRows.map((ticket) => [String(ticket.ticket_id || ticket.id), ticket]));
    return eventRows.map((event) => {
      const details = event.details || {};
      const ticket = ticketById.get(String(details.ticket_id || details.ticket || ""));
      return {
        ...event,
        project: details.project_name || details.project || ticket?.project || "Project",
        message: details.description || details.message || details.title || event.title,
        ticket_status: ticket?.status || details.status || event.status,
        ticket_id: details.ticket_id || ticket?.ticket_id || "",
      };
    });
  }, [eventRows, ticketRows]);

  const sourceOptions = useMemo(() => ["all", ...new Set(queryRows.map((row) => row.source_platform).filter(Boolean))], [queryRows]);
  const filteredQueries = queryRows.filter((row) => {
    const projectMatch = filters.project === "all" || String(row.project) === String(filters.project);
    const sourceMatch = filters.source === "all" || row.source_platform === filters.source;
    const statusMatch = filters.status === "all" || normalizeStatus(row.ticket_status) === filters.status;
    return projectMatch && sourceMatch && statusMatch;
  });

  async function copy(text) {
    if (text) await navigator.clipboard.writeText(text);
  }

  function submit(event) {
    event.preventDefault();
    const payload = { ...form };
    if (!payload.expires_at) delete payload.expires_at;
    create.mutate(payload);
  }

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-cyan-300">API Integration Engine</p>
          <h1 className="mt-2 text-3xl font-bold text-white">API Key Manager</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">Secure chatbot intake, project-scoped keys, automatic ticket creation, and live query tracking.</p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center">
          <Metric icon={KeyRound} label="Keys" value={keyRows.length} />
          <Metric icon={Zap} label="Queries" value={queryRows.length} />
          <Metric icon={ShieldCheck} label="Logs" value={logRows.length} />
        </div>
      </motion.div>

      <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 shadow-2xl backdrop-blur">
        <form onSubmit={submit} className="grid gap-3 lg:grid-cols-[1.1fr_1.1fr_0.7fr_0.8fr_0.8fr_auto]">
          <select required value={form.project} onChange={(e) => setForm({ ...form, project: e.target.value })} className="rounded-xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300">
            <option value="">Select project</option>
            {projectRows.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
          <input required placeholder="Key name, e.g. Website Chatbot" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="rounded-xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300" />
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className="rounded-xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300">
            {roles.map((role) => <option key={role} value={role}>{role}</option>)}
          </select>
          <input type="number" min="10" max="5000" value={form.rate_limit_per_minute} onChange={(e) => setForm({ ...form, rate_limit_per_minute: Number(e.target.value) })} className="rounded-xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300" />
          <input type="datetime-local" value={form.expires_at} onChange={(e) => setForm({ ...form, expires_at: e.target.value })} className="rounded-xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300" />
          <button disabled={create.isPending} className="inline-flex items-center justify-center gap-2 rounded-xl bg-cyan-400 px-5 py-3 text-sm font-bold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-wait disabled:opacity-60">
            {create.isPending ? <RefreshCw className="animate-spin" size={16} /> : <KeyRound size={16} />}
            Generate
          </button>
        </form>
        {create.isError && <p className="mt-3 text-sm text-rose-300">{apiErrorMessage(create.error, "API key could not be generated.")}</p>}
      </section>

      <AnimatePresence>
        {newKey && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="rounded-2xl border border-amber-300/30 bg-amber-300/10 p-4 text-amber-50">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-semibold">Copy this key now. It is shown once.</p>
                <code className="mt-2 block break-all rounded-xl bg-slate-950/60 px-3 py-2 text-xs text-amber-100">{newKey}</code>
              </div>
              <button onClick={() => copy(newKey)} className="inline-flex items-center gap-2 rounded-xl border border-amber-200/30 px-4 py-2 text-sm font-semibold transition hover:bg-amber-200/10"><Copy size={16} /> Copy</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-bold text-white">Project API Keys</h2>
            {keys.isFetching && <RefreshCw size={16} className="animate-spin text-cyan-300" />}
          </div>
          <div className="space-y-3">
            {keyRows.map((key) => (
              <motion.div key={key.id} layout className="grid gap-3 rounded-2xl border border-white/10 bg-slate-950/45 p-4 md:grid-cols-[1fr_auto]">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-white">{key.name}</p>
                    <StatusPill value={key.is_active ? key.role : "disabled"} />
                  </div>
                  <p className="mt-1 text-sm text-slate-400">{key.project_name} · prefix <span className="font-mono text-cyan-200">{key.key_prefix}****</span></p>
                  <p className="mt-2 text-xs text-slate-500">Rate {key.rate_limit_per_minute}/min · Last used {shortDate(key.last_used_at)} · Expires {shortDate(key.expires_at)}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button onClick={() => regenerate.mutate(key)} className="rounded-xl border border-white/10 p-2 text-slate-300 transition hover:border-cyan-300/40 hover:text-cyan-200" title="Regenerate key"><RefreshCw size={16} /></button>
                  <button onClick={() => toggle.mutate(key)} className="inline-flex items-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-sm font-semibold text-slate-300 transition hover:border-rose-300/40 hover:text-rose-200">
                    {key.is_active ? <Slash size={15} /> : <CheckCircle2 size={15} />}
                    {key.is_active ? "Disable" : "Enable"}
                  </button>
                </div>
              </motion.div>
            ))}
            {!keyRows.length && <Empty icon={Lock} title="No API keys yet" text="Generate a project-scoped key to connect an external chatbot." />}
          </div>
        </section>

        <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-bold text-white">Live Chatbot Queries</h2>
            <div className="flex flex-wrap gap-2">
              <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })} className="rounded-lg border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-white">
                {allStatuses.map((status) => <option key={status} value={status}>{status}</option>)}
              </select>
              <select value={filters.project} onChange={(e) => setFilters({ ...filters, project: e.target.value })} className="rounded-lg border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-white">
                <option value="all">all projects</option>
                {projectRows.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
              </select>
              <select value={filters.source} onChange={(e) => setFilters({ ...filters, source: e.target.value })} className="rounded-lg border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-white">
                {sourceOptions.map((source) => <option key={source} value={source}>{source}</option>)}
              </select>
            </div>
          </div>
          <div className="space-y-3">
            {filteredQueries.map((query) => (
              <button key={query.id} onClick={() => setSelectedQuery(query)} className="w-full rounded-2xl border border-white/10 bg-slate-950/45 p-4 text-left transition hover:border-cyan-300/40 hover:bg-slate-950/60">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-white">{query.title}</p>
                    <p className="mt-1 line-clamp-2 text-sm text-slate-400">{query.message}</p>
                    <p className="mt-2 text-xs text-slate-500">{query.source_platform} · {shortDate(query.created_at)}</p>
                  </div>
                  <StatusPill value={query.ticket_status} />
                </div>
              </button>
            ))}
            {!filteredQueries.length && <Empty icon={Filter} title="No matching queries" text="Incoming chatbot queries appear here within the next poll cycle." />}
          </div>
        </section>
      </div>

      <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
        <h2 className="mb-4 text-lg font-bold text-white">API Usage Logs</h2>
        <div className="grid gap-2">
          {logRows.slice(0, 8).map((log) => (
            <div key={log.id} className="grid gap-3 rounded-xl border border-white/10 bg-slate-950/35 px-4 py-3 text-sm md:grid-cols-[1fr_auto_auto_auto]">
              <span className="truncate text-white">{log.http_method} {log.endpoint}</span>
              <span className="text-slate-400">{log.response_code}</span>
              <span className="text-slate-400">{log.response_time_ms}ms</span>
              <span className="text-slate-500">{shortDate(log.timestamp)}</span>
            </div>
          ))}
          {!logRows.length && <Empty icon={Eye} title="No usage yet" text="Validated external requests will be logged with response code and latency." />}
        </div>
      </section>

      <AnimatePresence>
        {selectedQuery && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 grid place-items-center bg-slate-950/70 p-4 backdrop-blur">
            <motion.div initial={{ scale: 0.96, y: 10 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.96, y: 10 }} className="w-full max-w-2xl rounded-2xl border border-white/10 bg-slate-950 p-5 shadow-2xl">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-cyan-300">{selectedQuery.source_platform}</p>
                  <h3 className="mt-1 text-xl font-bold text-white">{selectedQuery.title}</h3>
                </div>
                <StatusPill value={selectedQuery.ticket_status} />
              </div>
              <div className="mt-5 grid gap-3 text-sm text-slate-300">
                <p>{selectedQuery.message}</p>
                <p><span className="text-slate-500">Project:</span> {selectedQuery.project}</p>
                <p><span className="text-slate-500">Ticket:</span> {selectedQuery.ticket_id || "Auto-created"}</p>
                <p><span className="text-slate-500">Time:</span> {shortDate(selectedQuery.created_at)}</p>
              </div>
              <button onClick={() => setSelectedQuery(null)} className="mt-5 w-full rounded-xl bg-cyan-400 px-4 py-3 text-sm font-bold text-slate-950 transition hover:bg-cyan-300">Close</button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Metric({ icon: Icon, label, value }) {
  return (
    <div className="min-w-24 rounded-2xl border border-white/10 bg-white/[0.05] px-4 py-3">
      <Icon className="mx-auto text-cyan-300" size={18} />
      <p className="mt-1 text-xl font-bold text-white">{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  );
}

function Empty({ icon: Icon, title, text }) {
  return (
    <div className="rounded-2xl border border-dashed border-white/10 bg-slate-950/25 p-8 text-center">
      <Icon className="mx-auto text-cyan-300" size={24} />
      <p className="mt-3 font-semibold text-white">{title}</p>
      <p className="mt-1 text-sm text-slate-500">{text}</p>
    </div>
  );
}
