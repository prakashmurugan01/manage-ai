import { Cloud, ExternalLink, GitBranch, Github, GitCommitHorizontal, PlugZap, RadioTower, RefreshCw, Rocket, Server, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { projectsApi } from "../../api/services.js";
import { canManage } from "../../utils/rbac.js";
import FileUploader from "../files/FileUploader.jsx";
import Badge from "../ui/Badge.jsx";
import Button from "../ui/Button.jsx";

const modes = [
  { value: "LOCAL", label: "Local", icon: Server },
  { value: "GITHUB", label: "GitHub", icon: Github },
  { value: "HOSTED", label: "Hosted", icon: Cloud },
  { value: "NONE", label: "None", icon: PlugZap }
];

function emptyForm(project) {
  return {
    connection_type: project?.connection_type || "NONE",
    local_url: project?.local_url || "http://localhost:5173",
    hosted_url: project?.hosted_url || "",
    repository_url: project?.repository_url || "",
    local_repository_path: project?.local_repository_path || "",
    github_owner: project?.github_owner || "",
    github_repo: project?.github_repo || "",
    github_default_branch: project?.github_default_branch || "main",
    selected_branch: project?.selected_branch || project?.github_default_branch || "main"
  };
}

function dateTime(value) {
  return value ? new Date(value).toLocaleString() : "Not synced";
}

export default function ProjectConnectionPanel({ project, user, deployment, onProjectChange, onDeploymentChange }) {
  const [form, setForm] = useState(() => emptyForm(project));
  const [branches, setBranches] = useState([]);
  const [commits, setCommits] = useState([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState("");
  const [pushForm, setPushForm] = useState({ commit_message: "", branch: "" });
  const [submissionMode, setSubmissionMode] = useState("files");

  useEffect(() => {
    setForm(emptyForm(project));
  }, [project?.id]);

  useEffect(() => {
    if (!project?.id || project.connection_type !== "GITHUB") return;
    loadBranches();
    loadCommits(project.selected_branch || project.github_default_branch);
  }, [project?.id, project?.connection_type]);

  const developerActivity = useMemo(() => {
    const totals = commits.reduce((acc, commit) => {
      const key = commit.author_login || commit.author_name || commit.author_email || "Unknown";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
    return Object.entries(totals)
      .map(([name, total]) => ({ name, total }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 5);
  }, [commits]);

  if (!project) return null;

  async function loadBranches() {
    setBusy("branches");
    setStatus("");
    try {
      const { data } = await projectsApi.branches(project.id);
      setBranches(data.branches || []);
    } catch (error) {
      setStatus(error.response?.data?.detail || "Unable to load GitHub branches.");
    } finally {
      setBusy("");
    }
  }

  async function loadCommits(branch = form.selected_branch) {
    setBusy("commits");
    setStatus("");
    try {
      const { data } = await projectsApi.commits(project.id, { branch });
      setCommits(data);
    } catch (error) {
      setStatus(error.response?.data?.detail || "Unable to load commit history.");
    } finally {
      setBusy("");
    }
  }

  async function saveConnection(event) {
    event.preventDefault();
    setBusy("save");
    setStatus("");
    try {
      const { data } = await projectsApi.connect(project.id, form);
      onProjectChange?.(data);
      setStatus(data.warning || "Connection saved.");
      if (data.connection_type === "GITHUB" && !data.warning) {
        await loadCommits(data.selected_branch);
      }
    } catch (error) {
      setStatus(error.response?.data?.detail || "Connection could not be saved.");
    } finally {
      setBusy("");
    }
  }

  async function syncGit() {
    setBusy("sync");
    setStatus("");
    try {
      const { data } = await projectsApi.syncGit(project.id, { branch: form.selected_branch });
      setCommits(data);
      const response = await projectsApi.get(project.id);
      onProjectChange?.(response.data);
      setStatus(`Synced ${data.length} commits from ${form.selected_branch}.`);
    } catch (error) {
      setStatus(error.response?.data?.detail || "Git sync failed.");
    } finally {
      setBusy("");
    }
  }

  async function pushGit() {
    setBusy("push");
    setStatus("");
    try {
      const { data } = await projectsApi.pushGit(project.id, {
        branch: pushForm.branch || form.selected_branch,
        commit_message: pushForm.commit_message
      });
      setCommits((items) => [data, ...items.filter((item) => item.sha !== data.sha)]);
      const response = await projectsApi.get(project.id);
      onProjectChange?.(response.data);
      setStatus(`Pushed ${data.short_sha} to ${data.branch || form.selected_branch}.`);
      setPushForm({ commit_message: "", branch: "" });
    } catch (error) {
      setStatus(error.response?.data?.detail || error.response?.data?.local_repository_path || "Git push failed.");
    } finally {
      setBusy("");
    }
  }

  async function deployBranch() {
    setBusy("deploy");
    setStatus("");
    try {
      const { data } = await projectsApi.deployBranch(project.id, {
        branch: form.selected_branch,
        environment: deployment?.environment || "production",
        notes: `Deployment triggered from ${form.selected_branch}`
      });
      onDeploymentChange?.(data);
      const response = await projectsApi.get(project.id);
      onProjectChange?.(response.data);
      setStatus(`Deployment healthy from ${form.selected_branch || "selected source"}.`);
    } catch (error) {
      setStatus(error.response?.data?.detail || "Deployment trigger failed.");
    } finally {
      setBusy("");
    }
  }

  async function checkLocal() {
    setBusy("local");
    setStatus("");
    try {
      const { data } = await projectsApi.localStatus(project.id);
      setStatus(data.ok ? `Local URL responded with ${data.status_code}.` : data.error);
    } catch (error) {
      setStatus(error.response?.data?.detail || "Local status check failed.");
    } finally {
      setBusy("");
    }
  }

  const allowManage = canManage(user);
  const allowPush = allowManage || project.developers_detail?.some((developer) => developer.id === user?.id);

  return (
    <section className="mt-6 grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
      <form onSubmit={saveConnection} className="panel p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Project Connection</h2>
            <p className="mt-1 text-xs text-slate-500">Local URLs, hosted links, GitHub repository sync, branch selection, and deployment triggers.</p>
          </div>
          <Badge value={project.connection_status || "DISCONNECTED"} />
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {modes.map((mode) => {
            const Icon = mode.icon;
            return (
              <button
                key={mode.value}
                type="button"
                disabled={!allowManage}
                onClick={() => setForm({ ...form, connection_type: mode.value })}
                className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm transition ${form.connection_type === mode.value ? "border-teal-300/60 bg-white/15 text-white" : "border-white/10 bg-white/[0.035] text-slate-400 hover:text-white"}`}
              >
                <Icon size={15} />
                {mode.label}
              </button>
            );
          })}
        </div>

        <div className="mt-4 grid gap-4">
          {form.connection_type === "LOCAL" && (
            <div>
              <label className="label">Local URL</label>
              <input className="field" disabled={!allowManage} value={form.local_url} onChange={(event) => setForm({ ...form, local_url: event.target.value })} />
            </div>
          )}

          {form.connection_type === "HOSTED" && (
            <div>
              <label className="label">Hosted URL</label>
              <input className="field" disabled={!allowManage} value={form.hosted_url} onChange={(event) => setForm({ ...form, hosted_url: event.target.value })} />
            </div>
          )}

          {form.connection_type === "GITHUB" && (
            <>
              <div>
                <label className="label">GitHub Repository URL</label>
                <input className="field" disabled={!allowManage} placeholder="https://github.com/org/repo" value={form.repository_url} onChange={(event) => setForm({ ...form, repository_url: event.target.value })} />
              </div>
              <div>
                <label className="label">Local Repository Path</label>
                <input className="field" disabled={!allowManage} placeholder="D:\\projects\\project-folder" value={form.local_repository_path} onChange={(event) => setForm({ ...form, local_repository_path: event.target.value })} />
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label className="label">Owner</label>
                  <input className="field" disabled={!allowManage} value={form.github_owner} onChange={(event) => setForm({ ...form, github_owner: event.target.value })} />
                </div>
                <div>
                  <label className="label">Repository</label>
                  <input className="field" disabled={!allowManage} value={form.github_repo} onChange={(event) => setForm({ ...form, github_repo: event.target.value })} />
                </div>
                <div>
                  <label className="label">Branch</label>
                  {branches.length ? (
                    <select className="field" disabled={!allowManage} value={form.selected_branch} onChange={(event) => setForm({ ...form, selected_branch: event.target.value })}>
                      {branches.map((branch) => <option key={branch.name} value={branch.name}>{branch.name}</option>)}
                    </select>
                  ) : (
                    <input className="field" disabled={!allowManage} value={form.selected_branch} onChange={(event) => setForm({ ...form, selected_branch: event.target.value })} />
                  )}
                </div>
              </div>
            </>
          )}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {allowManage && (
            <Button type="submit" disabled={busy === "save"}>
              <PlugZap size={16} />
              Save Connection
            </Button>
          )}
          {project.connection_type === "LOCAL" && (
            <Button variant="secondary" onClick={checkLocal} disabled={busy === "local"}>
              <RadioTower size={16} />
              Check Local
            </Button>
          )}
          {project.connection_type === "GITHUB" && (
            <>
              <Button variant="secondary" onClick={loadBranches} disabled={busy === "branches"}>
                <GitBranch size={16} />
                Branches
              </Button>
              {allowManage && (
                <Button variant="secondary" onClick={syncGit} disabled={busy === "sync"}>
                  <RefreshCw size={16} />
                  Sync
                </Button>
              )}
              {allowPush && submissionMode === "git" && (
                <Button variant="secondary" onClick={pushGit} disabled={busy === "push"}>
                  <UploadCloud size={16} />
                  Push Work
                </Button>
              )}
              {allowManage && (
                <Button onClick={deployBranch} disabled={busy === "deploy"}>
                  <Rocket size={16} />
                  Deploy Branch
                </Button>
              )}
            </>
          )}
        </div>

        {status && <p className="mt-4 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-300">{status}</p>}
      </form>

      <div className="panel p-4">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Commit Activity</h2>
            <p className="mt-1 text-xs text-slate-500">Latest updates from the selected branch and developer commit counts.</p>
          </div>
          <div className="text-right text-xs text-slate-500">
            <p>Last sync</p>
            <p className="mt-1 text-slate-300">{dateTime(project.last_synced_at)}</p>
          </div>
        </div>

        <div className="grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-3">
            {commits.slice(0, 5).map((commit) => (
              <a key={`${commit.sha}-${commit.branch}`} href={commit.html_url || undefined} target="_blank" rel="noreferrer" className="block rounded-lg border border-white/10 bg-white/[0.035] p-3 transition hover:border-teal-300/40">
                <div className="flex items-center justify-between gap-3">
                  <span className="inline-flex items-center gap-2 text-xs font-medium text-teal-200">
                    <GitCommitHorizontal size={14} />
                    {commit.short_sha}
                  </span>
                  {commit.html_url && <ExternalLink size={14} className="text-slate-500" />}
                </div>
                <p className="mt-2 text-sm font-medium text-white">{commit.message || "Commit update"}</p>
                <p className="mt-1 text-xs text-slate-500">{commit.author_login || commit.author_name || commit.author_email || "Unknown"} · {dateTime(commit.committed_at)}</p>
              </a>
            ))}
            {!commits.length && <p className="rounded-lg bg-white/[0.035] p-4 text-sm text-slate-500">No commits synced yet.</p>}
          </div>

          <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
            <h3 className="text-xs font-medium uppercase tracking-[0.14em] text-slate-400">Developer Activity</h3>
            <div className="mt-3 space-y-3">
              {developerActivity.map((item) => (
                <div key={item.name}>
                  <div className="mb-1 flex items-center justify-between text-xs text-slate-400">
                    <span className="truncate">{item.name}</span>
                    <span>{item.total}</span>
                  </div>
                  <div className="h-2 rounded-full bg-white/8">
                    <div className="h-2 rounded-full bg-[color:var(--accent)]" style={{ width: `${Math.min(item.total * 20, 100)}%` }} />
                  </div>
                </div>
              ))}
              {!developerActivity.length && <p className="text-sm text-slate-500">Commit authors appear after sync.</p>}
            </div>
          </div>
        </div>
      </div>

      {allowPush && (
        <div className="panel p-4 xl:col-span-2">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Developer Submission</h2>
              <p className="mt-1 text-xs text-slate-500">Choose Git push manually, or upload files to server storage for Admin review.</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-white/[0.04] p-1">
              {[
                ["files", "Upload Files"],
                ["git", "Push Git"]
              ].map(([value, label]) => (
                <button key={value} type="button" onClick={() => setSubmissionMode(value)} className={`rounded-md px-3 py-1.5 text-sm ${submissionMode === value ? "bg-white/15 text-white" : "text-slate-400"}`}>
                  {label}
                </button>
              ))}
            </div>
          </div>

          {submissionMode === "git" ? (
            <div className="mt-4 grid gap-3 rounded-lg border border-white/10 bg-white/[0.035] p-3 sm:grid-cols-[1fr_160px_auto]">
              <div>
                <label className="label">Commit Message</label>
                <input className="field" value={pushForm.commit_message} onChange={(event) => setPushForm({ ...pushForm, commit_message: event.target.value })} placeholder="Completed project updates" />
              </div>
              <div>
                <label className="label">Push Branch</label>
                <input className="field" value={pushForm.branch} onChange={(event) => setPushForm({ ...pushForm, branch: event.target.value })} placeholder={form.selected_branch || "main"} />
              </div>
              <div className="flex items-end">
                <Button onClick={pushGit} disabled={busy === "push"} className="w-full">
                  <UploadCloud size={16} />
                  Push
                </Button>
              </div>
            </div>
          ) : (
            <div className="mt-4">
              <FileUploader projects={[project]} defaultProject={project.id} lockedProject defaultVisibility="INTERNAL" />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
