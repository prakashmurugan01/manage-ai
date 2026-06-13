import { motion } from "framer-motion";
import { Activity, AlertTriangle, ExternalLink, Globe2, Loader2, RefreshCcw, Rocket, TerminalSquare } from "lucide-react";

import { apiErrorMessage } from "../../api/client.js";

function NetlifyLogo() {
  return (
    <div className="relative grid size-11 place-items-center rounded-2xl bg-gradient-to-br from-teal-300 via-cyan-300 to-emerald-400 text-slate-950 shadow-lg shadow-teal-400/25">
      <span className="absolute inset-1 rounded-xl border border-slate-950/10" />
      <Rocket size={20} />
    </div>
  );
}

export default function NetlifyCard({ data, loading, error, active, onOpen, onRedeploy, redeploying }) {
  const hasError = Boolean(error) || data?.status === "Error";
  const indicator = hasError ? "Error" : data?.indicator || "Live";
  return (
    <motion.button
      type="button"
      whileHover={{ y: -6, scale: 1.035, boxShadow: hasError ? "0 24px 70px rgba(244,63,94,.2)" : "0 24px 70px rgba(45,212,191,.22)" }}
      whileTap={{ scale: 0.97 }}
      onClick={onOpen}
      className={`netlify-gradient-card group relative overflow-hidden rounded-2xl border p-5 text-left shadow-sm transition duration-300 ${
        active
          ? "border-teal-300/80 bg-[color:var(--card-bg-hover)] shadow-xl shadow-teal-500/15"
          : hasError
            ? "border-rose-400/45 bg-[color:var(--card-bg)] shadow-rose-500/10 hover:border-rose-300/70"
            : "border-[color:var(--border)] bg-[color:var(--card-bg)] hover:border-teal-300/60"
      }`}
    >
      <div className="pointer-events-none absolute inset-0 opacity-0 transition duration-300 group-hover:opacity-100" style={{ background: "radial-gradient(circle at 18% 0%, rgba(45,212,191,.2), transparent 34%)" }} />
      <div className="flex items-start justify-between gap-4">
        <NetlifyLogo />
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${hasError ? "bg-rose-500/12 text-rose-300 ring-rose-400/25" : "bg-emerald-500/12 text-emerald-300 ring-emerald-400/25 animate-netlify-live"}`}>
          <span className={`size-1.5 rounded-full ${hasError ? "bg-rose-300" : "bg-emerald-300"}`} />
          {hasError ? "Error" : "Active"}
        </span>
      </div>
      <h3 className="mt-5 text-lg font-semibold text-[color:var(--text-strong)]">Netlify</h3>
      <p className="mt-1 text-sm text-[color:var(--text-muted)]">Frontend hosting & CI/CD deployments</p>

      {loading ? (
        <NetlifySkeleton />
      ) : (
        <>
          <div className="mt-5 grid grid-cols-3 gap-3">
            <NetlifyMiniStat label="Active" value={data?.active ?? 0} />
            <NetlifyMiniStat label="Failed" value={data?.failed ?? 0} tone={hasError ? "rose" : "default"} />
            <NetlifyMiniStat label="Uptime" value={data?.uptime || "0%"} />
          </div>
          <div className={`mt-4 rounded-xl border px-3 py-2 ${hasError ? "border-rose-400/25 bg-rose-500/10" : "border-teal-400/25 bg-teal-400/10"}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-medium text-[color:var(--text-faint)]">Last Deploy</p>
                <p className="mt-1 text-sm font-semibold text-[color:var(--text-strong)]">{data?.lastDeployLabel || "No deploys yet"}</p>
              </div>
              <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${indicator === "Error" ? "bg-rose-500/15 text-rose-300" : indicator === "Building" ? "bg-amber-500/15 text-amber-300" : "bg-cyan-500/15 text-cyan-300"}`}>
                {indicator}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onRedeploy?.();
            }}
            className="relative mt-4 inline-flex h-10 w-full items-center justify-center gap-2 overflow-hidden rounded-xl bg-gradient-to-r from-teal-300 via-cyan-300 to-blue-400 px-4 text-sm font-semibold text-slate-950 shadow-lg shadow-teal-400/20 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={redeploying}
          >
            {redeploying ? <Loader2 size={16} className="animate-spin" /> : <RefreshCcw size={16} />}
            Redeploy
          </button>
        </>
      )}
    </motion.button>
  );
}

export function NetlifyDetailsPanel({ data, loading, error, onRedeploy, redeploying }) {
  if (loading) return <NetlifyDetailSkeleton />;
  if (error) {
    return (
      <div className="rounded-2xl border border-rose-400/35 bg-rose-500/10 p-5">
        <div className="flex gap-3">
          <AlertTriangle className="mt-0.5 size-5 text-rose-300" />
          <div>
            <p className="font-semibold text-[color:var(--text-strong)]">Netlify API error</p>
            <p className="mt-1 text-sm text-[color:var(--text-muted)]">{apiErrorMessage(error, "Unable to fetch Netlify data.")}</p>
          </div>
        </div>
      </div>
    );
  }

  const sites = data?.sites || [];
  const deploys = data?.deploys || [];
  const logs = data?.logsPreview || [];
  return (
    <div className="grid gap-5">
      <div className="grid gap-4 md:grid-cols-4">
        <NetlifyMetric icon={Globe2} label="Active Sites" value={data?.active ?? 0} />
        <NetlifyMetric icon={AlertTriangle} label="Failed Deploys" value={data?.failed ?? 0} tone="rose" />
        <NetlifyMetric icon={Activity} label="Uptime" value={data?.uptime || "0%"} tone="emerald" />
        <NetlifyMetric icon={Rocket} label="Status" value={data?.indicator || "Live"} tone="cyan" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
          <PanelTitle icon={Globe2} title="Sites" subtitle="Published Netlify projects" />
          <div className="mt-4 space-y-3">
            {sites.slice(0, 8).map((site) => (
              <div key={site.id || site.name} className="flex items-center justify-between gap-3 rounded-xl border border-[color:var(--border)] bg-[color:var(--card-bg)] px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-[color:var(--text-strong)]">{site.name || "Netlify Site"}</p>
                  <p className="truncate text-xs text-[color:var(--text-muted)]">{site.url || site.adminUrl || "No URL"}</p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button type="button" onClick={() => onRedeploy?.(site.id)} className="grid size-9 place-items-center rounded-xl border border-teal-400/25 bg-teal-400/10 text-teal-200 transition hover:border-teal-300" title="Redeploy site" disabled={redeploying}>
                    {redeploying ? <Loader2 size={15} className="animate-spin" /> : <RefreshCcw size={15} />}
                  </button>
                  {site.url && (
                    <a href={site.url} target="_blank" rel="noreferrer" className="grid size-9 place-items-center rounded-xl border border-[color:var(--border)] text-[color:var(--text-muted)] transition hover:border-[color:var(--primary)] hover:text-[color:var(--text-strong)]" title="Open site">
                      <ExternalLink size={15} />
                    </a>
                  )}
                </div>
              </div>
            ))}
            {!sites.length && <EmptyNetlifyState title="No sites found" />}
          </div>
        </section>

        <section className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
          <PanelTitle icon={TerminalSquare} title="Logs Preview" subtitle="Recent deployment messages" />
          <div className="mt-4 space-y-3">
            {logs.map((log) => (
              <div key={log.id || log.title} className={`rounded-xl border px-4 py-3 ${log.level === "error" ? "border-rose-400/25 bg-rose-500/10" : "border-cyan-400/20 bg-cyan-400/10"}`}>
                <p className="text-sm font-semibold text-[color:var(--text-strong)]">{log.title}</p>
                <p className="mt-1 text-xs text-[color:var(--text-muted)]">{log.message}</p>
              </div>
            ))}
            {!logs.length && <EmptyNetlifyState title="No log preview" />}
          </div>
        </section>
      </div>

      <section className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface-soft)] p-4">
        <PanelTitle icon={Rocket} title="Deploy History" subtitle="Latest Netlify deployment states" />
        <div className="mt-4 overflow-hidden rounded-xl border border-[color:var(--border)]">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-[color:var(--card-bg)] text-xs text-[color:var(--text-muted)]">
              <tr>
                <th className="px-4 py-3">Site</th>
                <th className="px-4 py-3">State</th>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">URL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--border)]">
              {deploys.slice(0, 10).map((deploy) => (
                <tr key={deploy.id} className="bg-[color:var(--card-bg)]">
                  <td className="px-4 py-3 font-semibold text-[color:var(--text-strong)]">{deploy.siteName || "Netlify"}</td>
                  <td className="px-4 py-3"><DeployState value={deploy.state} /></td>
                  <td className="px-4 py-3 text-[color:var(--text-muted)]">{deploy.title}</td>
                  <td className="px-4 py-3 text-[color:var(--text-muted)]">{formatDate(deploy.createdAt)}</td>
                  <td className="px-4 py-3 text-[color:var(--text-muted)]">{deploy.url ? <a href={deploy.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-cyan-300 hover:text-cyan-200">Open <ExternalLink size={13} /></a> : "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!deploys.length && <EmptyNetlifyState title="No deploy history" />}
        </div>
      </section>
    </div>
  );
}

function NetlifySkeleton() {
  return (
    <div className="mt-5">
      <div className="grid grid-cols-3 gap-3">
        <div className="hosting-shimmer h-14 rounded-xl" />
        <div className="hosting-shimmer h-14 rounded-xl" />
        <div className="hosting-shimmer h-14 rounded-xl" />
      </div>
      <div className="hosting-shimmer mt-4 h-14 rounded-xl" />
      <div className="hosting-shimmer mt-4 h-10 rounded-xl" />
    </div>
  );
}

function NetlifyDetailSkeleton() {
  return <div className="hosting-shimmer h-80 rounded-2xl" />;
}

function NetlifyMiniStat({ label, value, tone = "default" }) {
  return (
    <div className={`rounded-xl border px-3 py-2 ${tone === "rose" ? "border-rose-400/25 bg-rose-500/10" : "border-teal-400/20 bg-white/[.035]"}`}>
      <p className="text-[11px] font-medium text-[color:var(--text-faint)]">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-[color:var(--text-strong)]">{value}</p>
    </div>
  );
}

function NetlifyMetric({ icon: Icon, label, value, tone = "teal" }) {
  const colors = {
    teal: "text-teal-300 bg-teal-400/10",
    rose: "text-rose-300 bg-rose-500/10",
    emerald: "text-emerald-300 bg-emerald-500/10",
    cyan: "text-cyan-300 bg-cyan-500/10",
  };
  return (
    <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--card-bg)] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-[color:var(--text-muted)]">{label}</p>
        <span className={`grid size-9 place-items-center rounded-xl ${colors[tone]}`}><Icon size={17} /></span>
      </div>
      <p className="mt-3 text-2xl font-semibold text-[color:var(--text-strong)]">{value}</p>
    </div>
  );
}

function PanelTitle({ icon: Icon, title, subtitle }) {
  return (
    <div className="flex items-center gap-3">
      <span className="grid size-9 place-items-center rounded-xl border border-teal-400/25 bg-teal-400/10 text-teal-200"><Icon size={17} /></span>
      <div>
        <h3 className="font-semibold text-[color:var(--text-strong)]">{title}</h3>
        <p className="text-xs text-[color:var(--text-muted)]">{subtitle}</p>
      </div>
    </div>
  );
}

function DeployState({ value }) {
  const state = String(value || "unknown").toLowerCase();
  const tone = state === "error" ? "bg-rose-500/15 text-rose-300" : state === "building" ? "bg-amber-500/15 text-amber-300" : "bg-emerald-500/15 text-emerald-300";
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>{state}</span>;
}

function EmptyNetlifyState({ title }) {
  return <div className="rounded-xl border border-dashed border-[color:var(--border-strong)] p-5 text-center text-sm text-[color:var(--text-muted)]">{title}</div>;
}

function formatDate(value) {
  if (!value) return "n/a";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
