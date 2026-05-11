import { CheckCircle2, Images, ImagePlus, LifeBuoy, MessageSquare, Plus, Sparkles, Trash2, UserRoundCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listFrom } from "../api/client.js";
import { projectsApi, ticketsApi, usersApi } from "../api/services.js";
import Badge from "../components/ui/Badge.jsx";
import Button from "../components/ui/Button.jsx";
import Modal from "../components/ui/Modal.jsx";
import Page from "../components/ui/Page.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { canManage, ROLES } from "../utils/rbac.js";

const statuses = ["OPEN", "TRIAGED", "IN_PROGRESS", "RESOLVED", "CLOSED"];
const priorities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

function TicketCard({ ticket, users, canAssign, onUpdate, onComment, onDelete }) {
  const [reply, setReply] = useState("");
  const developers = users.filter((user) => [ROLES.DEVELOPER, ROLES.ADMIN, ROLES.SUPER_ADMIN].includes(user.role));

  async function submitReply(event) {
    event.preventDefault();
    if (!reply.trim()) return;
    await onComment(ticket.id, reply.trim());
    setReply("");
  }

  return (
    <article className="panel overflow-hidden p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge value={ticket.status} />
            <Badge value={ticket.priority} />
            <Badge value={ticket.source} />
          </div>
          <h2 className="mt-3 text-base font-semibold text-white">{ticket.title}</h2>
          <p className="mt-1 text-sm text-slate-400">{ticket.description}</p>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
            <span>{ticket.project_name}</span>
            <span>Raised by {ticket.raised_by_detail?.full_name || ticket.raised_by_detail?.email || "System"}</span>
            <span>Assigned to {ticket.assigned_to_detail?.full_name || ticket.assigned_to_detail?.email || "Unassigned"}</span>
          </div>
          {ticket.auto_assigned && (
            <div className="mt-3 inline-flex items-center gap-2 rounded-lg border border-teal-300/20 bg-teal-300/10 px-3 py-2 text-xs text-teal-100">
              <Sparkles size={14} />
              {ticket.assignment_reason || "Auto-assigned to the project team"}
            </div>
          )}
          {(ticket.screenshot || ticket.attachments?.length > 0) && (
            <div className="mt-4 overflow-hidden rounded-lg border border-white/10 bg-white/[0.035]">
              <div className="flex items-center gap-2 border-b border-white/10 px-3 py-2 text-xs text-slate-400">
                <Images size={14} />
                Screenshots
              </div>
              <div className="grid gap-3 p-3 sm:grid-cols-2">
                {ticket.screenshot && (
                  <a href={ticket.screenshot} target="_blank" rel="noreferrer" className="overflow-hidden rounded-lg border border-white/10 bg-black/20">
                    <img src={ticket.screenshot} alt={`${ticket.title} screenshot`} className="h-48 w-full object-contain" />
                  </a>
                )}
                {(ticket.attachments || []).map((attachment) => (
                  <a key={attachment.id} href={attachment.file} target="_blank" rel="noreferrer" className="overflow-hidden rounded-lg border border-white/10 bg-black/20">
                    <img src={attachment.file} alt={attachment.caption || `${ticket.title} screenshot`} className="h-48 w-full object-contain" />
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="grid min-w-60 gap-2">
          <select className="field" value={ticket.status} onChange={(event) => onUpdate(ticket.id, { status: event.target.value })}>
            {statuses.map((status) => <option key={status} value={status}>{status.replace("_", " ")}</option>)}
          </select>
          {canAssign && (
            <select className="field" value={ticket.assigned_to || ""} onChange={(event) => onUpdate(ticket.id, { assigned_to: event.target.value || null })}>
              <option value="">Unassigned</option>
              {developers.map((developer) => (
                <option key={developer.id} value={developer.id}>{developer.full_name || developer.email}</option>
              ))}
            </select>
          )}
          {onDelete && (
            <Button variant="danger" onClick={() => onDelete(ticket.id)}>
              <Trash2 size={16} />
              Delete
            </Button>
          )}
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-white/10 bg-white/[0.035] p-3">
        <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
          <MessageSquare size={14} />
          Responses
        </div>
        <div className="space-y-2">
          {(ticket.comments || []).map((comment) => (
            <div key={comment.id} className="rounded-lg bg-white/[0.04] px-3 py-2 text-sm">
              <p className="text-slate-300">{comment.body}</p>
              <p className="mt-1 text-xs text-slate-500">{comment.author_detail?.full_name || comment.author_detail?.email} · {new Date(comment.created_at).toLocaleString()}</p>
            </div>
          ))}
          {!ticket.comments?.length && <p className="text-sm text-slate-500">No responses yet.</p>}
        </div>
        <form onSubmit={submitReply} className="mt-3 flex gap-2">
          <input className="field" placeholder="Respond to this ticket" value={reply} onChange={(event) => setReply(event.target.value)} />
          <Button type="submit" variant="secondary">
            <MessageSquare size={16} />
            Reply
          </Button>
        </form>
      </div>
    </article>
  );
}

export default function Tickets() {
  const { user } = useAuth();
  const [tickets, setTickets] = useState([]);
  const [projects, setProjects] = useState([]);
  const [users, setUsers] = useState([]);
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ project: "", title: "", description: "", priority: "MEDIUM", screenshot: null, screenshots: [] });

  useEffect(() => {
    ticketsApi.list({ status }).then((response) => setTickets(listFrom(response)));
  }, [status]);

  useEffect(() => {
    projectsApi.list().then((response) => {
      const items = listFrom(response);
      setProjects(items);
      setForm((current) => ({ ...current, project: current.project || items[0]?.id || "" }));
    });
    usersApi.list().then((response) => setUsers(listFrom(response)));
  }, []);

  const counts = useMemo(() => {
    return statuses.reduce((acc, item) => {
      acc[item] = tickets.filter((ticket) => ticket.status === item).length;
      return acc;
    }, {});
  }, [tickets]);

  async function createTicket(event) {
    event.preventDefault();
    const payload = new FormData();
    payload.append("project", form.project);
    payload.append("title", form.title);
    payload.append("description", form.description);
    payload.append("priority", form.priority);
    if (form.screenshot) payload.append("screenshot", form.screenshot);
    form.screenshots.forEach((file) => payload.append("screenshots", file));
    const { data } = await ticketsApi.create(payload);
    setTickets((items) => [data, ...items]);
    setOpen(false);
    setForm((current) => ({ ...current, title: "", description: "", screenshot: null, screenshots: [] }));
  }

  async function updateTicket(id, payload) {
    const { data } = await ticketsApi.update(id, payload);
    setTickets((items) => items.map((item) => (item.id === id ? data : item)));
  }

  async function addComment(id, body) {
    const { data } = await ticketsApi.comment(id, { body });
    setTickets((items) => items.map((item) => (item.id === id ? { ...item, comments: [...(item.comments || []), data] } : item)));
  }

  async function deleteTicket(id) {
    await ticketsApi.remove(id);
    setTickets((items) => items.filter((item) => item.id !== id));
  }

  return (
    <Page
      title="Tickets"
      subtitle="Client issues, developer bug reports, screenshots, assignments, responses, and resolution tracking."
      actions={
        <>
          <select className="field w-44" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All tickets</option>
            {statuses.map((item) => <option key={item} value={item}>{item.replace("_", " ")}</option>)}
          </select>
          <Button onClick={() => setOpen(true)}>
            <Plus size={16} />
            Ticket
          </Button>
        </>
      }
    >
      <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {statuses.map((item) => (
          <div key={item} className="panel p-4">
            <div className="flex items-center justify-between">
              <Badge value={item} />
              {item === "RESOLVED" ? <CheckCircle2 size={18} className="text-emerald-300" /> : <LifeBuoy size={18} className="text-sky-300" />}
            </div>
            <p className="mt-3 text-2xl font-semibold text-white">{counts[item] || 0}</p>
          </div>
        ))}
      </div>

      <div className="space-y-4">
        {tickets.map((ticket) => (
          <TicketCard
            key={ticket.id}
            ticket={ticket}
            users={users}
            canAssign={canManage(user)}
            onUpdate={updateTicket}
            onComment={addComment}
            onDelete={canManage(user) ? deleteTicket : null}
          />
        ))}
        {!tickets.length && <p className="panel p-6 text-sm text-slate-500">No tickets found.</p>}
      </div>

      <Modal open={open} title="Raise Ticket" onClose={() => setOpen(false)}>
        <form onSubmit={createTicket} className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">Project</label>
              <select className="field" required value={form.project} onChange={(event) => setForm({ ...form, project: event.target.value })}>
                {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Priority</label>
              <select className="field" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}>
                {priorities.map((priority) => <option key={priority} value={priority}>{priority}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="label">Title</label>
            <input className="field" required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
          </div>
          <div>
            <label className="label">Description</label>
            <textarea className="field min-h-28" required value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
          </div>
          <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-3 text-sm text-slate-300">
            <span className="inline-flex items-center gap-2">
              <ImagePlus size={16} />
              {form.screenshot?.name || "Primary screenshot"}
            </span>
            <input type="file" accept="image/*" className="hidden" onChange={(event) => setForm({ ...form, screenshot: event.target.files?.[0] || null })} />
          </label>
          <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-3 text-sm text-slate-300">
            <span className="inline-flex items-center gap-2">
              <Images size={16} />
              {form.screenshots.length ? `${form.screenshots.length} screenshots selected` : "Additional screenshots"}
            </span>
            <input type="file" accept="image/*" multiple className="hidden" onChange={(event) => setForm({ ...form, screenshots: Array.from(event.target.files || []) })} />
          </label>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit">
              <UserRoundCheck size={16} />
              Submit
            </Button>
          </div>
        </form>
      </Modal>
    </Page>
  );
}
