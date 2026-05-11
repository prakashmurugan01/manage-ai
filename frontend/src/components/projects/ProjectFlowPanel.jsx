import { GitBranch, Loader2, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";

import { projectsApi } from "../../api/services.js";
import Badge from "../ui/Badge.jsx";
import Button from "../ui/Button.jsx";

function asList(value) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

export default function ProjectFlowPanel({ project, canEdit, onProjectChange }) {
  const [loading, setLoading] = useState(false);
  const flow = asList(project?.project_flow);
  const progressByPhase = useMemo(() => {
    if (!flow.length) return 0;
    const complete = flow.filter((step) => ["DONE", "COMPLETE", "COMPLETED"].includes(String(step.status || "").toUpperCase())).length;
    return Math.round((complete / flow.length) * 100);
  }, [flow]);

  async function generateFlow() {
    setLoading(true);
    try {
      const prompt = [project?.project_idea, project?.description, ...(project?.features_to_implement || [])].filter(Boolean).join("\n");
      const { data } = await projectsApi.projectFlow(project.id, { prompt });
      onProjectChange(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mb-6 panel p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <GitBranch size={17} className="text-sky-300" />
            Project Flow
          </div>
          <p className="mt-1 text-sm text-slate-400">
            Delivery path from prompt to release, aligned with scope, tasks, validation, and deployment.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge value={`${progressByPhase}% Flow`} />
          {canEdit && (
            <Button variant="secondary" onClick={generateFlow} disabled={loading || !project?.id}>
              {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Generate
            </Button>
          )}
        </div>
      </div>

      {flow.length ? (
        <div className="mt-5 grid gap-3 xl:grid-cols-5">
          {flow.map((step, index) => (
            <div key={step.key || `${step.title}-${index}`} className="surface-soft rounded-lg p-3">
              <div className="flex items-start justify-between gap-3">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-sky-300/25 bg-sky-300/10 text-sm font-semibold text-sky-200">
                  {step.phase || index + 1}
                </span>
                <Badge value={step.status || "READY"} />
              </div>
              <h3 className="mt-3 text-sm font-semibold text-white">{step.title}</h3>
              <p className="mt-2 min-h-12 text-xs leading-5 text-slate-400">{step.outcome}</p>
              <div className="mt-3 space-y-2">
                {asList(step.activities).slice(0, 3).map((activity) => (
                  <div key={activity} className="rounded-md border border-white/10 bg-white/[0.035] px-2 py-1.5 text-xs text-slate-300">
                    {activity}
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[11px] uppercase tracking-[0.14em] text-slate-500">{step.owner_role || "Team"}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-lg border border-dashed border-white/15 bg-white/[0.025] p-4 text-sm text-slate-400">
          No project flow has been generated yet. Generate it after adding the project idea, technologies, and features.
        </div>
      )}
    </div>
  );
}
