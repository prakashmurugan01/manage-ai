import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  CloudUpload,
  Code2,
  ExternalLink,
  FileArchive,
  FolderUp,
  Globe2,
  Loader2,
  Play,
  RefreshCcw,
  Rocket,
  Server,
  ShieldCheck,
  TerminalSquare,
  UploadCloud,
  Zap
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { api } from "../api/client.js";

const steps = ["Upload Project", "Analyze Project", "Select Hosting", "Configure Deployment", "Deploy & Monitor"];
const providers = [
  { id: "aws", name: "AWS", speed: "Enterprise", cost: "$$$", use: "Django, Node, high-scale APIs", icon: Server },
  { id: "hostinger", name: "Hostinger", speed: "Fast", cost: "$", use: "Budget shared hosting and landing sites", icon: Globe2 },
  { id: "siteground", name: "SiteGround", speed: "Premium", cost: "$$", use: "WordPress, e-commerce, Google Cloud", icon: ShieldCheck },
  { id: "digitalocean", name: "DigitalOcean", speed: "Cloud", cost: "$$", use: "Droplets, apps, backend workloads", icon: Server },
  { id: "netlify", name: "Netlify", speed: "Edge", cost: "$", use: "React, static, JAMstack", icon: Zap },
  { id: "vercel", name: "Vercel", speed: "Edge", cost: "$$", use: "React, Next.js, previews", icon: Rocket }
];

export default function HostingDeployment() {
  const [step, setStep] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [upload, setUpload] = useState(null);
  const [uploadStatus, setUploadStatus] = useState("Waiting for project");
  const [selectedPrimary, setSelectedPrimary] = useState("vercel");
  const [selectedBackup, setSelectedBackup] = useState("digitalocean");
  const [config, setConfig] = useState({ custom_domain: "", build_command: "", output_directory: "", environmentText: "NODE_ENV=production" });
  const [deployment, setDeployment] = useState(null);
  const [deploying, setDeploying] = useState(false);
  const inputRef = useRef(null);
  const folderRef = useRef(null);

  const analysis = upload?.analysis || {};
  const detectedType = upload?.project_type || "pending";
  const suggested = upload?.suggested_providers || [];

  const autoConfig = useMemo(() => ({
    project_slug: slugFromName(upload?.original_name),
    default_domain: `${slugFromName(upload?.original_name)}.vercel.app`,
    custom_domain: normalizeDomain(config.custom_domain),
    build_command: config.build_command || analysis.build_command || "npm install && npm run build",
    output_directory: config.output_directory || analysis.output_directory || "dist"
  }), [analysis, config, upload]);

  async function handleFile(file) {
    if (!file) return;
    const allowed = file.name.endsWith(".zip") || file.webkitRelativePath || file.type === "application/zip";
    if (!allowed && file.size > 0) {
      setUploadStatus("Please upload a ZIP file or drag a project folder.");
      return;
    }
    if (file.size > 1024 * 1024 * 1024) {
      setUploadStatus("Project is too large. Limit is 1GB.");
      return;
    }
    const data = new FormData();
    data.append("upload", file);
    setUploadStatus("Uploading");
    setUploadProgress(2);
    const response = await api.post("/hosting/uploads/", data, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 120000,
      onUploadProgress: (event) => {
        if (event.total) setUploadProgress(Math.round((event.loaded / event.total) * 100));
      }
    });
    setUpload(response.data);
    setUploadStatus("Processing");
    setStep(1);
    pollUpload(response.data.id);
  }

  async function pollUpload(id) {
    for (let i = 0; i < 12; i += 1) {
      await wait(1400);
      const { data } = await api.get(`/hosting/uploads/${id}/`);
      setUpload(data);
      if (["analyzed", "failed"].includes(data.status)) {
        setUploadStatus(data.status === "analyzed" ? "Completed" : "Analysis failed");
        if (data.suggested_providers?.[0]) setSelectedPrimary(data.suggested_providers[0]);
        if (data.suggested_providers?.[1]) setSelectedBackup(data.suggested_providers[1]);
        return;
      }
    }
  }

  async function deploy() {
    if (!upload) return;
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
    const { data } = await api.post(`/hosting/uploads/${upload.id}/deploy/`, {
      primary_provider: selectedPrimary,
      backup_provider: selectedBackup,
      domain: autoConfig.custom_domain,
      build_command: autoConfig.build_command,
      output_directory: autoConfig.output_directory,
      environment
    });
    setDeployment(data);
    setStep(4);
    pollDeployment(data.id);
  }

  async function pollDeployment(id) {
    for (let i = 0; i < 14; i += 1) {
      await wait(1200);
      const { data } = await api.get(`/hosting/deployments/${id}/`);
      setDeployment(data);
      if (["live", "error"].includes(data.status)) {
        setDeploying(false);
        return;
      }
    }
    setDeploying(false);
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm font-medium text-cyan-200">Project Hosting Upload & Deployment</p>
          <h1 className="mt-1 text-3xl font-semibold text-white">Deploy Center</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary" onClick={() => inputRef.current?.click()}><FileArchive size={16} /> ZIP Upload</button>
          <button className="btn-primary" onClick={() => folderRef.current?.click()}><FolderUp size={16} /> Folder Upload</button>
        </div>
      </header>

      <input ref={inputRef} type="file" accept=".zip,application/zip" className="hidden" onChange={(e) => handleFile(e.target.files?.[0])} />
      <input ref={folderRef} type="file" className="hidden" webkitdirectory="true" multiple onChange={(e) => handleFile(e.target.files?.[0])} />

      <StepTracker step={step} />

      <AnimatePresence mode="wait">
        {step === 0 && (
          <StepShell key="upload">
            <div
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files?.[0]); }}
              className={`grid min-h-[420px] place-items-center rounded-lg border border-dashed p-8 text-center transition ${dragging ? "border-cyan-300 bg-cyan-300/10 shadow-[0_0_70px_rgba(34,211,238,.2)]" : "border-cyan-300/30 bg-white/5"}`}
            >
              <div className="max-w-xl">
                <motion.div animate={{ y: [0, -8, 0] }} transition={{ duration: 2.6, repeat: Infinity }} className="mx-auto grid size-20 place-items-center rounded-2xl bg-cyan-300/15 text-cyan-200">
                  <UploadCloud size={42} />
                </motion.div>
                <h2 className="mt-6 text-2xl font-semibold text-white">Drop your project ZIP or folder here</h2>
                <p className="mt-2 text-sm text-slate-400">Upload React, Django, Node, or static projects. We analyze the stack and guide hosting selection.</p>
                <div className="mt-6 flex flex-wrap justify-center gap-3">
                  <button className="btn-primary" onClick={() => inputRef.current?.click()}><CloudUpload size={16} /> Choose ZIP</button>
                  <button className="btn-secondary" onClick={() => folderRef.current?.click()}><FolderUp size={16} /> Choose Folder</button>
                </div>
                <UploadProgress status={uploadStatus} progress={uploadProgress} upload={upload} />
              </div>
            </div>
          </StepShell>
        )}

        {step === 1 && (
          <StepShell key="analysis">
            <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
              <div className="saas-card p-5">
                <h2 className="text-xl font-semibold text-white">Smart Analysis</h2>
                <p className="mt-2 text-sm text-slate-400">Detected type: <span className="font-semibold text-cyan-200">{detectedType}</span></p>
                <div className="mt-5 grid gap-3">
                  {(upload?.detected_stack || ["Analyzing..."]).map((item) => <StackPill key={item} label={item} />)}
                </div>
              </div>
              <div className="saas-card p-5">
                <h3 className="text-sm font-semibold uppercase text-cyan-200">Suggestions</h3>
                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  {(suggested.length ? suggested : ["vercel", "netlify", "aws"]).map((item) => <ProviderMini key={item} id={item} />)}
                </div>
                <div className="mt-5 rounded-lg border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
                  Files scanned: {analysis.file_count || 0}. Build: {analysis.build_command || "detecting..."} Output: {analysis.output_directory || "detecting..."}
                </div>
              </div>
            </div>
          </StepShell>
        )}

        {step === 2 && (
          <StepShell key="providers">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {providers.map((provider) => <ProviderCard key={provider.id} provider={provider} primary={selectedPrimary} backup={selectedBackup} setPrimary={setSelectedPrimary} setBackup={setSelectedBackup} suggested={suggested.includes(provider.id)} />)}
            </div>
          </StepShell>
        )}

        {step === 3 && (
          <StepShell key="config">
            <div className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
              <div className="saas-card p-5">
                <h2 className="text-xl font-semibold text-white">Deployment Configuration</h2>
                <div className="mt-5 grid gap-4">
                  <ReadOnlyField label="Default Vercel URL" value={autoConfig.default_domain} />
                  <ConfigField label="Custom Domain (Optional)" value={config.custom_domain} onChange={(value) => setConfig({ ...config, custom_domain: value })} placeholder="app.yourdomain.com" />
                  <ConfigField label="Build Command" value={autoConfig.build_command} onChange={(value) => setConfig({ ...config, build_command: value })} />
                  <ConfigField label="Output Directory" value={autoConfig.output_directory} onChange={(value) => setConfig({ ...config, output_directory: value })} />
                  <label className="grid gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">Environment Variables</span>
                    <textarea className="form-control min-h-32 font-mono" value={config.environmentText} onChange={(e) => setConfig({ ...config, environmentText: e.target.value })} />
                  </label>
                </div>
              </div>
              <div className="saas-card p-5">
                <h3 className="text-sm font-semibold uppercase text-cyan-200">Deployment Plan</h3>
                <div className="mt-4 space-y-3 text-sm">
                  <PlanRow label="Primary" value={selectedPrimary} />
                  <PlanRow label="Backup" value={selectedBackup || "None"} />
                  <PlanRow label="Type" value={detectedType} />
                  <PlanRow label="Default URL" value={autoConfig.default_domain} />
                  <PlanRow label="Custom Domain" value={autoConfig.custom_domain || "Not set"} />
                  <PlanRow label="Output" value={autoConfig.output_directory} />
                </div>
              </div>
            </div>
          </StepShell>
        )}

        {step === 4 && (
          <StepShell key="deploy">
            <div className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
              <div className="saas-card p-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-semibold text-white">Deploy & Monitor</h2>
                  <DeploymentStatus status={deployment?.status || "queued"} />
                </div>
                <div className="mt-6 h-3 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-cyan-300 transition-all" style={{ width: `${deployment?.progress || 0}%` }} />
                </div>
                <p className="mt-3 text-sm text-slate-400">{deployment?.progress || 0}% complete</p>
                {deployment?.live_url && (
                  <a href={deployment.live_url} target="_blank" rel="noreferrer" className="btn-primary mt-6">
                    <ExternalLink size={16} /> Open Live URL
                  </a>
                )}
              </div>
              <div className="saas-card overflow-hidden">
                <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3 text-sm font-semibold text-white">
                  <TerminalSquare size={16} /> Deployment Logs
                </div>
                <div className="min-h-72 space-y-2 bg-slate-950/70 p-4 font-mono text-xs text-cyan-100">
                  {(deployment?.logs || [{ message: deploying ? "Starting deployment..." : "Waiting for deployment..." }]).map((log, index) => (
                    <p key={`${log.time || "log"}-${index}`}><span className="text-slate-500">$</span> {log.message}</p>
                  ))}
                </div>
              </div>
            </div>
          </StepShell>
        )}
      </AnimatePresence>

      <div className="flex justify-between">
        <button className="btn-secondary" disabled={step === 0} onClick={() => setStep((value) => Math.max(0, value - 1))}><ArrowLeft size={16} /> Back</button>
        {step < 3 && <button className="btn-primary" disabled={step === 0 && !upload} onClick={() => setStep((value) => Math.min(4, value + 1))}>Next <ArrowRight size={16} /></button>}
        {step === 3 && <button className="btn-primary" onClick={deploy}><Play size={16} /> Deploy Project</button>}
        {step === 4 && <button className="btn-secondary" onClick={() => deployment && api.post(`/hosting/deployments/${deployment.id}/redeploy/`).then((res) => { setDeployment(res.data); setDeploying(true); pollDeployment(res.data.id); })}><RefreshCcw size={16} /> Redeploy</button>}
      </div>
    </div>
  );
}

function StepTracker({ step }) {
  return (
    <div className="panel p-4">
      <div className="grid gap-2 md:grid-cols-5">
        {steps.map((label, index) => (
          <div key={label} className="flex items-center gap-2">
            <span className={`grid size-8 place-items-center rounded-full text-xs font-bold ${index <= step ? "bg-cyan-300 text-slate-950" : "bg-white/8 text-slate-400"}`}>{index < step ? <CheckCircle2 size={16} /> : index + 1}</span>
            <span className={`text-xs font-semibold ${index <= step ? "text-white" : "text-slate-500"}`}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function StepShell({ children }) {
  return (
    <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.22 }}>
      {children}
    </motion.section>
  );
}

function UploadProgress({ status, progress, upload }) {
  return (
    <div className="mt-6 rounded-lg border border-white/10 bg-white/5 p-4">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-300">{upload?.original_name || "No file selected"}</span>
        <span className="font-semibold text-cyan-200">{status}</span>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-cyan-300 transition-all" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}

function ProviderCard({ provider, primary, backup, setPrimary, setBackup, suggested }) {
  const Icon = provider.icon;
  return (
    <article className={`saas-card p-4 ${primary === provider.id ? "ring-2 ring-cyan-300/40" : ""}`}>
      <div className="flex items-start justify-between">
        <div className="grid size-11 place-items-center rounded-lg bg-cyan-300/12 text-cyan-200"><Icon size={22} /></div>
        {suggested && <span className="rounded-full bg-emerald-400/10 px-2 py-1 text-xs font-semibold text-emerald-100">Suggested</span>}
      </div>
      <h3 className="mt-4 text-lg font-semibold text-white">{provider.name}</h3>
      <p className="mt-1 text-sm text-slate-400">{provider.use}</p>
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <PlanRow label="Speed" value={provider.speed} />
        <PlanRow label="Cost" value={provider.cost} />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <button
          className={primary === provider.id ? "btn-primary px-3" : "btn-secondary px-3"}
          onClick={() => {
            setPrimary(provider.id);
            if (backup === provider.id) {
              setBackup(providers.find((item) => item.id !== provider.id)?.id || "");
            }
          }}
        >
          Primary
        </button>
        <button
          className={backup === provider.id ? "btn-primary px-3" : "btn-secondary px-3"}
          disabled={primary === provider.id}
          onClick={() => setBackup(provider.id)}
        >
          Backup
        </button>
      </div>
    </article>
  );
}

function ProviderMini({ id }) {
  return <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-sm font-semibold capitalize text-white">{id.replace("_", " ")}</div>;
}

function StackPill({ label }) {
  return <div className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 p-3 text-sm text-white"><Code2 size={16} className="text-cyan-300" /> {label}</div>;
}

function ConfigField({ label, value, onChange, placeholder }) {
  return (
    <label className="grid gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</span>
      <input className="form-control" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function ReadOnlyField({ label, value }) {
  return (
    <label className="grid gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</span>
      <input className="form-control cursor-not-allowed opacity-80" value={value} readOnly />
      <span className="text-xs text-slate-500">Auto-generated from uploaded file name. Add a custom domain only if DNS is ready.</span>
    </label>
  );
}

function PlanRow({ label, value }) {
  return <div><p className="text-xs text-slate-500">{label}</p><p className="mt-1 font-semibold capitalize text-white">{value}</p></div>;
}

function DeploymentStatus({ status }) {
  const live = status === "live";
  return <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${live ? "bg-emerald-400/10 text-emerald-100" : "bg-cyan-400/10 text-cyan-100"}`}>{live ? <CheckCircle2 size={14} /> : <Loader2 size={14} className="animate-spin" />} {status}</span>;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
