import { useMemo, useState } from "react";

import { tasksApi } from "../../api/services.js";
import TaskCard from "./TaskCard.jsx";

const columns = [
  ["BACKLOG", "Backlog"],
  ["TODO", "To Do"],
  ["IN_PROGRESS", "In Progress"],
  ["REVIEW", "Review"],
  ["DONE", "Done"],
  ["BLOCKED", "Blocked"]
];

export default function KanbanBoard({ tasks = [], onTasksChange, workflowDays }) {
  const [dragged, setDragged] = useState(null);
  const maxWorkflowDays = workflowDays || Math.max(7, ...tasks.map((task) => Number(task.workflow_day || 1)));
  const grouped = useMemo(() => {
    return columns.reduce((acc, [status]) => {
      acc[status] = tasks.filter((task) => task.status === status);
      return acc;
    }, {});
  }, [tasks]);

  async function drop(status) {
    if (!dragged || dragged.status === status) return;
    const nextPosition = grouped[status]?.length ?? 0;
    const optimistic = tasks.map((task) => (task.id === dragged.id ? { ...task, status, position: nextPosition } : task));
    onTasksChange?.(optimistic);
    const { data } = await tasksApi.move(dragged.id, { status, position: nextPosition });
    onTasksChange?.(optimistic.map((task) => (task.id === data.id ? data : task)));
    setDragged(null);
  }

  async function updateWorkflow(task, workflowDay, progressPercent = task.progress_percent || 0) {
    const dayProgress = Array.from({ length: maxWorkflowDays }, (_, index) => index + 1).reduce((acc, day) => {
      acc[`day_${day}`] = workflowDay > day ? 100 : workflowDay === day ? progressPercent : 0;
      return acc;
    }, { ...(task.day_progress || {}) });
    const optimistic = tasks.map((item) => (item.id === task.id ? { ...item, workflow_day: workflowDay, progress_percent: progressPercent, day_progress: dayProgress } : item));
    onTasksChange?.(optimistic);
    const { data } = await tasksApi.update(task.id, { workflow_day: workflowDay, progress_percent: progressPercent, day_progress: dayProgress });
    onTasksChange?.(optimistic.map((item) => (item.id === data.id ? data : item)));
  }

  return (
    <div className="grid gap-3 overflow-x-auto pb-2 lg:grid-cols-6">
      {columns.map(([status, label]) => (
        <section
          key={status}
          onDragOver={(event) => event.preventDefault()}
          onDrop={() => drop(status)}
          className="min-h-[420px] min-w-64 rounded-lg border border-white/10 bg-white/[0.035] p-3"
        >
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">{label}</h2>
            <span className="rounded-full bg-white/10 px-2 py-1 text-xs text-slate-400">{grouped[status]?.length || 0}</span>
          </div>
          <div className="space-y-3">
            {grouped[status]?.map((task) => (
              <TaskCard key={task.id} task={task} workflowDays={maxWorkflowDays} onDragStart={(_, item) => setDragged(item)} onProgressChange={updateWorkflow} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
