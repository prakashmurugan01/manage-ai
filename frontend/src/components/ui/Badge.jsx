const tones = {
  ACTIVE: "bg-emerald-400/12 text-emerald-200 ring-emerald-300/20",
  HEALTHY: "bg-emerald-400/12 text-emerald-200 ring-emerald-300/20",
  DONE: "bg-emerald-400/12 text-emerald-200 ring-emerald-300/20",
  APPROVED: "bg-emerald-400/12 text-emerald-200 ring-emerald-300/20",
  SUCCESS: "bg-emerald-400/12 text-emerald-200 ring-emerald-300/20",
  HIGH: "bg-amber-400/12 text-amber-200 ring-amber-300/20",
  PENDING: "bg-amber-400/12 text-amber-200 ring-amber-300/20",
  IN_REVIEW: "bg-amber-400/12 text-amber-200 ring-amber-300/20",
  WARNING: "bg-amber-400/12 text-amber-200 ring-amber-300/20",
  CRITICAL: "bg-rose-400/12 text-rose-200 ring-rose-300/20",
  BLOCKED: "bg-rose-400/12 text-rose-200 ring-rose-300/20",
  DISAPPROVED: "bg-rose-400/12 text-rose-200 ring-rose-300/20",
  CORRECTION_REQUESTED: "bg-rose-400/12 text-rose-200 ring-rose-300/20",
  REJECTED: "bg-rose-400/12 text-rose-200 ring-rose-300/20",
  IN_PROGRESS: "bg-cyan-400/12 text-cyan-200 ring-cyan-300/20",
  DRAFT: "bg-cyan-400/12 text-cyan-200 ring-cyan-300/20",
  REVIEW: "bg-violet-400/12 text-violet-200 ring-violet-300/20",
  PAUSED: "bg-slate-400/12 text-slate-200 ring-slate-300/20",
  SUSPENDED: "bg-slate-400/12 text-slate-200 ring-slate-300/20"
};

export default function Badge({ value }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ring-1 ${tones[value] || "bg-white/10 text-slate-200 ring-white/10"}`}>
      {String(value || "None").replaceAll("_", " ")}
    </span>
  );
}
