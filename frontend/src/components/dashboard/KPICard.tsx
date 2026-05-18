import { motion } from "framer-motion";

export default function KPICard({ icon: Icon, label, value, trend, color }) {
  const isPositive = trend?.startsWith("+");

  return (
    <motion.div
      whileHover={{ y: -8, scale: 1.02 }}
      className="group relative"
    >
      {/* Gradient border on hover */}
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-r opacity-0 group-hover:opacity-100 transition duration-500 p-[1px]"
        style={{
          backgroundImage: `linear-gradient(135deg, rgb(168, 85, 247), rgb(59, 130, 246))`
        }}
      />

      {/* Card content */}
      <div className="relative rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6 transition-all duration-300 group-hover:bg-white/10">
        {/* Background gradient accent */}
        <div className={`absolute top-0 right-0 w-32 h-32 rounded-full blur-3xl opacity-0 group-hover:opacity-20 transition duration-500 -z-10 bg-gradient-to-r ${color}`} />

        {/* Icon container */}
        <div className={`inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br ${color} text-white mb-4 shadow-lg group-hover:shadow-2xl transition-shadow`}>
          <Icon size={24} />
        </div>

        {/* Content */}
        <p className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-1">{label}</p>
        <div className="flex items-end gap-3 mb-2">
          <h3 className="text-3xl font-bold text-white">{value}</h3>
          <span className={`text-sm font-semibold ${isPositive ? "text-emerald-400" : "text-red-400"}`}>
            {trend}
          </span>
        </div>

        {/* Micro label */}
        <p className="text-xs text-slate-500">vs last month</p>
      </div>
    </motion.div>
  );
}
