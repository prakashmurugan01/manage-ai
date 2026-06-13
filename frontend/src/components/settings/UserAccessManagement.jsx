import { CheckCircle2, Lock, Plus, ShieldCheck, Trash2, UserCheck, UsersRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../api/client.js";
import { ROLE_LABELS, ROLES } from "../../utils/rbac.js";

const MODULES = [
  "TASKS",
  "COLLABORATION",
  "TICKETS",
  "NOTIFICATIONS",
  "AI_CHATBOT",
  "MONITORING",
  "CONNECTION_ENGINE",
  "PROJECT_FILES",
  "ANALYTICS",
  "AUDIT",
];

const ACTIONS = ["VIEW", "CREATE", "EDIT", "DELETE", "ADMIN", "EXPORT"];
const ROLE_ACTIONS = {
  [ROLES.SUPER_ADMIN]: ACTIONS,
  [ROLES.ADMIN]: ["VIEW", "CREATE", "EDIT", "ADMIN", "EXPORT"],
  [ROLES.DEVELOPER]: ["VIEW", "CREATE", "EDIT"],
  [ROLES.CLIENT]: ["VIEW", "EXPORT"],
};

export default function UserAccessManagement({ data, onRefresh }) {
  const [controls, setControls] = useState(data || []);
  const [users, setUsers] = useState([]);
  const [isAdding, setIsAdding] = useState(false);
  const [message, setMessage] = useState(null);
  const [formData, setFormData] = useState({
    user: "",
    module: MODULES[0],
    role: ROLES.DEVELOPER,
    actions: ["VIEW"],
    is_enabled: true,
    expires_at: "",
  });

  useEffect(() => {
    setControls(data || []);
  }, [data]);

  useEffect(() => {
    api.get("/users/")
      .then((response) => setUsers(response.data.results || response.data || []))
      .catch(() => setUsers([]));
  }, []);

  const summary = useMemo(() => {
    const active = controls.filter((control) => control.is_enabled && control.is_valid !== false).length;
    const clients = controls.filter((control) => control.role === ROLES.CLIENT || control.user_detail?.role === ROLES.CLIENT).length;
    const admins = controls.filter((control) => [ROLES.ADMIN, ROLES.SUPER_ADMIN].includes(control.role || control.user_detail?.role)).length;
    return { active, clients, admins, total: controls.length };
  }, [controls]);

  function notify(text, type = "success") {
    setMessage({ text, type });
    window.setTimeout(() => setMessage(null), 2800);
  }

  function setRole(role) {
    setFormData((current) => ({ ...current, role, actions: ROLE_ACTIONS[role] || ["VIEW"] }));
  }

  async function handleAddAccess() {
    if (!formData.user) {
      notify("Please select a user", "error");
      return;
    }

    try {
      const payload = { ...formData };
      if (!payload.expires_at) delete payload.expires_at;
      const response = await api.post("/settings/access-controls/", payload);
      setControls((items) => [response.data, ...items]);
      setFormData({ user: "", module: MODULES[0], role: ROLES.DEVELOPER, actions: ["VIEW"], is_enabled: true, expires_at: "" });
      setIsAdding(false);
      notify("Access rule created");
      onRefresh?.();
    } catch (err) {
      notify(err.response?.data?.detail || "Failed to add access control", "error");
    }
  }

  async function handleRemove(id) {
    if (!confirm("Remove this access control?")) return;

    try {
      await api.delete(`/settings/access-controls/${id}/`);
      setControls((items) => items.filter((control) => control.id !== id));
      notify("Access rule removed");
      onRefresh?.();
    } catch {
      notify("Failed to remove access control", "error");
    }
  }

  async function updateControl(controlId, patch, successMessage = "Access updated") {
    try {
      const response = await api.patch(`/settings/access-controls/${controlId}/`, patch);
      setControls((items) => items.map((control) => (control.id === controlId ? response.data : control)));
      notify(successMessage);
      onRefresh?.();
    } catch {
      notify("Failed to update access", "error");
    }
  }

  function handleToggleAction(control, action) {
    const actions = control.actions || [];
    const newActions = actions.includes(action)
      ? actions.filter((item) => item !== action)
      : [...actions, action];
    updateControl(control.id, { actions: newActions }, `${action} ${newActions.includes(action) ? "enabled" : "disabled"}`);
  }

  function applyPreset(preset) {
    setFormData((current) => ({
      ...current,
      actions: preset === "full" ? ACTIONS : preset === "client" ? ROLE_ACTIONS[ROLES.CLIENT] : ["VIEW"],
      role: preset === "client" ? ROLES.CLIENT : current.role,
    }));
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-4">
        <AccessStat icon={ShieldCheck} label="Active Rules" value={`${summary.active}/${summary.total}`} />
        <AccessStat icon={UsersRound} label="Client Controls" value={summary.clients} />
        <AccessStat icon={UserCheck} label="Admin Grants" value={summary.admins} />
        <AccessStat icon={Lock} label="Actions" value={ACTIONS.length} />
      </div>

      {message && (
        <div className={`rounded-lg border p-3 text-sm ${message.type === "error" ? "border-red-400/25 bg-red-400/10 text-red-200" : "border-emerald-400/25 bg-emerald-400/10 text-emerald-200"}`}>
          {message.text}
        </div>
      )}

      {isAdding && (
        <div className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4">
          <div className="mb-4 flex items-center gap-2 text-sm font-bold text-[color:var(--text-strong)]">
            <Plus size={17} />
            New Access Rule
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Field label="User">
              <select
                value={formData.user}
                onChange={(event) => setFormData({ ...formData, user: event.target.value })}
                className="form-control"
              >
                <option value="">Select a user</option>
                {users.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.full_name || item.email} / {ROLE_LABELS[item.role] || item.role}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Module">
              <select
                value={formData.module}
                onChange={(event) => setFormData({ ...formData, module: event.target.value })}
                className="form-control"
              >
                {MODULES.map((module) => (
                  <option key={module} value={module}>{labelize(module)}</option>
                ))}
              </select>
            </Field>
            <Field label="Role Mode">
              <div className="grid grid-cols-2 gap-2">
                {Object.values(ROLES).map((role) => (
                  <button
                    key={role}
                    type="button"
                    onClick={() => setRole(role)}
                    className={`rounded-lg border px-3 py-2 text-sm font-semibold transition ${
                      formData.role === role ? "border-[color:var(--primary)] bg-[color:var(--surface-soft)] text-[color:var(--text-strong)]" : "border-[color:var(--border)] text-[color:var(--text-muted)]"
                    }`}
                  >
                    {ROLE_LABELS[role]}
                  </button>
                ))}
              </div>
            </Field>
            <Field label="Expires At">
              <input
                type="datetime-local"
                value={formData.expires_at}
                onChange={(event) => setFormData({ ...formData, expires_at: event.target.value })}
                className="form-control"
              />
            </Field>
          </div>

          <div className="mt-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-bold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">Actions</span>
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => applyPreset("full")} className="btn-secondary text-xs">Full Access</button>
                <button type="button" onClick={() => applyPreset("client")} className="btn-secondary text-xs">Client Mode</button>
                <button type="button" onClick={() => applyPreset("view")} className="btn-secondary text-xs">View Only</button>
              </div>
            </div>
            <ActionChips
              selected={formData.actions}
              onToggle={(action) => setFormData({
                ...formData,
                actions: formData.actions.includes(action)
                  ? formData.actions.filter((item) => item !== action)
                  : [...formData.actions, action],
              })}
            />
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" onClick={handleAddAccess} className="btn-primary">
              <CheckCircle2 size={16} />
              Add Access
            </button>
            <button type="button" onClick={() => setIsAdding(false)} className="btn-secondary">
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {controls.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[color:var(--border)] bg-[color:var(--soft-card-bg)] py-8 text-center text-[color:var(--text-muted)]">No access controls configured</div>
        ) : (
          controls.map((control) => (
            <AccessRule
              key={control.id}
              control={control}
              onToggleAction={handleToggleAction}
              onToggleEnabled={() => updateControl(control.id, { is_enabled: !control.is_enabled }, `Access ${control.is_enabled ? "disabled" : "enabled"}`)}
              onRemove={() => handleRemove(control.id)}
            />
          ))
        )}
      </div>

      {!isAdding && (
        <button
          type="button"
          onClick={() => setIsAdding(true)}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] px-4 py-3 text-sm font-bold text-[color:var(--text-strong)] transition hover:border-[color:var(--border-strong)]"
        >
          <Plus size={18} />
          Add User Access
        </button>
      )}

      <div className="rounded-lg border border-blue-500/20 bg-blue-500/10 p-4 text-sm text-blue-300">
        Use this panel to grant specific permissions to admins, developers, and clients. Each action can be controlled independently.
      </div>
    </div>
  );
}

function AccessRule({ control, onToggleAction, onToggleEnabled, onRemove }) {
  const valid = control.is_valid !== false && control.is_enabled !== false;
  return (
    <article className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-sm font-bold text-[color:var(--text-strong)]">{control.user_detail?.full_name || control.user_detail?.email || "User"}</h3>
            <span className={`rounded-full px-2 py-1 text-[11px] font-bold ${valid ? "bg-emerald-400/12 text-emerald-200" : "bg-red-400/12 text-red-200"}`}>
              {valid ? "Active" : "Locked"}
            </span>
            <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] font-bold text-[color:var(--text-muted)]">{ROLE_LABELS[control.role || control.user_detail?.role] || control.role || "Role"}</span>
          </div>
          <p className="mt-1 text-sm text-[color:var(--text-muted)]">{labelize(control.module)} / {control.user_detail?.email}</p>
          <p className="mt-1 text-xs text-[color:var(--text-muted)]">{control.expires_at ? `Expires ${new Date(control.expires_at).toLocaleString()}` : "No expiry"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={onToggleEnabled} className={`rounded-lg px-3 py-2 text-sm font-bold transition ${valid ? "bg-emerald-500/15 text-emerald-200" : "bg-slate-500/15 text-slate-300"}`}>
            {valid ? "Enabled" : "Disabled"}
          </button>
          <button type="button" onClick={onRemove} className="rounded-lg bg-red-500/12 p-2 text-red-300 transition hover:bg-red-500/18">
            <Trash2 size={18} />
          </button>
        </div>
      </div>
      <div className="mt-4">
        <ActionChips selected={control.actions || []} onToggle={(action) => onToggleAction(control, action)} />
      </div>
    </article>
  );
}

function ActionChips({ selected, onToggle }) {
  return (
    <div className="flex flex-wrap gap-2">
      {ACTIONS.map((action) => (
        <button
          key={action}
          type="button"
          onClick={() => onToggle(action)}
          className={`rounded-lg border px-3 py-1.5 text-xs font-bold transition ${
            selected.includes(action)
              ? "border-emerald-400/30 bg-emerald-400/12 text-emerald-200"
              : "border-[color:var(--border)] bg-[color:var(--surface)] text-[color:var(--text-muted)]"
          }`}
        >
          {action}
        </button>
      ))}
    </div>
  );
}

function AccessStat({ icon: Icon, label, value }) {
  return (
    <div className="rounded-lg border border-[color:var(--border)] bg-[color:var(--soft-card-bg)] p-4">
      <Icon size={18} className="text-[color:var(--primary)]" />
      <p className="mt-2 text-xs uppercase tracking-[0.14em] text-[color:var(--text-muted)]">{label}</p>
      <p className="mt-1 text-xl font-black text-[color:var(--text-strong)]">{value}</p>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-bold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">{label}</span>
      {children}
    </label>
  );
}

function labelize(value) {
  return String(value || "None").replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}
