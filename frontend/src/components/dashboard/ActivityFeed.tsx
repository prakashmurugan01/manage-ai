import { motion } from "framer-motion";
import { Activity, Clock, User, FileText, CheckCircle, AlertCircle } from "lucide-react";

const activities = [
  {
    id: 1,
    icon: CheckCircle,
    title: "Project Deployment",
    description: "Internal Ops Command Center v2.1 deployed to production",
    time: "2 hours ago",
    user: "Avery Stone",
    color: "from-emerald-500 to-teal-500",
  },
  {
    id: 2,
    icon: FileText,
    title: "File Transfer Completed",
    description: "backup.sql (2.0 GB) transferred from Finance to Archive",
    time: "4 hours ago",
    user: "System",
    color: "from-blue-500 to-cyan-500",
  },
  {
    id: 3,
    icon: AlertCircle,
    title: "Approval Required",
    description: "New user registration request from john@example.com",
    time: "6 hours ago",
    user: "Jon Reed",
    color: "from-orange-500 to-red-500",
  },
  {
    id: 4,
    icon: Activity,
    title: "Team Member Added",
    description: "Mira Kapoor joined the Development Team",
    time: "1 day ago",
    user: "PRAKASH Murugan",
    color: "from-purple-500 to-pink-500",
  },
];

export default function ActivityFeed() {
  return (
    <motion.div
      whileHover={{ y: -4 }}
      className="group relative rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-6 overflow-hidden"
    >
      {/* Gradient background */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-10 transition duration-500 bg-gradient-to-br from-purple-500 via-transparent to-cyan-500 -z-10" />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white">
            <Activity size={20} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Recent Activity</h3>
            <p className="text-xs text-slate-400">Real-time updates from your team</p>
          </div>
        </div>
      </div>

      {/* Activity timeline */}
      <div className="space-y-4">
        {activities.map((activity, idx) => {
          const Icon = activity.icon;
          return (
            <motion.div
              key={activity.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.1 }}
              whileHover={{ x: 4, backgroundColor: "rgba(255, 255, 255, 0.05)" }}
              className="group/activity p-4 rounded-xl border border-white/5 hover:border-white/10 transition-all cursor-pointer"
            >
              <div className="flex gap-4">
                {/* Icon */}
                <div className={`w-10 h-10 rounded-lg bg-gradient-to-br ${activity.color} flex items-center justify-center text-white flex-shrink-0 shadow-lg`}>
                  <Icon size={18} />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-white">{activity.title}</p>
                      <p className="text-sm text-slate-400 mt-1">{activity.description}</p>
                    </div>
                  </div>

                  {/* Meta */}
                  <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
                    <div className="flex items-center gap-1">
                      <Clock size={14} />
                      {activity.time}
                    </div>
                    <div className="flex items-center gap-1">
                      <User size={14} />
                      {activity.user}
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* See more button */}
      <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className="mt-6 w-full py-2 rounded-lg border border-white/10 hover:border-white/20 text-white text-sm font-medium hover:bg-white/5 transition-all"
      >
        View All Activity
      </motion.button>
    </motion.div>
  );
}
