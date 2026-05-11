import { motion } from "framer-motion";
import {
  BarChart3,
  Bot,
  Building2,
  Cable,
  CheckCircle2,
  Cloud,
  Database,
  Download,
  FileSpreadsheet,
  FileText,
  KeyRound,
  Mail,
  Mic2,
  Network,
  Plus,
  Power,
  Radio,
  RefreshCcw,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  ToggleLeft,
  ToggleRight,
  Users
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listFrom } from "../api/client.js";
import { enterpriseApi, projectsApi, usersApi } from "../api/services.js";
import Badge from "../components/ui/Badge.jsx";
import Button from "../components/ui/Button.jsx";
import Modal from "../components/ui/Modal.jsx";
import Page from "../components/ui/Page.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { canManage, ROLES } from "../utils/rbac.js";

const reportKinds = [
  { key: "client", title: "Client Report", icon: FileText, detail: "Project details, progress, pricing, documents, and support status." },
  { key: "developer", title: "Developer Report", icon: Users, detail: "Completed projects, task metrics, ratings, and productivity score." },
  { key: "admin", title: "Admin Insights", icon: BarChart3, detail: "Database insights, usage, deployments, tickets, files, and API access." }
];

const moduleDefaults = [
  { key: "task_manager", label: "Task Manager", dashboard: "GLOBAL" },
  { key: "ai_chatbot", label: "AI Chatbot", dashboard: "DEVELOPER" },
  { key: "notifications", label: "Notifications", dashboard: "GLOBAL" },
  { key: "reports", label: "Reports", dashboard: "ADMIN" },
  { key: "voice_assistant", label: "Voice Assistant", dashboard: "GLOBAL" },
  { key: "crm", label: "CRM", dashboard: "ADMIN" },
  { key: "erp", label: "ERP", dashboard: "SUPER_ADMIN" }
];

const connectorCategories = ["CRM", "ERP", "HR", "INVENTORY", "PROJECT_MANAGEMENT", "HOSTING", "SERVER", "API", "CUSTOM"];

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function Panel({ title, subtitle, icon: Icon, children, action }) {
  return (
    <section className="panel overflow-hidden p-4">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Icon size={18} className="text-teal-200" />
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

export default function Enterprise() {
  const { user } = useAuth();
  const [tab, setTab] = useState("connections");
  const [users, setUsers] = useState([]);
  const [projects, setProjects] = useState([]);
  const [estimates, setEstimates] = useState([]);
  const [apiKeys, setApiKeys] = useState([]);
  const [flags, setFlags] = useState([]);
  const [emails, setEmails] = useState([]);
  const [hosting, setHosting] = useState([]);
  const [services, setServices] = useState([]);
  const [summary, setSummary] = useState(null);
  const [connectors, setConnectors] = useState([]);
  const [connectionEvents, setConnectionEvents] = useState([]);
  const [networkTelemetry, setNetworkTelemetry] = useState(null);
  const [voiceIntents, setVoiceIntents] = useState([]);
  const [estimateOpen, setEstimateOpen] = useState(false);
  const [keyOpen, setKeyOpen] = useState(false);
  const [serviceOpen, setServiceOpen] = useState(false);
  const [connectorOpen, setConnectorOpen] = useState(false);
  const [estimateForm, setEstimateForm] = useState({ title: "", client: "", project: "", scope: "", features: "", timeline_days: 30, development_cost: 0, hosting_cost: 0, maintenance_cost: 0, currency: "USD", demo_url: "", demo_notes: "", status: "DRAFT" });
  const [keyForm, setKeyForm] = useState({ name: "", provider: "OPENAI", raw_key: "", notes: "" });
  const [serviceForm, setServiceForm] = useState({ name: "", description: "", base_price: 0, recurring_price: 0, is_active: true });
  const [connectorForm, setConnectorForm] = useState({ name: "", category: "CRM", vendor: "", endpoint_url: "", project: "", sync_interval_seconds: 300, ai_enhancement_enabled: false });

  function loadEnterprise() {
    return Promise.all([
      usersApi.list(),
      projectsApi.list(),
      enterpriseApi.estimates(),
      enterpriseApi.apiKeys(),
      enterpriseApi.featureFlags(),
      enterpriseApi.emailEvents(),
      enterpriseApi.hosting(),
      enterpriseApi.services(),
      enterpriseApi.connectionSummary(),
      enterpriseApi.connectors(),
      enterpriseApi.connectionEvents(),
      enterpriseApi.networkLive(),
      enterpriseApi.voiceIntents()
    ]).then(([usersResponse, projectsResponse, estimatesResponse, keysResponse, flagsResponse, emailsResponse, hostingResponse, servicesResponse, summaryResponse, connectorsResponse, eventsResponse, networkResponse, voiceResponse]) => {
      setUsers(listFrom(usersResponse));
      const projectItems = listFrom(projectsResponse);
      setProjects(projectItems);
      setEstimates(listFrom(estimatesResponse));
      setApiKeys(listFrom(keysResponse));
      setFlags(listFrom(flagsResponse));
      setEmails(listFrom(emailsResponse));
      setHosting(listFrom(hostingResponse));
      setServices(listFrom(servicesResponse));
      setSummary(summaryResponse.data);
      setConnectors(listFrom(connectorsResponse));
      setConnectionEvents(listFrom(eventsResponse));
      setNetworkTelemetry(networkResponse.data);
      setVoiceIntents(listFrom(voiceResponse));
      const firstClient = listFrom(usersResponse).find((item) => item.role === ROLES.CLIENT);
      setEstimateForm((current) => ({ ...current, client: current.client || firstClient?.id || "", project: current.project || projectItems[0]?.id || "" }));
      setConnectorForm((current) => ({ ...current, project: current.project || projectItems[0]?.id || "" }));
    });
  }

  useEffect(() => {
    loadEnterprise();
  }, []);

  const clients = useMemo(() => users.filter((item) => item.role === ROLES.CLIENT), [users]);
  const developers = useMemo(() => users.filter((item) => item.role === ROLES.DEVELOPER), [users]);
  const visibleReports = reportKinds.filter((report) => report.key !== "admin" || canManage(user));

  async function downloadReport(kind, format) {
    const { data } = await enterpriseApi.report(kind, format);
    saveBlob(data, `${kind}-report.${format === "excel" ? "xlsx" : "pdf"}`);
  }

  async function createEstimate(event) {
    event.preventDefault();
    const payload = {
      ...estimateForm,
      project: estimateForm.project || null,
      features: estimateForm.features.split(",").map((item) => item.trim()).filter(Boolean),
      timeline_days: Number(estimateForm.timeline_days) || 1
    };
    const { data } = await enterpriseApi.createEstimate(payload);
    setEstimates((items) => [data, ...items]);
    setEstimateOpen(false);
  }

  async function sendEstimate(id) {
    const { data } = await enterpriseApi.sendEstimate(id);
    setEstimates((items) => items.map((item) => (item.id === id ? data : item)));
  }

  async function createApiKey(event) {
    event.preventDefault();
    const { data } = await enterpriseApi.createApiKey(keyForm);
    setApiKeys((items) => [data, ...items]);
    setKeyOpen(false);
    setKeyForm({ name: "", provider: "OPENAI", raw_key: "", notes: "" });
  }

  async function grantDeveloper(apiKey, developer) {
    const { data } = await enterpriseApi.createGrant({ api_key: apiKey, developer, can_view: true, can_use: true });
    setApiKeys((items) => items.map((item) => item.id === apiKey ? { ...item, grants: [...(item.grants || []), data] } : item));
  }

  async function toggleFlag(flag) {
    const { data } = await enterpriseApi.updateFeatureFlag(flag.id, { is_enabled: !flag.is_enabled });
    setFlags((items) => items.map((item) => (item.id === flag.id ? data : item)));
  }

  async function createService(event) {
    event.preventDefault();
    const { data } = await enterpriseApi.createService(serviceForm);
    setServices((items) => [data, ...items]);
    setServiceOpen(false);
  }

  async function createConnector(event) {
    event.preventDefault();
    const payload = { ...connectorForm, project: connectorForm.project || null, sync_interval_seconds: Number(connectorForm.sync_interval_seconds) || 300 };
    const { data } = await enterpriseApi.createConnector(payload);
    setConnectors((items) => [data, ...items]);
    setConnectorOpen(false);
    setConnectorForm({ name: "", category: "CRM", vendor: "", endpoint_url: "", project: projects[0]?.id || "", sync_interval_seconds: 300, ai_enhancement_enabled: false });
    loadEnterprise();
  }

  async function syncConnector(connector) {
    const { data } = await enterpriseApi.syncConnector(connector.id, { records_in: 24, records_out: 18, latency_ms: 72 });
    setConnectors((items) => items.map((item) => (item.id === connector.id ? data : item)));
    loadEnterprise();
  }

  async function controlConnector(connector, patch) {
    const { data } = await enterpriseApi.controlConnector(connector.id, patch);
    setConnectors((items) => items.map((item) => (item.id === connector.id ? data : item)));
    loadEnterprise();
  }

  async function toggleHosting(connection) {
    const { data } = await enterpriseApi.toggleHosting(connection.id, { is_enabled: !connection.is_enabled });
    setHosting((items) => items.map((item) => (item.id === connection.id ? data : item)));
  }

  return (
    <Page
      title="Enterprise Control"
      subtitle="Reports, project estimations, API keys, feature settings, hosting, ERP, CRM, and automation controls."
      actions={
        <div className="rounded-lg border border-white/10 bg-white/[0.04] p-1">
          {["connections", "reports", "estimations", "keys", "settings", "erp"].map((item) => (
            <button key={item} type="button" onClick={() => setTab(item)} className={`rounded-md px-3 py-1.5 text-sm capitalize ${tab === item ? "bg-white/15 text-white" : "text-slate-400"}`}>{item}</button>
          ))}
        </div>
      }
    >
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mb-6 overflow-hidden rounded-lg border border-white/10 bg-gradient-to-br from-teal-300/15 via-sky-300/10 to-rose-300/15 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs uppercase tracking-[0.14em] text-slate-300"><Sparkles size={14} />Universal Connection Engine</div>
            <h1 className="mt-4 text-2xl font-semibold text-white">Connect, monitor, sync, and control every company system</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">Central database visibility for CRM, ERP, HR, inventory, projects, hosting, servers, APIs, reporting, automation, access control, and optional AI enhancement layers.</p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg border border-white/10 bg-white/[0.04] p-3"><p className="text-xl font-semibold text-white">{summary?.totals?.connectors ?? connectors.length}</p><p className="text-xs text-slate-500">Connectors</p></div>
            <div className="rounded-lg border border-white/10 bg-white/[0.04] p-3"><p className="text-xl font-semibold text-white">{summary?.totals?.connected ?? 0}</p><p className="text-xs text-slate-500">Connected</p></div>
            <div className="rounded-lg border border-white/10 bg-white/[0.04] p-3"><p className="text-xl font-semibold text-white">{networkTelemetry?.current?.latency_ms ?? "--"}ms</p><p className="text-xs text-slate-500">Latency</p></div>
          </div>
        </div>
      </motion.div>

      {tab === "connections" && (
        <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <Panel title="Universal Connectors" subtitle="CRM, ERP, HR, inventory, project tools, hosting, servers, APIs, and custom systems." icon={Cable} action={canManage(user) && <Button onClick={() => setConnectorOpen(true)}><Plus size={16} />Connector</Button>}>
            <div className="mb-4 grid gap-3 md:grid-cols-4">
              <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3"><p className="text-lg font-semibold text-white">{summary?.totals?.connected ?? 0}</p><p className="text-xs text-slate-500">Live links</p></div>
              <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3"><p className="text-lg font-semibold text-white">{summary?.totals?.syncing ?? 0}</p><p className="text-xs text-slate-500">Syncing</p></div>
              <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3"><p className="text-lg font-semibold text-white">{summary?.totals?.events ?? 0}</p><p className="text-xs text-slate-500">Events</p></div>
              <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3"><p className="text-lg font-semibold text-white">{summary?.totals?.degraded ?? 0}</p><p className="text-xs text-slate-500">Degraded</p></div>
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              {connectors.map((connector) => (
                <motion.article key={connector.id} whileHover={{ y: -3 }} className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-white">{connector.name}</p>
                      <p className="mt-1 truncate text-xs text-slate-500">{connector.category} - {connector.vendor || "Custom"} - {connector.project_name || "Company-wide"}</p>
                    </div>
                    <Badge value={connector.status} />
                  </div>
                  <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                    <div className="rounded-md bg-white/[0.04] p-2"><p className="text-sm font-semibold text-white">{connector.records_in}</p><p className="text-[11px] text-slate-500">In</p></div>
                    <div className="rounded-md bg-white/[0.04] p-2"><p className="text-sm font-semibold text-white">{connector.records_out}</p><p className="text-[11px] text-slate-500">Out</p></div>
                    <div className="rounded-md bg-white/[0.04] p-2"><p className="text-sm font-semibold text-white">{connector.latency_ms}ms</p><p className="text-[11px] text-slate-500">Latency</p></div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button variant="secondary" onClick={() => syncConnector(connector)}><RefreshCcw size={15} />Sync</Button>
                    {canManage(user) && <Button variant="ghost" onClick={() => controlConnector(connector, { is_enabled: !connector.is_enabled })}><Power size={15} />{connector.is_enabled ? "Off" : "On"}</Button>}
                    {canManage(user) && <Button variant="ghost" onClick={() => controlConnector(connector, { ai_enhancement_enabled: !connector.ai_enhancement_enabled })}><Bot size={15} />AI {connector.ai_enhancement_enabled ? "On" : "Off"}</Button>}
                  </div>
                </motion.article>
              ))}
              {!connectors.length && <p className="rounded-lg bg-white/[0.035] p-4 text-sm text-slate-500">No connectors configured yet.</p>}
            </div>
          </Panel>
          <div className="space-y-4">
            <Panel title="Network Telemetry" subtitle="Upload, download, latency, packet loss, RPS, and health." icon={Network} action={<Button variant="secondary" onClick={loadEnterprise}><Radio size={16} />Live</Button>}>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3"><p className="text-lg font-semibold text-white">{networkTelemetry?.current?.download_mbps ?? "--"} Mbps</p><p className="text-xs text-slate-500">Download</p></div>
                <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3"><p className="text-lg font-semibold text-white">{networkTelemetry?.current?.upload_mbps ?? "--"} Mbps</p><p className="text-xs text-slate-500">Upload</p></div>
                <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3"><p className="text-lg font-semibold text-white">{networkTelemetry?.current?.requests_per_second ?? "--"}</p><p className="text-xs text-slate-500">Requests/sec</p></div>
                <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3"><p className="text-lg font-semibold text-white">{networkTelemetry?.current?.health_score ?? "--"}%</p><p className="text-xs text-slate-500">Health</p></div>
              </div>
              <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
                <div className="h-full rounded-full bg-teal-300" style={{ width: `${networkTelemetry?.current?.health_score ?? 0}%` }} />
              </div>
            </Panel>
            <Panel title="Event Stream" subtitle="Syncs, controls, deployments, server activity, and user actions." icon={Database}>
              <div className="space-y-3">
                {connectionEvents.slice(0, 8).map((event) => (
                  <div key={event.id} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
                    <div className="flex items-center justify-between gap-3"><p className="truncate text-sm font-medium text-white">{event.title}</p><Badge value={event.event_type} /></div>
                    <p className="mt-1 truncate text-xs text-slate-500">{event.connector_name || event.project_name || "Platform"} - {event.actor_email || "System"}</p>
                  </div>
                ))}
                {!connectionEvents.length && <p className="rounded-lg bg-white/[0.035] p-4 text-sm text-slate-500">No connection events yet.</p>}
              </div>
            </Panel>
            <Panel title="Voice Assistant Intents" subtitle="Voice commands are mapped to permission-aware platform actions." icon={Mic2}>
              <div className="space-y-2">
                {(voiceIntents.length ? voiceIntents : [{ phrase: "show server health", action: "OPEN_MONITORING", target_module: "monitoring" }, { phrase: "sync crm", action: "SYNC_CONNECTOR", target_module: "connections" }]).map((intent) => (
                  <div key={`${intent.phrase}-${intent.target_module}`} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
                    <p className="text-sm font-medium text-white">&quot;{intent.phrase}&quot;</p>
                    <p className="mt-1 text-xs text-slate-500">{intent.action} - {intent.target_module}</p>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
      )}

      {tab === "reports" && (
        <div className="grid gap-4 lg:grid-cols-3">
          {visibleReports.map((report) => {
            const Icon = report.icon;
            return (
              <Panel key={report.key} title={report.title} subtitle={report.detail} icon={Icon}>
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => downloadReport(report.key, "pdf")}><FileText size={16} />PDF</Button>
                  <Button variant="secondary" onClick={() => downloadReport(report.key, "excel")}><FileSpreadsheet size={16} />Excel</Button>
                </div>
              </Panel>
            );
          })}
        </div>
      )}

      {tab === "estimations" && (
        <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <Panel title="Project Estimation" subtitle="Admin defines scope, features, timeline, development cost, hosting, and client communication." icon={FileText} action={<Button onClick={() => setEstimateOpen(true)}><Plus size={16} />Estimate</Button>}>
            <div className="space-y-3">
              {estimates.map((estimate) => (
                <div key={estimate.id} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div><p className="text-sm font-medium text-white">{estimate.title}</p><p className="mt-1 text-xs text-slate-500">{estimate.client_detail?.full_name || estimate.client_detail?.email} - {estimate.timeline_days} days</p></div>
                    <Badge value={estimate.status} />
                  </div>
                  <p className="mt-2 text-sm text-slate-400">{estimate.scope}</p>
                  {(estimate.demo_url || estimate.demo_notes) && (
                    <div className="mt-3 rounded-lg border border-teal-300/20 bg-teal-300/10 p-3">
                      <p className="text-xs uppercase tracking-[0.14em] text-teal-200">Client Demo Preview</p>
                      {estimate.demo_url && <a className="mt-2 block truncate text-sm font-medium text-white underline" href={estimate.demo_url} target="_blank" rel="noreferrer">{estimate.demo_url}</a>}
                      {estimate.demo_notes && <p className="mt-2 text-sm text-slate-300">{estimate.demo_notes}</p>}
                    </div>
                  )}
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm">
                    <span className="font-semibold text-white">{estimate.currency} {estimate.total_cost}</span>
                    {canManage(user) && <Button variant="secondary" onClick={() => sendEstimate(estimate.id)}><Send size={16} />Send</Button>}
                  </div>
                </div>
              ))}
            </div>
          </Panel>
          <Panel title="Client Lifecycle" subtitle="Requests, estimation, approval, development, staging, production, support." icon={CheckCircle2}>
            <div className="grid gap-3 sm:grid-cols-2">
              {["Requested", "Estimated", "Approved", "Development", "Staging", "Production"].map((item, index) => (
                <div key={item} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
                  <p className="text-sm font-medium text-white">{index + 1}. {item}</p>
                  <p className="mt-1 text-xs text-slate-500">Lifecycle stage visibility for clients.</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}

      {tab === "keys" && (
        <div className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
          <Panel title="API Key Management" subtitle="Admin-managed provider keys with per-developer visibility and use grants." icon={KeyRound} action={canManage(user) && <Button onClick={() => setKeyOpen(true)}><Plus size={16} />API Key</Button>}>
            <div className="space-y-3">
              {apiKeys.map((item) => (
                <div key={item.id} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div><p className="text-sm font-medium text-white">{item.name}</p><p className="mt-1 font-mono text-xs text-slate-500">{item.key_preview}</p></div>
                    <Badge value={item.provider} />
                  </div>
                  {canManage(user) && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {developers.slice(0, 4).map((developer) => (
                        <Button key={developer.id} variant="ghost" onClick={() => grantDeveloper(item.id, developer.id)}><ShieldCheck size={15} />{developer.first_name || developer.email}</Button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Panel>
          <Panel title="AI Team Extensions" subtitle="AI developers see assigned AI keys, tools, and automation modules." icon={Bot}>
            <div className="space-y-3">
              {developers.map((developer) => (
                <div key={developer.id} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
                  <p className="text-sm font-medium text-white">{developer.full_name || developer.email}</p>
                  <p className="mt-1 text-xs text-slate-500">{developer.role_title || "Developer"} - {developer.skills?.join?.(", ") || "General"}</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}

      {tab === "settings" && (
        <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <Panel title="Settings Control Panel" subtitle="Enable or disable dashboard modules and platform behavior." icon={Settings2}>
            <div className="space-y-3">
              {(flags.length ? flags : moduleDefaults).map((flag) => (
                <button key={`${flag.key}-${flag.dashboard}`} type="button" onClick={() => flag.id && toggleFlag(flag)} className="flex w-full items-center justify-between rounded-lg border border-white/10 bg-white/[0.035] p-3 text-left">
                  <span><span className="block text-sm font-medium text-white">{flag.label}</span><span className="text-xs text-slate-500">{flag.dashboard}</span></span>
                  {flag.is_enabled ?? true ? <ToggleRight className="text-emerald-300" /> : <ToggleLeft className="text-slate-500" />}
                </button>
              ))}
            </div>
          </Panel>
          <Panel title="Email Automation" subtitle="Task updates, project updates, ticket responses, estimates, and report delivery." icon={Mail}>
            <div className="space-y-3">
              {emails.slice(0, 8).map((email) => (
                <div key={email.id} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
                  <div className="flex items-center justify-between gap-3"><p className="truncate text-sm font-medium text-white">{email.subject}</p><Badge value={email.status} /></div>
                  <p className="mt-1 truncate text-xs text-slate-500">{email.recipient}</p>
                </div>
              ))}
              {!emails.length && <p className="rounded-lg bg-white/[0.035] p-4 text-sm text-slate-500">No email events yet.</p>}
            </div>
          </Panel>
        </div>
      )}

      {tab === "erp" && (
        <div className="grid gap-4 xl:grid-cols-3">
          <Panel title="Company Services" subtitle="Define services, pricing, recurring hosting, and company offerings." icon={Building2} action={canManage(user) && <Button onClick={() => setServiceOpen(true)}><Plus size={16} />Service</Button>}>
            <div className="space-y-3">
              {services.map((service) => <div key={service.id} className="rounded-lg border border-white/10 bg-white/[0.035] p-3"><p className="text-sm font-medium text-white">{service.name}</p><p className="mt-1 text-xs text-slate-500">{service.base_price} setup / {service.recurring_price} recurring</p></div>)}
            </div>
          </Panel>
          <Panel title="CRM Clients" subtitle="Clients, project requests, plans, pricing, and lifecycle visibility." icon={Users}>
            <div className="space-y-3">
              {clients.map((client) => <div key={client.id} className="rounded-lg border border-white/10 bg-white/[0.035] p-3"><p className="text-sm font-medium text-white">{client.full_name || client.email}</p><p className="mt-1 text-xs text-slate-500">{client.assigned_project_count} projects / {client.open_ticket_count} tickets</p></div>)}
            </div>
          </Panel>
          <Panel title="Hosting Connections" subtitle="Multi-provider hosting, server ON/OFF control, and deployment triggers." icon={Cloud}>
            <div className="space-y-3">
              {hosting.map((connection) => <button key={connection.id} type="button" onClick={() => toggleHosting(connection)} className="flex w-full items-center justify-between rounded-lg border border-white/10 bg-white/[0.035] p-3 text-left"><span><span className="block text-sm font-medium text-white">{connection.name}</span><span className="text-xs text-slate-500">{connection.provider} - {connection.project_name}</span></span><Badge value={connection.is_enabled ? "ON" : "OFF"} /></button>)}
              {!hosting.length && <p className="rounded-lg bg-white/[0.035] p-4 text-sm text-slate-500">No hosting connections configured yet.</p>}
            </div>
          </Panel>
        </div>
      )}

      <Modal open={estimateOpen} title="Create Project Estimate" onClose={() => setEstimateOpen(false)}>
        <form onSubmit={createEstimate} className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <input className="field" required placeholder="Title" value={estimateForm.title} onChange={(event) => setEstimateForm({ ...estimateForm, title: event.target.value })} />
            <select className="field" required value={estimateForm.client} onChange={(event) => setEstimateForm({ ...estimateForm, client: event.target.value })}>{clients.map((client) => <option key={client.id} value={client.id}>{client.full_name || client.email}</option>)}</select>
            <select className="field" value={estimateForm.project} onChange={(event) => setEstimateForm({ ...estimateForm, project: event.target.value })}><option value="">New project request</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
            <input className="field" type="number" min="1" placeholder="Timeline days" value={estimateForm.timeline_days} onChange={(event) => setEstimateForm({ ...estimateForm, timeline_days: event.target.value })} />
          </div>
          <textarea className="field min-h-28" required placeholder="Project scope and requirements" value={estimateForm.scope} onChange={(event) => setEstimateForm({ ...estimateForm, scope: event.target.value })} />
          <input className="field" placeholder="Features, comma separated" value={estimateForm.features} onChange={(event) => setEstimateForm({ ...estimateForm, features: event.target.value })} />
          <div className="grid gap-4 sm:grid-cols-2">
            <input className="field" placeholder="Demo website / UI preview link" value={estimateForm.demo_url} onChange={(event) => setEstimateForm({ ...estimateForm, demo_url: event.target.value })} />
            <input className="field" placeholder="Demo notes for client" value={estimateForm.demo_notes} onChange={(event) => setEstimateForm({ ...estimateForm, demo_notes: event.target.value })} />
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <input className="field" type="number" min="0" placeholder="Development cost" value={estimateForm.development_cost} onChange={(event) => setEstimateForm({ ...estimateForm, development_cost: event.target.value })} />
            <input className="field" type="number" min="0" placeholder="Hosting cost" value={estimateForm.hosting_cost} onChange={(event) => setEstimateForm({ ...estimateForm, hosting_cost: event.target.value })} />
            <input className="field" type="number" min="0" placeholder="Maintenance cost" value={estimateForm.maintenance_cost} onChange={(event) => setEstimateForm({ ...estimateForm, maintenance_cost: event.target.value })} />
          </div>
          <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setEstimateOpen(false)}>Cancel</Button><Button type="submit"><Send size={16} />Create</Button></div>
        </form>
      </Modal>

      <Modal open={keyOpen} title="Add API Key" onClose={() => setKeyOpen(false)}>
        <form onSubmit={createApiKey} className="grid gap-4">
          <input className="field" required placeholder="Key name" value={keyForm.name} onChange={(event) => setKeyForm({ ...keyForm, name: event.target.value })} />
          <select className="field" value={keyForm.provider} onChange={(event) => setKeyForm({ ...keyForm, provider: event.target.value })}><option value="OPENAI">OpenAI</option><option value="META">Meta</option><option value="OPEN_SOURCE">Open source</option><option value="OTHER">Other</option></select>
          <input className="field" required type="password" placeholder="Secret API key" value={keyForm.raw_key} onChange={(event) => setKeyForm({ ...keyForm, raw_key: event.target.value })} />
          <textarea className="field min-h-24" placeholder="Notes" value={keyForm.notes} onChange={(event) => setKeyForm({ ...keyForm, notes: event.target.value })} />
          <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setKeyOpen(false)}>Cancel</Button><Button type="submit"><KeyRound size={16} />Save</Button></div>
        </form>
      </Modal>

      <Modal open={serviceOpen} title="Add Company Service" onClose={() => setServiceOpen(false)}>
        <form onSubmit={createService} className="grid gap-4">
          <input className="field" required placeholder="Service name" value={serviceForm.name} onChange={(event) => setServiceForm({ ...serviceForm, name: event.target.value })} />
          <textarea className="field min-h-24" placeholder="Description" value={serviceForm.description} onChange={(event) => setServiceForm({ ...serviceForm, description: event.target.value })} />
          <div className="grid gap-4 sm:grid-cols-2">
            <input className="field" type="number" min="0" placeholder="Base price" value={serviceForm.base_price} onChange={(event) => setServiceForm({ ...serviceForm, base_price: event.target.value })} />
            <input className="field" type="number" min="0" placeholder="Recurring price" value={serviceForm.recurring_price} onChange={(event) => setServiceForm({ ...serviceForm, recurring_price: event.target.value })} />
          </div>
          <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setServiceOpen(false)}>Cancel</Button><Button type="submit">Create</Button></div>
        </form>
      </Modal>

      <Modal open={connectorOpen} title="Add Universal Connector" onClose={() => setConnectorOpen(false)}>
        <form onSubmit={createConnector} className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <input className="field" required placeholder="Connector name" value={connectorForm.name} onChange={(event) => setConnectorForm({ ...connectorForm, name: event.target.value })} />
            <select className="field" value={connectorForm.category} onChange={(event) => setConnectorForm({ ...connectorForm, category: event.target.value })}>{connectorCategories.map((category) => <option key={category} value={category}>{category.replace("_", " ")}</option>)}</select>
            <input className="field" placeholder="Vendor or system" value={connectorForm.vendor} onChange={(event) => setConnectorForm({ ...connectorForm, vendor: event.target.value })} />
            <select className="field" value={connectorForm.project} onChange={(event) => setConnectorForm({ ...connectorForm, project: event.target.value })}><option value="">Company-wide</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
          </div>
          <input className="field" placeholder="Endpoint URL" value={connectorForm.endpoint_url} onChange={(event) => setConnectorForm({ ...connectorForm, endpoint_url: event.target.value })} />
          <div className="grid gap-4 sm:grid-cols-2">
            <input className="field" type="number" min="30" placeholder="Sync interval seconds" value={connectorForm.sync_interval_seconds} onChange={(event) => setConnectorForm({ ...connectorForm, sync_interval_seconds: event.target.value })} />
            <label className="flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-300">
              Optional AI enhancement
              <input type="checkbox" checked={connectorForm.ai_enhancement_enabled} onChange={(event) => setConnectorForm({ ...connectorForm, ai_enhancement_enabled: event.target.checked })} />
            </label>
          </div>
          <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setConnectorOpen(false)}>Cancel</Button><Button type="submit"><Cable size={16} />Create</Button></div>
        </form>
      </Modal>
    </Page>
  );
}
