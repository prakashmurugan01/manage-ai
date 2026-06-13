import { AlertTriangle, BriefcaseBusiness, CheckCircle2, Fingerprint, IdCard, KeyRound, LockKeyhole, PauseCircle, Plus, Save, ScanFace, Search, ShieldCheck, Sparkles, UploadCloud, UserX, UsersRound, UserRoundCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { apiErrorMessage, listFrom } from "../api/client.js";
import { authApi, teamsApi, usersApi } from "../api/services.js";
import FaceCapture from "../components/auth/FaceCapture.jsx";
import Badge from "../components/ui/Badge.jsx";
import Button from "../components/ui/Button.jsx";
import Modal from "../components/ui/Modal.jsx";
import Page from "../components/ui/Page.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { ROLES } from "../utils/rbac.js";

const emptyForm = {
  email: "",
  username: "",
  password: "",
  first_name: "",
  last_name: "",
  role: "DEVELOPER",
  department: "",
  phone: "",
  secret_id: "",
  role_title: "",
  skills: "",
  bio: "",
  availability_status: "Available"
};

const emptyTeam = { name: "", description: "", lead: "", members: [], max_members: 50 };
const approvalFilters = ["ALL", "PENDING", "APPROVED", "REJECTED", "SUSPENDED"];

function splitList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function displayName(user) {
  return user?.full_name || user?.email || "Unknown";
}

function approvalStatus(user) {
  if (user?.approval_status) return user.approval_status;
  return user?.is_active === false ? "SUSPENDED" : "APPROVED";
}

function mediaUrl(value) {
  if (!value) return "";
  if (String(value).startsWith("http")) return value;
  if (String(value).startsWith("/")) return value;
  const root = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api").replace(/\/api\/?$/, "");
  return `${root}${value}`;
}

function UserProfileEditor({ user, onSave, onReplace }) {
  const { user: currentUser, updateCurrentUser } = useAuth();
  const [edit, setEdit] = useState(() => profileToEdit(user));
  const [busy, setBusy] = useState(false);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [faceBusy, setFaceBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [avatarPreview, setAvatarPreview] = useState(mediaUrl(user?.avatar));

  useEffect(() => {
    setEdit(profileToEdit(user));
    setAvatarPreview(mediaUrl(user?.avatar));
    setMessage("");
    setError("");
  }, [user]);

  if (!user) return null;

  const isSelf = currentUser?.id === user.id;
  const isAdminProfile = [ROLES.ADMIN, ROLES.SUPER_ADMIN].includes(user.role);
  const canChangeRole = currentUser?.role === ROLES.SUPER_ADMIN;
  const canUseFace = isSelf && [ROLES.ADMIN, ROLES.SUPER_ADMIN].includes(currentUser?.role);
  const initials = displayName(user).slice(0, 2).toUpperCase();

  function syncUpdated(updated) {
    if (!updated) return;
    onReplace?.(updated);
    if (currentUser?.id === updated.id) {
      updateCurrentUser(updated);
      localStorage.setItem("manageaiFaceEmail", updated.email || "");
    }
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (edit.password && edit.password !== edit.confirm_password) {
        setError("Password confirmation does not match.");
        return;
      }
      const payload = new FormData();
      ["first_name", "last_name", "username", "email", "phone", "secret_id", "department", "role_title", "availability_status", "bio"].forEach((key) => {
        payload.append(key, edit[key] || "");
      });
      if (canChangeRole) payload.append("role", edit.role || user.role);
      payload.append("skills", JSON.stringify(splitList(edit.skills)));
      if (edit.password) payload.append("password", edit.password);
      const updated = await onSave(user.id, payload);
      syncUpdated(updated);
      setEdit((current) => ({ ...current, password: "", confirm_password: "" }));
      setMessage("Profile saved.");
    } catch (caught) {
      setError(apiErrorMessage(caught, "Profile could not be saved."));
    } finally {
      setBusy(false);
    }
  }

  async function uploadAvatar(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setAvatarBusy(true);
    setError("");
    setMessage("");
    const previewUrl = URL.createObjectURL(file);
    setAvatarPreview(previewUrl);
    try {
      const payload = new FormData();
      payload.append("avatar", file);
      const updated = await onSave(user.id, payload);
      syncUpdated(updated);
      setAvatarPreview(mediaUrl(updated.avatar));
      setMessage("Profile photo uploaded.");
    } catch (caught) {
      setAvatarPreview(mediaUrl(user.avatar));
      setError(apiErrorMessage(caught, "Profile photo upload failed."));
    } finally {
      URL.revokeObjectURL(previewUrl);
      setAvatarBusy(false);
    }
  }

  async function enrollFace(formData) {
    if (!canUseFace) return;
    setFaceBusy(true);
    setError("");
    setMessage("");
    try {
      await authApi.faceEnroll(formData);
      localStorage.setItem("manageaiFaceLoginReady", "true");
      localStorage.setItem("manageaiFaceEmail", currentUser.email || user.email || "");
      const { data } = await authApi.me();
      syncUpdated(data);
      setMessage("Face ID registered. Face Unlock will open automatically on the login page.");
    } catch (caught) {
      const nextError = apiErrorMessage(caught, "Face ID registration failed.");
      setError(nextError);
      throw caught;
    } finally {
      setFaceBusy(false);
    }
  }

  async function setFaceEnabled(enabled) {
    setFaceBusy(true);
    setError("");
    setMessage("");
    try {
      const payload = new FormData();
      payload.append("face_login_enabled", enabled ? "true" : "false");
      const updated = await onSave(user.id, payload);
      syncUpdated(updated);
      setMessage(enabled ? "Face ID enabled." : "Face ID disabled.");
    } catch (caught) {
      setError(apiErrorMessage(caught, "Face ID setting could not be updated."));
    } finally {
      setFaceBusy(false);
    }
  }

  return (
    <div className="grid gap-5">
      <div className="grid gap-4 xl:grid-cols-[300px_1fr]">
        <div className="relative overflow-hidden rounded-lg border border-white/10 bg-gradient-to-br from-cyan-400/10 via-white/[0.045] to-fuchsia-500/10 p-4">
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300 to-transparent" />
          <div className="mx-auto grid h-32 w-32 place-items-center overflow-hidden rounded-lg border border-white/15 bg-slate-950/50 text-3xl font-semibold text-white shadow-2xl">
            {avatarPreview ? <img src={avatarPreview} alt={displayName(user)} className="h-full w-full object-cover" /> : initials}
          </div>
          <label className={`mt-4 flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/10 px-3 py-2 text-sm font-medium text-slate-100 transition hover:bg-white/15 ${avatarBusy ? "pointer-events-none opacity-60" : ""}`}>
            {avatarBusy ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/60 border-t-transparent" /> : <UploadCloud size={16} />}
            {avatarBusy ? "Uploading..." : "Upload photo"}
            <input className="hidden" type="file" accept="image/*" onChange={uploadAvatar} />
          </label>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <Badge value={user.role} />
            <Badge value={approvalStatus(user)} />
            <Badge value={user.availability_status || "Available"} />
          </div>
          <div className="mt-4 rounded-lg border border-white/10 bg-black/20 p-3 text-center">
            <p className="text-xs uppercase tracking-[0.14em] text-slate-500">User ID</p>
            <p className="mt-1 break-all font-mono text-sm text-cyan-100">{user.secret_id}</p>
          </div>
          {user.rejection_reason && <p className="mt-3 rounded-lg border border-rose-300/20 bg-rose-300/10 p-3 text-xs text-rose-100">{user.rejection_reason}</p>}
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <ProfileMetric icon={ShieldCheck} label="Role" value={user.role_title || user.department || user.role} />
          <ProfileMetric icon={BriefcaseBusiness} label="Projects" value={user.assigned_project_count || 0} />
          <ProfileMetric icon={CheckCircle2} label="Open Work" value={user.assigned_task_count || 0} />
          <ProfileMetric icon={ScanFace} label="Face ID" value={user.face_login_enabled ? "Enabled" : user.face_enrolled_at ? "Registered" : "Optional"} tone={user.face_login_enabled ? "text-emerald-200" : "text-slate-300"} />
        </div>
      </div>

      {(message || error) && (
        <div className={`rounded-lg border px-4 py-3 text-sm ${error ? "border-rose-300/25 bg-rose-500/10 text-rose-100" : "border-emerald-300/25 bg-emerald-400/10 text-emerald-100"}`}>
          {error || message}
        </div>
      )}

      <form onSubmit={submit} className="grid gap-4">
        <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
          <div className="mb-4 flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-cyan-300/10 text-cyan-200"><IdCard size={19} /></div>
            <div>
              <h3 className="text-sm font-semibold text-white">Identity</h3>
              <p className="mt-1 text-xs text-slate-500">Profile, login name, user ID, and contact details.</p>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <Field label="First Name" value={edit.first_name} onChange={(value) => setEdit({ ...edit, first_name: value })} />
            <Field label="Last Name" value={edit.last_name} onChange={(value) => setEdit({ ...edit, last_name: value })} />
            <Field label="Login Username" value={edit.username} onChange={(value) => setEdit({ ...edit, username: value })} />
            <Field label="Email" type="email" value={edit.email} onChange={(value) => setEdit({ ...edit, email: value })} />
            <Field label="Phone" value={edit.phone} onChange={(value) => setEdit({ ...edit, phone: value })} />
            <Field label="User / Secret ID" value={edit.secret_id} onChange={(value) => setEdit({ ...edit, secret_id: value })} />
            <Field label="Department" value={edit.department} onChange={(value) => setEdit({ ...edit, department: value })} />
            <Field label="Role Title" value={edit.role_title} onChange={(value) => setEdit({ ...edit, role_title: value })} />
            <Field label="Availability" value={edit.availability_status} onChange={(value) => setEdit({ ...edit, availability_status: value })} />
            {canChangeRole && (
              <div>
                <label className="label">Role</label>
                <select className="field" value={edit.role} onChange={(event) => setEdit({ ...edit, role: event.target.value })}>
                  <option value="SUPER_ADMIN">Super Admin</option>
                  <option value="ADMIN">Admin</option>
                  <option value="DEVELOPER">Developer</option>
                  <option value="CLIENT">Client</option>
                </select>
              </div>
            )}
            <div className={canChangeRole ? "sm:col-span-2" : "sm:col-span-2 xl:col-span-3"}>
              <Field label="Skills" value={edit.skills} onChange={(value) => setEdit({ ...edit, skills: value })} placeholder="React, Django, Security, DevOps" />
            </div>
            <div className="sm:col-span-2 xl:col-span-3">
              <label className="label">Bio</label>
              <textarea className="field min-h-24" value={edit.bio} onChange={(event) => setEdit({ ...edit, bio: event.target.value })} />
            </div>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-[0.92fr_1.08fr]">
          <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
            <div className="mb-4 flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-lg bg-amber-300/10 text-amber-200"><KeyRound size={19} /></div>
              <div>
                <h3 className="text-sm font-semibold text-white">Credentials</h3>
                <p className="mt-1 text-xs text-slate-500">Admin and Super Admin password updates are saved securely.</p>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="New Password" type="password" value={edit.password} onChange={(value) => setEdit({ ...edit, password: value })} placeholder="Leave blank to keep current" />
              <Field label="Confirm Password" type="password" value={edit.confirm_password} onChange={(value) => setEdit({ ...edit, confirm_password: value })} placeholder="Repeat new password" />
            </div>
            <div className="mt-4 rounded-lg border border-white/10 bg-black/20 p-3 text-xs text-slate-400">
              <LockKeyhole className="mb-2 text-amber-200" size={16} />
              Password validation uses the backend security policy before saving.
            </div>
          </div>

          <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="grid h-10 w-10 place-items-center rounded-lg bg-violet-300/10 text-violet-200"><ScanFace size={19} /></div>
                <div>
                  <h3 className="text-sm font-semibold text-white">Face ID</h3>
                  <p className="mt-1 text-xs text-slate-500">{user.face_login_enabled ? "Registered and enabled" : user.face_enrolled_at ? "Registered, currently disabled" : "Optional biometric login"}</p>
                </div>
              </div>
              {user.face_login_enabled && <Badge value="Enabled" />}
            </div>
            {canUseFace ? (
              <div className="grid gap-3">
                <FaceCapture mode="enroll" email={edit.email} onSubmit={enrollFace} startLabel="Start camera" submitLabel={faceBusy ? "Saving..." : "Register Face ID"} autoStart={false} />
                {user.face_enrolled_at && (
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" onClick={() => setFaceEnabled(true)} disabled={faceBusy || user.face_login_enabled}><Sparkles size={16} />Enable</Button>
                    <Button variant="secondary" onClick={() => setFaceEnabled(false)} disabled={faceBusy || !user.face_login_enabled}><UserX size={16} />Disable</Button>
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-lg border border-white/10 bg-black/20 p-4 text-sm text-slate-400">
                Face ID enrollment is available from your own Admin or Super Admin profile.
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap justify-end gap-2">
          <Button type="submit" disabled={busy}><Save size={16} />{busy ? "Saving..." : "Save Profile"}</Button>
        </div>
      </form>

      <div className="grid gap-4 lg:grid-cols-2">
        <AssignmentPanel title="Assigned Projects" empty="No assigned projects.">
          {(user.assigned_projects || []).map((project) => (
            <div key={project.id} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-white">{project.name}</p>
                <Badge value={project.status} />
              </div>
              <div className="mt-2 h-2 rounded-full bg-white/[0.08]">
                <div className="h-2 rounded-full bg-[color:var(--accent)]" style={{ width: `${project.progress || 0}%` }} />
              </div>
            </div>
          ))}
        </AssignmentPanel>
        <AssignmentPanel title="Assigned Work" empty="No open tasks.">
          {(user.assigned_tasks || []).map((task) => (
            <div key={task.id} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-white">{task.title}</p>
                <Badge value={task.status} />
              </div>
              <p className="mt-1 text-xs text-slate-500">{task.project_name} - Day {task.workflow_day}</p>
            </div>
          ))}
        </AssignmentPanel>
      </div>

      {!isAdminProfile && (
        <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-400">
          Developer and client accounts keep the same profile tools, while admin-only Face ID enrollment remains scoped to Admin and Super Admin profiles.
        </div>
      )}
    </div>
  );
}

function profileToEdit(user) {
  return {
    first_name: user?.first_name || "",
    last_name: user?.last_name || "",
    username: user?.username || "",
    email: user?.email || "",
    phone: user?.phone || "",
    secret_id: user?.secret_id || "",
    department: user?.department || "",
    role_title: user?.role_title || "",
    role: user?.role || "DEVELOPER",
    availability_status: user?.availability_status || "Available",
    skills: (user?.skills || []).join(", "),
    bio: user?.bio || "",
    password: "",
    confirm_password: ""
  };
}

function ProfileMetric({ icon: Icon, label, value, tone = "text-white" }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</p>
        <Icon size={17} className="text-cyan-200" />
      </div>
      <p className={`mt-3 text-xl font-semibold ${tone}`}>{value}</p>
    </div>
  );
}

function Field({ label, value, onChange, type = "text", placeholder = "" }) {
  return (
    <div>
      <label className="label">{label}</label>
      <input className="field" type={type} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}

function AssignmentPanel({ title, empty, children }) {
  const hasItems = Array.isArray(children) ? children.length > 0 : Boolean(children);
  return (
    <div>
      <p className="label">{title}</p>
      <div className="space-y-2">
        {children}
        {!hasItems && <p className="rounded-lg border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-500">{empty}</p>}
      </div>
    </div>
  );
}

function TeamPanel({ teams, developers, teamForm, setTeamForm, onCreateTeam }) {
  function toggleMember(id) {
    setTeamForm((current) => ({
      ...current,
      members: current.members.includes(id) ? current.members.filter((item) => item !== id) : [...current.members, id]
    }));
  }

  return (
    <div className="mt-6 grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
      <form onSubmit={onCreateTeam} className="panel p-4">
        <div className="mb-4 flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-lg bg-white/10 text-teal-200"><UsersRound size={20} /></div>
          <div>
            <h2 className="text-sm font-semibold text-white">Team Allocation</h2>
            <p className="mt-1 text-xs text-slate-500">Create scalable teams, usually up to 50 developers per team.</p>
          </div>
        </div>
        <div className="grid gap-3">
          <input className="field" required placeholder="Team name" value={teamForm.name} onChange={(event) => setTeamForm({ ...teamForm, name: event.target.value })} />
          <textarea className="field min-h-20" placeholder="Team focus" value={teamForm.description} onChange={(event) => setTeamForm({ ...teamForm, description: event.target.value })} />
          <div className="grid gap-3 sm:grid-cols-2">
            <select className="field" value={teamForm.lead} onChange={(event) => setTeamForm({ ...teamForm, lead: event.target.value })}>
              <option value="">Select lead</option>
              {developers.map((developer) => <option key={developer.id} value={developer.id}>{displayName(developer)}</option>)}
            </select>
            <input className="field" type="number" min={1} max={250} value={teamForm.max_members} onChange={(event) => setTeamForm({ ...teamForm, max_members: Number(event.target.value) })} />
          </div>
          <div className="max-h-48 space-y-2 overflow-y-auto rounded-lg border border-white/10 bg-white/[0.035] p-2">
            {developers.map((developer) => (
              <label key={developer.id} className="flex cursor-pointer items-center justify-between gap-3 rounded-lg bg-white/[0.035] px-3 py-2 text-sm text-slate-300">
                <span>
                  <span className="block font-medium text-white">{displayName(developer)}</span>
                  <span className="text-xs text-slate-500">{developer.secret_id}</span>
                </span>
                <input type="checkbox" checked={teamForm.members.includes(developer.id)} onChange={() => toggleMember(developer.id)} />
              </label>
            ))}
          </div>
          <Button type="submit"><Plus size={16} />Create Team</Button>
        </div>
      </form>

      <div className="panel p-4">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-white">Active Teams</h2>
          <Badge value={`${teams.length} Teams`} />
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {teams.map((team) => (
            <div key={team.id} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-white">{team.name}</p>
                  <p className="mt-1 text-xs text-slate-500">{team.lead_detail?.full_name || team.lead_detail?.email || "No lead"}</p>
                </div>
                <Badge value={`${team.member_count}/${team.max_members}`} />
              </div>
              <p className="mt-3 line-clamp-2 text-xs text-slate-400">{team.description || "No description"}</p>
            </div>
          ))}
          {!teams.length && <p className="rounded-lg bg-white/[0.035] p-4 text-sm text-slate-500">No teams created yet.</p>}
        </div>
      </div>
    </div>
  );
}

export default function Users() {
  const { user } = useAuth();
  const [users, setUsers] = useState([]);
  const [teams, setTeams] = useState([]);
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(null);
  const [secretId, setSecretId] = useState("");
  const [lookupError, setLookupError] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [teamForm, setTeamForm] = useState(emptyTeam);
  const [statusFilter, setStatusFilter] = useState("ALL");

  useEffect(() => {
    usersApi.list().then((response) => setUsers(listFrom(response)));
    teamsApi.list().then((response) => setTeams(listFrom(response)));
  }, []);

  const developers = useMemo(() => users.filter((item) => item.role === ROLES.DEVELOPER), [users]);
  const filteredUsers = useMemo(() => {
    if (statusFilter === "ALL") return users;
    return users.filter((item) => approvalStatus(item) === statusFilter);
  }, [statusFilter, users]);
  const approvalStats = useMemo(() => {
    const totals = { all: users.length, pending: 0, approved: 0, rejected: 0, suspended: 0 };
    users.forEach((item) => {
      const key = approvalStatus(item).toLowerCase();
      totals[key] = (totals[key] || 0) + 1;
    });
    totals.approvalRate = totals.all ? Math.round((totals.approved / totals.all) * 100) : 0;
    return totals;
  }, [users]);
  const canCreateAdmin = user?.role === ROLES.SUPER_ADMIN;

  async function create(event) {
    event.preventDefault();
    const payload = { ...form, skills: splitList(form.skills) };
    if (!payload.secret_id) delete payload.secret_id;
    const { data } = await usersApi.create(payload);
    setUsers((items) => [data, ...items]);
    setForm(emptyForm);
    setOpen(false);
  }

  async function saveUser(id, payload) {
    const { data } = await usersApi.update(id, payload);
    setUsers((items) => items.map((item) => (item.id === id ? data : item)));
    setSelected(data);
    return data;
  }

  function replaceUser(updated) {
    setUsers((items) => items.map((item) => (item.id === updated.id ? updated : item)));
    setSelected((current) => (current?.id === updated.id ? updated : current));
  }

  async function approveUser(item) {
    const { data } = await usersApi.approve(item.id);
    replaceUser(data);
  }

  async function rejectUser(item) {
    const reason = window.prompt("Optional rejection reason", item.rejection_reason || "");
    if (reason === null) return;
    const { data } = await usersApi.reject(item.id, { reason });
    replaceUser(data);
  }

  async function suspendUser(item) {
    const reason = window.prompt("Optional suspension note", item.rejection_reason || "");
    if (reason === null) return;
    const { data } = await usersApi.suspend(item.id, { reason });
    replaceUser(data);
  }

  async function createTeam(event) {
    event.preventDefault();
    const payload = { ...teamForm, lead: teamForm.lead || null };
    const { data } = await teamsApi.create(payload);
    setTeams((items) => [data, ...items]);
    setTeamForm(emptyTeam);
  }

  async function lookup(event) {
    event.preventDefault();
    setLookupError("");
    try {
      const { data } = await usersApi.lookupSecret(secretId);
      setSelected(data);
    } catch (error) {
      setLookupError(error.response?.data?.secret_id || "No profile found for that Secret ID.");
    }
  }

  return (
    <Page
      title={user?.role === ROLES.SUPER_ADMIN ? "Super Admin User Management" : "Admin User Management"}
      subtitle="Profiles, photos, passwords, contact details, developer Secret IDs, team allocation, and workload visibility."
      actions={<Button onClick={() => setOpen(true)}><Plus size={16} />User</Button>}
    >
      <div className="mb-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div className="panel p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Pending</p>
            <AlertTriangle size={18} className="text-amber-200" />
          </div>
          <p className="mt-3 text-3xl font-semibold text-white">{approvalStats.pending}</p>
          <p className="mt-1 text-xs text-slate-500">Waiting for admin review</p>
        </div>
        <div className="panel p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Approved</p>
            <CheckCircle2 size={18} className="text-emerald-200" />
          </div>
          <p className="mt-3 text-3xl font-semibold text-white">{approvalStats.approved}</p>
          <p className="mt-1 text-xs text-slate-500">Full dashboard access</p>
        </div>
        <div className="panel p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Approval Rate</p>
            <ShieldCheck size={18} className="text-cyan-200" />
          </div>
          <p className="mt-3 text-3xl font-semibold text-white">{approvalStats.approvalRate}%</p>
          <p className="mt-1 text-xs text-slate-500">Approved of total users</p>
        </div>
        <div className="panel p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Restricted</p>
            <UserX size={18} className="text-rose-200" />
          </div>
          <p className="mt-3 text-3xl font-semibold text-white">{approvalStats.rejected + approvalStats.suspended}</p>
          <p className="mt-1 text-xs text-slate-500">Rejected or suspended</p>
        </div>
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
        <form onSubmit={lookup} className="panel p-4">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-lg bg-white/10 text-teal-200">
              <Fingerprint size={21} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Secret ID Lookup</h2>
              <p className="mt-1 text-xs text-slate-500">Fetch profile, role, skills, projects, and assigned work.</p>
            </div>
          </div>
          <div className="mt-4 flex gap-2">
            <input className="field" placeholder="DEV-XXXXXXXX" value={secretId} onChange={(event) => setSecretId(event.target.value)} />
            <Button type="submit"><Search size={16} />Fetch</Button>
          </div>
          {lookupError && <p className="mt-3 rounded-lg border border-rose-300/20 bg-rose-300/10 px-3 py-2 text-sm text-rose-200">{lookupError}</p>}
        </form>

        <div className="panel p-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white">Developer Bench</h2>
              <p className="mt-1 text-xs text-slate-500">Click any profile to edit and inspect assignments.</p>
            </div>
            <Badge value={`${developers.length} Developers`} />
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {developers.slice(0, 6).map((developer) => (
              <button key={developer.id} type="button" onClick={() => setSelected(developer)} className="rounded-lg border border-white/10 bg-white/[0.035] p-3 text-left transition hover:border-teal-300/40 hover:bg-white/[0.07]">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-white">{displayName(developer)}</p>
                    <p className="mt-1 text-xs text-slate-500">{developer.role_title || developer.department || "Developer"}</p>
                  </div>
                  <UserRoundCheck size={18} className="text-teal-200" />
                </div>
                <p className="mt-3 font-mono text-xs text-slate-400">{developer.secret_id}</p>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="panel overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 p-4">
          <div>
            <h2 className="text-sm font-semibold text-white">Registration Approval Queue</h2>
            <p className="mt-1 text-xs text-slate-500">Filter users by review state and take one-click admin action.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {approvalFilters.map((filter) => (
              <button
                key={filter}
                type="button"
                onClick={() => setStatusFilter(filter)}
                className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${statusFilter === filter ? "border-teal-300/40 bg-teal-300/15 text-teal-100" : "border-white/10 bg-white/[0.035] text-slate-400 hover:text-white"}`}
              >
                {filter === "ALL" ? "All" : filter.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>
        <table className="w-full min-w-[980px] text-left text-sm">
          <thead className="border-b border-white/10 bg-white/[0.035] text-xs uppercase tracking-[0.14em] text-slate-400">
            <tr>
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Secret ID</th>
              <th className="px-4 py-3">Role</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Phone</th>
              <th className="px-4 py-3">Projects</th>
              <th className="px-4 py-3">Open Work</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {filteredUsers.map((item) => (
              <tr key={item.id} className="cursor-pointer transition hover:bg-white/[0.035]" onClick={() => setSelected(item)}>
                <td className="px-4 py-3">
                  <p className="font-medium text-white">{displayName(item)}</p>
                  <p className="text-xs text-slate-500">{item.email}</p>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-slate-300">{item.secret_id}</td>
                <td className="px-4 py-3"><Badge value={item.role} /></td>
                <td className="px-4 py-3"><Badge value={approvalStatus(item)} /></td>
                <td className="px-4 py-3 text-slate-300">{item.phone || "None"}</td>
                <td className="px-4 py-3 text-slate-300">{item.assigned_project_count || 0}</td>
                <td className="px-4 py-3 text-slate-300">{item.assigned_task_count || 0}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-2" onClick={(event) => event.stopPropagation()}>
                    <button type="button" title="Approve user" onClick={() => approveUser(item)} className="grid h-8 w-8 place-items-center rounded-lg border border-emerald-300/20 bg-emerald-300/10 text-emerald-200 transition hover:bg-emerald-300/20">
                      <CheckCircle2 size={15} />
                    </button>
                    <button type="button" title="Reject user" onClick={() => rejectUser(item)} className="grid h-8 w-8 place-items-center rounded-lg border border-rose-300/20 bg-rose-300/10 text-rose-200 transition hover:bg-rose-300/20">
                      <UserX size={15} />
                    </button>
                    <button type="button" title="Suspend user" onClick={() => suspendUser(item)} className="grid h-8 w-8 place-items-center rounded-lg border border-slate-300/20 bg-slate-300/10 text-slate-200 transition hover:bg-slate-300/20">
                      <PauseCircle size={15} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!filteredUsers.length && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-sm text-slate-500">No users match this approval filter.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <TeamPanel teams={teams} developers={developers} teamForm={teamForm} setTeamForm={setTeamForm} onCreateTeam={createTeam} />

      <Modal open={open} title="Create User" onClose={() => setOpen(false)}>
        <form onSubmit={create} className="grid gap-4 sm:grid-cols-2">
          {["first_name", "last_name", "username", "email", "password", "phone", "secret_id", "department", "role_title", "availability_status"].map((key) => (
            <div key={key}>
              <label className="label">{key.replace("_", " ")}</label>
              <input className="field" required={["first_name", "username", "email", "password"].includes(key)} type={key === "password" ? "password" : key === "email" ? "email" : "text"} value={form[key]} onChange={(event) => setForm({ ...form, [key]: event.target.value })} />
            </div>
          ))}
          <div>
            <label className="label">Role</label>
            <select className="field" value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
              {canCreateAdmin && <option value="ADMIN">Admin</option>}
              <option value="DEVELOPER">Developer</option>
              <option value="CLIENT">Client</option>
              {canCreateAdmin && <option value="SUPER_ADMIN">Super Admin</option>}
            </select>
          </div>
          <div>
            <label className="label">Skills</label>
            <input className="field" placeholder="React, Django, AI, DevOps" value={form.skills} onChange={(event) => setForm({ ...form, skills: event.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Profile Bio</label>
            <textarea className="field min-h-24" value={form.bio} onChange={(event) => setForm({ ...form, bio: event.target.value })} />
          </div>
          <div className="flex items-end justify-end gap-2 sm:col-span-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit"><BriefcaseBusiness size={16} />Create</Button>
          </div>
        </form>
      </Modal>

      <Modal open={Boolean(selected)} title={displayName(selected)} onClose={() => setSelected(null)} size="wide">
        <UserProfileEditor user={selected} onSave={saveUser} onReplace={replaceUser} />
      </Modal>
    </Page>
  );
}
