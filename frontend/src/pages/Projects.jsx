import { Plus, Sparkles, UsersRound } from "lucide-react";
import { useEffect, useState } from "react";

import { listFrom } from "../api/client.js";
import { documentsApi, projectsApi, tasksApi, teamsApi, usersApi } from "../api/services.js";
import ProjectCard from "../components/projects/ProjectCard.jsx";
import Button from "../components/ui/Button.jsx";
import Modal from "../components/ui/Modal.jsx";
import Page from "../components/ui/Page.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { canManage } from "../utils/rbac.js";

export default function Projects() {
  const { user } = useAuth();
  const [projects, setProjects] = useState([]);
  const [users, setUsers] = useState([]);
  const [teams, setTeams] = useState([]);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: "",
    slug: "",
    project_idea: "",
    description: "",
    technologies_used: "",
    features_to_implement: "",
    status: "ACTIVE",
    priority: "MEDIUM",
    owner: user?.id,
    client: "",
    developers: [],
    teams: [],
    due_date: "",
    workflow_days: 7,
    starter_tasks: "",
    project_files: []
  });

  useEffect(() => {
    projectsApi.list({ search: query }).then((response) => setProjects(listFrom(response)));
  }, [query]);

  useEffect(() => {
    usersApi.list().then((response) => setUsers(listFrom(response)));
    teamsApi.list().then((response) => setTeams(listFrom(response)));
  }, []);

  const developers = users.filter((item) => item.role === "DEVELOPER");
  const clients = users.filter((item) => item.role === "CLIENT");

  function splitList(value) {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function toggleDeveloper(id) {
    setForm((current) => ({
      ...current,
      developers: current.developers.includes(id) ? current.developers.filter((item) => item !== id) : [...current.developers, id]
    }));
  }

  function toggleTeam(id) {
    setForm((current) => ({
      ...current,
      teams: current.teams.includes(id) ? current.teams.filter((item) => item !== id) : [...current.teams, id]
    }));
  }

  async function createProject(event) {
    event.preventDefault();
    const payload = {
      name: form.name,
      project_idea: form.project_idea,
      description: form.description,
      status: form.status,
      priority: form.priority,
      owner: form.owner,
      client: form.client || null,
      developers: form.developers,
      teams: form.teams,
      due_date: form.due_date,
      slug: form.slug || form.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
      technologies_used: splitList(form.technologies_used),
      features_to_implement: splitList(form.features_to_implement),
      workflow_days: Number(form.workflow_days) || 7
    };
    if (!payload.due_date) delete payload.due_date;
    const { data } = await projectsApi.create(payload);
    const starterTasks = form.starter_tasks.split("\n").map((item) => item.trim()).filter(Boolean);
    const assignees = data.developers?.length ? data.developers : form.developers;
    await Promise.all(starterTasks.map((title, index) => tasksApi.create({
      project: data.id,
      title,
      description: `Starter task for ${data.name}`,
      priority: form.priority,
      status: "TODO",
      workflow_day: Math.min(index + 1, Number(form.workflow_days) || 7),
      assignee: assignees[index % Math.max(assignees.length, 1)] || null
    })));
    await Promise.all(form.project_files.map((file) => {
      const formData = new FormData();
      formData.append("project", data.id);
      formData.append("title", file.name);
      formData.append("category", "Project Setup");
      formData.append("visibility", "INTERNAL");
      formData.append("file", file);
      return documentsApi.upload(formData);
    }));
    setProjects((items) => [data, ...items]);
    setOpen(false);
  }

  return (
    <Page
      title="Projects"
      subtitle="Project delivery, owners, client visibility, task load, and deployment state."
      actions={
        <>
          <input className="field w-64" placeholder="Search projects" value={query} onChange={(event) => setQuery(event.target.value)} />
          {canManage(user) && (
            <Button onClick={() => setOpen(true)}>
              <Plus size={16} />
              Project
            </Button>
          )}
        </>
      }
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {projects.map((project) => <ProjectCard key={project.id} project={project} />)}
      </div>
      {!projects.length && <p className="panel p-6 text-sm text-slate-500">No projects found.</p>}

      <Modal open={open} title="Create Project" onClose={() => setOpen(false)}>
        <form onSubmit={createProject} className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">Name</label>
              <input className="field" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </div>
            <div>
              <label className="label">Slug</label>
              <input className="field" value={form.slug} onChange={(event) => setForm({ ...form, slug: event.target.value })} />
            </div>
            <div>
              <label className="label">Client</label>
              <select className="field" value={form.client} onChange={(event) => setForm({ ...form, client: event.target.value })}>
                <option value="">Internal project</option>
                {clients.map((client) => <option key={client.id} value={client.id}>{client.full_name || client.email}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Due Date</label>
              <input className="field" type="date" value={form.due_date} onChange={(event) => setForm({ ...form, due_date: event.target.value })} />
            </div>
            <div>
              <label className="label">Status</label>
              <select className="field" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
                <option value="PLANNING">Planning</option>
                <option value="ACTIVE">Active</option>
                <option value="ON_HOLD">On hold</option>
              </select>
            </div>
            <div>
              <label className="label">Priority</label>
              <select className="field" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}>
                <option value="LOW">Low</option>
                <option value="MEDIUM">Medium</option>
                <option value="HIGH">High</option>
                <option value="CRITICAL">Critical</option>
              </select>
            </div>
            <div>
              <label className="label">Workflow Days</label>
              <input className="field" min={1} max={365} type="number" value={form.workflow_days} onChange={(event) => setForm({ ...form, workflow_days: event.target.value })} />
            </div>
          </div>
          <div>
            <label className="label">Project Idea</label>
            <textarea className="field min-h-24" placeholder="Core idea and outcome expected from the project" value={form.project_idea} onChange={(event) => setForm({ ...form, project_idea: event.target.value })} />
          </div>
          <div>
            <label className="label">Description</label>
            <textarea className="field min-h-28" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">Technologies Used</label>
              <input className="field" placeholder="React, Django, PostgreSQL, AI" value={form.technologies_used} onChange={(event) => setForm({ ...form, technologies_used: event.target.value })} />
            </div>
            <div>
              <label className="label">Features To Implement</label>
              <input className="field" placeholder="Auth, dashboards, tickets, approvals" value={form.features_to_implement} onChange={(event) => setForm({ ...form, features_to_implement: event.target.value })} />
            </div>
          </div>
          <div>
            <div className="mb-2 flex items-center gap-2">
              <UsersRound size={15} className="text-teal-200" />
              <label className="label mb-0">Assign Developers</label>
            </div>
            <div className="grid max-h-48 gap-2 overflow-y-auto rounded-lg border border-white/10 bg-white/[0.035] p-2 sm:grid-cols-2">
              {developers.map((developer) => (
                <label key={developer.id} className="flex cursor-pointer items-center justify-between gap-3 rounded-lg bg-white/[0.035] px-3 py-2 text-sm text-slate-300">
                  <span>
                    <span className="block font-medium text-white">{developer.full_name || developer.email}</span>
                    <span className="text-xs text-slate-500">{developer.secret_id} · {developer.role_title || "Developer"}</span>
                  </span>
                  <input type="checkbox" checked={form.developers.includes(developer.id)} onChange={() => toggleDeveloper(developer.id)} />
                </label>
              ))}
              {!developers.length && <p className="p-3 text-sm text-slate-500">Create developers first to assign a team.</p>}
            </div>
          </div>
          <div>
            <div className="mb-2 flex items-center gap-2">
              <UsersRound size={15} className="text-cyan-200" />
              <label className="label mb-0">Allocate Teams</label>
            </div>
            <div className="grid max-h-40 gap-2 overflow-y-auto rounded-lg border border-white/10 bg-white/[0.035] p-2 sm:grid-cols-2">
              {teams.map((team) => (
                <label key={team.id} className="flex cursor-pointer items-center justify-between gap-3 rounded-lg bg-white/[0.035] px-3 py-2 text-sm text-slate-300">
                  <span>
                    <span className="block font-medium text-white">{team.name}</span>
                    <span className="text-xs text-slate-500">{team.member_count}/{team.max_members} members</span>
                  </span>
                  <input type="checkbox" checked={form.teams.includes(team.id)} onChange={() => toggleTeam(team.id)} />
                </label>
              ))}
              {!teams.length && <p className="p-3 text-sm text-slate-500">Create teams in User Management.</p>}
            </div>
          </div>
          <div>
            <label className="label">Starter Tasks</label>
            <textarea className="field min-h-24" placeholder={"One task per line\nBuild authentication\nDesign dashboard\nConnect Git repository"} value={form.starter_tasks} onChange={(event) => setForm({ ...form, starter_tasks: event.target.value })} />
          </div>
          <div>
            <label className="label">Project Documents</label>
            <input className="field" type="file" multiple onChange={(event) => setForm({ ...form, project_files: Array.from(event.target.files || []) })} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit"><Sparkles size={16} />Create</Button>
          </div>
        </form>
      </Modal>
    </Page>
  );
}
