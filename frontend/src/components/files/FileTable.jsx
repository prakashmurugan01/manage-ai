import { AnimatePresence, motion } from "framer-motion";
import { Download, Eye, FileText, Trash2, X } from "lucide-react";
import { useState } from "react";

import { documentsApi } from "../../api/services.js";
import { bytes, dateShort } from "../../utils/format.js";
import Badge from "../ui/Badge.jsx";
import Button from "../ui/Button.jsx";

function canInline(file) {
  return ["pdf", "txt", "png", "jpg", "jpeg", "webp", "gif"].includes(String(file.extension || "").toLowerCase());
}

function FileViewer({ file, onClose, onReview }) {
  const [previewObjectUrl, setPreviewObjectUrl] = useState("");
  const [previewError, setPreviewError] = useState("");
  if (!file) return null;

  async function loadPreview() {
    setPreviewError("");
    try {
      const { data } = await documentsApi.preview(file.id);
      const url = URL.createObjectURL(data);
      setPreviewObjectUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return url;
      });
    } catch {
      setPreviewError("Preview needs an approved file and an active login session.");
    }
  }

  async function downloadFile() {
    const { data } = await documentsApi.download(file.id);
    const url = URL.createObjectURL(data);
    const link = document.createElement("a");
    link.href = url;
    link.download = file.file?.split("/").pop() || file.title || "download";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 bg-black/75 p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <motion.div
          className="mx-auto grid h-full max-w-7xl overflow-hidden rounded-lg border border-white/10 bg-[color:var(--app-bg)] shadow-2xl lg:grid-cols-[260px_1fr]"
          initial={{ opacity: 0, scale: 0.96, y: 18 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.98, y: 12 }}
          transition={{ duration: 0.22 }}
        >
          <aside className="border-b border-white/10 bg-white/[0.035] p-4 lg:border-b-0 lg:border-r">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Project File</p>
                <h2 className="mt-2 text-base font-semibold text-white">{file.title}</h2>
              </div>
              <Button variant="ghost" onClick={onClose} aria-label="Close"><X size={16} /></Button>
            </div>
            <div className="mt-4 grid gap-2 text-sm text-slate-400">
              <span>{file.project_name}</span>
              <span>{bytes(file.file_size)}</span>
              <span>{dateShort(file.updated_at)}</span>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge value={file.visibility} />
              <Badge value={file.review_status} />
            </div>
            <button type="button" onClick={downloadFile} className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-[color:var(--accent)] px-3 py-2 text-sm font-medium text-white hover:brightness-110">
              <Download size={16} />
              Download
            </button>
            {onReview && (
              <div className="mt-4 grid gap-2">
                <Button variant="secondary" onClick={() => onReview(file.id, { review_status: "APPROVED", review_note: "Approved" })}>Approve</Button>
                <Button variant="ghost" onClick={() => onReview(file.id, { review_status: "CORRECTION_REQUESTED", review_note: "Correction requested" })}>Request Correction</Button>
                <Button variant="danger" onClick={() => onReview(file.id, { review_status: "REJECTED", review_note: "Rejected" })}>Reject</Button>
              </div>
            )}
          </aside>
          <main className="min-h-0 bg-white/[0.02] p-4">
            {canInline(file) ? (
              previewObjectUrl ? (
                <iframe title={file.title} src={previewObjectUrl} className="h-full min-h-[68vh] w-full rounded-lg border border-white/10 bg-white" />
              ) : (
                <div className="grid h-full min-h-[68vh] place-items-center rounded-lg border border-white/10 bg-white/[0.035] p-8 text-center">
                  <div>
                    <FileText size={42} className="mx-auto text-teal-200" />
                    <p className="mt-4 text-base font-semibold text-white">Authenticated preview is ready</p>
                    <p className="mt-2 text-sm text-slate-400">{previewError || "Load the file through the app so your secure bearer token is included."}</p>
                    <Button className="mt-4" onClick={loadPreview}><Eye size={16} />Load Preview</Button>
                  </div>
                </div>
              )
            ) : (
              <div className="grid h-full min-h-[68vh] place-items-center rounded-lg border border-white/10 bg-white/[0.035] p-8 text-center">
                <div>
                  <FileText size={42} className="mx-auto text-teal-200" />
                  <p className="mt-4 text-base font-semibold text-white">Preview is not available for this file type.</p>
                  <p className="mt-2 text-sm text-slate-400">Use the download action on the left to review it locally.</p>
                </div>
              </div>
            )}
          </main>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

export default function FileTable({ files = [], onDelete, onReview }) {
  const [selected, setSelected] = useState(null);

  async function review(id, payload) {
    await onReview?.(id, payload);
    setSelected((current) => current && current.id === id ? { ...current, ...payload } : current);
  }

  return (
    <>
      <div className="panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-white/10 bg-white/[0.035] text-xs uppercase tracking-[0.14em] text-slate-400">
              <tr>
                <th className="px-4 py-3">Document</th>
                <th className="px-4 py-3">Project</th>
                <th className="px-4 py-3">Visibility</th>
                <th className="px-4 py-3">Review</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Updated</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {files.map((file) => (
                <tr key={file.id} className="text-slate-300">
                  <td className="px-4 py-3">
                    <p className="font-medium text-white">{file.title}</p>
                    <p className="text-xs text-slate-500">{file.uploaded_by_detail?.full_name || file.uploaded_by_detail?.email || "System"}</p>
                  </td>
                  <td className="px-4 py-3">{file.project_name}</td>
                  <td className="px-4 py-3"><Badge value={file.visibility} /></td>
                  <td className="px-4 py-3"><Badge value={file.review_status} /></td>
                  <td className="px-4 py-3">{bytes(file.file_size)}</td>
                  <td className="px-4 py-3">{dateShort(file.updated_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <Button variant="secondary" onClick={() => setSelected(file)} aria-label="View">
                        <Eye size={16} />
                      </Button>
                      {onDelete && (
                        <Button variant="ghost" onClick={() => onDelete(file.id)} aria-label="Delete">
                          <Trash2 size={16} />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!files.length && <p className="p-6 text-sm text-slate-500">No files found.</p>}
        </div>
      </div>
      <FileViewer file={selected} onClose={() => setSelected(null)} onReview={onReview ? review : null} />
    </>
  );
}
