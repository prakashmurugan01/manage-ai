import { ArrowRight, CalendarDays, GitBranch, Link2, UsersRound } from "lucide-react";
import { Link } from "react-router-dom";

import { dateShort, pct } from "../../utils/format.js";
import Badge from "../ui/Badge.jsx";

export default function ProjectCard({ project }) {
  return (
    <Link to={`/projects/${project.id}`} className="panel block p-4 transition hover:border-teal-300/40 hover:bg-white/[0.075]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-white">{project.name}</h2>
          <p className="mt-1 line-clamp-2 text-sm text-slate-400">{project.description || "No description"}</p>
        </div>
        <ArrowRight size={18} className="text-slate-500" />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Badge value={project.status} />
        <Badge value={project.priority} />
        <Badge value={project.deployment_enabled ? "DEPLOYMENT ON" : "DEPLOYMENT OFF"} />
        <Badge value={project.connection_type || "NONE"} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-400">
        {(project.technologies_used || []).slice(0, 4).map((tech) => <span key={tech} className="rounded-md bg-white/[0.05] px-2 py-1">{tech}</span>)}
      </div>
      <div className="mt-5">
        <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
          <span>Progress</span>
          <span>{pct(project.progress)}</span>
        </div>
        <div className="h-2 rounded-full bg-white/8">
          <div className="h-2 rounded-full bg-teal-300" style={{ width: pct(project.progress) }} />
        </div>
      </div>
      <div className="mt-4 flex items-center gap-2 text-xs text-slate-400">
        <CalendarDays size={14} />
        <span>{dateShort(project.due_date)}</span>
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
        <UsersRound size={14} />
        <span>{project.developers_detail?.length || 0} developers · {project.teams_detail?.length || 0} teams · {project.open_task_count || 0} open tasks</span>
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.035] px-3 py-2 text-xs text-slate-400">
        <span className="inline-flex min-w-0 items-center gap-2">
          {project.connection_type === "GITHUB" ? <GitBranch size={14} /> : <Link2 size={14} />}
          <span className="truncate">{project.selected_branch || project.local_url || project.hosted_url || "No connection"}</span>
        </span>
        <span>{project.connection_status || "DISCONNECTED"}</span>
      </div>
    </Link>
  );
}
