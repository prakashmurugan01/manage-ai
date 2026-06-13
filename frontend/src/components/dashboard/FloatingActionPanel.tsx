import { motion } from "framer-motion";
import { Settings, Users, Files, Activity, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

const quickActions = [
  { icon: Settings, label: "Settings", to: "/settings", color: "from-purple-500 to-pink-500" },
  { icon: Users, label: "Users", to: "/users", color: "from-blue-500 to-cyan-500" },
  { icon: Files, label: "Files", to: "/files", color: "from-emerald-500 to-teal-500" },
  { icon: Activity, label: "Activity", to: "/dashboard", color: "from-orange-500 to-red-500" },
];

export default function FloatingActionPanel() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <motion.div className="fixed right-8 bottom-8 flex flex-col items-center gap-4">
      {/* Quick action buttons */}
      <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={isOpen ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.8 }}
        transition={{ duration: 0.2 }}
        className={`flex flex-col gap-3 ${isOpen ? "pointer-events-auto" : "pointer-events-none"}`}
      >
        {quickActions.map((action, idx) => {
          const Icon = action.icon;
          return (
            <motion.div
              key={idx}
              initial={{ opacity: 0, x: 20 }}
              animate={isOpen ? { opacity: 1, x: 0 } : { opacity: 0, x: 20 }}
              transition={{ delay: idx * 0.05 }}
            >
              <Link to={action.to}>
                <motion.button
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.95 }}
                  className={`group relative w-14 h-14 rounded-full bg-gradient-to-br ${action.color} flex items-center justify-center text-white shadow-lg hover:shadow-2xl transition-all`}
                  title={action.label}
                >
                  <Icon size={20} />
                  {/* Tooltip */}
                  <motion.div
                    initial={{ opacity: 0, x: 10 }}
                    whileHover={{ opacity: 1, x: 0 }}
                    className="absolute right-full mr-3 px-3 py-1 rounded-lg bg-slate-900 text-white text-sm font-medium whitespace-nowrap border border-white/10 pointer-events-none"
                  >
                    {action.label}
                  </motion.div>
                </motion.button>
              </Link>
            </motion.div>
          );
        })}
      </motion.div>

      {/* Main floating button */}
      <motion.button
        onClick={() => setIsOpen(!isOpen)}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.95 }}
        className="relative w-16 h-16 rounded-full bg-gradient-to-br from-purple-500 via-pink-500 to-red-500 flex items-center justify-center text-white shadow-2xl hover:shadow-purple-500/50 transition-all"
      >
        <motion.div
          animate={{ rotate: isOpen ? 45 : 0 }}
          transition={{ duration: 0.3 }}
        >
          <Plus size={24} />
        </motion.div>

        {/* Pulse ring on hover */}
        <motion.div
          animate={{ scale: [1, 1.2, 1] }}
          transition={{ duration: 2, repeat: Infinity }}
          className="absolute inset-0 rounded-full border-2 border-purple-400 opacity-0 group-hover:opacity-100"
        />
      </motion.button>
    </motion.div>
  );
}
