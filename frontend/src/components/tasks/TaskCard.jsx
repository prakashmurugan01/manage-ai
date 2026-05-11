import { CheckCircle2, Clock3, GripVertical, Hourglass, MessageSquareWarning } from "lucide-react";

import { dateShort } from "../../utils/format.js";
import Badge from "../ui/Badge.jsx";

export default function TaskCard({ task, draggable = true, workflowDays = 7, onDragStart, onProgressChange }) {
  const day = Number(task.workflow_day || 1);
  const progress = Number(task.progress_percent || 0);
  const visibleDays = Array.from({ length: Math.min(workflowDays, 10) }, (_, index) => index + 1);

  return (
    <article
      draggable={draggable}
      onDragStart={(event) => onDragStart?.(event, task)}
      className="task-card rounded-lg p-3 shadow-sm transition hover:border-teal-300/30"
    >
      <div className="flex items-start gap-2">
        <GripVertical size={16} className="mt-1 shrink-0 text-slate-500" />
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-medium text-white">{task.title}</h3>
          <p className="mt-1 line-clamp-2 text-xs text-slate-400">{task.description || task.project_name}</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge value={task.priority} />
        <Badge value={`DAY ${day}`} />
        <Badge value={`${progress}%`} />
        <Badge value={task.approval_status || "NOT_SUBMITTED"} />
        {task.ai_suggested && <Badge value="AI" />}
      </div>
      <div className="mt-3">
        <div className="mb-2 flex items-center justify-between gap-3 text-xs">
          <span className="text-slate-400">Developer progress</span>
          <span className="font-medium text-white">{progress}%</span>
        </div>
        <input
          type="range"
          min="0"
          max="100"
          step="5"
          value={progress}
          onChange={(event) => onProgressChange?.(task, day, Number(event.target.value))}
          className="w-full accent-teal-300"
        />
        <div className="h-2 overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full bg-[color:var(--accent)]" style={{ width: `${progress}%` }} />
        </div>
      </div>
      <div className="mt-3 grid grid-cols-5 gap-1">
        {visibleDays.map((item) => (
          <button
            key={item}
            type="button"
            onClick={(event) => {
              event.preventDefault();
              onProgressChange?.(task, item, Math.max(progress, Math.round((item / Math.max(workflowDays, 1)) * 100)));
            }}
            className={`h-8 rounded-md text-[11px] font-medium transition ${item <= day ? "progress-day-active bg-[color:var(--accent)] text-white" : "bg-white/8 text-slate-500 hover:bg-white/12"}`}
          >
            Day {item}
          </button>
        ))}
      </div>
      {workflowDays > 10 && <p className="mt-2 text-[11px] text-slate-500">+{workflowDays - 10} more days</p>}
      <div className="mt-3 grid gap-2 text-xs text-slate-500">
        {task.delay_reason && (
          <span className="inline-flex items-center gap-1 text-amber-200">
            <MessageSquareWarning size={13} />
            {task.delay_reason}
          </span>
        )}
        {task.approval_status === "PENDING" && (
          <span className="inline-flex items-center gap-1 text-sky-300">
            <Hourglass size={13} />
            Pending approval
          </span>
        )}
        {task.approval_status === "APPROVED" && (
          <span className="inline-flex items-center gap-1 text-emerald-300">
            <CheckCircle2 size={13} />
            Approved
          </span>
        )}
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 text-xs text-slate-500">
        <span>{task.assignee_detail?.full_name || task.assignee_detail?.email || "Unassigned"}</span>
        <span className="inline-flex items-center gap-1">
          <Clock3 size={13} />
          {dateShort(task.due_date)}
        </span>
      </div>
    </article>
  );
}
