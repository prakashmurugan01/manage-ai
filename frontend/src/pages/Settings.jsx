import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bell,
  Building2,
  CheckCircle,
  CheckCircle2,
  Clock3,
  Cloud,
  Eye,
  Globe2,
  KeyRound,
  Link2,
  Loader,
  LockKeyhole,
  MonitorCog,
  Palette,
  RadioTower,
  RefreshCw,
  Search,
  Server,
  Settings as SettingsIcon,
  ShieldCheck,
  Sparkles,
  Upload,
  UsersRound,
  Volume2,
  Zap
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";

import { api } from "../api/client.js";
import { navigation } from "../constants/navigation.js";
import { useAuth } from "../context/AuthContext.jsx";
import { THEMES, useTheme } from "../context/ThemeContext.jsx";
import { connectRealtime } from "../realtime/socket.js";
import { ROLE_LABELS } from "../utils/rbac.js";
import AvatarUpload from "../components/settings/AvatarUpload.jsx";
import ModuleControl from "../components/settings/ModuleControl.jsx";
import UserAccessManagement from "../components/settings/UserAccessManagement.jsx";
import AuthenticationSettings from "../components/settings/AuthenticationSettings.jsx";
import APIKeyManagement from "../components/settings/APIKeyManagement.jsx";
import CloudStorageSettings from "../components/settings/CloudStorageSettings.jsx";
import ServerFileAccess from "../components/settings/ServerFileAccess.jsx";
import SettingsAuditLog from "../components/settings/SettingsAuditLog.jsx";
import AdvancedTechSettings from "../components/settings/AdvancedTechSettings.jsx";

const TABS = [
  { id: "command", label: "Command", icon: Activity },
  { id: "general", label: "General", icon: Building2 },
  { id: "modules", label: "Modules", icon: MonitorCog },
  { id: "access", label: "Full Access", icon: UsersRound },
  { id: "links", label: "Page Links", icon: Link2 },
  { id: "realtime", label: "Realtime", icon: RadioTower },
  { id: "security", label: "Security", icon: ShieldCheck },
  { id: "hosting", label: "Hosting", icon: Cloud },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "ai", label: "AI", icon: Sparkles },
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "advanced", label: "Advanced", icon: Zap },
  { id: "audit", label: "Audit Logs", icon: Clock3 }
];

const timezones = ["Asia/Calcutta", "UTC", "America/New_York", "Europe/London", "Asia/Singapore"];
const accentColors = ["#f97316", "#ec4899", "#8b5cf6", "#06b6d4", "#10b981"];
const AUTO_REFRESH_MS = 8000;

const PAGE_MODULES = {
  "/dashboard": "ANALYTICS",
  "/hosting": "MONITORING",
  "/projects": "PROJECT_FILES",
  "/project-intelligence": "AI_CHATBOT",
  "/tickets": "TICKETS",
  "/api-keys": "CONNECTION_ENGINE",
  "/api-keys/chatbot": "AI_CHATBOT",
  "/api-keys/erp": "CONNECTION_ENGINE",
  "/server-monitor": "MONITORING",
  "/remote-access": "MONITORING",
  "/file-tracking": "PROJECT_FILES",
  "/hosting/deploy": "PROJECT_FILES",
  "/enterprise": "CONNECTION_ENGINE",
  "/notifications": "NOTIFICATIONS",
  "/users": "AUDIT",
  "/settings": "AUDIT",
  "/logs": "AUDIT",
  "/api-monitor": "ANALYTICS"
};

const ROLE_MODES = [
  {
    role: "SUPER_ADMIN",
    label: "Super Admin",
    detail: "Full platform control, settings, users, hosting, modules, audit, and access policy.",
    actions: ["VIEW", "CREATE", "EDIT", "DELETE", "ADMIN", "EXPORT"]
  },
  {
    role: "ADMIN",
    label: "Admin",
    detail: "Company operations, client/project controls, approvals, deployment, and monitoring.",
    actions: ["VIEW", "CREATE", "EDIT", "ADMIN", "EXPORT"]
  },
  {
    role: "DEVELOPER",
    label: "Developer",
    detail: "Assigned project work, files, tickets, deployment submission, and approved API tools.",
    actions: ["VIEW", "CREATE", "EDIT"]
  },
  {
    role: "CLIENT",
    label: "Client",
    detail: "Client portal access for project status, messages, files, approvals, and invoices.",
    actions: ["VIEW", "EXPORT"]
  }
];

export default function Settings() {
  const { user } = useAuth();
  const { theme, setTheme } = useTheme();
  const outlet = useOutletContext() || {};
  const shellEvents = outlet.events || [];
  const [activeTab, setActiveTab] = useState("command");
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notification, setNotification] = useState(null);
  const [liveStatus, setLiveStatus] = useState("connecting");
  const [lastRefresh, setLastRefresh] = useState(null);
  const [liveEvents, setLiveEvents] = useState([]);
  const [settings, setSettings] = useState({
    companyName: "ManageAI Enterprise",
    timezone: "Asia/Calcutta",
    mfa: true,
    sessionTimeout: 30,
    passwordMinLength: 12,
    emailAlerts: true,
    pushAlerts: true,
    smsAlerts: false,
    inAppAlerts: true,
    approvalAlerts: true,
    deploymentAlerts: true,
    autoRefresh: true,
    realtimeApply: true,
    aiModel: "smart-router",
    voiceEnabled: true,
    layout: "Comfortable",
    accentColor: "#f97316"
  });

  const modules = dashboardData?.modules || [];
  const health = dashboardData?.settings_health || {};
  const accessControls = dashboardData?.access_controls || [];
  const auditLogs = dashboardData?.recent_audit_logs || [];
  const features = dashboardData?.advanced_features || [];
  const storage = dashboardData?.storage_settings;
  const serverControl = dashboardData?.server_control;

  const healthScore = useMemo(() => {
    if (!modules.length) return 100;
    const moduleScore = (modules.filter((item) => item.is_enabled).length / modules.length) * 52;
    const featureScore = features.length ? (features.filter((item) => item.is_enabled).length / features.length) * 24 : 24;
    const storageScore = Math.max(0, 24 - Number(storage?.usage_percent || 0) * 0.24);
    return Math.round(Math.min(100, moduleScore + featureScore + storageScore));
  }, [features, modules, storage?.usage_percent]);

  const commandStats = useMemo(() => buildCommandStats({ modules, health, accessControls, auditLogs, features, serverControl, storage, healthScore }), [modules, health, accessControls, auditLogs, features, serverControl, storage, healthScore]);

  useEffect(() => {
    fetchDashboardData({ silent: false });
  }, []);

  useEffect(() => {
    if (!settings.autoRefresh) return undefined;
    const timer = window.setInterval(() => fetchDashboardData({ silent: true, reason: "Auto refresh" }), AUTO_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [settings.autoRefresh]);

  useEffect(() => {
    const socket = connectRealtime({
      onOpen: () => setLiveStatus("connected"),
      onClose: () => setLiveStatus("offline"),
      onMessage: (message) => handleRealtimeMessage(message, "socket")
    });
    if (!socket) setLiveStatus("offline");
    return () => socket?.close();
  }, [settings.realtimeApply]);

  useEffect(() => {
    const latest = shellEvents[0];
    if (latest) handleRealtimeMessage(latest, "shell");
  }, [shellEvents]);

  async function fetchDashboardData({ silent = false, reason = "Manual refresh" } = {}) {
    try {
      if (silent) setRefreshing(true);
      else setLoading(true);
      const response = await api.get("/settings/dashboard/");
      setDashboardData(response.data);
      setLastRefresh(new Date());
      setError(null);
      if (silent && reason !== "Auto refresh") pushLiveEvent({ type: "settings.refresh", title: reason, detail: "Settings dashboard synced." });
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load settings");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  function handleRealtimeMessage(message, source = "socket") {
    const title = realtimeTitle(message);
    pushLiveEvent({ type: message?.type || "event", title, detail: message?.message || message?.title || source });
    if (!settings.realtimeApply) return;
    if (isSettingsSignal(message)) {
      fetchDashboardData({ silent: true, reason: "Realtime update applied" });
      showNotification(`${title}. Settings updated automatically.`, "success");
    }
  }

  function pushLiveEvent(event) {
    setLiveEvents((items) => [{ ...event, at: new Date().toISOString() }, ...items].slice(0, 12));
  }

  function showNotification(message, type = "success") {
    setNotification({ message, type });
    window.setTimeout(() => setNotification(null), 3200);
  }

  function updateSetting(key, value) {
    setSettings((current) => ({ ...current, [key]: value }));
  }

  function saveLocalSection(label) {
    showNotification(`${label} settings saved`);
    pushLiveEvent({ type: "settings.local", title: `${label} saved`, detail: "Local preference layer updated." });
  }

  async function handleModuleToggle(module) {
    try {
      const existingModule = modules.find((item) => item.module === module.module);
      const response = await api.patch(`/settings/modules/${existingModule.id}/`, {
        is_enabled: !module.is_enabled
      });
      setDashboardData((prev) => ({
        ...prev,
        modules: prev.modules.map((item) => (item.id === response.data.id ? response.data : item))
      }));
      showNotification(`${module.module.replaceAll("_", " ")} ${response.data.is_enabled ? "enabled" : "disabled"}`);
      pushLiveEvent({
        type: "settings.module",
        title: `${module.module.replaceAll("_", " ")} ${response.data.is_enabled ? "enabled" : "disabled"}`,
        detail: "Access and page availability refreshed."
      });
      fetchDashboardData({ silent: true, reason: "Module state synced" });
    } catch {
      showNotification("Failed to update module", "error");
    }
  }

  async function setAllModules(enabled) {
    const targets = modules.filter((module) => module.is_enabled !== enabled);
    if (!targets.length) {
      showNotification(`All modules are already ${enabled ? "enabled" : "disabled"}`);
      return;
    }
    setBulkBusy(true);
    try {
      await Promise.all(targets.map((module) => api.patch(`/settings/modules/${module.id}/`, { is_enabled: enabled })));
      showNotification(`All modules ${enabled ? "enabled" : "disabled"}`);
      pushLiveEvent({ type: "settings.bulk", title: `Bulk ${enabled ? "enable" : "disable"}`, detail: `${targets.length} modules updated.` });
      fetchDashboardData({ silent: true, reason: "Bulk module sync" });
    } catch {
      showNotification("Failed to update all modules", "error");
    } finally {
      setBulkBusy(false);
    }
  }

  function togglePageModule(page) {
    const moduleKey = PAGE_MODULES[page.to];
    const module = modules.find((item) => item.module === moduleKey);
    if (!module) {
      showNotification("No module control is mapped to this page yet.", "error");
      return;
    }
    handleModuleToggle(module);
  }

  const renderContent = () => {
    if (loading) {
      return (
        <div className="grid min-h-80 place-items-center">
          <div className="text-center">
            <Loader className="mx-auto animate-spin text-[color:var(--primary)]" size={32} />
            <p className="mt-3 text-sm text-[color:var(--text-muted)]">Loading Settings Command Center</p>
          </div>
        </div>
      );
    }

    switch (activeTab) {
      case "command":
        return (
          <CommandCenter
            stats={commandStats}
            modules={modules}
            accessControls={accessControls}
            features={features}
            health={health}
            liveStatus={liveStatus}
            liveEvents={liveEvents}
            lastRefresh={lastRefresh}
            refreshing={refreshing}
            onRefresh={() => fetchDashboardData({ silent: true, reason: "Manual refresh" })}
            onSetTab={setActiveTab}
            onSetAllModules={setAllModules}
            bulkBusy={bulkBusy}
          />
        );
      case "general":
        return (
          <Section title="General" description="Company identity, logo, timezone, live update behavior, and system defaults.">
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Company Name">
                  <input className="form-control w-full" value={settings.companyName} onChange={(event) => updateSetting("companyName", event.target.value)} />
                </Field>
                <Field label="Timezone">
                  <select className="form-control w-full" value={settings.timezone} onChange={(event) => updateSetting("timezone", event.target.value)}>
                    {timezones.map((item) => <option key={item}>{item}</option>)}
                  </select>
                </Field>
                <Field label="Layout Density">
                  <select className="form-control w-full" value={settings.layout} onChange={(event) => updateSetting("layout", event.target.value)}>
                    <option>Comfortable</option>
                    <option>Compact</option>
                    <option>Spacious</option>
                  </select>
                </Field>
                <ToggleCard title="Auto Apply Realtime Updates" description="Refresh settings panels automatically when the platform receives a live settings event." enabled={settings.realtimeApply} onToggle={() => updateSetting("realtimeApply", !settings.realtimeApply)} icon={RadioTower} />
                <div className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4 sm:col-span-2">
                  <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-[color:var(--text-strong)]">
                    <Upload size={16} /> Logo
                  </div>
                  <AvatarUpload onUploadComplete={() => fetchDashboardData({ silent: true, reason: "Logo updated" })} />
                </div>
              </div>
              <StatusCard healthScore={healthScore} user={user} serverControl={serverControl} />
            </div>
            <SaveButton onClick={() => saveLocalSection("General")} />
          </Section>
        );
      case "modules":
        return (
          <Section title="Module Control" description="Enable or disable major system modules. Changes are audited and reflected across page access immediately.">
            <ControlStrip onSetAllModules={setAllModules} bulkBusy={bulkBusy} enabledCount={health.enabled_modules || modules.filter((item) => item.is_enabled).length} total={health.total_modules || modules.length} />
            <ModuleControl data={modules} onToggle={handleModuleToggle} />
          </Section>
        );
      case "access":
        return (
          <Section title="Full Access Control" description="Control user, role, client, developer, admin, and module actions from one place.">
            <AccessModeGrid accessControls={accessControls} />
            <div className="mt-5">
              <UserAccessManagement data={accessControls} onRefresh={() => fetchDashboardData({ silent: true, reason: "Access control synced" })} />
            </div>
          </Section>
        );
      case "links":
        return (
          <Section title="Page Link Control" description="Map every major page link to the module that controls it, then enable or disable access from Settings.">
            <PageLinkControl modules={modules} onToggle={togglePageModule} />
          </Section>
        );
      case "realtime":
        return (
          <Section title="Realtime Updates and Notifications" description="Seconds-level refresh, WebSocket signals, notification channels, and automatic settings sync.">
            <RealtimeOps
              settings={settings}
              updateSetting={updateSetting}
              liveStatus={liveStatus}
              liveEvents={liveEvents}
              lastRefresh={lastRefresh}
              refreshing={refreshing}
              onRefresh={() => fetchDashboardData({ silent: true, reason: "Realtime manual sync" })}
            />
            <SaveButton onClick={() => saveLocalSection("Realtime")} />
          </Section>
        );
      case "security":
        return (
          <Section title="Security" description="MFA, session timeout, password policy, JWT posture, and authentication controls.">
            <div className="grid gap-4 lg:grid-cols-3">
              <ToggleCard title="MFA" description="Require multi-factor authentication for privileged accounts." enabled={settings.mfa} onToggle={() => updateSetting("mfa", !settings.mfa)} />
              <Field label="Session Timeout">
                <div className="flex items-center gap-3">
                  <input className="form-control w-28" type="number" min="5" value={settings.sessionTimeout} onChange={(event) => updateSetting("sessionTimeout", event.target.value)} />
                  <span className="text-sm text-[color:var(--text-muted)]">minutes</span>
                </div>
              </Field>
              <Field label="Password Policy">
                <div className="flex items-center gap-3">
                  <LockKeyhole size={16} className="text-[color:var(--primary)]" />
                  <input className="form-control w-28" type="number" min="8" value={settings.passwordMinLength} onChange={(event) => updateSetting("passwordMinLength", event.target.value)} />
                  <span className="text-sm text-[color:var(--text-muted)]">min chars</span>
                </div>
              </Field>
            </div>
            <div className="mt-5">
              <AuthenticationSettings data={dashboardData?.auth_settings} onRefresh={() => fetchDashboardData({ silent: true, reason: "Auth settings synced" })} />
            </div>
          </Section>
        );
      case "hosting":
        return (
          <Section title="Hosting" description="API keys, provider tokens, cloud storage, and server file access.">
            <div className="grid gap-4 xl:grid-cols-2">
              <Panel title="API Keys" icon={KeyRound}><APIKeyManagement onRefresh={() => fetchDashboardData({ silent: true, reason: "API key settings synced" })} /></Panel>
              <Panel title="Provider Tokens" icon={Cloud}>
                <CloudStorageSettings data={dashboardData?.storage_settings} onRefresh={() => fetchDashboardData({ silent: true, reason: "Storage settings synced" })} />
              </Panel>
            </div>
            <div className="mt-4"><ServerFileAccess /></div>
          </Section>
        );
      case "notifications":
        return (
          <Section title="Notifications" description="Control email, push, SMS, approvals, deployments, and realtime browser alerts.">
            <NotificationMatrix settings={settings} updateSetting={updateSetting} />
            <SaveButton onClick={() => saveLocalSection("Notification")} />
          </Section>
        );
      case "ai":
        return (
          <Section title="AI" description="Model routing, voice settings, assistant behavior, automation readiness, and AI feature gates.">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Model Settings">
                <select className="form-control w-full" value={settings.aiModel} onChange={(event) => updateSetting("aiModel", event.target.value)}>
                  <option value="smart-router">OpenAI + Gemini Smart Router</option>
                  <option value="local">ManageAI Local</option>
                  <option value="gemini">Gemini</option>
                  <option value="openai">OpenAI</option>
                </select>
              </Field>
              <ToggleCard title="Voice Settings" description="Enable speech recognition and text-to-speech controls." enabled={settings.voiceEnabled} onToggle={() => updateSetting("voiceEnabled", !settings.voiceEnabled)} icon={Volume2} />
            </div>
            <FeatureGatePreview features={features} />
            <SaveButton onClick={() => saveLocalSection("AI")} />
          </Section>
        );
      case "appearance":
        return (
          <Section title="Appearance" description="Theme, accent colors, layout, and interface density.">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Theme">
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                  {Object.values(THEMES).map((item) => (
                    <button key={item} type="button" onClick={() => setTheme(item)} className={`rounded-lg border px-3 py-2 text-sm font-semibold capitalize transition ${theme === item ? "border-[color:var(--primary)] bg-[color:var(--surface-soft)] text-[color:var(--text-strong)]" : "border-[color:var(--border)] text-[color:var(--text-muted)] hover:text-[color:var(--text-strong)]"}`}>
                      {item}
                    </button>
                  ))}
                </div>
              </Field>
              <Field label="Accent Colors">
                <div className="flex flex-wrap gap-2">
                  {accentColors.map((color) => (
                    <button key={color} type="button" onClick={() => updateSetting("accentColor", color)} className={`h-10 w-10 rounded-lg border-2 ${settings.accentColor === color ? "border-white" : "border-transparent"}`} style={{ backgroundColor: color }} aria-label={`Use accent ${color}`} />
                  ))}
                </div>
              </Field>
            </div>
            <SaveButton onClick={() => saveLocalSection("Appearance")} />
          </Section>
        );
      case "advanced":
        return (
          <div className="space-y-5">
            <AdvancedTechSettings
              features={features}
              health={health}
              serverControl={serverControl}
              onRefresh={() => fetchDashboardData({ silent: true, reason: "Advanced controls synced" })}
              onNotify={showNotification}
            />
          </div>
        );
      case "audit":
        return <SettingsAuditLog logs={auditLogs} />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6 text-[color:var(--text)]">
      <section className="relative overflow-hidden rounded-lg border border-[color:var(--border)] bg-[color:var(--surface)] p-5 shadow-[var(--shadow)]">
        <div className="pointer-events-none absolute inset-0 role-hero-overlay opacity-70" />
        <div className="relative grid gap-5 xl:grid-cols-[1fr_auto] xl:items-center">
          <div className="flex items-center gap-3">
            <div className="grid h-12 w-12 place-items-center rounded-lg bg-gradient-to-br from-orange-500 to-pink-600 text-white shadow-lg">
              <SettingsIcon size={24} />
            </div>
            <div>
              <h1 className="text-3xl font-black text-[color:var(--text-strong)]">Settings Command Center</h1>
              <p className="text-sm text-[color:var(--text-muted)]">Enterprise controls for access, modules, page links, realtime updates, notifications, hosting, AI, and audit.</p>
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <HeaderPill label="System Health" value={`${healthScore}%`} tone={healthScore >= 80 ? "green" : "amber"} />
            <HeaderPill label="Realtime" value={liveStatus} tone={liveStatus === "connected" ? "green" : "amber"} />
            <button type="button" onClick={() => fetchDashboardData({ silent: true, reason: "Manual refresh" })} className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] px-4 py-3 text-left text-sm transition hover:border-[color:var(--border-strong)]">
              <span className="block text-[color:var(--text-muted)]">Last Sync</span>
              <strong className="mt-1 inline-flex items-center gap-2 text-[color:var(--text-strong)]">
                <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
                {lastRefresh ? lastRefresh.toLocaleTimeString() : "Sync now"}
              </strong>
            </button>
          </div>
        </div>
      </section>

      {notification && (
        <div className={`flex items-center gap-3 rounded-lg border p-4 ${notification.type === "success" ? "border-emerald-500/30 bg-emerald-500/12 text-emerald-200" : "border-red-500/30 bg-red-500/12 text-red-200"}`}>
          {notification.type === "success" ? <CheckCircle size={20} /> : <AlertTriangle size={20} />}
          {notification.message}
        </div>
      )}

      {error && <div className="rounded-lg border border-red-500/30 bg-red-500/12 p-4 text-red-200">{error}</div>}

      <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
        <nav className="rounded-lg border border-[color:var(--border)] bg-[color:var(--surface)] p-2 shadow-[var(--shadow-soft)]">
          <div className="mb-2 rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-3">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[color:var(--text-muted)]">Full Control</p>
            <p className="mt-1 text-sm font-semibold text-[color:var(--text-strong)]">{ROLE_LABELS[user?.role] || user?.role || "Admin"}</p>
          </div>
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setActiveTab(id)}
              className={`mb-1 flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm font-semibold transition ${
                activeTab === id ? "bg-[color:var(--surface-soft)] text-[color:var(--text-strong)] ring-1 ring-[color:var(--border-strong)]" : "text-[color:var(--text-muted)] hover:bg-[color:var(--soft-card-bg)] hover:text-[color:var(--text-strong)]"
              }`}
            >
              <Icon size={17} />
              {label}
            </button>
          ))}
        </nav>
        <main className="min-w-0 rounded-lg border border-[color:var(--border)] bg-[color:var(--surface)] p-5 shadow-[var(--shadow-soft)]">
          {renderContent()}
        </main>
      </div>
    </div>
  );
}

function CommandCenter({ stats, modules, accessControls, features, liveStatus, liveEvents, lastRefresh, refreshing, onRefresh, onSetTab, onSetAllModules, bulkBusy }) {
  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-2xl font-black text-[color:var(--text-strong)]">Live Platform Control</h2>
        <p className="mt-1 text-sm text-[color:var(--text-muted)]">Monitor every critical setting, access rule, live signal, and module switch from one surface.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => <CommandStat key={stat.label} {...stat} />)}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_0.85fr]">
        <div className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <PanelHeading icon={MonitorCog} title="Instant Module Operations" subtitle="Global enable/disable with audit and access refresh." />
            <div className="flex flex-wrap gap-2">
              <button disabled={bulkBusy} type="button" onClick={() => onSetAllModules(true)} className="btn-secondary">
                <CheckCircle2 size={16} />
                Enable All
              </button>
              <button disabled={bulkBusy} type="button" onClick={() => onSetAllModules(false)} className="btn-secondary">
                <AlertTriangle size={16} />
                Disable All
              </button>
            </div>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {modules.slice(0, 6).map((module) => (
              <button key={module.id} type="button" onClick={() => onSetTab("modules")} className="rounded-lg border border-[color:var(--border)] bg-[color:var(--surface)] p-3 text-left transition hover:border-[color:var(--border-strong)]">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-[color:var(--text-strong)]">{labelize(module.module)}</span>
                  <StatusDot enabled={module.is_enabled} />
                </div>
                <p className="mt-1 line-clamp-2 text-xs text-[color:var(--text-muted)]">{module.description || "Module access control"}</p>
              </button>
            ))}
          </div>
        </div>
        <LiveSignalCard liveStatus={liveStatus} liveEvents={liveEvents} lastRefresh={lastRefresh} refreshing={refreshing} onRefresh={onRefresh} />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <QuickAction icon={UsersRound} title="Full User Access" detail={`${accessControls.length} granular rules configured`} onClick={() => onSetTab("access")} />
        <QuickAction icon={Link2} title="Page Link Controls" detail="Enable or disable module-backed page access" onClick={() => onSetTab("links")} />
        <QuickAction icon={Sparkles} title="Power Features" detail={`${features.filter((item) => item.is_enabled).length}/${features.length || 0} advanced features active`} onClick={() => onSetTab("advanced")} />
      </div>
    </section>
  );
}

function ControlStrip({ onSetAllModules, bulkBusy, enabledCount, total }) {
  return (
    <div className="mb-5 grid gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4 lg:grid-cols-[1fr_auto] lg:items-center">
      <div>
        <p className="text-sm font-semibold text-[color:var(--text-strong)]">Global module gate</p>
        <p className="mt-1 text-sm text-[color:var(--text-muted)]">{enabledCount}/{total} modules enabled. Changes affect navigation access and operational availability.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button disabled={bulkBusy} type="button" onClick={() => onSetAllModules(true)} className="btn-primary">
          <CheckCircle2 size={16} />
          Full Enable
        </button>
        <button disabled={bulkBusy} type="button" onClick={() => onSetAllModules(false)} className="btn-secondary">
          <AlertTriangle size={16} />
          Lock Down
        </button>
      </div>
    </div>
  );
}

function AccessModeGrid({ accessControls }) {
  return (
    <div className="grid gap-4 xl:grid-cols-4">
      {ROLE_MODES.map((mode) => {
        const count = accessControls.filter((item) => item.role === mode.role || item.user_detail?.role === mode.role).length;
        return (
          <div key={mode.role} className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-lg bg-[color:var(--surface-soft)] text-[color:var(--primary)]">
                <UsersRound size={19} />
              </div>
              <span className="rounded-full bg-white/10 px-2 py-1 text-xs font-semibold text-[color:var(--text-muted)]">{count} rules</span>
            </div>
            <h3 className="mt-3 text-sm font-bold text-[color:var(--text-strong)]">{mode.label}</h3>
            <p className="mt-2 min-h-16 text-sm leading-6 text-[color:var(--text-muted)]">{mode.detail}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {mode.actions.map((action) => <span key={action} className="rounded-full border border-[color:var(--border)] px-2 py-1 text-[11px] font-semibold text-[color:var(--text-muted)]">{action}</span>)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PageLinkControl({ modules, onToggle }) {
  const [query, setQuery] = useState("");
  const filtered = navigation.filter((item) => `${item.label} ${item.to}`.toLowerCase().includes(query.toLowerCase()));
  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-semibold text-[color:var(--text-strong)]">All page links update automatically from module state</p>
          <p className="mt-1 text-sm text-[color:var(--text-muted)]">Disable a mapped module here and the related page is treated as locked by Settings policy.</p>
        </div>
        <label className="flex min-w-0 items-center gap-2 rounded-lg border border-[color:var(--border)] bg-[color:var(--surface)] px-3 py-2">
          <Search size={16} className="text-[color:var(--text-muted)]" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} className="min-w-0 bg-transparent text-sm outline-none" placeholder="Search pages" />
        </label>
      </div>
      <div className="grid gap-3">
        {filtered.map((item) => {
          const moduleKey = PAGE_MODULES[item.to];
          const module = modules.find((entry) => entry.module === moduleKey);
          const enabled = module ? module.is_enabled : true;
          const Icon = item.icon || Globe2;
          return (
            <div key={item.to} className="grid gap-3 rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4 lg:grid-cols-[1fr_auto_auto] lg:items-center">
              <div className="flex min-w-0 items-center gap-3">
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-[color:var(--surface-soft)] text-[color:var(--primary)]">
                  <Icon size={18} />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-[color:var(--text-strong)]">{item.label}</p>
                  <p className="truncate text-xs text-[color:var(--text-muted)]">{item.to}</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full bg-white/10 px-2 py-1 text-[color:var(--text-muted)]">{moduleKey ? labelize(moduleKey) : "Always visible"}</span>
                <span className="rounded-full bg-white/10 px-2 py-1 text-[color:var(--text-muted)]">{item.roles?.map((role) => ROLE_LABELS[role] || role).join(", ") || "All roles"}</span>
              </div>
              <button type="button" disabled={!module} onClick={() => onToggle(item)} className={`inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition disabled:opacity-50 ${enabled ? "bg-emerald-500/15 text-emerald-200" : "bg-red-500/15 text-red-200"}`}>
                <StatusDot enabled={enabled} />
                {enabled ? "Enabled" : "Disabled"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RealtimeOps({ settings, updateSetting, liveStatus, liveEvents, lastRefresh, refreshing, onRefresh }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[0.9fr_1fr]">
      <div className="space-y-4">
        <ToggleCard title="Auto Refresh Every Few Seconds" description={`Reload dashboard state every ${AUTO_REFRESH_MS / 1000} seconds so settings stay current.`} enabled={settings.autoRefresh} onToggle={() => updateSetting("autoRefresh", !settings.autoRefresh)} icon={RefreshCw} />
        <ToggleCard title="Realtime Auto Apply" description="Apply live WebSocket settings updates immediately without manual refresh." enabled={settings.realtimeApply} onToggle={() => updateSetting("realtimeApply", !settings.realtimeApply)} icon={RadioTower} />
        <ToggleCard title="In-App Notification Feed" description="Show settings and platform updates inside this command center." enabled={settings.inAppAlerts} onToggle={() => updateSetting("inAppAlerts", !settings.inAppAlerts)} icon={Bell} />
      </div>
      <LiveSignalCard liveStatus={liveStatus} liveEvents={liveEvents} lastRefresh={lastRefresh} refreshing={refreshing} onRefresh={onRefresh} />
    </div>
  );
}

function NotificationMatrix({ settings, updateSetting }) {
  const rows = [
    ["emailAlerts", "Email Alerts", "Send operational alerts by email.", Bell],
    ["pushAlerts", "Push Alerts", "Realtime browser and app notifications.", RadioTower],
    ["smsAlerts", "SMS Alerts", "Critical incidents and approval escalations.", Bell],
    ["approvalAlerts", "Approval Alerts", "Project, task, client, and file approval changes.", CheckCircle2],
    ["deploymentAlerts", "Deployment Alerts", "Hosting, server, deploy, and outage notifications.", Server],
    ["inAppAlerts", "In-App Feed", "Show instant alerts inside Settings and the top bar.", Activity]
  ];
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {rows.map(([key, title, detail, Icon]) => (
        <ToggleCard key={key} title={title} description={detail} enabled={settings[key]} onToggle={() => updateSetting(key, !settings[key])} icon={Icon} />
      ))}
    </div>
  );
}

function FeatureGatePreview({ features }) {
  return (
    <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {features.slice(0, 6).map((feature) => (
        <div key={feature.id} className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-[color:var(--text-strong)]">{feature.label}</p>
            <StatusDot enabled={feature.is_enabled} />
          </div>
          <p className="mt-2 text-xs leading-5 text-[color:var(--text-muted)]">{feature.config?.description || "Advanced platform feature gate."}</p>
        </div>
      ))}
    </div>
  );
}

function LiveSignalCard({ liveStatus, liveEvents, lastRefresh, refreshing, onRefresh }) {
  return (
    <div className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PanelHeading icon={RadioTower} title="Realtime Operations Feed" subtitle="Live platform events and automatic settings refresh state." />
        <button type="button" onClick={onRefresh} className="btn-secondary">
          <RefreshCw size={16} className={refreshing ? "animate-spin" : ""} />
          Sync
        </button>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <InfoPill label="Socket" value={liveStatus} tone={liveStatus === "connected" ? "green" : "amber"} />
        <InfoPill label="Last Refresh" value={lastRefresh ? lastRefresh.toLocaleTimeString() : "Pending"} />
      </div>
      <div className="mt-4 max-h-72 space-y-2 overflow-y-auto pr-1 scrollbar-thin">
        {liveEvents.map((event) => (
          <div key={`${event.at}-${event.title}`} className="rounded-lg border border-[color:var(--border)] bg-[color:var(--surface)] p-3">
            <div className="flex items-center justify-between gap-3">
              <p className="truncate text-sm font-semibold text-[color:var(--text-strong)]">{event.title}</p>
              <span className="text-[11px] text-[color:var(--text-muted)]">{new Date(event.at).toLocaleTimeString()}</span>
            </div>
            <p className="mt-1 line-clamp-2 text-xs text-[color:var(--text-muted)]">{event.detail}</p>
          </div>
        ))}
        {!liveEvents.length && <EmptyState title="Waiting for events" detail="Settings events, notifications, and websocket updates appear here." />}
      </div>
    </div>
  );
}

function Section({ title, description, children }) {
  return (
    <section>
      <div className="mb-5">
        <h2 className="text-2xl font-black text-[color:var(--text-strong)]">{title}</h2>
        <p className="mt-1 text-sm text-[color:var(--text-muted)]">{description}</p>
      </div>
      {children}
    </section>
  );
}

function Panel({ title, icon: Icon, children }) {
  return (
    <section className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4">
      <div className="mb-4 flex items-center gap-2 text-sm font-bold text-[color:var(--text-strong)]">
        <Icon size={17} />
        {title}
      </div>
      {children}
    </section>
  );
}

function PanelHeading({ icon: Icon, title, subtitle }) {
  return (
    <div>
      <div className="flex items-center gap-2 text-sm font-bold text-[color:var(--text-strong)]">
        <Icon size={17} className="text-[color:var(--primary)]" />
        {title}
      </div>
      {subtitle && <p className="mt-1 text-sm text-[color:var(--text-muted)]">{subtitle}</p>}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4">
      <span className="mb-2 block text-xs font-bold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">{label}</span>
      {children}
    </label>
  );
}

function ToggleCard({ title, description, enabled, onToggle, icon: Icon = ShieldCheck }) {
  return (
    <div className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 font-semibold text-[color:var(--text-strong)]"><Icon size={17} /> {title}</div>
          <p className="mt-2 text-sm leading-6 text-[color:var(--text-muted)]">{description}</p>
        </div>
        <button type="button" onClick={onToggle} className="toggle-switch shrink-0" data-state={enabled ? "on" : "off"} aria-label={`Toggle ${title}`}>
          <span className="toggle-knob">{enabled ? "On" : "Off"}</span>
        </button>
      </div>
    </div>
  );
}

function StatusCard({ healthScore, user, serverControl }) {
  return (
    <aside className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4">
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">Control Summary</p>
      <div className="mt-4 grid gap-3">
        <SummaryRow label="Health" value={`${healthScore}%`} />
        <SummaryRow label="Role" value={ROLE_LABELS[user?.role] || user?.role || "User"} />
        <SummaryRow label="Approval" value={user?.approval_status || "APPROVED"} />
        <SummaryRow label="Server" value={serverControl?.health || "STABLE"} />
        <SummaryRow label="Scale" value={`${serverControl?.scale_units || 1} units`} />
      </div>
    </aside>
  );
}

function SaveButton({ onClick }) {
  return (
    <div className="mt-5 flex justify-end">
      <button type="button" onClick={onClick} className="btn-primary">Save changes</button>
    </div>
  );
}

function CommandStat({ icon: Icon, label, value, detail, tone = "cyan" }) {
  const tones = {
    cyan: "text-cyan-300 bg-cyan-400/10",
    green: "text-emerald-300 bg-emerald-400/10",
    amber: "text-amber-300 bg-amber-400/10",
    rose: "text-rose-300 bg-rose-400/10",
    violet: "text-violet-300 bg-violet-400/10"
  };
  return (
    <div className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4">
      <div className={`grid h-10 w-10 place-items-center rounded-lg ${tones[tone] || tones.cyan}`}>
        <Icon size={19} />
      </div>
      <p className="mt-3 text-xs font-bold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">{label}</p>
      <p className="mt-1 text-2xl font-black text-[color:var(--text-strong)]">{value}</p>
      <p className="mt-1 text-xs text-[color:var(--text-muted)]">{detail}</p>
    </div>
  );
}

function HeaderPill({ label, value, tone = "cyan" }) {
  return (
    <div className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] px-4 py-3 text-sm">
      <span className="block text-[color:var(--text-muted)]">{label}</span>
      <strong className={`mt-1 inline-flex capitalize ${tone === "green" ? "text-emerald-300" : tone === "amber" ? "text-amber-300" : "text-[color:var(--text-strong)]"}`}>{value}</strong>
    </div>
  );
}

function QuickAction({ icon: Icon, title, detail, onClick }) {
  return (
    <button type="button" onClick={onClick} className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4 text-left transition hover:border-[color:var(--border-strong)] hover:bg-[color:var(--surface-soft)]">
      <Icon size={20} className="text-[color:var(--primary)]" />
      <p className="mt-3 text-sm font-bold text-[color:var(--text-strong)]">{title}</p>
      <p className="mt-1 text-sm text-[color:var(--text-muted)]">{detail}</p>
    </button>
  );
}

function InfoPill({ label, value, tone = "cyan" }) {
  return (
    <div className="rounded-lg border border-[color:var(--border)] bg-[color:var(--surface)] p-3">
      <p className="text-xs uppercase tracking-[0.14em] text-[color:var(--text-muted)]">{label}</p>
      <p className={`mt-1 text-sm font-semibold capitalize ${tone === "green" ? "text-emerald-300" : tone === "amber" ? "text-amber-300" : "text-[color:var(--text-strong)]"}`}>{value}</p>
    </div>
  );
}

function SummaryRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-[color:var(--text-muted)]">{label}</span>
      <strong className="text-right text-[color:var(--text-strong)]">{value}</strong>
    </div>
  );
}

function StatusDot({ enabled }) {
  return <span className={`h-2.5 w-2.5 rounded-full ${enabled ? "bg-emerald-300 shadow-[0_0_18px_rgba(52,211,153,0.6)]" : "bg-rose-300"}`} />;
}

function EmptyState({ title, detail }) {
  return (
    <div className="rounded-lg border border-dashed border-[color:var(--border)] bg-[color:var(--surface)] p-4 text-center">
      <p className="text-sm font-semibold text-[color:var(--text-strong)]">{title}</p>
      <p className="mt-1 text-sm text-[color:var(--text-muted)]">{detail}</p>
    </div>
  );
}

function buildCommandStats({ modules, health, accessControls, auditLogs, features, serverControl, storage, healthScore }) {
  const enabledModules = health.enabled_modules ?? modules.filter((item) => item.is_enabled).length;
  const totalModules = health.total_modules ?? modules.length;
  const enabledFeatures = features.filter((item) => item.is_enabled).length;
  const validAccess = accessControls.filter((item) => item.is_valid !== false && item.is_enabled !== false).length;
  return [
    { icon: ShieldCheck, label: "System Health", value: `${healthScore}%`, detail: "Modules, storage, and feature posture", tone: healthScore >= 80 ? "green" : "amber" },
    { icon: MonitorCog, label: "Modules Online", value: `${enabledModules}/${totalModules}`, detail: "Global feature access gates", tone: enabledModules === totalModules ? "green" : "amber" },
    { icon: UsersRound, label: "Access Rules", value: validAccess, detail: `${accessControls.length} total role/user grants`, tone: "violet" },
    { icon: Sparkles, label: "Power Features", value: `${enabledFeatures}/${features.length || 0}`, detail: "AI, realtime, audit, backup controls", tone: "cyan" },
    { icon: Server, label: "Platform Scale", value: `${serverControl?.scale_units || 1}x`, detail: `${serverControl?.health || "STABLE"} / ${serverControl?.active_users || 0} users`, tone: "green" },
    { icon: Cloud, label: "Storage Usage", value: `${Number(storage?.usage_percent || 0).toFixed(1)}%`, detail: `${storage?.provider || "LOCAL"} provider`, tone: Number(storage?.usage_percent || 0) > 80 ? "rose" : "cyan" },
    { icon: Clock3, label: "Recent Changes", value: auditLogs.length, detail: "Settings audit events loaded", tone: "amber" },
    { icon: Globe2, label: "Page Links", value: navigation.length, detail: "Navigation links mapped to settings", tone: "violet" }
  ];
}

function isSettingsSignal(message) {
  const type = String(message?.type || "").toLowerCase();
  return type.includes("settings")
    || type.includes("feature")
    || type.includes("module")
    || type.includes("access")
    || type.includes("auth")
    || type.includes("storage")
    || type.includes("notification");
}

function realtimeTitle(message) {
  const type = String(message?.type || "Realtime event").replaceAll("_", " ").replaceAll(".", " / ");
  if (message?.title) return message.title;
  if (message?.module) return `${labelize(message.module)} updated`;
  return type;
}

function labelize(value) {
  return String(value || "None").replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}
