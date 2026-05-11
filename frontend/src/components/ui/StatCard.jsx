export default function StatCard({ icon: Icon, label, value, accent = "text-teal-200" }) {
  return (
    <div className="panel p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.14em] text-slate-400">{label}</p>
          <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
        </div>
        {Icon && (
          <div className={`rounded-lg bg-white/10 p-2 ${accent}`}>
            <Icon size={20} />
          </div>
        )}
      </div>
    </div>
  );
}
