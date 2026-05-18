import { motion } from "framer-motion";
import { Lightbulb, ArrowRight, TrendingUp, AlertCircle } from "lucide-react";

const insights = [
  {
    icon: TrendingUp,
    title: "Project Growth",
    description: "24% increase in active projects this month",
    color: "from-emerald-500 to-teal-500",
  },
  {
    icon: AlertCircle,
    title: "Pending Reviews",
    description: "12 items awaiting your approval",
    color: "from-orange-500 to-red-500",
  },
  {
    icon: Lightbulb,
    title: "AI Suggestion",
    description: "Automate recurring file transfers to save time",
    color: "from-cyan-500 to-blue-500",
  },
];

export default function InsightsPanel() {
  return (
    <motion.div
      whileHover={{ y: -4 }}
      className="group relative rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6 overflow-hidden"
    >
      {/* Gradient background */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-10 transition duration-500 bg-gradient-to-br from-cyan-500 via-transparent to-purple-500 -z-10" />

      {/* Header */}
      <div className="flex items-center gap-2 mb-6">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center text-white">
          <Lightbulb size={20} />
        </div>
        <h3 className="text-lg font-semibold text-white">AI Insights</h3>
      </div>

      {/* Insights list */}
      <div className="space-y-4">
        {insights.map((insight, idx) => {
          const Icon = insight.icon;
          return (
            <motion.div
              key={idx}
              whileHover={{ x: 8 }}
              className="group/insight p-4 rounded-xl border border-white/5 hover:border-white/10 hover:bg-white/10 transition-all cursor-pointer"
            >
              <div className="flex items-start gap-3">
                <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${insight.color} flex items-center justify-center text-white flex-shrink-0`}>
                  <Icon size={16} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-white truncate">{insight.title}</p>
                  <p className="text-xs text-slate-400 mt-1">{insight.description}</p>
                </div>
                <ArrowRight size={16} className="text-slate-500 group-hover/insight:text-white transition ml-2 flex-shrink-0" />
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Footer CTA */}
      <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className="mt-6 w-full py-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white text-sm font-semibold hover:shadow-lg hover:shadow-purple-500/20 transition-all"
      >
        View All Recommendations
      </motion.button>
    </motion.div>
  );
}
