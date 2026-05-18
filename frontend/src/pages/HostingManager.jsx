import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format, parseISO } from "date-fns";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate, useParams } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  Bell,
  CheckCircle2,
  ChevronDown,
  Cloud,
  Download,
  Edit3,
  ExternalLink,
  Globe2,
  LayoutDashboard,
  Loader2,
  Pause,
  Play,
  RefreshCcw,
  Rocket,
  Search,
  Server,
  Settings,
  ShieldCheck,
  TerminalSquare,
  Trash2,
  WifiOff,
  X,
  Zap
} from "lucide-react";
import { Area, AreaChart, Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api, apiErrorMessage, listFrom } from "../api/client.js";
import { fetchNetlifyStatus, redeployNetlify } from "../api/netlify.js";
import NetlifyCard, { NetlifyDetailsPanel } from "../components/hosting/NetlifyCard.jsx";
import Modal from "../components/ui/Modal.jsx";

const PLATFORM_CONFIG = {
  aws: {
    id: "aws",
    name: "AWS",
    label: "EC2, S3 and CloudFront",
    icon: Server,
    providers: ["aws", "aws_s3", "aws_cloudfront"],
    accent: "from-orange-400 to-amber-300"
  },
  hostinger: providerConfig("hostinger", "Hostinger", "Shared hosting and email", Server, "from-violet-400 to-fuchsia-400"),
  scalahosting: providerConfig("scalahosting", "ScalaHosting", "Managed VPS hosting", Server, "from-sky-300 to-blue-500"),
  siteground: providerConfig("siteground", "SiteGround", "Managed web hosting", Cloud, "from-cyan-300 to-teal-400"),
  bluehost: providerConfig("bluehost", "Bluehost", "WordPress hosting", Globe2, "from-blue-400 to-indigo-500"),
  godaddy: providerConfig("godaddy", "GoDaddy", "Domains and hosting", Globe2, "from-emerald-300 to-cyan-400"),
  hostgator: providerConfig("hostgator", "HostGator", "Shared hosting", Server, "from-amber-300 to-orange-400"),
  cyberin: providerConfig("cyberin", "Cyberin", "India hosting", Cloud, "from-rose-300 to-pink-500"),
  hostingraja: providerConfig("hostingraja", "HostingRaja", "India web hosting", Server, "from-orange-300 to-red-400"),
  bigrock: providerConfig("bigrock", "BigRock", "Domains and hosting", Globe2, "from-lime-300 to-emerald-500"),
  hosting_home: providerConfig("hosting_home", "Hosting Home", "Regional hosting", Server, "from-slate-200 to-sky-300"),
  cloudways: providerConfig("cloudways", "Cloudways", "Managed cloud hosting", Cloud, "from-teal-300 to-cyan-500"),
  digitalocean: providerConfig("digitalocean", "DigitalOcean", "Droplets and cloud apps", Server, "from-blue-300 to-sky-500"),
  vercel: providerConfig("vercel", "Vercel", "Frontend deployments", Rocket, "from-slate-200 to-cyan-300"),
  netlify: providerConfig("netlify", "Netlify", "Frontend hosting & CI/CD deployments", Rocket, "from-teal-300 via-cyan-300 to-emerald-400"),
  dns: {
    id: "dns",
    name: "DNS / Cloudflare",
    label: "Domains and edge routing",
    icon: Globe2,
    providers: ["cloudflare", "dns", "custom"],
    accent: "from-cyan-300 to-blue-500"
  }
};

const pageVariants = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.42, ease: "easeInOut" } }
};

const staggerContainer = {
  animate: { transition: { staggerChildren: 0.055, delayChildren: 0.04 } }
};

const cardVariants = {
  initial: { opacity: 0, y: 18, scale: 0.98 },
  animate: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.34, ease: "easeInOut" } }
};

const TABS = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "projects", label: "Projects", icon: Server },
  { id: "logs", label: "Logs", icon: TerminalSquare },
  { id: "settings", label: "Settings", icon: Settings }
];

const emptyForm = {
  client_name: "",
  name: "",
  domain: "",
  hosting_platform: "vercel",
  deploy_url: "",
  server_ip: "",
  access_key: "",
  status: "live",
  tag: "active",
  link_is_active: true,
  check_interval_seconds: 60,
  start_date: new Date().toISOString().slice(0, 10),
  expiry_date: nextYear(),
  monthly_cost: "0",
  notes: ""
};

export default function HostingManager() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { provider: routeProvider } = useParams();
  const [selectedPlatform, setSelectedPlatform] = useState(PLATFORM_CONFIG[routeProvider] ? routeProvider : "aws");
  const [activeTab, setActiveTab] = useState("overview");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [platformFilter, setPlatformFilter] = useState("all");
  const [editing, setEditing] = useState(null);
  const [logProject, setLogProject] = useState(null);
  const [deleteProject, setDeleteProject] = useState(null);
  const [projectActions, setProjectActions] = useState({});

  const projects = useQuery({
    queryKey: ["hosting-manager-projects"],
    queryFn: () => api.get("/hosting/").then(listFrom),
    refetchInterval: 5000
  });
  const summary = useQuery({
    queryKey: ["hosting-manager-summary"],
    queryFn: () => api.get("/hosting/summary/").then((res) => res.data),
    refetchInterval: 5000
  });
  const dashboard = useQuery({
    queryKey: ["hosting-manager-dashboard"],
    queryFn: () => api.get("/hosting/dashboard/").then((res) => res.data),
    refetchInterval: 5000
  });
  const hostingLinks = useQuery({
    queryKey: ["hosting-manager-links"],
    queryFn: () => api.get("/hosting/links/").then(listFrom),
    refetchInterval: 5000
  });
  const hostingProviders = useQuery({
    queryKey: ["hosting-manager-providers"],
    queryFn: () => api.get("/hosting/providers/").then(listFrom),
    refetchInterval: 5000
  });
  const vercelProjects = useQuery({
    queryKey: ["hosting-manager-vercel-projects"],
    queryFn: () => api.get("/vercel/projects/").then(listFrom),
    refetchInterval: 5000
  });
  const netlifyStatus = useQuery({
    queryKey: ["hosting-manager-netlify-status"],
    queryFn: fetchNetlifyStatus,
    refetchInterval: 5000
  });
  const universalOverview = useQuery({
    queryKey: ["hosting-manager-universal"],
    queryFn: () => api.get("/hosting/universal-overview/").then((res) => res.data),
    refetchInterval: 5000
  });

  useEffect(() => {
    if (routeProvider && PLATFORM_CONFIG[routeProvider]) {
      setSelectedPlatform(routeProvider);
      setActiveTab("projects");
    }
  }, [routeProvider]);

  const invalidate = () => {
    ["hosting-manager-projects", "hosting-manager-summary", "hosting-manager-dashboard", "hosting-manager-links", "hosting-manager-providers", "hosting-manager-vercel-projects", "hosting-manager-netlify-status", "hosting-manager-universal"].forEach((key) => {
      qc.invalidateQueries({ queryKey: [key] });
    });
  };

  const saveProject = useMutation({
    mutationFn: (payload) => {
      const body = cleanPayload(payload);
      return payload.id ? api.patch(`/hosting/${payload.id}/`, body) : api.post("/hosting/", body);
    },
    onSuccess: () => {
      invalidate();
      setEditing(null);
    }
  });
  const toggleProject = useMutation({
    mutationFn: ({ project, link_is_active }) => {
      const provider = controlProviderFor(project);
      const action = link_is_active ? "start" : "stop";
      if (supportsProviderControls(provider)) {
        return api.post(`/hosting/providers/${provider}/projects/${project.id}/${action}/`);
      }
      return api.post(`/hosting/${project.id}/toggle_link/`, { link_is_active });
    },
    onMutate: ({ project, link_is_active }) => {
      setProjectActions((current) => ({ ...current, [project.id]: link_is_active ? "Starting..." : "Stopping..." }));
    },
    onSuccess: (_, variables) => {
      toast("success", variables.link_is_active ? "Starting..." : "Stopping...");
      invalidate();
    },
    onError: (error) => toast("error", apiErrorMessage(error, "Server control failed.")),
    onSettled: (_, __, variables) => {
      window.setTimeout(() => {
        setProjectActions((current) => {
          const next = { ...current };
          delete next[variables.project.id];
          return next;
        });
      }, 900);
    }
  });
  const restartProject = useMutation({
    mutationFn: (project) => {
      const provider = controlProviderFor(project);
      if (supportsProviderControls(provider)) {
        return api.post(`/hosting/providers/${provider}/projects/${project.id}/restart/`);
      }
      return api.post(`/hosting/${project.id}/health-check/`);
    },
    onMutate: (project) => {
      setProjectActions((current) => ({ ...current, [project.id]: "Restarting..." }));
    },
    onSuccess: () => {
      toast("success", "Restart requested.");
      invalidate();
    },
    onError: (error) => toast("error", apiErrorMessage(error, "Restart failed.")),
    onSettled: (_, __, project) => {
      window.setTimeout(() => {
        setProjectActions((current) => {
          const next = { ...current };
          delete next[project.id];
          return next;
        });
      }, 900);
    }
  });
  const deleteHostedProject = useMutation({
    mutationFn: (id) => api.delete(`/hosting/${id}/`),
    onSuccess: () => {
      invalidate();
      setDeleteProject(null);
    }
  });
  const renewProject = useMutation({
    mutationFn: (project) => api.post(`/hosting/${project.id}/renew/`, { new_expiry: nextYear(project.expiry_date), notes: "Renewed from Hosting Manager" }),
    onSuccess: invalidate
  });
  const syncProviders = useMutation({ mutationFn: () => api.post("/hosting/providers/sync/"), onSuccess: invalidate });
  const syncVercel = useMutation({ mutationFn: () => api.post("/vercel/projects/sync/"), onSuccess: invalidate });
  const toggleHostingLink = useMutation({
    mutationFn: ({ id, enabled }) => api.post(`/hosting/links/${id}/toggle/`, { enabled }),
    onSuccess: invalidate
  });
  const redeployVercel = useMutation({
    mutationFn: ({ id, deployment_id }) => api.post(`/vercel/projects/${id}/redeploy/`, { deployment_id }),
    onSuccess: invalidate
  });
  const redeployProviderProject = useMutation({
    mutationFn: (project) => api.post(`/hosting/providers/${controlProviderFor(project)}/projects/${project.id}/redeploy/`),
    onSuccess: () => {
      toast("success", "Redeploy requested.");
      invalidate();
    },
    onError: (error) => toast("error", apiErrorMessage(error, "Redeploy failed."))
  });
  const redeployNetlifySite = useMutation({
    mutationFn: (siteId) => redeployNetlify(siteId),
    onSuccess: invalidate
  });

  const rows = projects.data || [];
  const links = hostingLinks.data || [];
  const providers = hostingProviders.data || [];
  const selected = PLATFORM_CONFIG[selectedPlatform];
  const isDetailsRoute = Boolean(routeProvider && PLATFORM_CONFIG[routeProvider]);
  const globalLoading = projects.isLoading || hostingLinks.isLoading || hostingProviders.isLoading || (selectedPlatform === "vercel" && vercelProjects.isLoading) || (selectedPlatform === "netlify" && netlifyStatus.isLoading);
  const selectedError = selectedPlatform === "netlify" ? netlifyStatus.error : selectedPlatform === "vercel" ? vercelProjects.error : selectedPlatform === "dns" ? universalOverview.error : hostingProviders.error || hostingLinks.error;

  const platformModels = useMemo(() => {
    return Object.values(PLATFORM_CONFIG).map((platform) => {
      const platformProjects = rows.filter((project) => platformMatches(project.hosting_platform, platform));
      const platformLinks = links.filter((link) => platform.providers.includes(link.provider));
      const platformProviders = providers.filter((provider) => platform.providers.includes(provider.provider));
      const apiErrors = platformProviders.filter((provider) => provider.last_error);
      const down = platformProjects.filter(isDown).length + platformLinks.filter((link) => link.health_status === "down").length;
      const active = platformProjects.filter((project) => project.link_is_active && !isDown(project)).length + platformLinks.filter((link) => link.is_active || link.status === "on").length;
      const uptime = average([...platformProjects.map((project) => project.uptime_percentage), ...platformLinks.map((link) => link.uptime_percentage)]);
      return { ...platform, projects: platformProjects, links: platformLinks, providers: platformProviders, apiErrors, active, down, uptime };
    });
  }, [links, providers, rows]);

  const currentPlatform = platformModels.find((item) => item.id === selectedPlatform) || platformModels[0];
  const selectedProviderErrors = selectedPlatform === "netlify" && netlifyStatus.data && !netlifyStatus.error ? [] : currentPlatform.apiErrors;
  const filteredProjects = useMemo(() => {
    return rows
      .filter((project) => (platformFilter === "all" ? platformMatches(project.hosting_platform, selected) : project.hosting_platform === platformFilter))
      .filter((project) => {
        if (statusFilter === "running") return project.link_is_active && !isDown(project);
        if (statusFilter === "down") return isDown(project);
        if (statusFilter === "paused") return !project.link_is_active;
        return true;
      })
      .filter((project) => [project.name, project.domain, project.client_name, project.hosting_platform].join(" ").toLowerCase().includes(search.toLowerCase()));
  }, [platformFilter, rows, search, selected, statusFilter]);

  const activeServers = rows.filter((project) => project.link_is_active && !isDown(project));
  const failedServers = rows.filter(isDown);
  const expiringServers = rows.filter((project) => ["soon", "critical", "expired"].includes(expiryState(project.expiry_date)));
  const recentDeployments = selectedPlatform === "netlify" ? (netlifyStatus.data?.deploys || []).slice(0, 5) : selectedPlatform === "vercel" ? (vercelProjects.data || []).slice(0, 5) : currentPlatform.links.slice(0, 5);
  const chartData = rows.slice(0, 8).map((project) => ({
    name: shortName(project.name),
    uptime: Number(project.uptime_percentage || 0),
    response: Number(project.response_time_ms || 0)
  }));
  const responseData = rows.slice(0, 8).map((project) => ({ name: shortName(project.name), response: Number(project.response_time_ms || 0) }));

  async function handleExport() {
    const res = await api.get("/hosting/export/", { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = "hosting-report.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  function retrySelected() {
    if (selectedPlatform === "netlify") netlifyStatus.refetch();
    else if (selectedPlatform === "vercel") syncVercel.mutate();
    else syncProviders.mutate();
  }

  function openPlatform(providerId) {
    setSelectedPlatform(providerId);
    setActiveTab("projects");
    navigate(`/hosting/${providerId}`);
  }

  return (
    <motion.div variants={pageVariants} initial="initial" animate="animate" className="space-y-6 text-[color:var(--text)]">
      <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm font-semibold text-[color:var(--primary)]">Enterprise Hosting Control</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-[color:var(--text-strong)]">{isDetailsRoute ? `${selected.name} Hosting` : "Hosting Manager"}</h1>
          <p className="mt-2 max-w-2xl text-sm text-[color:var(--text-muted)]">{isDetailsRoute ? "Project controls, live URLs, health, uptime, deployment status, and logs for this provider." : "A platform-first control surface for deployments, uptime, domains, and incident response."}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isDetailsRoute && <ActionButton variant="secondary" onClick={() => navigate("/hosting")} icon={LayoutDashboard}>All Providers</ActionButton>}
          <ActionButton onClick={() => setEditing(emptyForm)} icon={Play}>Add Project</ActionButton>
          <ActionButton variant="secondary" onClick={handleExport} icon={Download}>Export</ActionButton>
          <ActionButton variant="pulse" onClick={retrySelected} loading={syncProviders.isPending || syncVercel.isPending} icon={RefreshCcw}>Redeploy / Sync</ActionButton>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Active servers" value={summary.data?.active_servers ?? activeServers.length} icon={CheckCircle2} tone="emerald" />
        <MetricCard label="Failed servers" value={summary.data?.down_servers ?? failedServers.length} icon={WifiOff} tone="rose" />
        <MetricCard label="Live links" value={summary.data?.link_active ?? 0} icon={ShieldCheck} tone="cyan" />
        <MetricCard label="Monthly revenue" value={`₹${summary.data?.monthly_revenue ?? 0}`} icon={Activity} tone="amber" />
      </section>

      {!isDetailsRoute && (
        <motion.section variants={staggerContainer} initial="initial" animate="animate" className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {platformModels.map((platform) => (
            platform.id === "netlify" ? (
              <NetlifyCard
                key={platform.id}
                data={netlifyStatus.data}
                loading={netlifyStatus.isLoading}
                error={netlifyStatus.error}
                active={false}
                redeploying={redeployNetlifySite.isPending}
                onRedeploy={(siteId) => redeployNetlifySite.mutate(siteId)}
                onOpen={() => openPlatform(platform.id)}
              />
            ) : (
              <PlatformCard key={platform.id} platform={platform} active={false} onClick={() => openPlatform(platform.id)} />
            )
          ))}
        </motion.section>
      )}

      {isDetailsRoute && <ApiState loading={globalLoading} error={selectedError} onRetry={retrySelected} platform={selected.name} />}

      {isDetailsRoute && (
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          <AnimatePresence mode="wait">
            <motion.div
              key={selectedPlatform}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.34, ease: "easeInOut" }}
            >
          <PremiumCard className="overflow-hidden p-0">
            <div className="border-b border-[color:var(--border)] p-5">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-center gap-4">
                  <div className={`grid size-12 place-items-center rounded-2xl bg-gradient-to-br ${selected.accent} text-slate-950 shadow-lg`}>
                    <selected.icon size={22} />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-[color:var(--text-strong)]">{selected.name}</h2>
                    <p className="text-sm text-[color:var(--text-muted)]">{selected.label}</p>
                  </div>
                </div>
                <Tabs tabs={TABS} active={activeTab} onChange={setActiveTab} />
              </div>
            </div>

            <AnimatePresence mode="wait">
              {activeTab === "overview" && (
                <TabPanel key="overview">
                  {selectedPlatform === "netlify" ? (
                    <NetlifyDetailsPanel
                      data={netlifyStatus.data}
                      loading={netlifyStatus.isLoading}
                      error={netlifyStatus.error}
                      redeploying={redeployNetlifySite.isPending}
                      onRedeploy={(siteId) => redeployNetlifySite.mutate(siteId)}
                    />
                  ) : (
                    <OverviewTab
                      platform={currentPlatform}
                      activeServers={activeServers}
                      failedServers={failedServers}
                      expiringServers={expiringServers}
                      recentDeployments={recentDeployments}
                      chartData={chartData}
                      responseData={responseData}
                      dashboard={dashboard.data}
                    />
                  )}
                </TabPanel>
              )}
              {activeTab === "projects" && (
                <TabPanel key="projects">
                  <ProjectFilters search={search} setSearch={setSearch} status={statusFilter} setStatus={setStatusFilter} platform={platformFilter} setPlatform={setPlatformFilter} />
                  <motion.div variants={staggerContainer} initial="initial" animate="animate" className="mt-4 grid gap-4 md:grid-cols-2">
                    {projects.isLoading ? <ProjectSkeleton count={4} /> : filteredProjects.map((project) => (
                      <ProjectCard
                        key={project.id}
                        project={project}
                        onToggle={(next) => toggleProject.mutate({ project, link_is_active: next })}
                        onEdit={() => setEditing(project)}
                        onDelete={() => setDeleteProject(project)}
                        onLogs={() => setLogProject(project)}
                        onRestart={() => restartProject.mutate(project)}
                        onRenew={() => renewProject.mutate(project)}
                        onRedeploy={() => handleRedeployProject(project, vercelProjects.data || [], redeployVercel, redeployProviderProject)}
                        actionState={projectActions[project.id]}
                      />
                    ))}
                  </motion.div>
                  {!projects.isLoading && !filteredProjects.length && <EmptyState title="No data available" message="Try another filter or sync live hosting data." />}
                </TabPanel>
              )}
              {activeTab === "logs" && (
                <TabPanel key="logs">
                  <LogsTab projects={filteredProjects} links={currentPlatform.links} vercelProjects={selectedPlatform === "vercel" ? vercelProjects.data || [] : []} />
                </TabPanel>
              )}
              {activeTab === "settings" && (
                <TabPanel key="settings">
                  <SettingsTab
                    platform={currentPlatform}
                    syncing={syncProviders.isPending || syncVercel.isPending}
                    onSync={retrySelected}
                    onBulkRestart={() => activeServers.slice(0, 6).forEach((project) => restartProject.mutate(project))}
                    onToggleLink={(link) => toggleHostingLink.mutate({ id: link.id, enabled: !(link.status === "on" && link.is_enabled) })}
                  />
                </TabPanel>
              )}
            </AnimatePresence>
          </PremiumCard>
            </motion.div>
          </AnimatePresence>
        </div>

        <aside className="space-y-4">
          <NotificationCenter projects={rows} providerErrors={selectedProviderErrors} events={dashboard.data?.ai_insights || []} />
          <PremiumCard>
            <SectionTitle icon={Activity} title="Live Monitoring" subtitle="Uptime and response time" />
            <div className="mt-4 h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="hostingUptime" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="5%" stopColor="#38BDF8" stopOpacity={0.42} />
                      <stop offset="95%" stopColor="#38BDF8" stopOpacity={0.04} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="name" tick={{ fill: "var(--text-faint)", fontSize: 11 }} />
                  <YAxis hide domain={[0, 100]} />
                  <Tooltip contentStyle={tooltipStyle()} />
                  <Area type="monotone" dataKey="uptime" stroke="#38BDF8" strokeWidth={2} fill="url(#hostingUptime)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </PremiumCard>
          <QuickActions onSync={retrySelected} onAdd={() => setEditing(emptyForm)} onExport={handleExport} loading={syncProviders.isPending || syncVercel.isPending} />
        </aside>
      </section>
      )}

      <ProjectModal project={editing} onClose={() => setEditing(null)} onSave={saveProject.mutate} saving={saveProject.isPending} />
      <LogsModal project={logProject} onClose={() => setLogProject(null)} />
      <DeleteConfirmModal project={deleteProject} onClose={() => setDeleteProject(null)} onConfirm={() => deleteHostedProject.mutate(deleteProject.id)} deleting={deleteHostedProject.isPending} />
    </motion.div>
  );
}

function PlatformCard({ platform, active, onClick }) {
  const Icon = platform.icon;
  const state = platform.apiErrors.length ? "API issue" : platform.down ? "Attention" : "Active";
  return (
    <motion.button
      variants={cardVariants}
      type="button"
      whileHover={{ y: -5, scale: 1.03, boxShadow: "0 22px 60px rgba(56,189,248,0.18)" }}
      whileTap={{ scale: 0.97 }}
      onClick={onClick}
      className={`group relative overflow-hidden rounded-2xl border p-5 text-left shadow-sm transition duration-300 ${active ? "border-[color:var(--primary)] bg-[color:var(--card-bg-hover)] shadow-xl shadow-cyan-500/10" : "border-[color:var(--border)] bg-[color:var(--card-bg)] hover:border-[color:var(--border-strong)]"}`}
    >
      <div className="pointer-events-none absolute inset-0 opacity-0 transition duration-300 group-hover:opacity-100" style={{ background: "radial-gradient(circle at 18% 0%, rgba(56,189,248,.18), transparent 32%)" }} />
      <div className="flex items-start justify-between gap-4">
        <div className={`grid size-11 place-items-center rounded-2xl bg-gradient-to-br ${platform.accent} text-slate-950 shadow-lg`}>
          <Icon size={21} />
        </div>
        <StatusBadge value={state} tone={platform.apiErrors.length || platform.down ? "rose" : "emerald"} />
      </div>
      <h3 className="mt-5 text-lg font-semibold text-[color:var(--text-strong)]">{platform.name}</h3>
      <p className="mt-1 text-sm text-[color:var(--text-muted)]">{platform.label}</p>
      <div className="mt-5 grid grid-cols-3 gap-3">
        <MiniStat label="Active" value={<AnimatedValue value={platform.active} />} />
        <MiniStat label="Down" value={<AnimatedValue value={platform.down} />} />
        <MiniStat label="Uptime" value={<><AnimatedValue value={platform.uptime} />%</>} />
      </div>
    </motion.button>
  );
}

function ApiState({ loading, error, onRetry, platform }) {
  if (loading) {
    return (
      <PremiumCard className="flex items-center gap-3 border-cyan-300/30 bg-cyan-400/10">
        <Loader2 className="size-5 animate-spin text-[color:var(--primary)]" />
        <div>
          <p className="text-sm font-semibold text-[color:var(--text-strong)]">Fetching live data...</p>
          <p className="text-xs text-[color:var(--text-muted)]">Connecting to {platform} APIs and monitoring endpoints.</p>
        </div>
      </PremiumCard>
    );
  }
  if (error) {
    return (
      <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: [0, -5, 5, -3, 0] }} transition={{ duration: 0.42, ease: "easeInOut" }}>
      <PremiumCard className="border-rose-400/40 bg-rose-500/10 shadow-[0_0_36px_rgba(244,63,94,.16)]">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="flex gap-3">
            <AlertTriangle className="mt-0.5 size-5 text-rose-400" />
            <div>
              <p className="font-semibold text-[color:var(--text-strong)]">API Not Connected</p>
              <p className="mt-1 text-sm text-[color:var(--text-muted)]">{apiErrorMessage(error)}</p>
            </div>
          </div>
          <ActionButton variant="danger" onClick={onRetry} icon={RefreshCcw}>Retry</ActionButton>
        </div>
      </PremiumCard>
      </motion.div>
    );
  }
  return (
    <PremiumCard className="flex items-center gap-3 border-emerald-400/30 bg-emerald-500/10">
      <CheckCircle2 className="size-5 text-emerald-400" />
      <div>
        <p className="text-sm font-semibold text-[color:var(--text-strong)]">Running / Active</p>
        <p className="text-xs text-[color:var(--text-muted)]">Live data is connected and refreshing automatically.</p>
      </div>
    </PremiumCard>
  );
}

function OverviewTab({ platform, activeServers, failedServers, expiringServers, recentDeployments, chartData, responseData, dashboard }) {
  return (
    <div className="grid gap-5">
      <div className="grid gap-4 md:grid-cols-3">
        <SummaryBlock title="Active Servers" value={activeServers.length} icon={CheckCircle2} tone="emerald" />
        <SummaryBlock title="Failed Servers" value={failedServers.length} icon={WifiOff} tone="rose" />
        <SummaryBlock title="Recent Deployments" value={recentDeployments.length} icon={Rocket} tone="cyan" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartPanel title="Uptime graph" data={chartData} type="area" />
        <ChartPanel title="Response time" data={responseData} type="bar" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <PremiumCard>
          <SectionTitle icon={Rocket} title="Deployment History Timeline" subtitle="Latest platform activity" />
          <Timeline items={recentDeployments} />
        </PremiumCard>
        <PremiumCard>
          <SectionTitle icon={ShieldCheck} title="API Status Indicator" subtitle={`${platform.name} provider health`} />
          <div className="mt-4 space-y-3">
            {platform.providers.length ? platform.providers.map((provider) => (
              <div key={provider.provider || provider.name} className="flex items-center justify-between rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] px-4 py-3">
                <div>
                  <p className="text-sm font-semibold text-[color:var(--text-strong)]">{provider.name || pretty(provider.provider)}</p>
                  <p className="text-xs text-[color:var(--text-muted)]">{provider.last_error || (provider.last_synced_at ? `Synced ${format(parseISO(provider.last_synced_at), "MMM d, h:mm a")}` : "Ready for sync")}</p>
                </div>
                <StatusBadge value={provider.last_error ? "Error" : "Active"} tone={provider.last_error ? "rose" : "emerald"} />
              </div>
            )) : <EmptyState title="No provider data" message="Sync this platform to populate API status." compact />}
          </div>
          {dashboard?.ai_insights?.length > 0 && <p className="mt-4 text-xs text-[color:var(--text-muted)]">{dashboard.ai_insights[0].message}</p>}
        </PremiumCard>
      </div>
      <ExpiryTracker servers={expiringServers} />
    </div>
  );
}

function ProjectFilters({ search, setSearch, status, setStatus, platform, setPlatform }) {
  return (
    <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto]">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[color:var(--text-faint)]" />
        <input value={search} onChange={(event) => setSearch(event.target.value)} className="h-11 w-full rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-strong)] pl-10 pr-3 text-sm text-[color:var(--text-strong)] outline-none transition focus:border-[color:var(--primary)]" placeholder="Search projects, domains, clients" />
      </div>
      <Select value={platform} onChange={setPlatform} options={[["all", "All platforms"], ...Object.values(PLATFORM_CONFIG).map((item) => [item.id, item.name])]} />
      <Select value={status} onChange={setStatus} options={[["all", "All status"], ["running", "Running"], ["down", "Down"], ["paused", "Paused"]]} />
    </div>
  );
}

function ProjectCard({ project, onToggle, onEdit, onDelete, onLogs, onRestart, onRenew, onRedeploy, actionState }) {
  const running = project.link_is_active && !isDown(project);
  const expiry = expiryState(project.expiry_date);
  const daysLeft = remainingDays(project.expiry_date);
  const actionLabel = project.link_is_active ? "Stop" : "Start";
  const busy = Boolean(actionState);
  const offline = !running;
  const disabled = busy || offline;
  return (
    <motion.article
      variants={cardVariants}
      whileHover={{ y: -5, boxShadow: "0 24px 70px rgba(15,23,42,.18)" }}
      className={`rounded-2xl border bg-[color:var(--card-bg)] p-5 shadow-sm transition duration-300 hover:border-[color:var(--border-strong)] ${disabled ? "opacity-70 grayscale-[.25]" : ""} ${expiry === "critical" ? "animate-hosting-critical border-rose-400/50" : expiry === "soon" ? "animate-hosting-warning border-amber-400/45" : "border-[color:var(--border)]"}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusDot active={running} />
            <StatusBadge value={actionState || (running ? "Running" : isDown(project) ? "Offline" : "Paused")} tone={busy ? "cyan" : running ? "emerald" : isDown(project) ? "rose" : "amber"} />
            <PlatformTag value={project.hosting_platform} />
          </div>
          <h3 className="mt-3 truncate text-lg font-semibold text-[color:var(--text-strong)]">{project.name}</h3>
          <p className="mt-1 truncate text-sm text-[color:var(--text-muted)]">{project.domain || project.deploy_url || "No domain configured"}</p>
        </div>
        <Toggle checked={project.link_is_active} onChange={onToggle} disabled={busy} />
      </div>
      <div className="mt-5 grid grid-cols-3 gap-3">
        <MiniStat label="Uptime" value={<><AnimatedValue value={Number(project.uptime_percentage || 0)} />%</>} />
        <MiniStat label="Response" value={<><AnimatedValue value={Number(project.response_time_ms || 0)} />ms</>} />
        <MiniStat label="Server" value={project.server_status || "Unknown"} />
      </div>
      <UptimeBar value={Number(project.uptime_percentage || 0)} />
      <div className={`mt-4 grid gap-2 sm:grid-cols-2 ${offline && !busy ? "opacity-60" : ""}`}>
        <ActionButton variant={project.link_is_active ? "secondary" : "primary"} onClick={() => onToggle(!project.link_is_active)} loading={busy} icon={project.link_is_active ? Pause : Play}>
          {project.link_is_active ? "Stop Server" : "Start Server"}
        </ActionButton>
        <ActionButton variant="secondary" onClick={onRestart} disabled={disabled} icon={RefreshCcw}>Restart</ActionButton>
        <ActionButton variant="pulse" onClick={onRedeploy} disabled={disabled} icon={Rocket}>Redeploy</ActionButton>
        <ActionButton variant="secondary" onClick={onLogs} disabled={disabled} icon={TerminalSquare}>View Logs</ActionButton>
        <ActionButton variant="secondary" onClick={onEdit} disabled={busy} icon={Edit3}>Edit</ActionButton>
      </div>
      <div className={`mt-4 rounded-2xl border px-3 py-3 ${expiry === "normal" ? "border-[color:var(--border)] bg-[color:var(--surface-soft)]" : expiry === "soon" ? "border-amber-400/35 bg-amber-400/10" : "border-rose-400/35 bg-rose-500/10"}`}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-medium text-[color:var(--text-faint)]">Server Expiry</p>
            <p className="mt-1 text-sm font-semibold text-[color:var(--text-strong)]">{project.expiry_date || "No expiry date"}</p>
          </div>
          <StatusBadge value={expiryLabel(expiry, daysLeft)} tone={expiry === "normal" ? "emerald" : expiry === "soon" ? "amber" : "rose"} />
        </div>
        {expiry !== "normal" && (
          <div className="mt-3 flex flex-wrap gap-2">
            <ActionButton variant="secondary" onClick={onRenew} icon={ShieldCheck} disabled={busy}>Renew Now</ActionButton>
            <ActionButton variant="pulse" onClick={onRedeploy} icon={Rocket} disabled={disabled}>Redeploy</ActionButton>
          </div>
        )}
      </div>
      <div className="mt-5 grid grid-cols-5 gap-2">
        <IconButton label={actionLabel} icon={project.link_is_active ? Pause : Play} onClick={() => onToggle(!project.link_is_active)} disabled={busy} />
        <IconButton label="Edit" icon={Edit3} onClick={onEdit} disabled={busy} />
        <IconButton label="Logs" icon={TerminalSquare} onClick={onLogs} disabled={disabled} />
        <IconButton label="Restart" icon={RefreshCcw} onClick={onRestart} disabled={disabled} />
        <IconButton label="Delete" icon={Trash2} onClick={onDelete} tone="danger" disabled={busy} />
      </div>
      {project.deploy_url && (
        <a href={disabled ? undefined : project.deploy_url} target="_blank" rel="noreferrer" aria-disabled={disabled} className={`mt-4 flex items-center justify-between rounded-xl border border-[color:var(--border)] px-3 py-2 text-xs font-semibold text-[color:var(--text-muted)] transition hover:border-[color:var(--primary)] hover:text-[color:var(--text-strong)] ${disabled ? "pointer-events-none opacity-45" : ""}`}>
          <span className="truncate">{project.deploy_url}</span>
          <ExternalLink size={14} />
        </a>
      )}
    </motion.article>
  );
}

function LogsTab({ projects, links, vercelProjects }) {
  const items = [
    ...projects.slice(0, 6).map((project) => ({ title: project.name, message: `${project.server_status || "unknown"} · ${project.response_time_ms || 0}ms response`, level: isDown(project) ? "error" : "info" })),
    ...links.slice(0, 6).map((link) => ({ title: link.project_name || link.domain, message: `${pretty(link.provider)} ${link.health_status || "unknown"} · ${link.url || link.domain || "no url"}`, level: link.health_status === "down" ? "error" : "info" })),
    ...vercelProjects.slice(0, 6).map((project) => ({ title: project.name, message: `${project.latest_deployment_status || "UNKNOWN"} · ${project.latest_deployment_url || "No deployment URL"}`, level: project.latest_deployment_status === "ERROR" ? "error" : "info" }))
  ];
  if (!items.length) return <EmptyState title="No data available" message="No logs are available for the selected platform." />;
  return (
    <div className="space-y-3">
      {items.map((item, index) => (
        <div key={`${item.title}-${index}`} className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
          <div className="flex items-start gap-3">
            <span className={`mt-1 size-2 rounded-full ${item.level === "error" ? "bg-rose-400" : "bg-emerald-400"}`} />
            <div>
              <p className="text-sm font-semibold text-[color:var(--text-strong)]">{item.title}</p>
              <p className="mt-1 text-xs text-[color:var(--text-muted)]">{item.message}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function SettingsTab({ platform, syncing, onSync, onBulkRestart, onToggleLink }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <PremiumCard>
        <SectionTitle icon={Zap} title="Quick Actions" subtitle="One-click operations for this platform" />
        <div className="mt-4 grid gap-3">
          <ActionButton onClick={onSync} loading={syncing} icon={RefreshCcw}>Retry API Sync</ActionButton>
          <ActionButton variant="secondary" onClick={onBulkRestart} icon={RefreshCcw}>Bulk Restart Active Servers</ActionButton>
        </div>
      </PremiumCard>
      <PremiumCard>
        <SectionTitle icon={Cloud} title="Server Controls" subtitle="Start, stop, and failover links" />
        <div className="mt-4 space-y-3">
          {platform.links.slice(0, 5).map((link) => (
            <div key={link.id} className="flex items-center justify-between rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] px-4 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-[color:var(--text-strong)]">{link.project_name || link.label || link.domain}</p>
                <p className="truncate text-xs text-[color:var(--text-muted)]">{link.url || link.domain || pretty(link.provider)}</p>
              </div>
              <Toggle checked={link.status === "on" && link.is_enabled} onChange={() => onToggleLink(link)} />
            </div>
          ))}
          {!platform.links.length && <EmptyState title="No links found" message="Sync providers to manage platform links." compact />}
        </div>
      </PremiumCard>
    </div>
  );
}

function ExpiryTracker({ servers }) {
  const sorted = [...servers].sort((a, b) => remainingDays(a.expiry_date) - remainingDays(b.expiry_date));
  return (
    <PremiumCard>
      <SectionTitle icon={AlertTriangle} title="Server Expiry Tracker" subtitle="Renewal risk and expiring infrastructure" />
      {sorted.length > 0 && (
        <div className="mt-4 rounded-2xl border border-amber-400/30 bg-amber-400/10 p-4">
          <p className="text-sm font-semibold text-[color:var(--text-strong)]">Renewal attention required</p>
          <p className="mt-1 text-sm text-[color:var(--text-muted)]">{sorted.length} server{sorted.length === 1 ? "" : "s"} are expired or nearing expiry. Renew or redeploy to avoid downtime.</p>
        </div>
      )}
      <div className="mt-4 overflow-hidden rounded-2xl border border-[color:var(--border)]">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="bg-[color:var(--surface-soft)] text-xs text-[color:var(--text-muted)]">
            <tr>
              <th className="px-4 py-3">Project</th>
              <th className="px-4 py-3">Domain</th>
              <th className="px-4 py-3">Expiry Date</th>
              <th className="px-4 py-3">Remaining</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[color:var(--border)]">
            {sorted.map((project) => {
              const days = remainingDays(project.expiry_date);
              const state = expiryState(project.expiry_date);
              return (
                <tr key={project.id} className="bg-[color:var(--card-bg)]">
                  <td className="px-4 py-3 font-semibold text-[color:var(--text-strong)]">{project.name}</td>
                  <td className="px-4 py-3 text-[color:var(--text-muted)]">{project.domain || project.deploy_url || "No domain"}</td>
                  <td className="px-4 py-3 text-[color:var(--text-muted)]">{project.expiry_date || "n/a"}</td>
                  <td className="px-4 py-3 text-[color:var(--text-muted)]">{days < 0 ? `${Math.abs(days)} days overdue` : `${days} days left`}</td>
                  <td className="px-4 py-3"><StatusBadge value={expiryLabel(state, days)} tone={state === "soon" ? "amber" : "rose"} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!sorted.length && <EmptyState title="No expiring servers" message="No servers are inside the renewal risk window." compact />}
      </div>
    </PremiumCard>
  );
}

function NotificationCenter({ projects, providerErrors, events }) {
  const [dismissed, setDismissed] = useState([]);
  const down = projects.filter(isDown).slice(0, 3);
  const notices = [
    ...providerErrors.map((provider) => ({ title: `${pretty(provider.provider)} API failure`, message: provider.last_error, tone: "rose" })),
    ...down.map((project) => ({ title: `${project.name} downtime alert`, message: `${project.domain || "Project"} is reporting ${project.server_status}.`, tone: "rose" })),
    ...projects.filter((project) => ["soon", "critical", "expired"].includes(expiryState(project.expiry_date))).slice(0, 4).map((project) => ({ title: `${project.name} renewal alert`, message: `${project.domain || "Server"} expires ${project.expiry_date || "soon"} (${expiryLabel(expiryState(project.expiry_date), remainingDays(project.expiry_date))}).`, tone: expiryState(project.expiry_date) === "soon" ? "amber" : "rose" })),
    ...events.slice(0, 2).map((event) => ({ title: event.project || "AI insight", message: event.message, tone: "cyan" }))
  ].filter((notice) => !dismissed.includes(notice.title));
  return (
    <PremiumCard>
      <SectionTitle icon={Bell} title="Notification Center" subtitle="API failure and downtime alerts" />
      <div className="mt-4 space-y-3">
        <AnimatePresence initial={false}>
          {notices.length ? notices.map((notice, index) => (
            <motion.div
              key={notice.title}
              initial={{ opacity: 0, x: 48, scale: 0.96 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 80, scale: 0.94 }}
              transition={{ duration: 0.32, delay: index * 0.04, ease: "easeInOut" }}
              className={`rounded-xl border px-4 py-3 ${notice.tone === "rose" ? "border-rose-400/25 bg-rose-500/10" : notice.tone === "amber" ? "border-amber-400/25 bg-amber-500/10" : "border-cyan-400/25 bg-cyan-500/10"}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[color:var(--text-strong)]">{notice.title}</p>
                  <p className="mt-1 text-xs text-[color:var(--text-muted)]">{notice.message}</p>
                </div>
                <button type="button" onClick={() => setDismissed((items) => [...items, notice.title])} className="rounded-lg p-1 text-[color:var(--text-faint)] transition hover:bg-white/10 hover:text-[color:var(--text-strong)]" aria-label="Dismiss notification">
                  <X size={14} />
                </button>
              </div>
            </motion.div>
          )) : <EmptyState title="No active alerts" message="All monitored systems look calm." compact />}
        </AnimatePresence>
      </div>
    </PremiumCard>
  );
}

function QuickActions({ onSync, onAdd, onExport, loading }) {
  return (
    <PremiumCard>
      <SectionTitle icon={Zap} title="Quick Actions" subtitle="Fast operational shortcuts" />
      <div className="mt-4 grid gap-3">
        <ActionButton onClick={onSync} loading={loading} icon={RefreshCcw}>Sync Live Data</ActionButton>
        <ActionButton variant="secondary" onClick={onAdd} icon={Play}>Add Server</ActionButton>
        <ActionButton variant="secondary" onClick={onExport} icon={Download}>Download Report</ActionButton>
      </div>
    </PremiumCard>
  );
}

function ProjectModal({ project, onClose, onSave, saving }) {
  const [draft, setDraft] = useState(project || emptyForm);
  useEffect(() => {
    setDraft(project || emptyForm);
  }, [project]);
  if (!project) return null;
  const update = (key, value) => setDraft((item) => ({ ...item, [key]: value }));
  return (
    <Modal open={Boolean(project)} title={project.id ? "Edit hosted project" : "Add hosted project"} onClose={onClose}>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Project name" value={draft.name || ""} onChange={(value) => update("name", value)} />
        <Field label="Client" value={draft.client_name || ""} onChange={(value) => update("client_name", value)} />
        <Field label="Domain" value={draft.domain || ""} onChange={(value) => update("domain", value)} />
        <Field label="Deploy URL" value={draft.deploy_url || ""} onChange={(value) => update("deploy_url", value)} />
        <SelectField label="Platform" value={draft.hosting_platform || "vercel"} onChange={(value) => update("hosting_platform", value)} options={[["aws", "AWS"], ["vercel", "Vercel"], ["custom", "Custom"]]} />
        <Field label="Monthly cost" value={draft.monthly_cost || "0"} onChange={(value) => update("monthly_cost", value)} />
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <ActionButton variant="secondary" onClick={onClose} icon={X}>Cancel</ActionButton>
        <ActionButton onClick={() => onSave(draft)} loading={saving} icon={CheckCircle2}>Save Project</ActionButton>
      </div>
    </Modal>
  );
}

function LogsModal({ project, onClose }) {
  const timeline = useQuery({
    queryKey: ["hosting-project-timeline", project?.id],
    enabled: Boolean(project?.id),
    queryFn: () => api.get(`/hosting/${project.id}/timeline/`).then(listFrom)
  });
  return (
    <Modal open={Boolean(project)} title={`${project?.name || "Project"} logs`} onClose={onClose}>
      {timeline.isLoading ? <ProjectSkeleton count={2} /> : (
        <div className="space-y-3">
          {(timeline.data || []).map((item) => (
            <div key={item.id} className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
              <p className="text-sm font-semibold text-[color:var(--text-strong)]">{pretty(item.event_type)}</p>
              <p className="mt-1 text-sm text-[color:var(--text-muted)]">{item.notes || "No notes available."}</p>
            </div>
          ))}
          {!timeline.data?.length && <EmptyState title="No logs available" message="No deployment or control events were found for this project." compact />}
        </div>
      )}
    </Modal>
  );
}

function DeleteConfirmModal({ project, onClose, onConfirm, deleting }) {
  return (
    <Modal open={Boolean(project)} title="Delete hosted project" onClose={onClose}>
      <div className="rounded-2xl border border-rose-400/30 bg-rose-500/10 p-4">
        <div className="flex gap-3">
          <AlertTriangle className="mt-0.5 size-5 text-rose-300" />
          <div>
            <p className="font-semibold text-[color:var(--text-strong)]">This will remove {project?.name || "this project"} from Hosting Manager.</p>
            <p className="mt-1 text-sm text-[color:var(--text-muted)]">The hosted infrastructure is not deleted automatically, but the dashboard record, monitoring state, and local metadata will be removed.</p>
          </div>
        </div>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <ActionButton variant="secondary" onClick={onClose} icon={X}>Cancel</ActionButton>
        <ActionButton variant="danger" onClick={onConfirm} loading={deleting} icon={Trash2}>Delete Project</ActionButton>
      </div>
    </Modal>
  );
}

function PremiumCard({ children, className = "" }) {
  return <div className={`rounded-2xl border border-[color:var(--border)] bg-[color:var(--card-bg)] p-5 shadow-sm transition duration-300 ${className}`}>{children}</div>;
}

function ActionButton({ children, icon: Icon, variant = "primary", loading = false, className = "", ...props }) {
  const styles = {
    primary: "bg-[color:var(--primary)] text-[color:var(--primary-text)] hover:brightness-105",
    secondary: "border border-[color:var(--border)] bg-[color:var(--surface-strong)] text-[color:var(--text-strong)] hover:border-[color:var(--primary)]",
    danger: "bg-rose-500 text-white hover:bg-rose-400",
    pulse: "bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 text-slate-950 shadow-lg shadow-cyan-500/25 animate-hosting-pulse hover:brightness-110"
  };
  return (
    <motion.button whileHover={{ y: -1 }} whileTap={{ scale: 0.97 }} type="button" className={`relative inline-flex h-10 items-center justify-center gap-2 overflow-hidden rounded-xl px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${styles[variant]} ${className}`} disabled={loading || props.disabled} {...props}>
      <motion.span className="pointer-events-none absolute inset-0 bg-white/20" initial={{ x: "-120%", opacity: 0 }} whileTap={{ x: "120%", opacity: [0, 0.45, 0] }} transition={{ duration: 0.45, ease: "easeInOut" }} />
      {loading ? <Loader2 size={16} className="animate-spin" /> : Icon ? <Icon size={16} /> : null}
      <span className="relative">{children}</span>
    </motion.button>
  );
}

function IconButton({ label, icon: Icon, onClick, tone = "default", disabled = false }) {
  return (
    <motion.button whileTap={{ scale: disabled ? 1 : 0.94 }} type="button" onClick={onClick} title={label} disabled={disabled} className={`grid h-10 place-items-center rounded-xl border transition disabled:cursor-not-allowed disabled:opacity-45 ${tone === "danger" ? "border-rose-400/25 bg-rose-500/10 text-rose-300 hover:border-rose-300" : "border-[color:var(--border)] bg-[color:var(--surface-strong)] text-[color:var(--text-muted)] hover:border-[color:var(--primary)] hover:text-[color:var(--text-strong)]"}`}>
      <Icon size={16} />
    </motion.button>
  );
}

function Tabs({ tabs, active, onChange }) {
  return (
    <div className="flex rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-1">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        return (
          <button key={tab.id} type="button" onClick={() => onChange(tab.id)} className={`relative flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold transition ${active === tab.id ? "text-[color:var(--primary-text)]" : "text-[color:var(--text-muted)] hover:text-[color:var(--text-strong)]"}`}>
            {active === tab.id && <motion.span layoutId="hosting-tab" className="absolute inset-0 rounded-xl bg-[color:var(--primary)]" />}
            <Icon className="relative" size={15} />
            <span className="relative hidden sm:inline">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function TabPanel({ children }) {
  return (
    <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.2 }} className="p-5">
      {children}
    </motion.div>
  );
}

function MetricCard({ label, value, icon: Icon, tone }) {
  const parsed = parseMetricValue(value);
  return (
    <PremiumCard>
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm text-[color:var(--text-muted)]">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-[color:var(--text-strong)]">{parsed.prefix}<AnimatedValue value={parsed.number} />{parsed.suffix}</p>
        </div>
        <div className={`grid size-11 place-items-center rounded-2xl ${toneClass(tone)}`}>
          <Icon size={20} />
        </div>
      </div>
    </PremiumCard>
  );
}

function SummaryBlock({ title, value, icon: Icon, tone }) {
  return (
    <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-[color:var(--text-muted)]">{title}</p>
        <Icon className={toneText(tone)} size={18} />
      </div>
      <p className="mt-3 text-2xl font-semibold text-[color:var(--text-strong)]"><AnimatedValue value={Number(value || 0)} /></p>
    </div>
  );
}

function ChartPanel({ title, data, type }) {
  return (
    <PremiumCard>
      <SectionTitle icon={Activity} title={title} subtitle="Realtime monitoring" />
      <div className="mt-4 h-56">
        <ResponsiveContainer width="100%" height="100%">
          {type === "bar" ? (
            <BarChart data={data}>
              <XAxis dataKey="name" tick={{ fill: "var(--text-faint)", fontSize: 11 }} />
              <YAxis tick={{ fill: "var(--text-faint)", fontSize: 11 }} />
              <Tooltip contentStyle={tooltipStyle()} />
              <Bar dataKey="response" fill="#38BDF8" radius={[8, 8, 0, 0]} isAnimationActive animationDuration={900} animationEasing="ease-in-out" />
            </BarChart>
          ) : (
            <AreaChart data={data}>
              <defs>
                <linearGradient id={`${title.replace(/\s/g, "")}Fill`} x1="0" x2="0" y1="0" y2="1">
                  <stop offset="5%" stopColor="#22C55E" stopOpacity={0.36} />
                  <stop offset="95%" stopColor="#22C55E" stopOpacity={0.03} />
                </linearGradient>
              </defs>
              <XAxis dataKey="name" tick={{ fill: "var(--text-faint)", fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fill: "var(--text-faint)", fontSize: 11 }} />
              <Tooltip contentStyle={tooltipStyle()} />
              <Area type="monotone" dataKey="uptime" stroke="#22C55E" strokeWidth={2} fill={`url(#${title.replace(/\s/g, "")}Fill)`} isAnimationActive animationDuration={1000} animationEasing="ease-in-out" />
            </AreaChart>
          )}
        </ResponsiveContainer>
      </div>
    </PremiumCard>
  );
}

function Timeline({ items }) {
  if (!items.length) return <EmptyState title="No data available" message="No recent deployment activity found." compact />;
  return (
    <div className="mt-4 space-y-4">
      {items.slice(0, 5).map((item, index) => (
        <div key={item.id || item.vercel_id || index} className="relative pl-6">
          <span className="absolute left-0 top-1.5 size-3 rounded-full bg-[color:var(--primary)] shadow-lg shadow-cyan-400/30" />
          {index !== items.length - 1 && <span className="absolute bottom-[-18px] left-[5px] top-5 w-px bg-[color:var(--border)]" />}
          <p className="text-sm font-semibold text-[color:var(--text-strong)]">{item.name || item.project_name || item.domain || "Deployment"}</p>
          <p className="mt-1 text-xs text-[color:var(--text-muted)]">{item.latest_deployment_status || item.status || item.health_status || "Updated"} · {item.latest_deployment_url || item.url || item.production_domain || "No URL"}</p>
        </div>
      ))}
    </div>
  );
}

function SectionTitle({ icon: Icon, title, subtitle }) {
  return (
    <div className="flex items-center gap-3">
      <div className="grid size-9 place-items-center rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] text-[color:var(--primary)]">
        <Icon size={17} />
      </div>
      <div>
        <h3 className="font-semibold text-[color:var(--text-strong)]">{title}</h3>
        <p className="text-xs text-[color:var(--text-muted)]">{subtitle}</p>
      </div>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div className="rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] px-3 py-2">
      <p className="text-[11px] font-medium text-[color:var(--text-faint)]">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-[color:var(--text-strong)]">{value}</p>
    </div>
  );
}

function StatusBadge({ value, tone = "cyan" }) {
  return <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${badgeClass(tone)}`}>{value}</span>;
}

function PlatformTag({ value }) {
  return <span className="inline-flex rounded-full border border-[color:var(--border)] bg-[color:var(--surface-soft)] px-2.5 py-1 text-xs font-semibold text-[color:var(--text-muted)]">{pretty(value)}</span>;
}

function StatusDot({ active }) {
  return <span className={`size-2.5 rounded-full ${active ? "bg-emerald-400 shadow-[0_0_0_4px_rgba(52,211,153,.14)]" : "bg-rose-400 shadow-[0_0_0_4px_rgba(251,113,133,.14)]"}`} />;
}

function Toggle({ checked, onChange, disabled = false }) {
  return (
    <motion.button whileTap={{ scale: disabled ? 1 : 0.95 }} type="button" onClick={() => onChange(!checked)} disabled={disabled} className={`relative h-7 w-12 rounded-full border transition duration-300 disabled:cursor-not-allowed disabled:opacity-50 ${checked ? "border-emerald-400 bg-emerald-400" : "border-[color:var(--border)] bg-[color:var(--surface-strong)]"}`}>
      <motion.span animate={{ x: checked ? 20 : 2 }} transition={{ type: "spring", stiffness: 420, damping: 28 }} className="absolute top-1 size-5 rounded-full bg-white shadow" />
    </motion.button>
  );
}

function Select({ value, onChange, options }) {
  const [open, setOpen] = useState(false);
  const current = options.find(([id]) => id === value)?.[1] || options[0]?.[1];
  return (
    <div className="relative min-w-40">
      <motion.button whileTap={{ scale: 0.98 }} type="button" onClick={() => setOpen((next) => !next)} className="flex h-11 w-full items-center justify-between gap-3 rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-strong)] px-3 text-sm font-semibold text-[color:var(--text-strong)] outline-none transition hover:border-[color:var(--primary)]">
        <span className="truncate">{current}</span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}><ChevronDown size={16} /></motion.span>
      </motion.button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, scale: 0.96, y: -6 }} animate={{ opacity: 1, scale: 1, y: 6 }} exit={{ opacity: 0, scale: 0.96, y: -6 }} transition={{ duration: 0.18, ease: "easeInOut" }} className="absolute right-0 z-30 max-h-72 w-56 overflow-y-auto rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-strong)] p-1 shadow-2xl">
            {options.map(([id, label]) => (
              <button key={id} type="button" onClick={() => { onChange(id); setOpen(false); }} className={`w-full rounded-xl px-3 py-2 text-left text-sm transition ${id === value ? "bg-[color:var(--primary)] text-[color:var(--primary-text)]" : "text-[color:var(--text-muted)] hover:bg-[color:var(--surface-soft)] hover:text-[color:var(--text-strong)]"}`}>
                {label}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Field({ label, value, onChange }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-[color:var(--text-muted)]">{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} className="mt-2 h-11 w-full rounded-xl border border-[color:var(--border)] bg-[color:var(--surface-strong)] px-3 text-sm text-[color:var(--text-strong)] outline-none transition focus:border-[color:var(--primary)]" />
    </label>
  );
}

function SelectField({ label, value, onChange, options }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-[color:var(--text-muted)]">{label}</span>
      <div className="mt-2"><Select value={value} onChange={onChange} options={options} /></div>
    </label>
  );
}

function EmptyState({ title = "No data available", message = "There is nothing to show yet.", compact = false }) {
  return (
    <div className={`grid place-items-center rounded-2xl border border-dashed border-[color:var(--border-strong)] bg-[color:var(--surface-soft)] p-6 text-center ${compact ? "min-h-28" : "min-h-48"}`}>
      <div>
        <Cloud className="mx-auto size-8 text-[color:var(--primary)]" />
        <p className="mt-3 font-semibold text-[color:var(--text-strong)]">{title}</p>
        <p className="mt-1 text-sm text-[color:var(--text-muted)]">{message}</p>
      </div>
    </div>
  );
}

function AnimatedValue({ value, duration = 700 }) {
  const display = useCountUp(Number(value || 0), duration);
  const hasDecimal = !Number.isInteger(Number(value || 0));
  return <>{hasDecimal ? display.toFixed(2) : Math.round(display)}</>;
}

function UptimeBar({ value }) {
  const safe = Math.max(0, Math.min(100, value || 0));
  return (
    <div className="mt-4">
      <div className="mb-1 flex items-center justify-between text-[11px] font-medium text-[color:var(--text-faint)]">
        <span>Live uptime</span>
        <span>{safe.toFixed(0)}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-500/20">
        <motion.div initial={{ width: 0 }} animate={{ width: `${safe}%` }} transition={{ duration: 0.8, ease: "easeInOut" }} className={`h-full rounded-full ${safe < 80 ? "bg-rose-400" : safe < 96 ? "bg-amber-300" : "bg-emerald-400"}`} />
      </div>
    </div>
  );
}

function ProjectSkeleton({ count = 4 }) {
  return Array.from({ length: count }).map((_, index) => (
    <motion.div key={index} variants={cardVariants} className="h-60 rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-5">
      <div className="hosting-shimmer h-4 w-24 rounded" />
      <div className="hosting-shimmer mt-5 h-6 w-2/3 rounded" />
      <div className="hosting-shimmer mt-3 h-4 w-full rounded" />
      <div className="mt-8 grid grid-cols-3 gap-3">
        <div className="hosting-shimmer h-14 rounded-xl" />
        <div className="hosting-shimmer h-14 rounded-xl" />
        <div className="hosting-shimmer h-14 rounded-xl" />
      </div>
      <div className="mt-5 flex items-center gap-1 text-xs font-semibold text-[color:var(--text-muted)]">
        Fetching data<span className="animate-hosting-dot">.</span><span className="animate-hosting-dot animation-delay-150">.</span><span className="animate-hosting-dot animation-delay-300">.</span>
      </div>
    </motion.div>
  ));
}

function useCountUp(value, duration = 700) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let frame;
    const start = performance.now();
    const from = display;
    const change = value - from;
    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(from + change * eased);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);
  return display;
}

function providerConfig(id, name, label, icon, accent) {
  return { id, name, label, icon, providers: [id], accent };
}

function cleanPayload(payload) {
  const body = { ...payload };
  delete body.client_display_name;
  if (body.monthly_cost !== undefined) body.monthly_cost = String(body.monthly_cost || "0");
  return body;
}

function platformMatches(value, platform) {
  return platform.providers.includes(value) || value === platform.id || (platform.id === "dns" && ["custom", "cloudflare", "dns"].includes(value));
}

function isDown(project) {
  return ["offline", "down"].includes(String(project.server_status || "").toLowerCase()) || ["expired", "maintenance"].includes(String(project.status || "").toLowerCase());
}

function nextYear(date) {
  const base = date ? new Date(date) : new Date();
  base.setFullYear(base.getFullYear() + 1);
  return base.toISOString().slice(0, 10);
}

function expiryState(date) {
  if (!date) return "normal";
  const days = Math.ceil((new Date(date).getTime() - Date.now()) / 86400000);
  if (days < 0) return "expired";
  if (days <= 7) return "critical";
  if (days <= 30) return "soon";
  return "normal";
}

function remainingDays(date) {
  if (!date) return 365;
  return Math.ceil((new Date(date).getTime() - Date.now()) / 86400000);
}

function expiryLabel(state, days) {
  if (state === "expired") return "Expired";
  if (state === "critical") return `${Math.max(days, 0)} days left`;
  if (state === "soon") return "Expiring Soon";
  return "Healthy";
}

function handleRedeployProject(project, vercelRows, vercelMutation, providerMutation) {
  const provider = controlProviderFor(project);
  if (provider === "netlify") {
    providerMutation.mutate(project);
    return;
  }
  const match = vercelRows.find((item) => item.hosted_project === project.id || item.production_domain === project.domain || item.latest_deployment_url === project.deploy_url || item.name === project.name);
  if (match?.id && match?.latest_deployment_id) {
    vercelMutation.mutate({ id: match.id, deployment_id: match.latest_deployment_id });
    return;
  }
  window.dispatchEvent(new CustomEvent("manageai:toast", { detail: { type: "info", message: "Redeploy is available after the project is linked to a Vercel deployment." } }));
}

function controlProviderFor(project) {
  const value = String(project?.hosting_platform || "").toLowerCase();
  if (["aws", "s3", "cloudfront", "aws_s3", "aws_cloudfront"].includes(value)) return "aws";
  if (["custom", "dns", "cloudflare"].includes(value)) return "cloudflare";
  return value;
}

function supportsProviderControls(provider) {
  return ["aws", "vercel"].includes(provider);
}

function toast(type, message) {
  window.dispatchEvent(new CustomEvent("manageai:toast", { detail: { type, message } }));
}

function parseMetricValue(value) {
  const text = String(value ?? 0);
  const match = text.match(/^([^0-9.-]*)([0-9.-]+)(.*)$/);
  if (!match) return { prefix: "", number: Number(value || 0), suffix: "" };
  return { prefix: match[1], number: Number(match[2] || 0), suffix: match[3] };
}

function average(values) {
  const nums = values.map((value) => Number(value || 0)).filter((value) => Number.isFinite(value) && value > 0);
  if (!nums.length) return 0;
  return Math.round(nums.reduce((sum, value) => sum + value, 0) / nums.length);
}

function pretty(value) {
  return String(value || "unknown").replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function shortName(value) {
  const text = String(value || "App");
  return text.length > 10 ? `${text.slice(0, 9)}…` : text;
}

function badgeClass(tone) {
  return {
    emerald: "bg-emerald-500/12 text-emerald-300 ring-1 ring-emerald-400/25",
    rose: "bg-rose-500/12 text-rose-300 ring-1 ring-rose-400/25",
    amber: "bg-amber-500/12 text-amber-300 ring-1 ring-amber-400/25",
    cyan: "bg-cyan-500/12 text-cyan-300 ring-1 ring-cyan-400/25"
  }[tone];
}

function toneClass(tone) {
  return {
    emerald: "bg-emerald-500/12 text-emerald-300",
    rose: "bg-rose-500/12 text-rose-300",
    amber: "bg-amber-500/12 text-amber-300",
    cyan: "bg-cyan-500/12 text-cyan-300"
  }[tone];
}

function toneText(tone) {
  return {
    emerald: "text-emerald-300",
    rose: "text-rose-300",
    amber: "text-amber-300",
    cyan: "text-cyan-300"
  }[tone];
}

function tooltipStyle() {
  return {
    background: "var(--surface-strong)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    color: "var(--text-strong)"
  };
}
