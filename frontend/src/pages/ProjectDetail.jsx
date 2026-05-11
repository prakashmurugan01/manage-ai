import { BrainCircuit, CheckCircle2, ClipboardList, Lightbulb, MessageSquareWarning, Plus, UsersRound, Wrench } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { listFrom } from "../api/client.js";
import { aiApi, deploymentsApi, projectsApi, tasksApi } from "../api/services.js";
import DeploymentToggle from "../components/projects/DeploymentToggle.jsx";
import ProjectConnectionPanel from "../components/projects/ProjectConnectionPanel.jsx";
import ProjectFlowPanel from "../components/projects/ProjectFlowPanel.jsx";
import KanbanBoard from "../components/tasks/KanbanBoard.jsx";
import Badge from "../components/ui/Badge.jsx";
import Button from "../components/ui/Button.jsx";
import Modal from "../components/ui/Modal.jsx";
import Page from "../components/ui/Page.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { pct } from "../utils/format.js";
import { canManage } from "../utils/rbac.js";

export default function ProjectDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [project, setProject] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [deployment, setDeployment] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [taskOpen, setTaskOpen] = useState(false);
  const [taskForm, setTaskForm] = useState({ title: "", description: "", priority: "MEDIUM", status: "BACKLOG", workflow_day: 1, assignee: "", due_date: "", project: id });

  useEffect(() => {
    projectsApi.get(id).then(({ data }) => setProject(data));
    projectsApi.kanban(id).then((response) => setTasks(listFrom(response)));
    deploymentsApi.list({ project: id }).then((response) => setDeployment(listFrom(response)[0]));
    aiApi.list({ project: id }).then((response) => setSuggestions(listFrom(response)));
  }, [id]);

  async function createTask(event) {
    event.preventDefault();
    const payload = { ...taskForm, project: id, assignee: taskForm.assignee || null };
    if (!payload.due_date) delete payload.due_date;
    const { data } = await tasksApi.create(payload);
    setTasks((items) => [data, ...items]);
    setTaskOpen(false);
  }

  async function generateSuggestions() {
    const { data } = await aiApi.generate({ project: Number(id), context: project?.description, limit: 4 });
    setSuggestions(data);
  }

  async function approveSuggestion(suggestion) {
    const { data } = await aiApi.approve(suggestion.id, { status: "BACKLOG" });
    setTasks((items) => [data, ...items]);
    setSuggestions((items) => items.map((item) => (item.id === suggestion.id ? { ...item, status: "APPROVED" } : item)));
  }

  async function reviewProject(approvalStatus, approvalNote) {
    const { data } = await projectsApi.review(id, { approval_status: approvalStatus, approval_note: approvalNote });
    setProject(data);
  }

  return (
    <Page
      title={project?.name || "Project"}
      subtitle={project?.description}
      actions={
        <>
          {deployment && canManage(user) && <DeploymentToggle deployment={deployment} onChange={setDeployment} />}
          {canManage(user) && (
            <Button onClick={() => setTaskOpen(true)}>
              <Plus size={16} />
              Task
            </Button>
          )}
        </>
      }
    >
      <div className="mb-6 grid gap-4 lg:grid-cols-4">
        <div className="panel p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Status</p>
          <div className="mt-3"><Badge value={project?.status} /></div>
        </div>
        <div className="panel p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Priority</p>
          <div className="mt-3"><Badge value={project?.priority} /></div>
        </div>
        <div className="panel p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Progress</p>
          <p className="mt-2 text-3xl font-semibold text-white">{pct(project?.progress)}</p>
        </div>
        <div className="panel p-4">
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Deployment</p>
          <p className="mt-2 text-lg font-semibold text-white">{deployment?.is_enabled ? "ON" : "OFF"}</p>
        </div>
      </div>

      <div className="mb-6 panel p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Project Approval</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge value={project?.approval_status || "DRAFT"} />
              {project?.approval_note && <span className="text-sm text-slate-400">{project.approval_note}</span>}
            </div>
          </div>
          {canManage(user) && (
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={() => reviewProject("IN_REVIEW", "Submitted for review")}><ClipboardList size={16} />Review</Button>
              <Button onClick={() => reviewProject("APPROVED", "Project approved")}><CheckCircle2 size={16} />Approve</Button>
              <Button variant="ghost" onClick={() => reviewProject("CORRECTION_REQUESTED", "Correction requested")}><MessageSquareWarning size={16} />Request Correction</Button>
            </div>
          )}
        </div>
      </div>

      <ProjectFlowPanel project={project} canEdit={canManage(user)} onProjectChange={setProject} />

      <div className="mb-6 grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <div className="panel p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <Lightbulb size={17} className="text-amber-200" />
            Project Blueprint
          </div>
          <p className="text-sm leading-6 text-slate-300">{project?.project_idea || project?.description || "No project idea added yet."}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <p className="label">Technologies</p>
              <div className="flex flex-wrap gap-2">
                {(project?.technologies_used || []).map((item) => <Badge key={item} value={item} />)}
                {!project?.technologies_used?.length && <span className="text-sm text-slate-500">None added.</span>}
              </div>
            </div>
            <div>
              <p className="label">Features</p>
              <div className="flex flex-wrap gap-2">
                {(project?.features_to_implement || []).map((item) => <Badge key={item} value={item} />)}
                {!project?.features_to_implement?.length && <span className="text-sm text-slate-500">None added.</span>}
              </div>
            </div>
          </div>
        </div>
        <div className="panel p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <UsersRound size={17} className="text-teal-200" />
            Assigned Team
          </div>
          <div className="space-y-2">
            {(project?.teams_detail || []).map((team) => (
              <div key={`team-${team.id}`} className="flex items-center justify-between gap-3 rounded-lg border border-cyan-300/20 bg-cyan-300/10 px-3 py-2">
                <div>
                  <p className="text-sm font-medium text-white">{team.name}</p>
                  <p className="text-xs text-slate-500">{team.member_count}/{team.max_members} members</p>
                </div>
                <Badge value="TEAM" />
              </div>
            ))}
            {(project?.developers_detail || []).map((developer) => (
              <div key={developer.id} className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.035] px-3 py-2">
                <div>
                  <p className="text-sm font-medium text-white">{developer.full_name || developer.email}</p>
                  <p className="text-xs text-slate-500">{developer.secret_id} · {developer.role_title || developer.department || "Developer"}</p>
                </div>
                <Badge value={`${developer.assigned_task_count || 0} Tasks`} />
              </div>
            ))}
            {!project?.developers_detail?.length && <p className="text-sm text-slate-500">No developers assigned yet.</p>}
          </div>
        </div>
      </div>

      <KanbanBoard tasks={tasks} workflowDays={project?.workflow_days || 7} onTasksChange={setTasks} />

      <ProjectConnectionPanel project={project} user={user} deployment={deployment} onProjectChange={setProject} onDeploymentChange={setDeployment} />

      {canManage(user) && (
        <div className="mt-6 panel p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-white">AI Task Suggestions</h2>
            <Button variant="secondary" onClick={generateSuggestions}>
              <BrainCircuit size={16} />
              Generate
            </Button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {suggestions.map((suggestion) => (
              <div key={suggestion.id} className="surface-soft rounded-lg p-3">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-medium text-white">{suggestion.title}</h3>
                  <Badge value={suggestion.status} />
                </div>
                <p className="mt-2 text-xs text-slate-400">{suggestion.rationale}</p>
                {suggestion.status === "DRAFT" && (
                  <Button className="mt-3" variant="secondary" onClick={() => approveSuggestion(suggestion)}>Approve</Button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <Modal open={taskOpen} title="Create Task" onClose={() => setTaskOpen(false)}>
        <form onSubmit={createTask} className="grid gap-4">
          <div>
            <label className="label">Title</label>
            <input className="field" required value={taskForm.title} onChange={(event) => setTaskForm({ ...taskForm, title: event.target.value })} />
          </div>
          <div>
            <label className="label">Description</label>
            <textarea className="field min-h-28" value={taskForm.description} onChange={(event) => setTaskForm({ ...taskForm, description: event.target.value })} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
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
              <label className="label">Status</label>
              <select className="field" value={taskForm.status} onChange={(event) => setTaskForm({ ...taskForm, status: event.target.value })}>
                <option value="BACKLOG">Backlog</option>
                <option value="TODO">To Do</option>
                <option value="IN_PROGRESS">In Progress</option>
              </select>
            </div>
            <div>
              <label className="label">Workflow Day</label>
              <select className="field" value={taskForm.workflow_day} onChange={(event) => setTaskForm({ ...taskForm, workflow_day: Number(event.target.value) })}>
                {Array.from({ length: Math.min(project?.workflow_days || 7, 30) }, (_, index) => index + 1).map((day) => (
                  <option key={day} value={day}>Day {day}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Assignee</label>
              <select className="field" value={taskForm.assignee} onChange={(event) => setTaskForm({ ...taskForm, assignee: event.target.value })}>
                <option value="">Unassigned</option>
                {(project?.developers_detail || []).map((developer) => <option key={developer.id} value={developer.id}>{developer.full_name || developer.email}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Due Date</label>
              <input className="field" type="date" value={taskForm.due_date} onChange={(event) => setTaskForm({ ...taskForm, due_date: event.target.value })} />
            </div>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3 text-sm text-slate-400">
            <span className="inline-flex items-center gap-2 text-slate-300"><ClipboardList size={15} /> Workflow chain</span>
            <span className="ml-2">Day 1 to Day {project?.workflow_days || 7}</span>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setTaskOpen(false)}>Cancel</Button>
            <Button type="submit"><Wrench size={16} />Create</Button>
          </div>
        </form>
      </Modal>
    </Page>
  );
}
