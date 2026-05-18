import { LogOut } from "lucide-react";
import { NavLink } from "react-router-dom";
import { motion } from "framer-motion";

import { navigation } from "../../constants/navigation.js";
import { useAuth } from "../../context/AuthContext.jsx";
import { hasAnyRole, ROLE_LABELS } from "../../utils/rbac.js";

// Global styles for removing text selection highlight
import "./Sidebar.css";

export default function Sidebar() {
  const { user, logout } = useAuth();
  const items = navigation.filter((item) => hasAnyRole(user, item.roles));

  return (
    <aside className="app-sidebar fixed inset-y-0 left-0 z-40 hidden w-72 select-none overflow-y-auto border-r px-4 py-5 text-slate-300 backdrop-blur-2xl transition-colors lg:block">
      {/* Decorative animated gradient background */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden opacity-20">
        <motion.div
          className="absolute left-0 top-0 h-40 w-40 rounded-full bg-gradient-to-br from-cyan-400/30 to-blue-500/20 blur-3xl"
          animate={{
            x: [0, 20, 0],
            y: [0, -20, 0],
          }}
          transition={{ duration: 15, repeat: Infinity }}
        />
        <motion.div
          className="absolute bottom-0 right-0 h-40 w-40 rounded-full bg-gradient-to-br from-fuchsia-500/20 to-cyan-500/20 blur-3xl"
          animate={{
            x: [0, -20, 0],
            y: [0, 20, 0],
          }}
          transition={{ duration: 18, repeat: Infinity }}
        />
      </div>

      {/* Logo Section */}
      <motion.div 
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative mb-8 flex items-center gap-3 px-2 group"
      >
        <motion.div 
          whileHover={{ scale: 1.15, rotate: 5 }}
          className="brand-mark grid h-11 w-11 place-items-center rounded-xl border border-cyan-200/20 bg-gradient-to-br from-cyan-400 to-fuchsia-500 text-sm font-black text-white shadow-lg shadow-cyan-500/30"
        >
          MA
        </motion.div>
        <div>
          <p className="text-sm font-bold leading-tight text-white">ManageAI</p>
          <p className="text-xs font-semibold text-cyan-300">Control Center</p>
        </div>
      </motion.div>

      {/* Divider */}
      <div className="mb-6 h-px bg-gradient-to-r from-transparent via-current/10 to-transparent" />

      {/* Navigation */}
      <nav className="relative space-y-1 mb-8">
        {items.map((item, idx) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.label}
              to={item.to}
              className={({ isActive }) => {
                return `group relative flex items-center gap-3 px-3 py-3 text-sm font-medium rounded-xl transition-all duration-250 overflow-hidden ${
                  isActive
                    ? "text-white"
                    : "text-slate-400 hover:text-white"
                }`;
              }}
            >
              {({ isActive }) => (
                <>
                  {/* Background blur on active */}
                  {isActive && (
                    <motion.div
                      layoutId="activeBackground"
                      className="absolute inset-0 -z-10 rounded-xl bg-gradient-to-r from-cyan-400 via-blue-500 to-fuchsia-500 opacity-20"
                      transition={{ type: "spring", stiffness: 300, damping: 30 }}
                    />
                  )}

                  {/* Active state border glow */}
                  {isActive && (
                    <motion.div
                      className="absolute bottom-0 left-0 top-0 w-1 rounded-r-full bg-gradient-to-b from-cyan-300 to-fuchsia-400"
                      layoutId="activeBorder"
                      transition={{ type: "spring", stiffness: 300, damping: 30 }}
                    />
                  )}

                  {/* Icon */}
                  <motion.div
                    whileHover={{ scale: 1.15 }}
                    whileTap={{ scale: 0.95 }}
                    className={`relative flex-shrink-0 transition-all duration-250 ${
                      isActive ? "text-cyan-200" : "text-slate-500 group-hover:text-cyan-300"
                    }`}
                  >
                    <Icon size={18} />
                    
                    {/* Icon glow on active */}
                    {isActive && (
                      <motion.div
                        className="absolute inset-0 -z-10 rounded-full bg-cyan-300/30 blur-md"
                        animate={{ scale: [1, 1.3, 1] }}
                        transition={{ duration: 2, repeat: Infinity }}
                      />
                    )}
                  </motion.div>

                  {/* Label */}
                  <span className="relative flex-1">{item.label}</span>

                  {/* Hover background */}
                  {!isActive && (
                    <motion.div
                      className="absolute inset-0 rounded-xl bg-white/5 -z-10 opacity-0 group-hover:opacity-100"
                      transition={{ duration: 0.25 }}
                    />
                  )}

                  {/* Hover lift effect */}
                  {!isActive && (
                    <motion.div
                      className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition duration-300 -z-20"
                      style={{
                        background: "radial-gradient(circle at center, rgba(6,182,212,0.12), transparent)",
                      }}
                    />
                  )}

                  {/* Active glow shadow */}
                  {isActive && (
                    <motion.div
                      className="absolute -inset-2 rounded-xl -z-20 blur-xl opacity-30"
                      style={{
                        background: "linear-gradient(135deg, #06B6D4, #2563EB, #D946EF)",
                      }}
                      animate={{ opacity: [0.2, 0.4, 0.2] }}
                      transition={{ duration: 3, repeat: Infinity }}
                    />
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Divider */}
      <div className="mb-6 h-px bg-gradient-to-r from-transparent via-current/10 to-transparent" />

      {/* User Profile Card */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="relative"
      >
        <div className="saas-card relative overflow-hidden rounded-2xl">
          {/* Gradient accent on hover */}
          <motion.div
            className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-br from-cyan-400 to-fuchsia-500 opacity-0 transition-opacity duration-300 hover:opacity-10"
          />

          <div className="relative z-10 p-4">
            {/* Avatar + Info */}
            <div className="flex items-start gap-3 mb-3">
              <motion.div 
                whileHover={{ scale: 1.1 }}
                className="relative flex-shrink-0"
              >
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white font-bold text-sm shadow-lg border border-purple-400/30">
                  {user?.full_name?.charAt(0) || user?.email?.charAt(0)}
                </div>
                {/* Online indicator ring */}
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                  className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-slate-900 bg-emerald-400 shadow-lg shadow-emerald-400/50"
                />
              </motion.div>

              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-bold text-white leading-tight">{user?.full_name || user?.email}</p>
                <p className="text-xs text-cyan-300 font-semibold leading-tight">{ROLE_LABELS[user?.role]}</p>
              </div>
            </div>

            {/* Status */}
            <div className="mb-3 flex items-center gap-2 rounded-lg bg-white/5 px-2 py-1">
              <motion.div 
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="w-2 h-2 rounded-full bg-emerald-400 shadow-lg shadow-emerald-400/70"
              />
              <span className="text-xs text-slate-400">Online</span>
            </div>

            {/* Logout button */}
            <motion.button
              whileHover={{ scale: 1.02, boxShadow: "0 0 20px rgba(239,68,68,0.4)" }}
              whileTap={{ scale: 0.98 }}
              onClick={logout}
              type="button"
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-sm font-semibold text-red-200 transition-all duration-250"
              style={{
                background: "linear-gradient(135deg, rgba(239,68,68,0.2), rgba(244,63,94,0.2))",
                border: "1px solid rgba(239,68,68,0.4)",
              }}
            >
              <LogOut size={16} />
              Sign out
            </motion.button>
          </div>
        </div>
      </motion.div>
    </aside>
  );
}
