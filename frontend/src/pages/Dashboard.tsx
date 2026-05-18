import { motion } from "framer-motion";
import { AlertCircle, CheckCircle, Users, Zap } from "lucide-react";
import { useMemo } from "react";

import KPICard from "../components/dashboard/KPICard";
import ActivityFeed from "../components/dashboard/ActivityFeed";
import InsightsPanel from "../components/dashboard/InsightsPanel";
import OverviewChart from "../components/dashboard/OverviewChart";
import FloatingActionPanel from "../components/dashboard/FloatingActionPanel";

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: "easeOut" },
  },
};

export default function Dashboard() {
  // Mock data - replace with actual API calls
  const kpiData = useMemo(
    () => [
      {
        icon: Zap,
        label: "Active Projects",
        value: "24",
        trend: "+12%",
        color: "from-purple-500 to-pink-500",
      },
      {
        icon: Users,
        label: "Team Members",
        value: "156",
        trend: "+8%",
        color: "from-blue-500 to-cyan-500",
      },
      {
        icon: CheckCircle,
        label: "Completed Tasks",
        value: "892",
        trend: "+23%",
        color: "from-emerald-500 to-teal-500",
      },
      {
        icon: AlertCircle,
        label: "Pending Approvals",
        value: "12",
        trend: "-5%",
        color: "from-orange-500 to-red-500",
      },
    ],
    []
  );

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Animated background grid */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div
          className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: `
              linear-gradient(to right, rgba(15, 23, 42, 0.5) 1px, transparent 1px),
              linear-gradient(to bottom, rgba(15, 23, 42, 0.5) 1px, transparent 1px)
            `,
            backgroundSize: "4rem 4rem",
          }}
        />
        {/* Gradient orbs */}
        <motion.div
          className="absolute top-20 left-1/3 w-96 h-96 bg-purple-500 rounded-full blur-3xl opacity-10"
          animate={{
            x: [0, 50, 0],
            y: [0, -50, 0],
          }}
          transition={{ duration: 20, repeat: Infinity }}
        />
        <motion.div
          className="absolute bottom-20 right-1/4 w-96 h-96 bg-cyan-500 rounded-full blur-3xl opacity-10"
          animate={{
            x: [0, -50, 0],
            y: [0, 50, 0],
          }}
          transition={{ duration: 25, repeat: Infinity }}
        />
      </div>

      {/* Main content */}
      <div className="relative z-10 mx-auto max-w-7xl px-4 py-8 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-8"
        >
          <p className="text-sm font-medium text-cyan-400 uppercase tracking-widest mb-2">
            {getGreeting()}, Avery! 👋
          </p>
          <h1 className="text-4xl font-bold bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent mb-2">
            Control Center
          </h1>
          <p className="text-slate-400">
            Monitor projects, team activity, and system performance in real-time
          </p>
        </motion.div>

        {/* KPI Cards */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8"
        >
          {kpiData.map((card, idx) => (
            <motion.div key={idx} variants={itemVariants}>
              <KPICard {...card} />
            </motion.div>
          ))}
        </motion.div>

        {/* Charts and Activity */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8"
        >
          <motion.div variants={itemVariants} className="lg:col-span-2">
            <OverviewChart />
          </motion.div>

          <motion.div variants={itemVariants}>
            <InsightsPanel />
          </motion.div>
        </motion.div>

        {/* Activity Feed */}
        <motion.div variants={itemVariants} initial="hidden" animate="visible">
          <ActivityFeed />
        </motion.div>
      </div>

      {/* Floating Action Panel */}
      <FloatingActionPanel />
    </div>
  );
}
