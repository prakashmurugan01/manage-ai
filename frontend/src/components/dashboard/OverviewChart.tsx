import { motion } from "framer-motion";
import { Activity, MoreVertical } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

const chartData = [
  { date: "Jan 1", projects: 12, tasks: 45, users: 24 },
  { date: "Jan 8", projects: 15, tasks: 52, users: 28 },
  { date: "Jan 15", projects: 18, tasks: 61, users: 34 },
  { date: "Jan 22", projects: 22, tasks: 58, users: 38 },
  { date: "Jan 29", projects: 24, tasks: 72, users: 42 },
  { date: "Feb 5", projects: 28, tasks: 68, users: 45 },
  { date: "Feb 12", projects: 32, tasks: 85, users: 48 },
];

export default function OverviewChart() {
  return (
    <motion.div
      whileHover={{ y: -4 }}
      className="group relative rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6 overflow-hidden"
    >
      {/* Gradient background on hover */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-10 transition duration-500 bg-gradient-to-br from-purple-500 via-transparent to-cyan-500 -z-10" />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white">
            <Activity size={20} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Activity Overview</h3>
            <p className="text-xs text-slate-400">Last 30 days</p>
          </div>
        </div>
        <button className="p-2 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition">
          <MoreVertical size={18} />
        </button>
      </div>

      {/* Chart */}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <defs>
              <linearGradient id="colorProjects" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorTasks" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" vertical={false} />
            <XAxis dataKey="date" stroke="#94a3b8" style={{ fontSize: "12px" }} />
            <YAxis stroke="#94a3b8" style={{ fontSize: "12px" }} />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(15, 23, 42, 0.8)",
                border: "1px solid rgba(255, 255, 255, 0.1)",
                borderRadius: "12px",
                backdropFilter: "blur(10px)",
              }}
              cursor={{ stroke: "rgba(255, 255, 255, 0.1)" }}
              wrapperStyle={{ outline: "none" }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="projects"
              stroke="#a855f7"
              strokeWidth={2}
              dot={false}
              fillOpacity={1}
              fill="url(#colorProjects)"
            />
            <Line
              type="monotone"
              dataKey="tasks"
              stroke="#06b6d4"
              strokeWidth={2}
              dot={false}
              fillOpacity={1}
              fill="url(#colorTasks)"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
