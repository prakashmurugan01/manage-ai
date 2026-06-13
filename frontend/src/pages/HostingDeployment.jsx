import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Bot,
  Boxes,
  CheckCircle2,
  Cloud,
  CloudCog,
  CloudUpload,
  Code2,
  Cpu,
  Database,
  ExternalLink,
  FileArchive,
  FileCode2,
  FolderGit2,
  FolderUp,
  Gauge,
  GitBranch,
  Github,
  Gitlab,
  Globe2,
  HardDrive,
  Layers3,
  Loader2,
  LockKeyhole,
  Network,
  Play,
  RefreshCcw,
  Rocket,
  ScanSearch,
  Server,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  UploadCloud,
  WalletCards,
  Zap
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { api, apiErrorMessage as formatApiErrorMessage } from "../api/client.js";

const steps = ["Upload Project", "AI Analysis", "Select Hosting", "Configure", "Deploy & Monitor"];
const MAX_UPLOAD_BYTES = 5 * 1024 * 1024 * 1024;
const CHUNKED_UPLOAD_THRESHOLD = 128 * 1024 * 1024;
const CHUNK_SIZE = 8 * 1024 * 1024;
const ACCEPTED_UPLOAD_TYPES = ".zip,.gif,.png,.jpg,.jpeg,.webp,.svg,.mp4,.mov,.webm,.pdf,.html,.htm,.css,.js,.jsx,.ts,.tsx,.json,.txt,application/zip,image/*,video/*";
const ALLOWED_SINGLE_UPLOAD_EXTENSIONS = new Set([
  ".zip",
  ".gif",
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
  ".svg",
  ".mp4",
  ".mov",
  ".webm",
  ".pdf",
  ".html",
  ".htm",
  ".css",
  ".js",
  ".jsx",
  ".ts",
  ".tsx",
  ".json",
  ".txt"
]);

const frameworks = [
  "Django",
  "Flask",
  "FastAPI",
  "React",
  "Next.js",
  "Angular",
  "Vue",
  "Node.js",
  "PHP",
  "Laravel",
  "WordPress",
  "Static Website",
  "Spring Boot",
  ".NET"
];

const providerCatalog = [
  { id: "aws", name: "AWS", icon: Server, bestFor: "Django, Node, enterprise APIs", region: "Global", cost: "$$$", performance: 96, security: 98, scale: 99 },
  { id: "azure", name: "Azure", icon: CloudCog, bestFor: ".NET, enterprise workloads", region: "Global", cost: "$$$", performance: 93, security: 97, scale: 98 },
  { id: "gcp", name: "Google Cloud", icon: Cloud, bestFor: "AI apps, containers, data APIs", region: "Global", cost: "$$$", performance: 94, security: 96, scale: 98 },
  { id: "digitalocean", name: "DigitalOcean", icon: Server, bestFor: "Laravel, droplets, APIs", region: "14 regions", cost: "$$", performance: 89, security: 87, scale: 90 },
  { id: "vercel", name: "Vercel", icon: Rocket, bestFor: "React, Next.js, preview deploys", region: "Edge", cost: "$$", performance: 98, security: 91, scale: 95 },
  { id: "netlify", name: "Netlify", icon: Zap, bestFor: "React, Vue, JAMstack", region: "Edge", cost: "$", performance: 94, security: 90, scale: 92 },
  { id: "railway", name: "Railway", icon: GitBranch, bestFor: "Fast API launches and workers", region: "Cloud", cost: "$$", performance: 87, security: 86, scale: 88 },
  { id: "render", name: "Render", icon: Layers3, bestFor: "Web services and cron jobs", region: "Global", cost: "$$", performance: 88, security: 88, scale: 89 },
  { id: "firebase", name: "Firebase", icon: FlameIcon, bestFor: "Static, mobile, realtime apps", region: "Global", cost: "$", performance: 92, security: 90, scale: 94 },
  { id: "hostinger", name: "Hostinger", icon: Globe2, bestFor: "WordPress and budget sites", region: "Global", cost: "$", performance: 82, security: 84, scale: 78 },
  { id: "siteground", name: "SiteGround", icon: ShieldCheck, bestFor: "WordPress and commerce", region: "Global", cost: "$$", performance: 86, security: 89, scale: 82 },
  { id: "cloudflare", name: "Cloudflare Pages", icon: Network, bestFor: "Static sites and edge functions", region: "Edge", cost: "$", performance: 97, security: 96, scale: 96 },
  { id: "supabase", name: "Supabase", icon: Database, bestFor: "Postgres-backed full stack apps", region: "Global", cost: "$$", performance: 88, security: 89, scale: 90 },
  { id: "fly", name: "Fly.io", icon: Boxes, bestFor: "Docker apps close to users", region: "Global", cost: "$$", performance: 91, security: 88, scale: 91 },
  { id: "github", name: "GitHub Deployments", icon: Github, bestFor: "Actions-native workflows", region: "Global", cost: "$", performance: 84, security: 88, scale: 82 },
  { id: "cpanel", name: "cPanel", icon: HardDrive, bestFor: "PHP and shared hosting", region: "Hosted", cost: "$", performance: 78, security: 80, scale: 72 },
  { id: "plesk", name: "Plesk", icon: Server, bestFor: "Managed VPS panels", region: "Hosted", cost: "$$", performance: 80, security: 83, scale: 76 }
];

const recommendationMap = {
  React: "vercel",
  "Next.js": "vercel",
  Django: "aws",
  Laravel: "digitalocean",
  WordPress: "hostinger",
  "Static Website": "cloudflare",
  FastAPI: "fly",
  Flask: "render",
  Angular: "netlify",
  Vue: "netlify",
  "Node.js": "railway",
  PHP: "cpanel",
  "Spring Boot": "aws",
  ".NET": "azure"
};

export default function HostingDeployment() {
  const [step, setStep] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadQueue, setUploadQueue] = useState([]);
  const [uploadSession, setUploadSession] = useState(null);
  const [uploadPaused, setUploadPaused] = useState(false);
  const [upload, setUpload] = useState(null);
  const [uploadStatus, setUploadStatus] = useState("Waiting for project");
  const [autoDeploy, setAutoDeploy] = useState(false);
  const [selectedFramework, setSelectedFramework] = useState("React");
  const [providerRoles, setProviderRoles] = useState({
    aws: [],
    azure: [],
    gcp: [],
    vercel: [],
    netlify: [],
    cloudflare: []
  });
  const [config, setConfig] = useState({
    custom_domain: "",
    subdomain: "app",
    build_command: "",
    output_directory: "",
    environmentText: "NODE_ENV=production\nAPI_HEALTHCHECK=/health",
    database: "PostgreSQL",
    redis: true,
    storage: true,
    ssl: true,
    cdn: true,
    backups: true
  });
  const [deployment, setDeployment] = useState(null);
  const [deploying, setDeploying] = useState(false);
  const inputRef = useRef(null);
  const folderRef = useRef(null);
  const uploadAbortRef = useRef(null);
  const lastUploadItemsRef = useRef([]);
  const uploadSessionRef = useRef(null);

  const analysis = upload?.analysis || {};
  const detectedType = readableFramework(upload?.project_type) || selectedFramework;
  const recommendedProvider = providerCatalog.find((item) => item.id === (recommendationMap[detectedType] || "vercel")) || providerCatalog[4];
  const suggestedProviderIds = new Set([recommendedProvider.id, ...(upload?.suggested_providers || [])]);

  const selectedSummary = useMemo(() => {
    const roles = { primary: [], backup: [], failover: [], recovery: [] };
    Object.entries(providerRoles).forEach(([id, values]) => values.forEach((role) => roles[role]?.push(id)));
    return roles;
  }, [providerRoles]);

  const deploymentPlan = useMemo(() => buildDeploymentPlan(selectedSummary), [selectedSummary]);

  const autoConfig = useMemo(() => ({
    project_slug: slugFromName(upload?.original_name),
    default_domain: defaultDomainForProvider(slugFromName(upload?.original_name), deploymentPlan.primary),
    custom_domain: normalizeDomain(config.custom_domain),
    build_command: config.build_command || analysis.build_command || commandForFramework(detectedType).build,
    start_command: analysis.start_command || commandForFramework(detectedType).start,
    output_directory: config.output_directory || analysis.output_directory || commandForFramework(detectedType).output,
    readiness: Math.min(99, Number(analysis.readiness_score || 92))
  }), [analysis, config, deploymentPlan.primary, detectedType, upload]);

  async function handleFiles(source) {
    const items = normalizeUploadItems(source);
    if (!items.length) return;
    lastUploadItemsRef.current = items;
    await uploadItems(items, { resume: false });
  }

  async function uploadItems(items, { resume = false } = {}) {
    const validation = validateUploadItems(items);
    if (validation) {
      setUploadStatus(validation);
      setUploadProgress(0);
      setUploadQueue([]);
      return;
    }
    setUpload(null);
    setUploadPaused(false);
    setUploadStatus(resume ? "Resuming upload" : "Preparing upload");
    setUploadProgress(1);
    setUploadQueue(queueFromItems(items));
    const singleLargeFile = items.length === 1 && items[0].file.size >= CHUNKED_UPLOAD_THRESHOLD;
    if (singleLargeFile) {
      await uploadSingleFileInChunks(items[0], { resume });
      return;
    }
    await uploadMultipartItems(items);
  }

  async function uploadMultipartItems(items) {
    const folderUpload = isFolderUpload(items);
    const data = new FormData();
    items.forEach((item) => {
      data.append("upload", item.file, item.file.name);
      data.append("paths", item.path || item.file.webkitRelativePath || item.file.name);
    });
    data.append("source_type", folderUpload ? "folder" : uploadSourceType(items[0].file));
    const controller = new AbortController();
    uploadAbortRef.current = controller;
    setUploadStatus(folderUpload ? `Uploading folder with ${items.length} file(s)` : `Uploading ${items[0].file.name}`);
    try {
      const response = await api.post("/hosting/uploads/", data, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 0,
        signal: controller.signal,
        onUploadProgress: (event) => {
          if (!event.total) return;
          const progress = Math.round((event.loaded / event.total) * 100);
          setUploadProgress(progress);
          setUploadQueue((current) => markQueueProgress(current, progress));
        }
      });
      uploadAbortRef.current = null;
      const nextUpload = normalizeUploadRecord(response.data);
      setUpload(nextUpload);
      setUploadQueue((current) => current.map((item) => ({ ...item, status: "done", progress: 100 })));
      setUploadProgress(100);
      setUploadStatus("AI analysis running");
      setStep(1);
      const nextUploadId = getUploadId(nextUpload);
      if (nextUploadId) pollUpload(nextUploadId);
    } catch (error) {
      uploadAbortRef.current = null;
      if (isAbortError(error)) {
        setUploadPaused(true);
        setUploadStatus("Upload paused. Resume will retry the queued files.");
        setUploadQueue((current) => current.map((item) => item.status === "done" ? item : { ...item, status: "paused" }));
        return;
      }
      setUploadProgress(0);
      setUploadStatus(apiErrorMessage(error, "Project upload failed. Check the backend connection and try again."));
      setUploadQueue((current) => current.map((item) => item.status === "done" ? item : { ...item, status: "error" }));
    }
  }

  async function uploadSingleFileInChunks(item, { resume = false } = {}) {
    const file = item.file;
    let session = resume ? uploadSessionRef.current : null;
    const uploadKey = `${file.name}:${file.size}:${file.lastModified || 0}`;
    if (session?.uploadKey !== uploadKey) session = null;
    const controller = new AbortController();
    uploadAbortRef.current = controller;
    try {
      if (!session) {
        const { data } = await api.post("/hosting/uploads/chunk/initiate/", {
          original_name: file.name,
          source_type: uploadSourceType(file),
          size_bytes: file.size,
          chunk_size: CHUNK_SIZE
        }, { signal: controller.signal });
        session = { ...data, uploadKey };
      } else {
        const { data } = await api.get("/hosting/uploads/chunk/status/", {
          params: { upload_id: session.upload_id },
          signal: controller.signal
        });
        session = { ...data, uploadKey };
      }
      uploadSessionRef.current = session;
      setUploadSession(session);
      const missingChunks = Array.isArray(session.missing_chunks) && session.missing_chunks.length
        ? session.missing_chunks
        : Array.from({ length: session.total_chunks }, (_, index) => index).filter((index) => !(session.received_chunks || []).includes(index));
      const uploaded = new Set(session.received_chunks || []);
      setUploadStatus(`Uploading ${file.name} in ${session.total_chunks} resumable chunk(s)`);
      for (const chunkIndex of missingChunks) {
        if (controller.signal.aborted) throw new DOMException("Upload cancelled", "AbortError");
        const start = chunkIndex * session.chunk_size;
        const end = Math.min(file.size, start + session.chunk_size);
        const formData = new FormData();
        formData.append("upload_id", session.upload_id);
        formData.append("chunk_index", String(chunkIndex));
        formData.append("chunk", file.slice(start, end), file.name);
        await api.post("/hosting/uploads/chunk/upload/", formData, {
          headers: { "Content-Type": "multipart/form-data" },
          timeout: 0,
          signal: controller.signal,
          onUploadProgress: (event) => {
            const chunkProgress = event.total ? event.loaded / event.total : 0;
            const progress = Math.round(((uploaded.size + chunkProgress) / session.total_chunks) * 100);
            setUploadProgress(progress);
            setUploadQueue((current) => markQueueProgress(current, progress));
          }
        });
        uploaded.add(chunkIndex);
        const progress = Math.round((uploaded.size / session.total_chunks) * 100);
        setUploadProgress(progress);
        setUploadQueue((current) => markQueueProgress(current, progress));
      }
      const { data: completedUpload } = await api.post("/hosting/uploads/chunk/complete/", { upload_id: session.upload_id }, { signal: controller.signal });
      const nextUpload = normalizeUploadRecord(completedUpload);
      const nextUploadId = getUploadId(nextUpload);
      uploadAbortRef.current = null;
      setUpload(nextUpload);
      setUploadSession(null);
      uploadSessionRef.current = null;
      setUploadQueue((current) => current.map((queueItem) => ({ ...queueItem, status: "done", progress: 100 })));
      setUploadProgress(100);
      setUploadStatus("AI analysis running");
      setStep(1);
      if (nextUploadId) {
        pollUpload(nextUploadId);
      } else {
        setUploadStatus("Upload completed, but the backend did not return a project upload id. Refresh uploads and retry.");
      }
    } catch (error) {
      uploadAbortRef.current = null;
      if (isAbortError(error)) {
        setUploadPaused(true);
        setUploadStatus("Upload paused. Resume will continue from received chunks.");
        setUploadQueue((current) => current.map((queueItem) => ({ ...queueItem, status: "paused" })));
        return;
      }
      setUploadProgress(0);
      setUploadStatus(apiErrorMessage(error, "Resumable upload failed. Retry will continue from completed chunks when possible."));
      setUploadQueue((current) => current.map((queueItem) => ({ ...queueItem, status: "error" })));
    }
  }

  function cancelUpload() {
    uploadAbortRef.current?.abort();
  }

  async function retryUpload() {
    if (!lastUploadItemsRef.current.length) return;
    await uploadItems(lastUploadItemsRef.current, { resume: true });
  }

  async function pollUpload(id) {
    if (!validId(id)) {
      setUploadStatus("Upload record is not ready yet. Complete upload before analysis or deployment.");
      return;
    }
    try {
      for (let i = 0; i < 12; i += 1) {
        await wait(1400);
        const { data } = await api.get(`/hosting/uploads/${id}/`);
        setUpload(data);
        if (["analyzed", "failed"].includes(data.status)) {
          setUploadStatus(data.status === "analyzed" ? "Analysis completed" : "Analysis failed");
          const detected = readableFramework(data.project_type);
          if (detected) setSelectedFramework(detected);
          if (Array.isArray(data.analysis?.environment_variables) && data.analysis.environment_variables.length) {
            setConfig((current) => ({
              ...current,
              environmentText: data.analysis.environment_variables
                .map((key) => `${key}=${current.environmentText.match(new RegExp(`^${key}=(.*)$`, "m"))?.[1] || ""}`)
                .join("\n"),
              database: Array.isArray(data.analysis.databases) && data.analysis.databases[0] && data.analysis.databases[0] !== "None detected" ? data.analysis.databases[0] : current.database,
            }));
          }
          if (data.status === "analyzed" && autoDeploy) {
            if (!deploymentPlan.primary) {
              setUploadStatus("Validation completed. Select a primary hosting provider before auto deploy can start.");
              return;
            }
            setUploadStatus(`Validation completed. Deployment target selected: ${providerDisplayName(deploymentPlan.primary)}.`);
            deploy(data, deploymentPlan.primary);
          }
          return;
        }
      }
      setUploadStatus("Analysis is still running. You can continue when the scan completes.");
    } catch (error) {
      setUploadStatus(apiErrorMessage(error, "Analysis status could not be loaded."));
    }
  }

  async function deploy(uploadOverride = null, providerOverride = "") {
    const activeUpload = uploadOverride || upload;
    const activeUploadId = getUploadId(activeUpload);
    const activeAnalysis = activeUpload?.analysis || analysis;
    const activeFramework = readableFramework(activeUpload?.project_type) || detectedType;
    const activeCommands = commandForFramework(activeFramework);
    const selectedProvider = providerOverride || deploymentPlan.primary;
    const activeAutoConfig = {
      custom_domain: normalizeDomain(config.custom_domain),
      build_command: config.build_command || activeAnalysis.build_command || activeCommands.build,
      output_directory: config.output_directory || activeAnalysis.output_directory || activeCommands.output,
    };
    if (!activeUploadId) {
      setStep(4);
      setDeployment({
        status: "error",
        progress: 0,
        error_message: "Upload a project before deployment. No provider deployment was started.",
        logs: [{ message: "Deployment stopped: no project upload record id is available yet." }]
      });
      return;
    }
    if (!selectedProvider) {
      setStep(4);
      setDeployment({
        status: "error",
        progress: 0,
        error_message: "Select a primary hosting provider before deployment. No provider deployment was started.",
        logs: [{ message: "Deployment stopped: primary_provider is required." }]
      });
      return;
    }
    setDeploying(true);
    const environment = Object.fromEntries(
      config.environmentText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
          const [key, ...rest] = line.split("=");
          return [key, rest.join("=")];
        })
    );
    if (Array.isArray(activeAnalysis.environment_variables)) {
      activeAnalysis.environment_variables.forEach((key) => {
        if (!(key in environment)) environment[key] = "";
      });
    }
    try {
      const { data } = await api.post(`/hosting/uploads/${activeUploadId}/deploy/`, {
        primary_provider: selectedProvider,
        backup_provider: deploymentPlan.backup,
        domain: activeAutoConfig.custom_domain,
        build_command: activeAutoConfig.build_command,
        output_directory: activeAutoConfig.output_directory,
        environment
      });
      setDeployment(data);
      setStep(4);
      pollDeployment(data.id);
    } catch (error) {
      setDeploying(false);
      setStep(4);
      const message = apiErrorMessage(error, "Deployment request failed.");
      const payload = error?.response?.data || {};
      if (payload.id) {
        setDeployment({
          ...payload,
          error_message: payload.error_message || message,
          logs: appendDeploymentLog(payload.logs, message),
        });
        return;
      }
      setDeployment({
        status: "error",
        progress: 0,
        primary_provider: payload.provider || selectedProvider,
        error_message: message,
        logs: [{ message }]
      });
    }
  }

  async function pollDeployment(id) {
    if (!validId(id)) {
      setDeploying(false);
      setDeployment((current) => ({
        ...(current || {}),
        status: "error",
        error_message: "Deployment record id is missing. Start deployment again from a completed upload.",
        logs: appendDeploymentLog(current?.logs, "Deployment record id is missing. Start deployment again from a completed upload.")
      }));
      return;
    }
    try {
      for (let i = 0; i < 60; i += 1) {
        await wait(5000);
        const { data } = await api.get(`/hosting/deployments/${id}/`);
        let nextDeployment = data;
        try {
          const { data: logData } = await api.get(`/hosting/deployments/${id}/logs/`);
          nextDeployment = {
            ...nextDeployment,
            logs: mergeProviderLogPayload(logData.logs || nextDeployment.logs, logData.provider_logs)
          };
        } catch (logError) {
          const logMessage = apiErrorMessage(logError, "");
          if (logMessage) nextDeployment = { ...nextDeployment, logs: appendDeploymentLog(nextDeployment.logs, logMessage) };
        }
        if (nextDeployment.live_url) {
          try {
            const { data: metricData } = await api.get(`/hosting/deployments/${id}/metrics/`);
            nextDeployment = { ...nextDeployment, metrics: metricData.metrics || nextDeployment.metrics };
          } catch {
            nextDeployment = { ...nextDeployment, metrics: nextDeployment.metrics || {} };
          }
        }
        setDeployment(nextDeployment);
        if (["live", "error", "failed"].includes(data.status)) {
          setDeploying(false);
          return;
        }
      }
      setDeploying(false);
    } catch (error) {
      const message = apiErrorMessage(error, "Deployment status could not be loaded.");
      setDeployment((current) => ({
        ...(current || {}),
        status: "error",
        progress: current?.progress ?? 0,
        error_message: message,
        logs: appendDeploymentLog(current?.logs, message)
      }));
      setDeploying(false);
    }
  }

  async function handleRedeploy() {
    if (!deployment?.id) return;
    setDeploying(true);
    try {
      const { data } = await api.post(`/hosting/deployments/${deployment.id}/redeploy/`, {
        primary_provider: deployment.primary_provider
      });
      setDeployment(data);
      pollDeployment(data.id);
    } catch (error) {
      const message = apiErrorMessage(error, "Redeploy request failed.");
      const payload = error?.response?.data || {};
      if (payload.id) {
        setDeployment({
          ...payload,
          error_message: payload.error_message || message,
          logs: appendDeploymentLog(payload.logs, message),
        });
        setDeploying(false);
        return;
      }
      setDeployment((current) => ({
        ...(current || {}),
        status: "error",
        progress: current?.progress ?? 100,
        error_message: message,
        logs: appendDeploymentLog(current?.logs, message)
      }));
      setDeploying(false);
    }
  }

  function toggleProviderRole(providerId, role) {
    setProviderRoles((current) => {
      const existing = current[providerId] || [];
      if (role === "primary") {
        if (existing.includes(role)) {
          return { ...current, [providerId]: existing.filter((item) => item !== role) };
        }
        return withPrimaryProvider(current, providerId);
      }
      const nextRoles = existing.includes(role) ? existing.filter((item) => item !== role) : [...existing, role];
      return { ...current, [providerId]: nextRoles };
    });
  }

  return (
    <div className="deploy-center-page relative -m-2 overflow-hidden rounded-xl border border-cyan-300/10 bg-[#050816] p-3 text-slate-100 shadow-[0_30px_100px_rgba(2,6,23,.58)] md:-m-4 md:p-6">
      <div className="deploy-grid-overlay pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(34,211,238,.055)_1px,transparent_1px),linear-gradient(90deg,rgba(168,85,247,.05)_1px,transparent_1px)] bg-[size:36px_36px]" />
      <div className="deploy-aurora pointer-events-none absolute inset-x-0 top-0 h-72 bg-[linear-gradient(115deg,rgba(34,211,238,.18),transparent_42%,rgba(168,85,247,.18))]" />

      <div className="relative space-y-5">
        <HeroHeader inputRef={inputRef} folderRef={folderRef} />

        <input ref={inputRef} type="file" accept={ACCEPTED_UPLOAD_TYPES} className="hidden" onChange={(event) => handleFiles(event.target.files)} />
        <input ref={folderRef} type="file" className="hidden" webkitdirectory="true" multiple onChange={(event) => handleFiles(event.target.files)} />

        <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_360px]">
          <main className="space-y-5">
            <StepTracker step={step} setStep={setStep} />

            <AnimatePresence mode="wait">
              {step === 0 && (
                <StepShell key="upload">
                  <UploadCenter
                    dragging={dragging}
                    setDragging={setDragging}
                    handleFiles={handleFiles}
                    autoDeploy={autoDeploy}
                    setAutoDeploy={setAutoDeploy}
                    inputRef={inputRef}
                    folderRef={folderRef}
                    upload={upload}
                    uploadProgress={uploadProgress}
                    uploadStatus={uploadStatus}
                    uploadQueue={uploadQueue}
                    uploadPaused={uploadPaused}
                    uploadSession={uploadSession}
                    canCancel={Boolean(uploadAbortRef.current)}
                    onCancel={cancelUpload}
                    onRetry={retryUpload}
                  />
                </StepShell>
              )}

              {step === 1 && (
                <StepShell key="analysis">
                  <AnalysisCenter
                    detectedType={detectedType}
                    setSelectedFramework={setSelectedFramework}
                    autoConfig={autoConfig}
                    analysis={analysis}
                    upload={upload}
                    recommendedProvider={recommendedProvider}
                  />
                </StepShell>
              )}

              {step === 2 && (
                <StepShell key="providers">
                  <ProviderSelection
                    providerRoles={providerRoles}
                    toggleProviderRole={toggleProviderRole}
                    suggestedProviderIds={suggestedProviderIds}
                    recommendedProvider={recommendedProvider}
                    deploymentPlan={deploymentPlan}
                  />
                </StepShell>
              )}

              {step === 3 && (
                <StepShell key="config">
                  <ConfigurationCenter config={config} setConfig={setConfig} autoConfig={autoConfig} selectedSummary={selectedSummary} deploymentPlan={deploymentPlan} detectedType={detectedType} />
                </StepShell>
              )}

              {step === 4 && (
                <StepShell key="monitor">
                  <MonitorCenter deployment={deployment} deploying={deploying} selectedSummary={selectedSummary} recommendedProvider={recommendedProvider} />
                </StepShell>
              )}
            </AnimatePresence>

            <div className="flex flex-col gap-3 rounded-lg border border-white/10 bg-white/[.045] p-3 backdrop-blur-xl sm:flex-row sm:items-center sm:justify-between">
              <button className="btn-secondary" disabled={step === 0} onClick={() => setStep((value) => Math.max(0, value - 1))}>
                <ArrowLeft size={16} /> Back
              </button>
              <div className="flex flex-wrap gap-2">
                {step < 3 && (
                  <button className="btn-primary" onClick={() => setStep((value) => Math.min(4, value + 1))}>
                    Continue <ArrowRight size={16} />
                  </button>
                )}
                {step === 3 && (
                  <button className="btn-primary" onClick={deploy} disabled={deploying}>
                    {deploying ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />} One Click Deploy
                  </button>
                )}
                {step === 4 && (
                  <button
                    className="btn-secondary"
                    disabled={!deployment?.id || deploying}
                    title={deployment?.id ? "Retry this deployment on its selected provider" : "Run a deployment before retrying"}
                    onClick={handleRedeploy}
                  >
                    {deploying ? <Loader2 size={16} className="animate-spin" /> : <RefreshCcw size={16} />} Retry Deployment
                  </button>
                )}
              </div>
            </div>
          </main>

          <aside className="space-y-5">
            <RecommendationPanel detectedType={detectedType} provider={recommendedProvider} />
            <AIAssistantPanel autoConfig={autoConfig} selectedSummary={selectedSummary} />
            <CostSecurityPanel />
          </aside>
        </div>
      </div>
    </div>
  );
}

function HeroHeader({ inputRef, folderRef }) {
  return (
    <header className="rounded-xl border border-white/10 bg-white/[.055] p-5 shadow-[0_24px_80px_rgba(2,6,23,.3)] backdrop-blur-2xl">
      <div className="grid gap-5 xl:grid-cols-[1fr_auto] xl:items-center">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs font-semibold text-cyan-100">
            <Sparkles size={14} /> AI-Powered Project Hosting Upload & Deployment Center
          </div>
          <h1 className="mt-4 text-3xl font-semibold tracking-normal text-white md:text-5xl">Deploy Center</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300 md:text-base">
            Upload any project, detect the framework, validate required secrets and domains, then deploy only through the provider adapter you select.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:flex">
          <button className="btn-secondary" onClick={() => inputRef.current?.click()}><FileArchive size={16} /> ZIP Upload</button>
          <button className="btn-primary" onClick={() => folderRef.current?.click()}><FolderUp size={16} /> Folder Upload</button>
        </div>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-4">
        <HeroMetric icon={Gauge} label="Readiness" value="After scan" />
        <HeroMetric icon={ShieldCheck} label="Security" value="Validated" />
        <HeroMetric icon={Activity} label="Provider Logs" value="Live only" />
        <HeroMetric icon={WalletCards} label="Cost" value="Provider API" />
      </div>
    </header>
  );
}

function StepTracker({ step, setStep }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[.055] p-3 backdrop-blur-xl">
      <div className="grid gap-2 lg:grid-cols-5">
        {steps.map((label, index) => (
          <button
            key={label}
            className={`group flex min-h-14 items-center gap-3 rounded-lg border px-3 text-left transition ${index <= step ? "border-cyan-300/35 bg-cyan-300/12 text-white" : "border-white/10 bg-white/[.035] text-slate-400 hover:border-white/20"}`}
            onClick={() => setStep(index)}
          >
            <span className={`grid size-9 shrink-0 place-items-center rounded-lg text-sm font-bold ${index <= step ? "bg-gradient-to-br from-cyan-300 to-violet-500 text-slate-950" : "bg-white/10 text-slate-400"}`}>
              {index < step ? <CheckCircle2 size={17} /> : index + 1}
            </span>
            <span className="text-sm font-semibold">{label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function UploadCenter({ dragging, setDragging, handleFiles, inputRef, folderRef, upload, uploadProgress, uploadStatus, uploadQueue, uploadPaused, uploadSession, canCancel, onCancel, onRetry, autoDeploy, setAutoDeploy }) {
  const imports = [
    { label: "GitHub Repository Import", icon: Github },
    { label: "GitLab Import", icon: Gitlab },
    { label: "Bitbucket Import", icon: FolderGit2 },
    { label: "One-click Clone Repository", icon: GitBranch }
  ];

  return (
    <div className="grid gap-5 xl:grid-cols-[1.1fr_.9fr]">
      <div
        onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={async (event) => {
          event.preventDefault();
          setDragging(false);
          handleFiles(await collectDroppedItems(event.dataTransfer));
        }}
        className={`relative grid min-h-[460px] place-items-center overflow-hidden rounded-xl border border-dashed p-6 text-center backdrop-blur-xl transition ${dragging ? "border-cyan-200 bg-cyan-300/15 shadow-[0_0_90px_rgba(34,211,238,.22)]" : "border-cyan-300/25 bg-white/[.045]"}`}
      >
        <motion.div animate={{ y: [0, -10, 0], rotateX: [0, 7, 0] }} transition={{ duration: 3, repeat: Infinity }} className="mx-auto grid size-24 place-items-center rounded-2xl border border-cyan-300/25 bg-gradient-to-br from-cyan-300/20 to-violet-500/20 text-cyan-100 shadow-[0_22px_70px_rgba(34,211,238,.16)]">
          <UploadCloud size={46} />
        </motion.div>
        <div className="max-w-xl">
          <h2 className="mt-7 text-2xl font-semibold text-white">Drag, drop, import, or clone your project</h2>
          <p className="mt-3 text-sm leading-6 text-slate-300">Supports ZIP upload, folder upload, GitHub, GitLab, Bitbucket, and repository cloning for Django, React, Laravel, WordPress, Spring Boot, .NET, and more.</p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button type="button" className="btn-primary" onClick={() => inputRef.current?.click()}><CloudUpload size={16} /> Choose Files</button>
            <button type="button" className="btn-secondary" onClick={() => folderRef.current?.click()}><FolderUp size={16} /> Choose Folder</button>
          </div>
          <button
            type="button"
            className={`mx-auto mt-4 flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition ${autoDeploy ? "border-emerald-300/35 bg-emerald-300/12 text-emerald-100" : "border-white/10 bg-white/[.04] text-slate-300"}`}
            onClick={() => setAutoDeploy(!autoDeploy)}
          >
            {autoDeploy ? <CheckCircle2 size={15} /> : <Play size={15} />} Auto deploy after validation
          </button>
          <UploadProgress status={uploadStatus} progress={uploadProgress} upload={upload} queue={uploadQueue} paused={uploadPaused} session={uploadSession} canCancel={canCancel} onCancel={onCancel} onRetry={onRetry} />
        </div>
      </div>

      <div className="space-y-4">
        {imports.map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.label} className="group flex w-full cursor-not-allowed items-center justify-between rounded-lg border border-white/10 bg-white/[.055] p-4 text-left opacity-70 backdrop-blur-xl" disabled>
              <span className="flex items-center gap-3">
                <span className="grid size-11 place-items-center rounded-lg bg-cyan-300/10 text-cyan-100"><Icon size={20} /></span>
                <span>
                  <span className="block text-sm font-semibold text-white">{item.label}</span>
                  <span className="mt-1 block text-xs text-slate-400">Connector required before repository clone is enabled</span>
                </span>
              </span>
              <ExternalLink size={16} className="text-slate-500 transition group-hover:text-cyan-200" />
            </button>
          );
        })}
      </div>
    </div>
  );
}

function AnalysisCenter({ detectedType, setSelectedFramework, autoConfig, analysis, upload, recommendedProvider }) {
  const databases = Array.isArray(analysis.databases) ? analysis.databases.join(", ") : databaseForFramework(detectedType);
  const envVars = Array.isArray(analysis.environment_variables) ? analysis.environment_variables.join(", ") : "Pending analysis";
  const runtimes = analysis.runtime_versions ? Object.entries(analysis.runtime_versions).map(([key, value]) => `${key} ${value}`).join(", ") : "Auto detected";
  const fileCount = analysis.file_count ?? upload?.analysis?.file_count ?? "Pending";
  return (
    <div className="grid gap-5 xl:grid-cols-[.95fr_1.05fr]">
      <section className="rounded-xl border border-white/10 bg-white/[.055] p-5 backdrop-blur-xl">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase text-cyan-200">AI Project Analysis</p>
            <h2 className="mt-1 text-2xl font-semibold text-white">{detectedType}</h2>
          </div>
          <ReadinessRing value={autoConfig.readiness} />
        </div>
        <div className="mt-5 grid gap-2 sm:grid-cols-2">
          {frameworks.map((item) => (
            <button key={item} onClick={() => setSelectedFramework(item)} className={`rounded-lg border px-3 py-2 text-left text-sm font-semibold transition ${item === detectedType ? "border-cyan-300/50 bg-cyan-300/15 text-cyan-100" : "border-white/10 bg-white/[.035] text-slate-300 hover:border-cyan-300/25"}`}>
              {item}
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-white/10 bg-white/[.055] p-5 backdrop-blur-xl">
        <div className="grid gap-3 md:grid-cols-2">
          <AnalysisField label="Framework" value={detectedType} icon={Code2} />
          <AnalysisField label="Build Command" value={autoConfig.build_command} icon={TerminalSquare} />
          <AnalysisField label="Start Command" value={autoConfig.start_command} icon={Play} />
          <AnalysisField label="Database Requirements" value={databases} icon={Database} />
          <AnalysisField label="Required Environment Variables" value={envVars} icon={LockKeyhole} />
          <AnalysisField label="Runtime Versions" value={runtimes} icon={Cpu} />
          <AnalysisField label="Best Hosting Recommendation" value={recommendedProvider.name} icon={Rocket} />
        </div>
        <div className="mt-4 rounded-lg border border-cyan-300/20 bg-cyan-300/10 p-4 text-sm text-cyan-50">
          Files scanned: {fileCount}. Deployment readiness is calculated from framework, package metadata, env requirements, database hints, and security baseline.
        </div>
      </section>
    </div>
  );
}

function ProviderSelection({ providerRoles, toggleProviderRole, suggestedProviderIds, recommendedProvider, deploymentPlan }) {
  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-cyan-300/20 bg-gradient-to-r from-cyan-300/12 to-violet-500/12 p-4 backdrop-blur-xl">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase text-cyan-200">AI Recommendation Engine</p>
            <h2 className="mt-1 text-xl font-semibold text-white">Best Hosting Recommendation: {recommendedProvider.name}</h2>
            <p className="mt-2 flex items-center gap-2 text-sm text-slate-300">
              <LockKeyhole size={15} className="text-cyan-200" />
              Deployment target is selected only by the user: {deploymentPlan.primaryLabel}. Recommendations are advisory and never change it automatically.
            </p>
          </div>
          <div className="grid grid-cols-4 gap-2 text-center text-xs">
            <ScorePill label="Perf" value={recommendedProvider.performance} />
            <ScorePill label="Cost" value={costScore(recommendedProvider.cost)} />
            <ScorePill label="Sec" value={recommendedProvider.security} />
            <ScorePill label="Scale" value={recommendedProvider.scale} />
          </div>
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {providerCatalog.map((provider) => (
          <ProviderCard key={provider.id} provider={provider} roles={providerRoles[provider.id] || []} onToggle={toggleProviderRole} suggested={suggestedProviderIds.has(provider.id)} />
        ))}
      </div>
    </div>
  );
}

function ConfigurationCenter({ config, setConfig, autoConfig, selectedSummary, deploymentPlan, detectedType }) {
  const preflightRows = [
    ["Provider Target", deploymentPlan.primary ? `${deploymentPlan.primaryLabel} selected` : "Select a provider", deploymentPlan.primary ? "Selected" : "Required"],
    ["Credential Validation", deploymentPlan.uploadAdapterAvailable ? "Backend validates provider credentials before queueing" : "Provider selection required", deploymentPlan.uploadAdapterAvailable ? "Ready" : "Required"],
    ["Build Strategy", autoConfig.build_command || "Required", "Detected"],
    ["Env Validation", "Missing project secrets block deployment", "Required"],
    ["Domain Validation", "DNS checked when a custom domain is provided", "Required"],
    ["Log Source", "Provider task logs only", "Live"]
  ];

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_.9fr]">
      <section className="rounded-xl border border-white/10 bg-white/[.055] p-5 backdrop-blur-xl">
        <h2 className="text-2xl font-semibold text-white">Deployment Configuration</h2>
        <div className="mt-5 grid grid-cols-[repeat(auto-fit,minmax(min(230px,100%),1fr))] gap-4">
          <ConfigField label="Domain" value={config.custom_domain} onChange={(value) => setConfig({ ...config, custom_domain: value })} placeholder="app.yourdomain.com" />
          <ConfigField label="Subdomain" value={config.subdomain} onChange={(value) => setConfig({ ...config, subdomain: value })} />
          <ConfigField label="Build Command" value={autoConfig.build_command} onChange={(value) => setConfig({ ...config, build_command: value })} />
          <ConfigField label="Output Directory" value={autoConfig.output_directory} onChange={(value) => setConfig({ ...config, output_directory: value })} />
          <SelectField label="Database" value={config.database} onChange={(value) => setConfig({ ...config, database: value })} options={["PostgreSQL", "MySQL", "MongoDB", "MariaDB", "SQLite", "Redis", "Firebase", "None"]} />
          <SelectField label="Storage Bucket" value={config.storage ? "managed-project-assets" : "disabled"} onChange={(value) => setConfig({ ...config, storage: value !== "disabled" })} options={["managed-project-assets", "disabled"]} />
        </div>
        <label className="mt-4 grid gap-2">
          <span className="text-xs font-semibold uppercase text-slate-400">Environment Variables</span>
          <textarea className="form-control min-h-32 font-mono" value={config.environmentText} onChange={(event) => setConfig({ ...config, environmentText: event.target.value })} />
        </label>
        <div className="mt-4 grid grid-cols-[repeat(auto-fit,minmax(88px,1fr))] gap-2">
          <ToggleTile label="SSL" checked={config.ssl} onChange={() => setConfig({ ...config, ssl: !config.ssl })} />
          <ToggleTile label="CDN" checked={config.cdn} onChange={() => setConfig({ ...config, cdn: !config.cdn })} />
          <ToggleTile label="Redis" checked={config.redis} onChange={() => setConfig({ ...config, redis: !config.redis })} />
          <ToggleTile label="Auto Backup" checked={config.backups} onChange={() => setConfig({ ...config, backups: !config.backups })} />
        </div>
        {!deploymentPlan.primary && (
          <div className="mt-4 rounded-lg border border-amber-300/25 bg-amber-300/10 p-3 text-sm text-amber-100">
            Select a primary provider before deploying. The recommendation panel cannot silently choose one for you.
          </div>
        )}
      </section>

      <section className="space-y-4">
        <div className="rounded-xl border border-white/10 bg-white/[.055] p-5 backdrop-blur-xl">
          <p className="text-xs font-semibold uppercase text-cyan-200">Deployment Preflight</p>
          <div className="mt-4 grid gap-2">
            {preflightRows.map(([label, value, state]) => (
              <PreflightRow key={label} label={label} value={value} state={state} />
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-white/10 bg-white/[.055] p-5 backdrop-blur-xl">
          <p className="text-xs font-semibold uppercase text-cyan-200">Deployment Plan</p>
          <div className="mt-4 grid gap-3 text-sm">
            <PlanRow label="Framework" value={detectedType} />
            <PlanRow label="Default URL" value={autoConfig.default_domain} />
            <PlanRow label="Primary Hosting" value={deploymentPlan.primaryLabel} />
            <PlanRow label="Backup Hosting" value={deploymentPlan.backupLabel} />
            <PlanRow label="Failover Hosting" value={providerDisplayList(selectedSummary.failover)} />
            <PlanRow label="Disaster Recovery" value={providerDisplayList(selectedSummary.recovery)} />
          </div>
        </div>
      </section>
    </div>
  );
}

function MonitorCenter({ deployment, deploying, selectedSummary, recommendedProvider }) {
  const status = deployment?.status || (deploying ? "deploying" : "ready");
  const isError = ["error", "failed"].includes(status);
  const progress = clampPercent(deployment?.progress ?? (deploying ? 8 : 0));
  const logs = normalizeDeploymentLogs(deployment, deploying);
  const providerLabel = providerDisplayName(deployment?.primary_provider || selectedSummary.primary[0] || "");
  const metrics = deployment?.metrics || {};
  const displayProgress = isError ? Math.min(progress, 12) : progress;
  const progressText = isError
    ? `Deployment failed on selected primary target: ${providerLabel}.`
    : `${progress}% complete on selected primary target: ${providerLabel}.`;

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[.9fr_1.1fr]">
        <section className="rounded-xl border border-white/10 bg-white/[.055] p-5 backdrop-blur-xl">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase text-cyan-200">Deploy & Monitor</p>
              <h2 className="mt-1 text-2xl font-semibold text-white">One Click Deployment</h2>
            </div>
            <DeploymentStatus status={status} />
          </div>
          <div className="mt-6 h-4 overflow-hidden rounded-full bg-white/10">
            <motion.div
              className={`h-full rounded-full ${isError ? "bg-gradient-to-r from-amber-300 to-rose-400" : "bg-gradient-to-r from-cyan-300 via-sky-400 to-violet-500"}`}
              initial={{ width: 0 }}
              animate={{ width: `${displayProgress}%` }}
            />
          </div>
          <p className={`mt-3 text-sm ${isError ? "text-amber-200" : "text-slate-300"}`}>{progressText}</p>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <UsageMetric icon={Gauge} label="Latency" value={metrics.latency_ms ? `${metrics.latency_ms}ms` : "Awaiting live probe"} />
            <UsageMetric icon={Activity} label="HTTP" value={metrics.http_status || "Awaiting live probe"} />
            <UsageMetric icon={Network} label="DNS" value={metrics.dns_ok === true ? "Healthy" : metrics.dns_ok === false ? "Failed" : "Awaiting live probe"} />
            <UsageMetric icon={ShieldCheck} label="SSL" value={metrics.ssl_ok === true ? "Healthy" : metrics.ssl_ok === false ? "Failed" : "Awaiting live probe"} />
          </div>
          {deployment?.live_url && (
            <a href={deployment.live_url} target="_blank" rel="noreferrer" className="btn-primary mt-5">
              <ExternalLink size={16} /> Open Live URL
            </a>
          )}
        </section>

        <section className="overflow-hidden rounded-xl border border-white/10 bg-slate-950/70 backdrop-blur-xl">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <span className="flex items-center gap-2 text-sm font-semibold text-white"><TerminalSquare size={16} /> Live Deployment Logs</span>
            <span className="text-xs font-semibold text-cyan-200">Real-time</span>
          </div>
          <div className="h-80 space-y-2 overflow-auto p-4 font-mono text-xs leading-5 text-cyan-100 scrollbar-thin">
            {logs.map((log, index) => (
              <p key={`${log.time || "log"}-${index}`} className="flex gap-2">
                <span className="shrink-0 text-slate-500">$</span>
                <span className="min-w-0 whitespace-pre-wrap break-words">{log.message}</span>
              </p>
            ))}
            {status === "error" && (
              <p className="flex gap-2 text-amber-200">
                <span className="shrink-0">$</span>
                <span className="min-w-0 whitespace-pre-wrap break-words">Deployment failed. Review the provider error, connect the required adapter or secret, then retry.</span>
              </p>
            )}
          </div>
        </section>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <ProviderTargetCard providerLabel={providerLabel} deployment={deployment} />
        <FailoverCard selectedSummary={selectedSummary} recommendedProvider={recommendedProvider} />
        <NotificationsCard />
      </div>
    </div>
  );
}

function RecommendationPanel({ detectedType, provider }) {
  return (
    <section className="rounded-xl border border-cyan-300/20 bg-gradient-to-br from-cyan-300/12 to-violet-500/12 p-5 backdrop-blur-xl">
      <p className="text-xs font-semibold uppercase text-cyan-200">Best Hosting Recommendation</p>
      <div className="mt-4 flex items-center gap-3">
        <div className="grid size-12 place-items-center rounded-xl bg-cyan-300/15 text-cyan-100"><provider.icon size={24} /></div>
        <div className="min-w-0">
          <h3 className="break-words text-xl font-semibold text-white">{provider.name}</h3>
          <p className="text-sm text-slate-300">{detectedType} optimized target</p>
        </div>
      </div>
      <div className="mt-5 grid gap-3">
        <ScoreBar label="Performance Score" value={provider.performance} />
        <ScoreBar label="Cost Score" value={costScore(provider.cost)} />
        <ScoreBar label="Security Score" value={provider.security} />
        <ScoreBar label="Scalability Score" value={provider.scale} />
      </div>
    </section>
  );
}

function AIAssistantPanel({ autoConfig, selectedSummary }) {
  const backupLabel = selectedSummary.backup[0] ? providerDisplayName(selectedSummary.backup[0]) : "backup hosting";

  return (
    <section className="rounded-xl border border-white/10 bg-white/[.055] p-5 backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <motion.div animate={{ y: [0, -6, 0] }} transition={{ duration: 2.3, repeat: Infinity }} className="grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-cyan-300 to-violet-500 text-slate-950">
          <Bot size={25} />
        </motion.div>
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase text-cyan-200">Floating AI Assistant</p>
          <h3 className="text-lg font-semibold text-white">Deployment Copilot</h3>
        </div>
      </div>
      <div className="mt-4 space-y-3 text-sm text-slate-300">
        <div className="rounded-lg border border-white/10 bg-white/[.04] p-3">
          <p>Detected project commands from scan signals.</p>
          <div className="mt-3 grid gap-2">
            <CommandRow label="Build" value={autoConfig.build_command} />
            <CommandRow label="Start" value={autoConfig.start_command} />
          </div>
        </div>
        <p className="rounded-lg border border-white/10 bg-white/[.04] p-3">Failover can promote {backupLabel} only after real health checks fail.</p>
        <p className="rounded-lg border border-emerald-300/20 bg-emerald-300/10 p-3 text-emerald-100">Repair suggestions appear after real provider error logs are available.</p>
      </div>
    </section>
  );
}

function CostSecurityPanel() {
  return (
    <section className="rounded-xl border border-white/10 bg-white/[.055] p-5 backdrop-blur-xl">
      <p className="text-xs font-semibold uppercase text-cyan-200">Cost Optimizer & Security Center</p>
      <div className="mt-4 grid gap-3">
        <PlanRow label="Current Cost" value="Provider API required" />
        <PlanRow label="Monthly Cost" value="Pending live data" />
        <PlanRow label="Yearly Cost" value="Pending live data" />
      </div>
      <div className="mt-4 rounded-lg border border-cyan-300/20 bg-cyan-300/10 p-3 text-sm text-cyan-50">Cost advice is shown after provider billing and usage APIs are connected.</div>
      <div className="mt-4 grid gap-2 text-sm">
        {["Malware Scan", "Vulnerability Scan", "SSL Monitoring", "Firewall Monitoring", "DDoS Protection Status"].map((item) => (
          <div key={item} className="flex items-center justify-between rounded-lg bg-white/[.04] px-3 py-2">
            <span>{item}</span>
            <span className="font-semibold text-cyan-200">Pending</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function ProviderCard({ provider, roles, onToggle, suggested }) {
  const Icon = provider.icon;
  return (
    <motion.article whileHover={{ y: -5, rotateX: 2, rotateY: -2 }} className="group relative overflow-hidden rounded-xl border border-white/10 bg-white/[.055] p-4 shadow-[0_24px_60px_rgba(2,6,23,.26)] backdrop-blur-xl transition hover:border-cyan-300/35">
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-cyan-300 via-sky-400 to-violet-500 opacity-60" />
      <div className="flex items-start justify-between">
        <div className="grid size-12 place-items-center rounded-xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-100"><Icon size={22} /></div>
        {suggested && <span className="rounded-full bg-emerald-400/12 px-2 py-1 text-xs font-semibold text-emerald-100">Suggested</span>}
      </div>
      <h3 className="mt-4 text-lg font-semibold text-white">{provider.name}</h3>
      <p className="mt-1 min-h-10 text-sm text-slate-300">{provider.bestFor}</p>
      <div className="mt-4 grid grid-cols-4 gap-2 text-center text-xs">
        <ScorePill label="Perf" value={provider.performance} />
        <ScorePill label="Cost" value={costScore(provider.cost)} />
        <ScorePill label="Sec" value={provider.security} />
        <ScorePill label="Scale" value={provider.scale} />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        {[
          ["primary", "Primary Hosting"],
          ["backup", "Backup Hosting"],
          ["failover", "Failover Hosting"],
          ["recovery", "Disaster Recovery"]
        ].map(([role, label]) => (
          <label key={role} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition ${roles.includes(role) ? "border-cyan-300/45 bg-cyan-300/15 text-cyan-100" : "border-white/10 bg-white/[.035] text-slate-300 hover:border-white/20"}`}>
            <input type="checkbox" className="shrink-0 accent-cyan-300" checked={roles.includes(role)} onChange={() => onToggle(provider.id, role)} />
            <span className="min-w-0 break-words">{label}</span>
          </label>
        ))}
      </div>
    </motion.article>
  );
}

function ProviderTargetCard({ providerLabel, deployment }) {
  return (
    <section className="rounded-xl border border-white/10 bg-white/[.055] p-4 backdrop-blur-xl">
      <p className="flex items-center gap-2 text-sm font-semibold text-white"><Network size={16} className="text-cyan-200" /> Provider Target</p>
      <div className="mt-4 rounded-lg border border-cyan-300/20 bg-cyan-300/10 p-3 text-sm text-cyan-50">
        Primary deployment target is {providerLabel}. The recommendation engine cannot reroute it or pick a fallback.
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-center text-xs">
        <MiniStat label="Provider" value={providerLabel} />
        <MiniStat label="Status" value={deployment?.status || "Ready"} />
        <MiniStat label="Fallback" value="Disabled" />
        <MiniStat label="Run ID" value={deployment?.id ? String(deployment.id).slice(0, 8) : "None"} />
      </div>
    </section>
  );
}

function FailoverCard({ selectedSummary }) {
  return (
    <section className="rounded-xl border border-white/10 bg-white/[.055] p-4 backdrop-blur-xl">
      <p className="flex items-center gap-2 text-sm font-semibold text-white"><ScanSearch size={16} className="text-cyan-200" /> High Availability</p>
      <div className="mt-4 rounded-lg border border-emerald-300/20 bg-emerald-300/10 p-3 text-sm text-emerald-100">
        Failover remains inactive until real health checks confirm primary failure.
      </div>
      <div className="mt-4 grid gap-2 text-sm">
        <PlanRow label="Backup" value={providerDisplayList(selectedSummary.backup)} />
        <PlanRow label="Failover" value={providerDisplayList(selectedSummary.failover)} />
        <PlanRow label="Recovery" value={providerDisplayList(selectedSummary.recovery)} />
      </div>
    </section>
  );
}

function NotificationsCard() {
  return (
    <section className="rounded-xl border border-white/10 bg-white/[.055] p-4 backdrop-blur-xl">
      <p className="flex items-center gap-2 text-sm font-semibold text-white"><AlertTriangle size={16} className="text-cyan-200" /> Notifications</p>
      <div className="mt-4 space-y-2">
        {["Deployment Success", "Deployment Failure", "Server Down", "SSL Expiry", "Domain Expiry", "Security Alerts"].map((item, index) => (
          <div key={item} className="flex items-start justify-between gap-3 rounded-lg border border-white/10 bg-white/[.04] px-3 py-2 text-sm">
            <span className="min-w-0 break-words text-slate-200">{item}</span>
            <span className="shrink-0 text-right text-cyan-200">{index < 2 ? "Provider logs" : "Pending checks"}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function UploadProgress({ status, progress, upload, queue = [], paused, session, canCancel, onCancel, onRetry }) {
  return (
    <div className="mt-6 rounded-lg border border-white/10 bg-white/[.055] p-4">
      <div className="flex flex-col gap-1 text-sm sm:flex-row sm:items-start sm:justify-between sm:gap-3">
        <span className="min-w-0 break-words text-slate-300">{upload?.original_name || queue[0]?.name || "No file selected"}</span>
        <span className="font-semibold text-cyan-200 sm:max-w-[52%] sm:text-right">{status}</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-gradient-to-r from-cyan-300 to-violet-500 transition-all" style={{ width: `${clampPercent(Math.max(progress, upload ? 100 : 0))}%` }} />
      </div>
      {session?.upload_id && (
        <p className="mt-2 text-xs text-slate-400">
          Session {String(session.upload_id).slice(0, 8)} · {session.received_chunks?.length || 0}/{session.total_chunks || 0} chunks received
        </p>
      )}
      {!!queue.length && (
        <div className="mt-4 max-h-36 space-y-2 overflow-auto pr-1 text-xs">
          {queue.slice(0, 8).map((item) => (
            <div key={item.id} className="flex items-center justify-between gap-3 rounded-md border border-white/10 bg-white/[.035] px-3 py-2">
              <span className="min-w-0 truncate text-slate-300">{item.path || item.name}</span>
              <span className={`shrink-0 font-semibold ${queueStatusTone(item.status)}`}>{formatStatusLabel(item.status || "queued")}</span>
            </div>
          ))}
          {queue.length > 8 && <p className="text-slate-500">+{queue.length - 8} more file(s) queued</p>}
        </div>
      )}
      {(canCancel || paused || queue.some((item) => item.status === "error")) && (
        <div className="mt-4 flex flex-wrap gap-2">
          {canCancel && (
            <button type="button" className="btn-secondary" onClick={onCancel}>
              <RefreshCcw size={14} /> Pause Upload
            </button>
          )}
          {(paused || queue.some((item) => item.status === "error")) && (
            <button type="button" className="btn-primary" onClick={onRetry}>
              <UploadCloud size={14} /> Resume / Retry
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function StepShell({ children }) {
  return (
    <motion.section initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -14 }} transition={{ duration: 0.24 }}>
      {children}
    </motion.section>
  );
}

function AnalysisField({ label, value, icon: Icon }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[.04] p-4">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-400"><Icon size={15} className="text-cyan-200" /> {label}</div>
      <p className="mt-2 break-words text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

function HeroMetric({ icon: Icon, label, value }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[.04] p-3">
      <Icon size={17} className="text-cyan-200" />
      <p className="mt-3 text-xs text-slate-400">{label}</p>
      <p className="text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function ScorePill({ label, value }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[.045] p-2">
      <p className="text-[10px] uppercase text-slate-400">{label}</p>
      <p className="mt-1 font-semibold text-white">{value}</p>
    </div>
  );
}

function ScoreBar({ label, value }) {
  const score = clampPercent(value);
  return (
    <div>
      <div className="flex justify-between gap-3 text-xs font-semibold text-slate-300"><span>{label}</span><span>{score}</span></div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-gradient-to-r from-cyan-300 to-violet-500" style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

function PreflightRow({ label, value, state }) {
  const tone = preflightTone(state);
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-white/10 bg-white/[.04] px-3 py-2 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
      <span className="flex min-w-0 items-center gap-2 text-sm font-semibold text-white"><FileCode2 size={16} className="shrink-0 text-cyan-200" /> <span className="break-words">{label}</span></span>
      <span className={`min-w-0 break-words text-left text-xs font-semibold sm:max-w-[58%] sm:text-right ${tone}`}>
        <span className="font-bold">{state}:</span> {value}
      </span>
    </div>
  );
}

function ConfigField({ label, value, onChange, placeholder }) {
  return (
    <label className="grid min-w-0 gap-2">
      <span className="text-xs font-semibold uppercase text-slate-400">{label}</span>
      <input className="form-control" value={value} placeholder={placeholder} autoComplete="off" spellCheck={false} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function SelectField({ label, value, onChange, options }) {
  return (
    <label className="grid min-w-0 gap-2">
      <span className="text-xs font-semibold uppercase text-slate-400">{label}</span>
      <select className="form-control" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option}>{option}</option>)}
      </select>
    </label>
  );
}

function ToggleTile({ label, checked, onChange }) {
  return (
    <button type="button" className={`min-h-16 rounded-lg border px-3 py-3 text-sm font-semibold transition ${checked ? "border-cyan-300/45 bg-cyan-300/15 text-cyan-100" : "border-white/10 bg-white/[.035] text-slate-400"}`} onClick={onChange}>
      {checked ? <CheckCircle2 size={16} className="mx-auto mb-1" /> : <Cloud size={16} className="mx-auto mb-1" />}
      <span className="block break-words leading-tight">{label}</span>
    </button>
  );
}

function PlanRow({ label, value }) {
  return <div className="flex items-start justify-between gap-3 border-b border-white/10 pb-2 last:border-b-0"><span className="shrink-0 text-slate-400">{label}</span><span className="min-w-0 break-words text-right font-semibold text-white">{displayValue(value)}</span></div>;
}

function UsageMetric({ icon: Icon, label, value }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[.04] p-3">
      <Icon size={16} className="text-cyan-200" />
      <p className="mt-2 text-xs text-slate-400">{label}</p>
      <p className="break-words font-semibold text-white">{displayValue(value)}</p>
    </div>
  );
}

function DeploymentStatus({ status }) {
  const normalized = String(status || "ready").toLowerCase();
  const live = normalized === "live";
  const error = normalized === "error";
  const active = ["deploying", "queued", "running", "uploading", "building", "configuring", "analyzing", "verifying"].includes(normalized);
  const Icon = live ? CheckCircle2 : error ? AlertTriangle : active ? Loader2 : Rocket;
  return (
    <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${live ? "bg-emerald-400/10 text-emerald-100" : error ? "bg-rose-400/10 text-rose-100" : "bg-cyan-400/10 text-cyan-100"}`}>
      <Icon size={14} className={active ? "animate-spin" : ""} /> {formatStatusLabel(normalized)}
    </span>
  );
}

function ReadinessRing({ value }) {
  return (
    <div className="relative grid size-24 place-items-center">
      <div className="absolute inset-0 rounded-full bg-[conic-gradient(#38bdf8_var(--score),rgba(255,255,255,.1)_0)]" style={{ "--score": `${value}%` }} />
      <div className="absolute inset-2 rounded-full bg-[#07111f]" />
      <span className="relative text-xl font-semibold text-white">{value}</span>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div className="min-w-0 rounded-lg bg-white/[.04] p-2">
      <p className="text-slate-400">{label}</p>
      <p className="break-words font-semibold text-white">{displayValue(value)}</p>
    </div>
  );
}

function CommandRow({ label, value }) {
  return (
    <div className="grid gap-1 rounded-md border border-cyan-300/15 bg-slate-950/35 px-3 py-2 sm:grid-cols-[3.5rem_minmax(0,1fr)] sm:items-start">
      <span className="text-xs font-semibold uppercase text-slate-400">{label}</span>
      <code className="min-w-0 whitespace-pre-wrap break-words font-mono text-xs font-semibold leading-5 text-cyan-100">{displayValue(value)}</code>
    </div>
  );
}

function FlameIcon(props) {
  return <Zap {...props} />;
}

function normalizeUploadItems(source) {
  if (!source) return [];
  if (Array.isArray(source) && source.every((item) => item?.file)) {
    return source.map((item) => ({ file: item.file, path: item.path || item.file.webkitRelativePath || item.file.name }));
  }
  return Array.from(source || [])
    .filter((file) => file && typeof file.name === "string")
    .map((file) => ({ file, path: file.webkitRelativePath || file.name }));
}

async function collectDroppedItems(dataTransfer) {
  const transferItems = Array.from(dataTransfer?.items || []);
  const entries = transferItems
    .filter((item) => item.kind === "file")
    .map((item) => (typeof item.webkitGetAsEntry === "function" ? item.webkitGetAsEntry() : null))
    .filter(Boolean);
  if (!entries.length) return normalizeUploadItems(dataTransfer?.files);
  const collected = [];
  for (const entry of entries) {
    await collectEntryFiles(entry, "", collected);
  }
  return collected;
}

async function collectEntryFiles(entry, prefix, collected) {
  if (entry.isFile) {
    const file = await new Promise((resolve, reject) => entry.file(resolve, reject));
    collected.push({ file, path: `${prefix}${file.name}` });
    return;
  }
  if (!entry.isDirectory) return;
  const directoryPrefix = `${prefix}${entry.name}/`;
  const reader = entry.createReader();
  const children = await readAllDirectoryEntries(reader);
  for (const child of children) {
    await collectEntryFiles(child, directoryPrefix, collected);
  }
}

async function readAllDirectoryEntries(reader) {
  const entries = [];
  while (true) {
    const batch = await new Promise((resolve) => reader.readEntries(resolve, () => resolve([])));
    if (!batch.length) break;
    entries.push(...batch);
  }
  return entries;
}

function validateUploadItems(items) {
  if (!items.length) return "Select a ZIP, file, or project folder to upload.";
  const totalSize = items.reduce((sum, item) => sum + Number(item.file.size || 0), 0);
  if (totalSize > MAX_UPLOAD_BYTES) return `Project is too large. Limit is ${formatBytes(MAX_UPLOAD_BYTES)}.`;
  const folderUpload = isFolderUpload(items);
  if (folderUpload) return "";
  const file = items[0].file;
  const extension = extensionFor(file.name);
  if (!ALLOWED_SINGLE_UPLOAD_EXTENSIONS.has(extension) && !file.type.startsWith("image/") && !file.type.startsWith("video/")) {
    return "Upload a ZIP, supported media asset, static/code file, or project folder.";
  }
  return "";
}

function isFolderUpload(items) {
  return items.length > 1 || Boolean(items[0]?.path && items[0].path.includes("/"));
}

function uploadSourceType(file) {
  const extension = extensionFor(file.name);
  if (extension === ".zip" || file.type === "application/zip") return "zip";
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  return "file";
}

function extensionFor(name) {
  const value = String(name || "").toLowerCase();
  const index = value.lastIndexOf(".");
  return index >= 0 ? value.slice(index) : "";
}

function queueFromItems(items) {
  return items.map((item, index) => ({
    id: `${item.path || item.file.name}-${index}-${item.file.size}`,
    name: item.file.name,
    path: item.path || item.file.name,
    size: item.file.size || 0,
    status: "queued",
    progress: 0
  }));
}

function markQueueProgress(queue, progress) {
  const totalSize = queue.reduce((sum, item) => sum + Number(item.size || 0), 0) || queue.length || 1;
  let uploadedBytes = (clampPercent(progress) / 100) * totalSize;
  return queue.map((item) => {
    const size = Number(item.size || 0) || totalSize / Math.max(1, queue.length);
    const itemUploaded = Math.max(0, Math.min(size, uploadedBytes));
    uploadedBytes -= size;
    const itemProgress = Math.round((itemUploaded / size) * 100);
    return {
      ...item,
      progress: itemProgress,
      status: itemProgress >= 100 ? "done" : itemProgress > 0 ? "uploading" : item.status === "error" ? "error" : "queued"
    };
  });
}

function isAbortError(error) {
  return error?.code === "ERR_CANCELED" || error?.name === "CanceledError" || error?.name === "AbortError";
}

function withPrimaryProvider(current, providerId) {
  return Object.fromEntries(
    providerCatalog.map((provider) => {
      const roles = (current[provider.id] || []).filter((role) => role !== "primary");
      if (provider.id === providerId) roles.unshift("primary");
      return [provider.id, uniqueRoles(roles)];
    })
  );
}

function queueStatusTone(status) {
  if (status === "done") return "text-emerald-200";
  if (status === "error") return "text-rose-200";
  if (status === "paused") return "text-amber-200";
  if (status === "uploading") return "text-cyan-200";
  return "text-slate-400";
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (value >= 1024 * 1024 * 1024) return `${Math.round(value / (1024 * 1024 * 1024))}GB`;
  if (value >= 1024 * 1024) return `${Math.round(value / (1024 * 1024))}MB`;
  if (value >= 1024) return `${Math.round(value / 1024)}KB`;
  return `${value}B`;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function uniqueRoles(values) {
  return Array.from(new Set(values.filter(Boolean)));
}

function normalizeUploadRecord(record) {
  const id = getUploadId(record);
  return id && record && !record.id ? { ...record, id } : record;
}

function getUploadId(record) {
  const value = record?.id ?? record?.created_upload?.id ?? record?.created_upload ?? record?.upload_record?.id ?? "";
  return validId(value) ? String(value) : "";
}

function validId(value) {
  const text = String(value ?? "").trim();
  return Boolean(text && text !== "undefined" && text !== "null" && text !== "NaN");
}

function buildDeploymentPlan(selectedSummary) {
  const requestedPrimary = selectedSummary.primary[0] || "";
  const backup = selectedSummary.backup[0] || selectedSummary.failover[0] || "";
  const uploadAdapterAvailable = Boolean(requestedPrimary);
  return {
    primary: requestedPrimary,
    backup,
    primaryLabel: requestedPrimary ? providerDisplayName(requestedPrimary) : "Not selected",
    backupLabel: backup ? providerDisplayName(backup) : "Not selected",
    uploadAdapterAvailable,
  };
}

function defaultDomainForProvider(slug, providerId) {
  if (!providerId) return "Select provider to generate deployment URL";
  if (providerId === "vercel") return `${slug}.vercel.app`;
  if (providerId === "netlify") return `${slug}.netlify.app`;
  if (providerId === "cloudflare") return `${slug}.pages.dev`;
  if (providerId === "aws") return `${slug}.s3-website.manageai.app`;
  if (providerId === "azure") return `${slug}.azurestaticapps.net`;
  if (providerId === "gcp") return `${slug}.run.app`;
  return `${slug}.${providerId}.manageai.app`;
}

function providerDisplayName(providerId) {
  return providerCatalog.find((provider) => provider.id === providerId)?.name || providerId || "Not selected";
}

function providerDisplayList(providerIds) {
  return (providerIds || []).map(providerDisplayName).filter(Boolean).join(", ") || "Not selected";
}

function apiErrorMessage(error, fallback) {
  const payload = error?.response?.data;
  const message = formatApiErrorMessage(error, fallback);
  const requiredAction = payload?.required_action || payload?.fix_wizard?.action || "";
  const missing = Array.isArray(payload?.missing) && payload.missing.length ? `Missing: ${payload.missing.join(", ")}.` : "";
  const reason = payload?.reason ? `Reason: ${payload.reason}` : "";
  const normalizedMessage = /^not found\.?$/i.test(message.trim())
    ? "The backend did not find this deployment record. Start a new deployment after selecting a provider."
    : message;
  return [normalizedMessage, missing, reason, requiredAction].filter(Boolean).join(" ");
}

function appendDeploymentLog(logs, message) {
  return [...normalizeLogItems(logs), { message }];
}

function mergeProviderLogPayload(logs, providerLogs) {
  const internalLogs = normalizeLogItems(logs);
  const providerItems = normalizeLogItems(flattenProviderLogs(providerLogs)).map((item) => ({
    ...item,
    source: item.source || "provider"
  }));
  const seen = new Set();
  return [...internalLogs, ...providerItems].filter((item) => {
    const key = `${item.time || ""}:${item.level || ""}:${item.message || JSON.stringify(item)}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function flattenProviderLogs(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.flatMap(flattenProviderLogs);
  if (typeof value === "string") return value.split("\n").filter(Boolean).map((message) => ({ message }));
  if (typeof value !== "object") return [{ message: String(value) }];
  if (Array.isArray(value.logs)) return flattenProviderLogs(value.logs);
  if (Array.isArray(value.events)) return flattenProviderLogs(value.events);
  if (Array.isArray(value.result)) return flattenProviderLogs(value.result);
  const message = value.message || value.text || value.name || value.title || value.summary || value.state || value.status || value.id || "";
  return message ? [{ ...value, message: String(message) }] : [{ message: JSON.stringify(value) }];
}

function normalizeDeploymentLogs(deployment, deploying) {
  const items = normalizeLogItems(deployment?.logs);
  if (items.length) return items;
  if (deployment?.error_message) return [{ message: deployment.error_message }];
  if (deploying) return [{ message: "Deployment request accepted. Waiting for provider logs..." }];
  return [{ message: "No provider logs received yet. Start a real deployment to stream build output." }];
}

function normalizeLogItems(logs) {
  if (!Array.isArray(logs)) return [];
  return logs
    .map((log) => {
      if (!log) return null;
      if (typeof log === "string") return { message: log };
      if (typeof log === "object") {
        return {
          time: log.time || log.timestamp || log.created_at,
          message: displayValue(log.message || log.detail || log.error || log.text || JSON.stringify(log))
        };
      }
      return { message: String(log) };
    })
    .filter((log) => log?.message);
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") return "Not selected";
  if (Array.isArray(value)) return value.map(displayValue).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function clampPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(100, Math.round(number)));
}

function preflightTone(state) {
  if (state === "Required") return "text-cyan-200";
  if (state === "Selected") return "text-emerald-200";
  return "text-emerald-200";
}

function formatStatusLabel(status) {
  return String(status || "ready")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function slugFromName(name) {
  const base = String(name || "project")
    .replace(/\.[^.]+$/, "")
    .replace(/[^a-z0-9]+/gi, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
  return base || "project";
}

function normalizeDomain(value) {
  return String(value || "")
    .trim()
    .replace(/^https?:\/\//i, "")
    .replace(/\/.*$/, "")
    .replace(/^\.+|\.+$/g, "")
    .toLowerCase();
}

function readableFramework(value) {
  const normalized = String(value || "").toLowerCase();
  if (!normalized || normalized === "pending") return "";
  if (normalized.includes("spring_boot") || normalized.includes("spring-boot")) return "Spring Boot";
  if (normalized.includes("dotnet") || normalized.includes("aspnet")) return ".NET";
  if (normalized.includes("fastapi")) return "FastAPI";
  const match = frameworks.find((item) => normalized.includes(item.toLowerCase().replace(".", "")) || normalized.includes(item.toLowerCase()));
  if (match) return match;
  if (normalized.includes("static")) return "Static Website";
  if (normalized.includes("node")) return "Node.js";
  return "";
}


function commandForFramework(framework) {
  const commands = {
    Django: { build: "pip install -r requirements.txt && python manage.py collectstatic --noinput", start: "gunicorn project.wsgi:application", output: "staticfiles" },
    Flask: { build: "pip install -r requirements.txt", start: "gunicorn app:app", output: "public" },
    FastAPI: { build: "pip install -r requirements.txt", start: "uvicorn main:app --host 0.0.0.0", output: "public" },
    React: { build: "npm install && npm run build", start: "npm run preview", output: "dist" },
    "Next.js": { build: "npm install && npm run build", start: "npm start", output: ".next" },
    Angular: { build: "npm install && npm run build", start: "npx serve dist", output: "dist" },
    Vue: { build: "npm install && npm run build", start: "npm run preview", output: "dist" },
    "Node.js": { build: "npm install", start: "node server.js", output: "public" },
    PHP: { build: "composer install --no-dev", start: "php -S 0.0.0.0:8080", output: "public" },
    Laravel: { build: "composer install --no-dev && npm install && npm run build", start: "php artisan serve --host=0.0.0.0", output: "public" },
    WordPress: { build: "composer install || true", start: "php-fpm", output: "public_html" },
    "Static Website": { build: "echo static site ready", start: "npx serve .", output: "." },
    "Spring Boot": { build: "./mvnw package -DskipTests", start: "java -jar target/app.jar", output: "target" },
    ".NET": { build: "dotnet publish -c Release", start: "dotnet app.dll", output: "bin/Release/net8.0/publish" }
  };
  return commands[framework] || commands.React;
}

function databaseForFramework(framework) {
  if (["Django", "Laravel", "FastAPI", "Spring Boot", ".NET"].includes(framework)) return "PostgreSQL or MySQL recommended";
  if (framework === "WordPress") return "MySQL required";
  if (["React", "Next.js", "Vue", "Angular", "Static Website"].includes(framework)) return "Optional API database";
  return "Detected from env and config files";
}

function costScore(cost) {
  return cost === "$" ? 94 : cost === "$$" ? 82 : 68;
}
