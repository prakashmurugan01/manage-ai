import { motion } from "framer-motion";
import { Activity, MoreVertical } from "lucide-react";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

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
      className="theme-panel group relative overflow-hidden rounded-2xl p-6 backdrop-blur-xl"
    >
      {/* Gradient background on hover */}
      <div className="absolute inset-0 -z-10 opacity-0 transition duration-500 group-hover:opacity-10" style={{ background: "linear-gradient(135deg, var(--accent-secondary), transparent, var(--accent-primary))" }} />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg text-[color:var(--text-on-accent)]" style={{ background: "linear-gradient(135deg, var(--accent-secondary), var(--accent-primary))" }}>
            <Activity size={20} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-[color:var(--text-primary)]">Activity Overview</h3>
            <p className="text-xs text-[color:var(--text-secondary)]">Last 30 days</p>
          </div>
        </div>
        <button className="rounded-lg p-2 text-[color:var(--text-secondary)] transition hover:bg-[color:var(--surface-soft)] hover:text-[color:var(--text-primary)]">
          <MoreVertical size={18} />
        </button>
      </div>

      {/* Chart */}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <defs>
              <linearGradient id="colorProjects" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--chart-memory)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--chart-memory)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorTasks" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--chart-cpu)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--chart-cpu)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--chart-grid)" vertical={false} />
            <XAxis dataKey="date" stroke="var(--chart-axis)" style={{ fontSize: "12px" }} />
            <YAxis stroke="var(--chart-axis)" style={{ fontSize: "12px" }} />
            <Tooltip
              contentStyle={{
                backgroundColor: "var(--tooltip-bg)",
                border: "1px solid var(--tooltip-border)",
                borderRadius: "12px",
                backdropFilter: "blur(10px)",
                color: "var(--text-primary)",
              }}
              cursor={{ stroke: "var(--chart-grid)" }}
              wrapperStyle={{ outline: "none" }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="projects"
              stroke="var(--chart-memory)"
              strokeWidth={2}
              dot={false}
              fillOpacity={1}
              fill="url(#colorProjects)"
            />
            <Line
              type="monotone"
              dataKey="tasks"
              stroke="var(--chart-cpu)"
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
