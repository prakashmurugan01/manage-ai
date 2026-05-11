export default function StatusBars({ title, data = {} }) {
  const entries = Object.entries(data);
  const total = Math.max(entries.reduce((sum, [, value]) => sum + Number(value), 0), 1);

  return (
    <div className="panel p-4">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-4 space-y-3">
        {entries.map(([label, value]) => (
          <div key={label}>
            <div className="mb-1 flex items-center justify-between text-xs text-slate-400">
              <span>{label.replaceAll("_", " ")}</span>
              <span>{value}</span>
            </div>
            <div className="h-2 rounded-full bg-white/8">
              <div className="h-2 rounded-full bg-gradient-to-r from-teal-300 via-cyan-300 to-amber-300" style={{ width: `${(Number(value) / total) * 100}%` }} />
            </div>
          </div>
        ))}
        {!entries.length && <p className="text-sm text-slate-500">No data yet.</p>}
      </div>
    </div>
  );
}
