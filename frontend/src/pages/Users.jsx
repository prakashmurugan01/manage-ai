import { motion } from "framer-motion";
import { Activity, AlertTriangle, Bell, Bot, BriefcaseBusiness, CalendarDays, CheckCircle2, ChevronDown, Database, Fingerprint, Gauge, HardDrive, IdCard, KeyRound, LockKeyhole, MessageSquarePlus, Mic, PauseCircle, Plus, RefreshCcw, Rocket, Save, ScanFace, Search, Send, Server, ShieldAlert, ShieldCheck, Sparkles, Ticket, UploadCloud, UserCheck, UserX, UsersRound, UserRoundCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { apiErrorMessage, listFrom } from "../api/client.js";
import { authApi, notificationsApi, projectsApi, teamsApi, ticketsApi, usersApi } from "../api/services.js";
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
  const [quickBusy, setQuickBusy] = useState("");
  const [assistantBusy, setAssistantBusy] = useState(false);
  const [openSections, setOpenSections] = useState({ personal: true, professional: true, access: true, security: true });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [tempPassword, setTempPassword] = useState("");
  const [avatarPreview, setAvatarPreview] = useState(mediaUrl(user?.avatar));
  const [assistantLines, setAssistantLines] = useState([]);

  const insights = useMemo(() => buildUserInsights(user), [user]);
  const timeline = useMemo(() => buildTimeline(user), [user]);
  const firstProject = user?.assigned_projects?.[0] || null;

  useEffect(() => {
    setEdit(profileToEdit(user));
    setAvatarPreview(mediaUrl(user?.avatar));
    setAssistantLines(makeAssistantLines(user));
    setMessage("");
    setError("");
    setTempPassword("");
  }, [user]);

  if (!user) return null;

  const isSelf = currentUser?.id === user.id;
  const isAdminProfile = [ROLES.ADMIN, ROLES.SUPER_ADMIN].includes(user.role);
  const canChangeRole = currentUser?.role === ROLES.SUPER_ADMIN;
  const canUseFace = isSelf && [ROLES.ADMIN, ROLES.SUPER_ADMIN].includes(currentUser?.role);
  const initials = displayName(user).slice(0, 2).toUpperCase();

  const metricCards = [
    { label: "Projects", value: user.assigned_project_count || 0, icon: BriefcaseBusiness, tone: "from-cyan-300 to-blue-500" },
    { label: "Open Tickets", value: user.open_ticket_count || 0, icon: Ticket, tone: "from-violet-300 to-fuchsia-500" },
    { label: "Servers", value: Math.max(1, user.assigned_project_count || 0), icon: Server, tone: "from-emerald-300 to-teal-500" },
    { label: "Deployments", value: (user.assigned_projects || []).filter((project) => project.status === "ACTIVE").length, icon: Rocket, tone: "from-orange-300 to-rose-500" },
    { label: "Storage", value: insights.storageUsage, suffix: "%", icon: HardDrive, tone: "from-sky-300 to-cyan-500" },
    { label: "API Usage", value: insights.apiUsage, suffix: "%", icon: Database, tone: "from-amber-300 to-orange-500" }
  ];

  function syncUpdated(updated) {
    if (!updated) return;
    onReplace?.(updated);
    if (currentUser?.id === updated.id) {
      updateCurrentUser(updated);
      localStorage.setItem("manageaiFaceEmail", updated.email || "");
    }
  }

  function toggleSection(id) {
    setOpenSections((current) => ({ ...current, [id]: !current[id] }));
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
      setMessage("Profile saved with enterprise security validation.");
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
      setMessage("Profile photo uploaded and synced.");
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
      setMessage("Face ID registered. Face Unlock will open automatically on login.");
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

  async function runQuickAction(action) {
    setQuickBusy(action);
    setError("");
    setMessage("");
    setTempPassword("");
    try {
      if (action === "approve") {
        const { data } = await usersApi.approve(user.id);
        syncUpdated(data);
        setMessage("User approved and access state refreshed.");
      }
      if (action === "suspend") {
        const reason = window.prompt("Suspension note", "Suspended from User Command Center.");
        if (reason === null) return;
        const { data } = await usersApi.suspend(user.id, { reason });
        syncUpdated(data);
        setMessage("User suspended.");
      }
      if (action === "reset_password") {
        const nextPassword = makeTemporaryPassword();
        const payload = new FormData();
        payload.append("password", nextPassword);
        const { data } = await usersApi.update(user.id, payload);
        syncUpdated(data);
        setTempPassword(nextPassword);
        setMessage("Temporary password generated and saved.");
      }
      if (action === "generate_secret") {
        const nextSecret = makeSecretId(edit.role || user.role);
        const payload = new FormData();
        payload.append("secret_id", nextSecret);
        const { data } = await usersApi.update(user.id, payload);
        syncUpdated(data);
        setEdit((current) => ({ ...current, secret_id: data.secret_id || nextSecret }));
        setMessage("Secret ID regenerated.");
      }
      if (action === "notify") {
        await notificationsApi.broadcast({
          recipients: [user.id],
          title: "User Command Center update",
          message: "An administrator reviewed your profile and security posture.",
          type: "INFO",
          urgency: "INFO"
        });
        setMessage("Notification sent.");
      }
      if (action === "open_ticket") {
        if (!firstProject?.id) throw new Error("Assign a project before opening a ticket.");
        await ticketsApi.create({
          project: firstProject.id,
          title: `Admin review for ${displayName(user)}`,
          description: `Created from User Command Center for ${user.email}.`,
          priority: "P3",
          assigned_to: [ROLES.ADMIN, ROLES.SUPER_ADMIN, ROLES.DEVELOPER].includes(user.role) ? user.id : undefined
        });
        setMessage("Ticket opened for the selected user's first project.");
      }
      if (action === "deploy") {
        if (!firstProject?.id) throw new Error("Assign a project before deployment.");
        await projectsApi.deployBranch(firstProject.id, {
          branch: "main",
          environment: "production",
          notes: `Deployment triggered from User Command Center for ${displayName(user)}.`
        });
        setMessage("Deployment triggered for the first assigned project.");
      }
    } catch (caught) {
      setError(apiErrorMessage(caught, caught?.message || "Quick action failed."));
    } finally {
      setQuickBusy("");
    }
  }

  async function runAssistant(mode) {
    setAssistantBusy(true);
    const lines = {
      analyze: [`Trust score ${insights.trustScore}% with ${insights.riskLevel.toLowerCase()} risk posture.`, `Primary action: ${insights.suggestion}.`],
      report: [`Executive report generated for ${displayName(user)}.`, `${user.assigned_project_count || 0} projects, ${user.open_ticket_count || 0} open tickets, ${insights.healthScore}% health.`],
      issues: insights.issues,
      recommend: insights.recommendations
    };
    await new Promise((resolve) => window.setTimeout(resolve, 450));
    setAssistantLines(lines[mode] || lines.analyze);
    setAssistantBusy(false);
  }

  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="user-command-shell relative overflow-hidden rounded-[24px] border border-white/10 bg-slate-950/95 p-4 text-slate-100 shadow-2xl sm:p-5">
      <div className="user-command-mesh" aria-hidden="true" />
      <div className="user-command-particles" aria-hidden="true" />

      <div className="relative z-10 grid gap-5">
        <CommandHeader user={user} insights={insights} onQuickAction={runQuickAction} quickBusy={quickBusy} />

        {(message || error || tempPassword) && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} className={`rounded-[18px] border px-4 py-3 text-sm ${error ? "border-rose-300/25 bg-rose-500/10 text-rose-100" : "border-emerald-300/25 bg-emerald-400/10 text-emerald-100"}`}>
            <p>{error || message}</p>
            {tempPassword && <p className="mt-2 font-mono text-xs text-amber-100">Temporary password: {tempPassword}</p>}
          </motion.div>
        )}

        <div className="grid gap-5 xl:grid-cols-[360px_1fr_320px]">
          <ProfileHero user={user} avatarPreview={avatarPreview} avatarBusy={avatarBusy} initials={initials} insights={insights} onUploadAvatar={uploadAvatar} />
          <div className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {metricCards.map((metric, index) => <DashboardMetric key={metric.label} metric={metric} index={index} />)}
            </div>
            <AiInsightPanel insights={insights} />
          </div>
          <AiAssistantPanel lines={assistantLines} busy={assistantBusy} onRun={runAssistant} />
        </div>

        <QuickActionBar onRun={runQuickAction} busy={quickBusy} hasProject={Boolean(firstProject)} status={approvalStatus(user)} />

        <div className="grid gap-5 2xl:grid-cols-[1.1fr_0.9fr]">
          <form onSubmit={submit} className="grid gap-4">
            <FormSection id="personal" title="Personal Information" icon={IdCard} open={openSections.personal} onToggle={toggleSection}>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <Field label="First Name" value={edit.first_name} onChange={(value) => setEdit({ ...edit, first_name: value })} />
                <Field label="Last Name" value={edit.last_name} onChange={(value) => setEdit({ ...edit, last_name: value })} />
                <Field label="Email" type="email" value={edit.email} onChange={(value) => setEdit({ ...edit, email: value })} />
                <Field label="Phone" value={edit.phone} onChange={(value) => setEdit({ ...edit, phone: value })} />
                <Field label="Availability" value={edit.availability_status} onChange={(value) => setEdit({ ...edit, availability_status: value })} />
                <Field label="User / Secret ID" value={edit.secret_id} onChange={(value) => setEdit({ ...edit, secret_id: value })} />
              </div>
            </FormSection>

            <FormSection id="professional" title="Professional Information" icon={BriefcaseBusiness} open={openSections.professional} onToggle={toggleSection}>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <Field label="Login Username" value={edit.username} onChange={(value) => setEdit({ ...edit, username: value })} />
                <Field label="Department" value={edit.department} onChange={(value) => setEdit({ ...edit, department: value })} />
                <Field label="Role Title" value={edit.role_title} onChange={(value) => setEdit({ ...edit, role_title: value })} />
                <div className="md:col-span-2 xl:col-span-3">
                  <Field label="Skills" value={edit.skills} onChange={(value) => setEdit({ ...edit, skills: value })} placeholder="React, Django, Security, DevOps" />
                </div>
                <div className="md:col-span-2 xl:col-span-3">
                  <label className="label text-slate-400">Bio</label>
                  <textarea className="field min-h-24 border-white/10 bg-white/[0.06] text-slate-100" value={edit.bio} onChange={(event) => setEdit({ ...edit, bio: event.target.value })} />
                </div>
              </div>
            </FormSection>

            <FormSection id="access" title="Access Permissions" icon={ShieldCheck} open={openSections.access} onToggle={toggleSection}>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="label text-slate-400">Role</label>
                  <select className="field border-white/10 bg-white/[0.06] text-slate-100" value={edit.role} disabled={!canChangeRole} onChange={(event) => setEdit({ ...edit, role: event.target.value })}>
                    <option value="SUPER_ADMIN">Super Admin</option>
                    <option value="ADMIN">Admin</option>
                    <option value="DEVELOPER">Developer</option>
                    <option value="CLIENT">Client</option>
                  </select>
                </div>
                <PermissionMatrix user={user} canChangeRole={canChangeRole} />
              </div>
            </FormSection>

            <FormSection id="security" title="Security Information" icon={LockKeyhole} open={openSections.security} onToggle={toggleSection}>
              <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="New Password" type="password" value={edit.password} onChange={(value) => setEdit({ ...edit, password: value })} placeholder="Leave blank to keep current" />
                  <Field label="Confirm Password" type="password" value={edit.confirm_password} onChange={(value) => setEdit({ ...edit, confirm_password: value })} placeholder="Repeat new password" />
                  <div className="sm:col-span-2 rounded-[18px] border border-white/10 bg-black/20 p-3 text-xs text-slate-400">
                    <LockKeyhole className="mb-2 text-amber-200" size={16} />
                    Password validation uses backend policy and audited role permissions.
                  </div>
                </div>
                <div className="rounded-[20px] border border-white/10 bg-white/[0.045] p-3">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">Face ID Registration</p>
                      <p className="mt-1 text-xs text-slate-400">{user.face_login_enabled ? "Registered and enabled" : user.face_enrolled_at ? "Registered, currently disabled" : "Optional biometric login"}</p>
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
                    <p className="rounded-[18px] border border-white/10 bg-black/20 p-4 text-sm text-slate-400">Face ID enrollment is available from your own Admin or Super Admin profile.</p>
                  )}
                </div>
              </div>
            </FormSection>

            <div className="flex flex-wrap justify-end gap-2">
              <Button type="submit" disabled={busy}><Save size={16} />{busy ? "Saving..." : "Save Command Profile"}</Button>
            </div>
          </form>

          <div className="grid gap-5">
            <ActivityTimeline timeline={timeline} />
            <AssignmentPanel title="Assigned Projects" empty="No assigned projects.">
              {(user.assigned_projects || []).map((project) => (
                <motion.div whileHover={{ y: -2 }} key={project.id} className="rounded-[18px] border border-white/10 bg-white/[0.045] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-white">{project.name}</p>
                    <Badge value={project.status} />
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-white/[0.08]">
                    <div className="h-2 rounded-full bg-gradient-to-r from-cyan-300 to-violet-400" style={{ width: `${project.progress || 0}%` }} />
                  </div>
                </motion.div>
              ))}
            </AssignmentPanel>
            <AssignmentPanel title="Assigned Work" empty="No open tasks.">
              {(user.assigned_tasks || []).map((task) => (
                <motion.div whileHover={{ y: -2 }} key={task.id} className="rounded-[18px] border border-white/10 bg-white/[0.045] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-white">{task.title}</p>
                    <Badge value={task.status} />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{task.project_name} - Day {task.workflow_day}</p>
                </motion.div>
              ))}
            </AssignmentPanel>
          </div>
        </div>
      </div>
    </motion.div>
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

function CommandHeader({ user, insights, onQuickAction, quickBusy }) {
  return (
    <motion.header initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="relative overflow-hidden rounded-[24px] border border-white/10 bg-white/[0.06] p-[1px] shadow-[0_24px_90px_rgba(34,211,238,0.12)]">
      <div className="user-command-gradient-border" aria-hidden="true" />
      <div className="relative rounded-[23px] bg-slate-950/80 p-4 backdrop-blur-2xl sm:p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1 text-xs font-semibold text-emerald-100">
                <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-300" />
                Live
              </span>
              <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs font-semibold text-cyan-100">AI Trust {insights.trustScore}%</span>
              <span className="rounded-full border border-violet-300/20 bg-violet-300/10 px-3 py-1 text-xs font-semibold text-violet-100">Health {insights.healthScore}%</span>
            </div>
            <h2 className="mt-4 text-3xl font-black tracking-tight text-white sm:text-4xl">User Command Center</h2>
            <p className="mt-2 text-sm text-slate-400">
              {displayName(user)} - last active {formatDateTime(user.last_seen_at || user.last_login || user.date_joined)}
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 xl:w-[460px]">
            <HeaderStat icon={Activity} label="Activity" value={`${insights.activityScore}%`} />
            <HeaderStat icon={ShieldCheck} label="Rank" value={insights.rank} />
            <HeaderStat icon={ClockLabel} label="Login" value={formatDateShort(user.last_login)} />
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <CommandButton icon={UserCheck} label="Approve" loading={quickBusy === "approve"} onClick={() => onQuickAction("approve")} tone="emerald" />
          <CommandButton icon={PauseCircle} label="Suspend" loading={quickBusy === "suspend"} onClick={() => onQuickAction("suspend")} tone="rose" />
          <CommandButton icon={RefreshCcw} label="Reset Password" loading={quickBusy === "reset_password"} onClick={() => onQuickAction("reset_password")} />
          <CommandButton icon={Bell} label="Notify" loading={quickBusy === "notify"} onClick={() => onQuickAction("notify")} />
        </div>
      </div>
    </motion.header>
  );
}

function ClockLabel(props) {
  return <CalendarDays {...props} />;
}

function HeaderStat({ icon: Icon, label, value }) {
  return (
    <div className="rounded-[18px] border border-white/10 bg-white/[0.045] p-3">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.14em] text-slate-500">
        <Icon size={14} className="text-cyan-200" />
        {label}
      </div>
      <p className="mt-2 truncate text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

function ProfileHero({ user, avatarPreview, avatarBusy, initials, insights, onUploadAvatar }) {
  return (
    <motion.section whileHover={{ scale: 1.02, y: -4 }} transition={{ type: "spring", stiffness: 230, damping: 18 }} className="relative overflow-hidden rounded-[24px] border border-white/10 bg-white/[0.06] p-5 shadow-[0_24px_80px_rgba(14,165,233,0.12)] backdrop-blur-2xl">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300 to-transparent" />
      <div className="mx-auto grid h-36 w-36 place-items-center rounded-[24px] border border-cyan-300/25 bg-cyan-300/10 p-2 shadow-[0_0_55px_rgba(34,211,238,0.22)]">
        <div className="relative grid h-full w-full place-items-center overflow-hidden rounded-[20px] bg-slate-950 text-4xl font-black text-white">
          <span className="absolute inset-0 animate-pulse rounded-[20px] ring-2 ring-emerald-300/35" />
          {avatarPreview ? <img src={avatarPreview} alt={displayName(user)} className="h-full w-full object-cover" /> : initials}
        </div>
      </div>
      <label className={`mt-5 flex cursor-pointer items-center justify-center gap-2 rounded-[18px] border border-white/10 bg-white/10 px-3 py-2 text-sm font-semibold text-slate-100 transition hover:bg-white/15 focus-within:ring-2 focus-within:ring-cyan-300/40 ${avatarBusy ? "pointer-events-none opacity-60" : ""}`}>
        {avatarBusy ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/60 border-t-transparent" /> : <UploadCloud size={16} />}
        {avatarBusy ? "Uploading..." : "Upload photo"}
        <input className="hidden" type="file" accept="image/*" onChange={onUploadAvatar} />
      </label>
      <div className="mt-5 text-center">
        <h3 className="text-2xl font-black text-white">{displayName(user)}</h3>
        <p className="mt-1 text-sm text-slate-400">{user.email}</p>
      </div>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        <Badge value={user.role} />
        <Badge value={approvalStatus(user)} />
        <Badge value={user.face_login_enabled ? "Verified" : "Face Optional"} />
      </div>
      <div className="mt-5 grid grid-cols-2 gap-3">
        <MiniProfileStat label="Activity" value={`${insights.activityScore}%`} />
        <MiniProfileStat label="Rank" value={insights.rank} />
        <MiniProfileStat label="Joined" value={formatDateShort(user.date_joined)} />
        <MiniProfileStat label="Last Login" value={formatDateShort(user.last_login)} />
      </div>
      <div className="mt-4 rounded-[18px] border border-white/10 bg-black/20 p-3 text-center">
        <p className="text-xs uppercase tracking-[0.14em] text-slate-500">User ID</p>
        <p className="mt-1 break-all font-mono text-sm text-cyan-100">{user.secret_id}</p>
      </div>
    </motion.section>
  );
}

function MiniProfileStat({ label, value }) {
  return (
    <div className="rounded-[18px] border border-white/10 bg-white/[0.045] p-3">
      <p className="text-[11px] uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="mt-2 truncate text-sm font-semibold text-white">{value || "--"}</p>
    </div>
  );
}

function DashboardMetric({ metric, index }) {
  const Icon = metric.icon;
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.04 }} whileHover={{ y: -5, scale: 1.015 }} className="group rounded-[22px] border border-white/10 bg-white/[0.055] p-4 shadow-[0_18px_55px_rgba(0,0,0,0.18)] backdrop-blur-2xl transition hover:border-cyan-300/30 hover:shadow-[0_20px_70px_rgba(34,211,238,0.14)]">
      <div className={`grid h-11 w-11 place-items-center rounded-[18px] bg-gradient-to-br ${metric.tone} text-white shadow-lg`}>
        <Icon size={20} />
      </div>
      <p className="mt-4 text-xs uppercase tracking-[0.14em] text-slate-500">{metric.label}</p>
      <p className="mt-2 text-3xl font-black text-white"><AnimatedCounter value={metric.value} suffix={metric.suffix || ""} /></p>
    </motion.div>
  );
}

function AnimatedCounter({ value, suffix = "" }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let frame = 0;
    const total = 22;
    const start = display;
    const end = Number(value) || 0;
    const timer = window.setInterval(() => {
      frame += 1;
      const progress = Math.min(1, frame / total);
      setDisplay(Math.round(start + (end - start) * progress));
      if (progress >= 1) window.clearInterval(timer);
    }, 18);
    return () => window.clearInterval(timer);
  }, [value]);
  return <>{display}{suffix}</>;
}

function AiInsightPanel({ insights }) {
  return (
    <section className="rounded-[24px] border border-white/10 bg-white/[0.055] p-5 shadow-[0_20px_80px_rgba(168,85,247,0.10)] backdrop-blur-2xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-[18px] bg-violet-300/15 text-violet-100"><Bot size={21} /></div>
          <div>
            <h3 className="text-sm font-semibold text-white">AI Insight Panel</h3>
            <p className="mt-1 text-xs text-slate-500">Risk, workload, login, and system recommendations.</p>
          </div>
        </div>
        <Badge value={insights.riskLevel} />
      </div>
      <div className="mt-5 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="grid gap-3">
          <InsightRow label="Project Performance" value={insights.projectPerformance} />
          <InsightRow label="Ticket Activity" value={insights.ticketActivity} />
          <InsightRow label="Storage Usage" value={`${insights.storageUsage}%`} />
          <InsightRow label="Login Pattern" value={insights.loginPattern} />
        </div>
        <div className="rounded-[20px] border border-white/10 bg-black/20 p-4">
          <Sparkline values={insights.chart} />
          <p className="mt-4 text-sm font-semibold text-white">AI Suggestion</p>
          <p className="mt-2 text-sm leading-6 text-slate-400">{insights.suggestion}</p>
        </div>
      </div>
    </section>
  );
}

function InsightRow({ label, value }) {
  return (
    <div className="rounded-[18px] border border-white/10 bg-white/[0.04] p-3">
      <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

function Sparkline({ values }) {
  const max = Math.max(...values, 1);
  const points = values.map((value, index) => {
    const x = (index / Math.max(values.length - 1, 1)) * 100;
    const y = 44 - (value / max) * 36;
    return `${index === 0 ? "M" : "L"}${x},${y}`;
  }).join(" ");
  return (
    <svg viewBox="0 0 100 48" className="h-24 w-full overflow-visible" role="img" aria-label="AI activity chart">
      <path d={points} fill="none" stroke="url(#aiChartGradient)" strokeWidth="3" strokeLinecap="round" />
      <defs>
        <linearGradient id="aiChartGradient" x1="0" x2="1">
          <stop offset="0%" stopColor="#67e8f9" />
          <stop offset="100%" stopColor="#c084fc" />
        </linearGradient>
      </defs>
    </svg>
  );
}

function QuickActionBar({ onRun, busy, hasProject, status }) {
  const actions = [
    ["approve", "Approve User", UserCheck, "emerald", false],
    ["suspend", "Suspend User", PauseCircle, "rose", false],
    ["reset_password", "Reset Password", KeyRound, "cyan", false],
    ["generate_secret", "Generate Secret ID", RefreshCcw, "violet", false],
    ["notify", "Send Notification", Bell, "cyan", false],
    ["open_ticket", "Open Ticket", MessageSquarePlus, "amber", !hasProject],
    ["deploy", "Deploy Project", Rocket, "emerald", !hasProject]
  ];
  return (
    <div className="rounded-[24px] border border-white/10 bg-white/[0.055] p-3 backdrop-blur-2xl" aria-label="Quick action bar">
      <div className="mb-3 flex items-center justify-between gap-3 px-1">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Quick Actions</p>
        <Badge value={status} />
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 2xl:grid-cols-7">
        {actions.map(([id, label, Icon, tone, disabled]) => (
          <CommandButton key={id} icon={Icon} label={label} tone={tone} disabled={disabled} loading={busy === id} onClick={() => onRun(id)} />
        ))}
      </div>
    </div>
  );
}

function CommandButton({ icon: Icon, label, onClick, tone = "cyan", loading = false, disabled = false }) {
  const tones = {
    cyan: "from-cyan-400/90 to-blue-500/90 hover:shadow-cyan-400/20",
    emerald: "from-emerald-400/90 to-teal-500/90 hover:shadow-emerald-400/20",
    rose: "from-rose-500/90 to-fuchsia-500/90 hover:shadow-rose-400/20",
    violet: "from-violet-400/90 to-fuchsia-500/90 hover:shadow-violet-400/20",
    amber: "from-amber-300/90 to-orange-500/90 hover:shadow-amber-400/20"
  };
  return (
    <motion.button whileTap={{ scale: disabled ? 1 : 0.96 }} whileHover={disabled ? undefined : { y: -2 }} type="button" onClick={onClick} disabled={disabled || loading} className={`relative inline-flex min-h-11 items-center justify-center gap-2 overflow-hidden rounded-[18px] bg-gradient-to-r px-3 py-2 text-sm font-bold text-white shadow-lg transition focus:outline-none focus:ring-2 focus:ring-cyan-300/40 disabled:cursor-not-allowed disabled:opacity-45 ${tones[tone] || tones.cyan}`} aria-label={label}>
      <span className="absolute inset-0 translate-x-[-130%] bg-white/20 transition group-hover:translate-x-[130%]" />
      {loading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/70 border-t-transparent" /> : <Icon size={16} />}
      <span className="truncate">{label}</span>
    </motion.button>
  );
}

function FormSection({ id, title, icon: Icon, open, onToggle, children }) {
  return (
    <section className="rounded-[24px] border border-white/10 bg-white/[0.055] backdrop-blur-2xl">
      <button type="button" onClick={() => onToggle(id)} className="flex w-full items-center justify-between gap-3 p-4 text-left focus:outline-none focus:ring-2 focus:ring-cyan-300/40" aria-expanded={open}>
        <span className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-[16px] bg-cyan-300/10 text-cyan-100"><Icon size={18} /></span>
          <span>
            <span className="block text-sm font-semibold text-white">{title}</span>
            <span className="text-xs text-slate-500">Enterprise profile controls</span>
          </span>
        </span>
        <motion.span animate={{ rotate: open ? 180 : 0 }}><ChevronDown size={18} className="text-slate-400" /></motion.span>
      </button>
      <motion.div initial={false} animate={{ height: open ? "auto" : 0, opacity: open ? 1 : 0 }} className="overflow-hidden">
        <div className="border-t border-white/10 p-4">{children}</div>
      </motion.div>
    </section>
  );
}

function PermissionMatrix({ user, canChangeRole }) {
  const permissions = [
    ["RBAC", ["SUPER_ADMIN", "ADMIN"].includes(user.role)],
    ["Deploy", ["SUPER_ADMIN", "ADMIN", "DEVELOPER"].includes(user.role)],
    ["Tickets", true],
    ["Secrets", canChangeRole]
  ];
  return (
    <div className="rounded-[18px] border border-white/10 bg-black/20 p-3">
      <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Access Map</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        {permissions.map(([label, enabled]) => (
          <span key={label} className={`rounded-[14px] border px-3 py-2 text-xs font-semibold ${enabled ? "border-emerald-300/20 bg-emerald-300/10 text-emerald-100" : "border-white/10 bg-white/[0.035] text-slate-500"}`}>{label}</span>
        ))}
      </div>
    </div>
  );
}

function ActivityTimeline({ timeline }) {
  return (
    <section className="rounded-[24px] border border-white/10 bg-white/[0.055] p-5 backdrop-blur-2xl">
      <div className="flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-[16px] bg-cyan-300/10 text-cyan-100"><Activity size={18} /></div>
        <div>
          <h3 className="text-sm font-semibold text-white">Activity Timeline</h3>
          <p className="mt-1 text-xs text-slate-500">Lifecycle and operational events.</p>
        </div>
      </div>
      <div className="mt-5 space-y-4">
        {timeline.map((item, index) => (
          <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.05 }} key={item.title} className="relative pl-8">
            <span className="absolute left-2 top-1 h-full w-px bg-gradient-to-b from-cyan-300/70 to-transparent" />
            <span className="absolute left-0 top-1 grid h-4 w-4 place-items-center rounded-full border border-cyan-300/35 bg-slate-950">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-300" />
            </span>
            <p className="text-sm font-semibold text-white">{item.title}</p>
            <p className="mt-1 text-xs text-slate-500">{item.detail}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

function AiAssistantPanel({ lines, busy, onRun }) {
  return (
    <aside className="rounded-[24px] border border-white/10 bg-white/[0.055] p-5 shadow-[0_22px_75px_rgba(168,85,247,0.12)] backdrop-blur-2xl">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-[18px] bg-violet-300/15 text-violet-100"><Bot size={21} /></div>
          <div>
            <h3 className="text-sm font-semibold text-white">AI Assistant</h3>
            <p className="mt-1 text-xs text-slate-500">Analyze, report, and recommend actions.</p>
          </div>
        </div>
        <button type="button" className="grid h-9 w-9 place-items-center rounded-[14px] border border-white/10 bg-white/[0.05] text-slate-300 transition hover:text-white focus:outline-none focus:ring-2 focus:ring-cyan-300/40" aria-label="Voice command">
          <Mic size={16} />
        </button>
      </div>
      <div className="mt-5 min-h-36 rounded-[20px] border border-white/10 bg-black/25 p-4">
        {busy ? (
          <div className="flex items-center gap-2 text-sm text-cyan-100"><span className="h-2 w-2 animate-pulse rounded-full bg-cyan-300" />AI is thinking...</div>
        ) : (
          <div className="space-y-3">
            {lines.map((line, index) => <p key={`${line}-${index}`} className="text-sm leading-6 text-slate-300"><span className="text-cyan-200">AI:</span> {line}</p>)}
          </div>
        )}
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
        <AssistantButton label="Analyze User" onClick={() => onRun("analyze")} />
        <AssistantButton label="Generate Report" onClick={() => onRun("report")} />
        <AssistantButton label="Find Issues" onClick={() => onRun("issues")} />
        <AssistantButton label="Recommend Actions" onClick={() => onRun("recommend")} />
      </div>
    </aside>
  );
}

function AssistantButton({ label, onClick }) {
  return (
    <button type="button" onClick={onClick} className="inline-flex items-center justify-between gap-3 rounded-[16px] border border-white/10 bg-white/[0.045] px-3 py-2 text-sm font-semibold text-slate-200 transition hover:border-cyan-300/30 hover:bg-white/[0.08] focus:outline-none focus:ring-2 focus:ring-cyan-300/40">
      {label}
      <Send size={14} />
    </button>
  );
}

function Field({ label, value, onChange, type = "text", placeholder = "" }) {
  return (
    <div>
      <label className="label text-slate-400">{label}</label>
      <input className="field border-white/10 bg-white/[0.06] text-slate-100 placeholder:text-slate-500 focus:border-cyan-300/50" type={type} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}

function AssignmentPanel({ title, empty, children }) {
  const hasItems = Array.isArray(children) ? children.length > 0 : Boolean(children);
  return (
    <section className="rounded-[24px] border border-white/10 bg-white/[0.055] p-5 backdrop-blur-2xl">
      <p className="label text-slate-400">{title}</p>
      <div className="mt-3 space-y-2">
        {children}
        {!hasItems && <p className="rounded-[18px] border border-white/10 bg-white/[0.035] p-4 text-sm text-slate-500">{empty}</p>}
      </div>
    </section>
  );
}

function buildUserInsights(user) {
  const projects = user?.assigned_project_count || 0;
  const tasks = user?.assigned_task_count || 0;
  const tickets = user?.open_ticket_count || 0;
  const face = user?.face_login_enabled ? 10 : 0;
  const approved = approvalStatus(user) === "APPROVED" ? 18 : 0;
  const trustScore = clamp(62 + face + approved + Math.min(projects * 3, 10) - tickets * 4);
  const healthScore = clamp(82 - tasks * 4 - tickets * 6 + approved);
  const activityScore = clamp(48 + projects * 11 + tasks * 5 + (user?.last_login ? 12 : 0));
  const riskLevel = trustScore > 82 ? "Low Risk" : trustScore > 65 ? "Moderate Risk" : "High Risk";
  const storageUsage = clamp(18 + projects * 9 + tasks * 3);
  const apiUsage = clamp(12 + projects * 14 + tickets * 5);
  const suggestion = !user?.face_login_enabled
    ? "Register Face ID to improve security posture and reduce password-only access risk."
    : tickets > 2
      ? "Review ticket backlog and rebalance workload before approving new assignments."
      : "Profile is stable. Keep audit monitoring and deployment access unchanged.";
  return {
    trustScore,
    healthScore,
    activityScore,
    riskLevel,
    storageUsage,
    apiUsage,
    projectPerformance: projects ? `${Math.min(100, 70 + projects * 6)}% productive` : "No active project signal",
    ticketActivity: tickets ? `${tickets} open tickets` : "No active ticket load",
    loginPattern: user?.last_login ? "Recent authenticated session" : "No recent login",
    rank: trustScore > 88 ? "Apex" : trustScore > 74 ? "Prime" : "Watch",
    suggestion,
    issues: [
      user?.face_login_enabled ? "No biometric enrollment issue detected." : "Face ID is not enabled for this account.",
      tickets ? "Open ticket load should be reviewed." : "No open ticket pressure detected.",
      approvalStatus(user) === "APPROVED" ? "Approval state is healthy." : "Approval state requires attention."
    ],
    recommendations: [
      suggestion,
      projects ? "Keep assigned project access under least privilege review." : "Assign a project before deployment actions.",
      "Schedule periodic credential and Secret ID rotation."
    ],
    chart: [trustScore - 18, healthScore - 8, activityScore - 16, trustScore, healthScore, activityScore].map(clamp)
  };
}

function buildTimeline(user) {
  return [
    { title: "User Created", detail: formatDateTime(user?.date_joined) },
    { title: "Projects Added", detail: `${user?.assigned_project_count || 0} active assignments` },
    { title: "Tickets Raised", detail: `${user?.open_ticket_count || 0} open tickets` },
    { title: "Deployments", detail: `${(user?.assigned_projects || []).filter((project) => project.status === "ACTIVE").length} active project routes` },
    { title: "Login Events", detail: user?.last_login ? formatDateTime(user.last_login) : "No recent login event" }
  ];
}

function makeAssistantLines(user) {
  const insights = buildUserInsights(user);
  return [
    `${displayName(user)} is currently ${approvalStatus(user).toLowerCase()} with ${insights.riskLevel.toLowerCase()}.`,
    insights.suggestion
  ];
}

function makeTemporaryPassword() {
  return `Temp@${Math.random().toString(36).slice(2, 8).toUpperCase()}${Math.floor(1000 + Math.random() * 9000)}`;
}

function makeSecretId(role = "") {
  const prefix = role === ROLES.DEVELOPER ? "DEV" : "USR";
  return `${prefix}-${Math.random().toString(16).slice(2, 10).toUpperCase()}`;
}

function clamp(value) {
  return Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
}

function formatDateTime(value) {
  if (!value) return "Not recorded";
  return new Date(value).toLocaleString();
}

function formatDateShort(value) {
  if (!value) return "--";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
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
