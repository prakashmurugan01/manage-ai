import { CalendarDays, CheckCircle2, Clock3, MessageSquareWarning, Plus, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listFrom } from "../api/client.js";
import { projectsApi, tasksApi, usersApi } from "../api/services.js";
import KanbanBoard from "../components/tasks/KanbanBoard.jsx";
import Badge from "../components/ui/Badge.jsx";
import Button from "../components/ui/Button.jsx";
import Modal from "../components/ui/Modal.jsx";
import Page from "../components/ui/Page.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { canManage } from "../utils/rbac.js";

export default function Tasks() {
  const { user } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [projects, setProjects] = useState([]);
  const [users, setUsers] = useState([]);
  const [mode, setMode] = useState("board");
  const [status, setStatus] = useState("");
  const [taskOpen, setTaskOpen] = useState(false);
  const [taskForm, setTaskForm] = useState({ project: "", title: "", description: "", priority: "MEDIUM", status: "TODO", assignee: "", workflow_day: 1, progress_percent: 0, due_date: "" });

  useEffect(() => {
    tasksApi.list({ status }).then((response) => setTasks(listFrom(response)));
  }, [status]);

  useEffect(() => {
    projectsApi.list().then((response) => {
      const items = listFrom(response);
      setProjects(items);
      setTaskForm((current) => ({ ...current, project: current.project || items[0]?.id || "" }));
    });
    usersApi.list().then((response) => setUsers(listFrom(response)));
  }, []);

  const summary = useMemo(() => ({
    pending: tasks.filter((task) => task.approval_status === "PENDING").length,
    delayed: tasks.filter((task) => task.delay_reason && task.status !== "DONE").length,
    completed: tasks.filter((task) => task.status === "DONE").length,
    open: tasks.filter((task) => task.status !== "DONE").length,
    averageProgress: tasks.length ? Math.round(tasks.reduce((total, task) => total + Number(task.progress_percent || 0), 0) / tasks.length) : 0
  }), [tasks]);

  const timeline = useMemo(() => {
    const maxDay = Math.max(3, ...tasks.map((task) => Number(task.workflow_day || 1)));
    return Array.from({ length: Math.min(maxDay, 14) }, (_, index) => {
      const day = index + 1;
      const scoped = tasks.filter((task) => Number(task.workflow_day || 1) === day);
      const completed = scoped.filter((task) => task.status === "DONE").length;
      return { day, total: scoped.length, completed, blocked: scoped.filter((task) => task.status === "BLOCKED").length };
    });
  }, [tasks]);

  async function updateTask(id, payload) {
    const { data } = await tasksApi.update(id, payload);
    setTasks((items) => items.map((task) => (task.id === id ? data : task)));
  }

  async function approveTask(id) {
    const { data } = await tasksApi.approve(id, {});
    setTasks((items) => items.map((task) => (task.id === id ? data : task)));
  }

  async function disapproveTask(id) {
    const { data } = await tasksApi.disapprove(id, { review_note: "Changes requested" });
    setTasks((items) => items.map((task) => (task.id === id ? data : task)));
  }

  async function createTask(event) {
    event.preventDefault();
    const payload = { ...taskForm, assignee: taskForm.assignee || null, workflow_day: Number(taskForm.workflow_day) || 1, progress_percent: Number(taskForm.progress_percent) || 0 };
    if (!payload.due_date) delete payload.due_date;
    const { data } = await tasksApi.create(payload);
    setTasks((items) => [data, ...items]);
    setTaskOpen(false);
    setTaskForm((current) => ({ ...current, title: "", description: "", assignee: "", progress_percent: 0, due_date: "" }));
  }

  return (
    <Page
      title="Tasks"
      subtitle="Assigned work, delivery state, priority, and drag-and-drop Kanban movement."
      actions={
        <>
          {canManage(user) && (
            <Button onClick={() => setTaskOpen(true)}>
              <Plus size={16} />
              Add New Task
            </Button>
          )}
          <select className="field w-44" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All status</option>
            <option value="BACKLOG">Backlog</option>
            <option value="TODO">To Do</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="REVIEW">Review</option>
            <option value="DONE">Done</option>
            <option value="BLOCKED">Blocked</option>
          </select>
          <div className="rounded-lg border border-white/10 bg-white/[0.04] p-1">
            {["board", "list"].map((item) => (
              <button key={item} type="button" onClick={() => setMode(item)} className={`rounded-md px-3 py-1.5 text-sm ${mode === item ? "bg-white/15 text-white" : "text-slate-400"}`}>
                {item}
              </button>
            ))}
          </div>
        </>
      }
    >
      <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="panel p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Open Workload</p>
          <p className="mt-2 text-2xl font-semibold text-white">{summary.open}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Completed</p>
          <p className="mt-2 text-2xl font-semibold text-white">{summary.completed}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Pending Approval</p>
          <p className="mt-2 text-2xl font-semibold text-white">{summary.pending}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Project Completion</p>
          <p className="mt-2 text-2xl font-semibold text-white">{summary.averageProgress}%</p>
        </div>
      </div>

      <div className="mb-6 panel p-4">
        <div className="mb-4 flex items-center gap-2">
          <CalendarDays size={17} className="text-teal-200" />
          <h2 className="text-sm font-semibold text-white">Timeline Tracking</h2>
        </div>
        <div className="grid gap-3 md:grid-cols-7">
          {timeline.map((item) => (
            <div key={item.day} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-white">Day {item.day}</p>
                {item.blocked ? <MessageSquareWarning size={15} className="text-amber-200" /> : <CheckCircle2 size={15} className="text-emerald-300" />}
              </div>
              <div className="mt-3 h-2 rounded-full bg-white/10">
                <div className="h-2 rounded-full bg-teal-300" style={{ width: `${item.total ? Math.round((item.completed / item.total) * 100) : 0}%` }} />
              </div>
              <p className="mt-2 text-xs text-slate-500">{item.completed}/{item.total} completed</p>
            </div>
          ))}
        </div>
      </div>

      {mode === "board" ? (
        <KanbanBoard tasks={tasks} onTasksChange={setTasks} workflowDays={Math.max(1, ...tasks.map((task) => Number(task.workflow_day || 1)))} />
      ) : (
        <div className="panel overflow-hidden">
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full min-w-[1120px] table-fixed text-left text-sm">
            <thead className="border-b border-white/10 bg-white/[0.035] text-xs uppercase tracking-[0.14em] text-slate-400">
              <tr>
                <th className="w-[190px] px-4 py-3">Task</th>
                <th className="w-[170px] px-4 py-3">Project</th>
                <th className="w-[145px] px-4 py-3">Assignee</th>
                <th className="w-[145px] px-4 py-3">Status</th>
                <th className="w-[105px] px-4 py-3">Priority</th>
                <th className="w-[110px] px-4 py-3">Workflow</th>
                <th className="w-[210px] px-4 py-3">Progress</th>
                <th className="w-[210px] px-4 py-3">Delay</th>
                <th className="w-[190px] px-4 py-3">Approval</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {tasks.map((task) => (
                <tr key={task.id} className="align-top transition hover:bg-white/[0.025]">
                  <td className="px-4 py-4">
                    <p className="line-clamp-3 font-medium leading-5 text-white" title={task.title}>{task.title}</p>
                  </td>
                  <td className="px-4 py-4">
                    <p className="line-clamp-3 leading-5 text-slate-300" title={task.project_name}>{task.project_name}</p>
                  </td>
                  <td className="px-4 py-4">
                    <p className="truncate text-slate-300" title={task.assignee_detail?.full_name || task.assignee_detail?.email || "Unassigned"}>{task.assignee_detail?.full_name || task.assignee_detail?.email || "Unassigned"}</p>
                  </td>
                  <td className="px-4 py-3">
                    <select className="field h-10 min-w-0" value={task.status} onChange={(event) => updateTask(task.id, { status: event.target.value })}>
                      <option value="BACKLOG">Backlog</option>
                      <option value="TODO">To Do</option>
                      <option value="IN_PROGRESS">In Progress</option>
                      <option value="REVIEW">Review</option>
                      <option value="DONE">Done</option>
                      <option value="BLOCKED">Blocked</option>
                    </select>
                  </td>
                  <td className="px-4 py-3"><Badge value={task.priority} /></td>
                  <td className="px-4 py-3"><Badge value={`DAY ${task.workflow_day || 1}`} /></td>
                  <td className="px-4 py-3">
                    <div className="min-w-0">
                      <input className="w-full accent-teal-300" type="range" min="0" max="100" step="5" value={task.progress_percent || 0} onChange={(event) => updateTask(task.id, { progress_percent: Number(event.target.value) })} />
                      <p className="mt-1 truncate text-xs text-slate-500" title={`${task.project_name} ${task.progress_percent || 0}% completed`}>{task.project_name} {task.progress_percent || 0}% completed</p>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <input className="field h-10 min-w-0" placeholder="Reason if delayed" defaultValue={task.delay_reason || ""} onBlur={(event) => updateTask(task.id, { delay_reason: event.target.value })} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <Badge value={task.approval_status || "NOT_SUBMITTED"} />
                      {task.delay_reason && <MessageSquareWarning size={15} className="text-amber-200" />}
                      {canManage(user) && task.approval_status === "PENDING" && (
                        <>
                          <Button variant="secondary" onClick={() => approveTask(task.id)}><CheckCircle2 size={15} />Approve</Button>
                          <Button variant="ghost" onClick={() => disapproveTask(task.id)}><XCircle size={15} />Reject</Button>
                        </>
                      )}
                      {!canManage(user) && task.approval_status === "PENDING" && <span className="inline-flex items-center gap-1 text-xs text-slate-500"><Clock3 size={13} />Review</span>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
            </table>
          </div>
        </div>
      )}

      <Modal open={taskOpen} title="Add New Task" onClose={() => setTaskOpen(false)}>
        <form onSubmit={createTask} className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">Project</label>
              <select className="field" required value={taskForm.project} onChange={(event) => setTaskForm({ ...taskForm, project: event.target.value })}>
                {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Assignee</label>
              <select className="field" value={taskForm.assignee} onChange={(event) => setTaskForm({ ...taskForm, assignee: event.target.value })}>
                <option value="">Unassigned</option>
                {users.filter((item) => ["DEVELOPER", "ADMIN", "SUPER_ADMIN"].includes(item.role)).map((item) => <option key={item.id} value={item.id}>{item.full_name || item.email}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Priority</label>
              <select className="field" value={taskForm.priority} onChange={(event) => setTaskForm({ ...taskForm, priority: event.target.value })}>
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
                <option value="CRITICAL">Critical</option>
              </select>
            </div>
            <div>
              <label className="label">Workflow Day</label>
              <input className="field" type="number" min={1} max={365} value={taskForm.workflow_day} onChange={(event) => setTaskForm({ ...taskForm, workflow_day: event.target.value })} />
            </div>
            <div>
              <label className="label">Progress %</label>
              <input className="field" type="number" min={0} max={100} value={taskForm.progress_percent} onChange={(event) => setTaskForm({ ...taskForm, progress_percent: event.target.value })} />
            </div>
          </div>
          <div>
            <label className="label">Title</label>
            <input className="field" required value={taskForm.title} onChange={(event) => setTaskForm({ ...taskForm, title: event.target.value })} />
          </div>
          <div>
            <label className="label">Description</label>
            <textarea className="field min-h-24" value={taskForm.description} onChange={(event) => setTaskForm({ ...taskForm, description: event.target.value })} />
          </div>
          <div>
            <label className="label">Due Date</label>
            <input className="field" type="date" value={taskForm.due_date} onChange={(event) => setTaskForm({ ...taskForm, due_date: event.target.value })} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setTaskOpen(false)}>Cancel</Button>
            <Button type="submit">Assign Task</Button>
          </div>
        </form>
      </Modal>
    </Page>
  );
}
