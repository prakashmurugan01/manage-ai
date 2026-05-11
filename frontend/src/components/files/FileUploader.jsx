import { AlertTriangle, FileArchive, ShieldCheck, UploadCloud } from "lucide-react";
import { useEffect, useState } from "react";

import { documentsApi } from "../../api/services.js";
import { useAuth } from "../../context/AuthContext.jsx";
import { ROLES } from "../../utils/rbac.js";
import Button from "../ui/Button.jsx";

const MAX_UPLOAD_BYTES = 5 * 1024 * 1024 * 1024;

export default function FileUploader({ projects = [], defaultProject = "", lockedProject = false, defaultVisibility = "CLIENT", onUploaded }) {
  const { user } = useAuth();
  const [form, setForm] = useState({ title: "", project: defaultProject || "", visibility: defaultVisibility, category: "General", file: null });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setForm((current) => ({ ...current, project: defaultProject || current.project, visibility: defaultVisibility }));
  }, [defaultProject, defaultVisibility]);

  const selectedProject = projects.find((project) => String(project.id) === String(form.project));
  const isDeveloperUpload = user?.role === ROLES.DEVELOPER;
  const developerBlocked = isDeveloperUpload && selectedProject && selectedProject.approval_status !== "APPROVED";
  const selectedFileSize = form.file?.size || 0;

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (selectedFileSize > MAX_UPLOAD_BYTES) {
      setError("Project ZIP uploads are limited to 5GB.");
      return;
    }
    if (developerBlocked) {
      setError("Admin approval is required before this project can receive developer uploads.");
      return;
    }
    setBusy(true);
    try {
      const formData = new FormData();
      Object.entries(form).forEach(([key, value]) => value !== null && formData.append(key, value));
      const { data } = await documentsApi.upload(formData);
      onUploaded?.(data);
      setForm({ title: "", project: defaultProject || "", visibility: defaultVisibility, category: "General", file: null });
      event.currentTarget.reset();
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="panel overflow-hidden">
      <div className="border-b border-white/10 bg-white/[0.035] p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <FileArchive size={17} className="text-teal-200" />
              Server File Upload
            </div>
            <p className="mt-1 text-xs text-slate-500">ZIP packages and project documents are stored by project, reviewed by Admin, and limited to 5GB per upload.</p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-lg border border-emerald-300/20 bg-emerald-300/10 px-3 py-2 text-xs text-emerald-100">
            <ShieldCheck size={14} />
            {isDeveloperUpload ? "Developer uploads require approved project access" : "Admin upload gate active"}
          </div>
        </div>
      </div>
      <div className="grid gap-3 p-4 md:grid-cols-5">
        <div>
          <label className="label">Title</label>
          <input className="field" required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
        </div>
        <div>
          <label className="label">Project</label>
          <select className="field" disabled={lockedProject} required value={form.project} onChange={(event) => setForm({ ...form, project: event.target.value })}>
            <option value="">Select</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}{isDeveloperUpload && project.approval_status !== "APPROVED" ? " (approval required)" : ""}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Visibility</label>
          <select className="field" value={form.visibility} onChange={(event) => setForm({ ...form, visibility: event.target.value })}>
            <option value="INTERNAL">Internal</option>
            <option value="CLIENT">Client</option>
            <option value="PUBLIC">Public</option>
          </select>
        </div>
        <div>
          <label className="label">File</label>
          <input className="field" required type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.png,.jpg,.jpeg,.webp,.zip" onChange={(event) => setForm({ ...form, file: event.target.files?.[0] || null })} />
        </div>
        <div className="flex items-end">
          <Button type="submit" disabled={busy || developerBlocked} className="w-full">
            <UploadCloud size={16} />
            Upload
          </Button>
        </div>
      </div>
      {(error || developerBlocked) && (
        <div className="mx-4 mb-4 flex items-center gap-2 rounded-lg border border-amber-300/20 bg-amber-300/10 px-3 py-2 text-sm text-amber-100">
          <AlertTriangle size={16} />
          {error || "Admin approval is required before this project can receive developer uploads."}
        </div>
      )}
    </form>
  );
}
