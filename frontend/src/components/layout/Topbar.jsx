import { AnimatePresence, motion } from "framer-motion";
import { Bell, Camera, CheckCheck, Moon, RefreshCw, ScanFace, Sparkles, SunMedium, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, NavLink } from "react-router-dom";

import { listFrom } from "../../api/client.js";
import { authApi, notificationsApi } from "../../api/services.js";
import FaceCapture from "../auth/FaceCapture.jsx";
import { navigation } from "../../constants/navigation.js";
import { useAuth } from "../../context/AuthContext.jsx";
import { THEMES, useTheme } from "../../context/ThemeContext.jsx";
import { hasAnyRole, ROLE_LABELS } from "../../utils/rbac.js";
import EnterpriseControls from "./EnterpriseControls.jsx";

const themeItems = [
  { value: THEMES.DARK, label: "Dark", icon: Moon },
  { value: THEMES.LIGHT, label: "Light", icon: SunMedium },
  { value: THEMES.WHITE, label: "White", icon: Sparkles }
];

export default function Topbar({ events = [] }) {
  const { user, updateCurrentUser } = useAuth();
  const { theme, setTheme } = useTheme();
  const [panelOpen, setPanelOpen] = useState(false);
  const [facePanelOpen, setFacePanelOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const mobileItems = navigation.filter((item) => hasAnyRole(user, item.roles)).slice(0, 5);
  const unreadCount = useMemo(() => notifications.filter((item) => !item.is_read).length + events.filter((event) => event.type !== "connected").length, [events, notifications]);

  useEffect(() => {
    let mounted = true;
    notificationsApi.list().then((response) => {
      if (mounted) setNotifications(listFrom(response).slice(0, 8));
    });
    return () => {
      mounted = false;
    };
  }, [events.length]);

  async function markRead(id) {
    const { data } = await notificationsApi.markRead(id);
    setNotifications((items) => items.map((item) => (item.id === id ? data : item)));
  }

  async function enrollFace(formData) {
    await authApi.faceEnroll(formData);
    setFacePanelOpen(false);
  }

  async function uploadAvatar(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("avatar", file);
    const { data } = await authApi.uploadAvatar(formData);
    updateCurrentUser?.(data);
    event.target.value = "";
  }

  return (
    <header className="app-topbar sticky top-0 z-30 border-b backdrop-blur-2xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex flex-1 items-center justify-end gap-3">
          <EnterpriseControls />
          <div className="theme-control relative hidden rounded-2xl p-1 transition-all sm:flex">
            {themeItems.map((item) => {
              const Icon = item.icon;
              const active = theme === item.value;
              return (
                <motion.button
                  key={item.value}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  type="button"
                  title={`${item.label} mode`}
                  onClick={() => setTheme(item.value)}
                  className={`relative inline-flex h-9 w-9 items-center justify-center rounded-xl transition ${active ? "text-[color:var(--text-on-accent)]" : "text-[color:var(--text-secondary)] hover:bg-[color:var(--surface-soft)] hover:text-[color:var(--text-primary)]"}`}
                >
                  {active && (
                    <motion.span
                      layoutId="theme-mode-pill"
                      className="absolute inset-0 rounded-xl shadow-lg"
                      style={{ background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))" }}
                      transition={{ type: "spring", stiffness: 360, damping: 28 }}
                    />
                  )}
                  <span className="relative z-10">
                  <Icon size={16} />
                  </span>
                </motion.button>
              );
            })}
          </div>
          <motion.button 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            type="button" 
            onClick={() => setPanelOpen((open) => !open)} 
            className="theme-control relative rounded-xl p-2.5 text-[color:var(--text-secondary)] transition-all hover:bg-[color:var(--surface-soft)] hover:text-[color:var(--text-primary)]" 
            aria-label="Open notifications"
          >
            <motion.span animate={unreadCount > 0 ? { rotate: [0, -10, 10, -8, 0] } : {}} transition={{ duration: 1.8, repeat: unreadCount > 0 ? Infinity : 0, repeatDelay: 2 }}>
              <Bell size={18} />
            </motion.span>
            {unreadCount > 0 && (
              <motion.span 
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="absolute -right-1 -top-1 grid min-h-5 min-w-5 place-items-center rounded-full px-1 text-[10px] font-bold text-[color:var(--text-on-accent)] shadow-lg"
                style={{ background: "linear-gradient(135deg, var(--danger), var(--accent-secondary))" }}
              >
                {Math.min(unreadCount, 9)}
              </motion.span>
            )}
          </motion.button>
          <motion.button 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            type="button" 
            onClick={() => setFacePanelOpen((open) => !open)} 
            className="theme-control rounded-xl p-2.5 text-[color:var(--text-secondary)] transition-all hover:bg-[color:var(--surface-soft)] hover:text-[color:var(--text-primary)]" 
            aria-label="Enroll face login"
          >
            <ScanFace size={18} />
          </motion.button>
          <motion.label
            whileHover={{ scale: 1.02 }}
            className="group flex cursor-pointer items-center gap-3 rounded-xl px-2 py-1.5 transition hover:bg-[color:var(--surface-soft)]"
          >
            <input type="file" accept="image/*" onChange={uploadAvatar} className="hidden" />
            <span className="relative grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-xl border border-[color:var(--border-color)] bg-[color:var(--surface-soft)] text-sm font-bold text-[color:var(--accent-primary)]">
              {user?.avatar ? <img src={user.avatar} alt="" className="h-full w-full object-cover" /> : (user?.full_name || user?.email || "U").slice(0, 1).toUpperCase()}
              <span className="absolute inset-0 hidden place-items-center bg-[color:var(--modal-backdrop)] text-[color:var(--text-primary)] group-hover:grid">
                <Camera size={15} />
              </span>
            </span>
            <span className="hidden text-right sm:block">
              <p className="text-sm font-semibold text-[color:var(--text-primary)]">{user?.full_name || user?.email}</p>
              <p className="text-xs text-[color:var(--accent-primary)]">{ROLE_LABELS[user?.role]}</p>
            </span>
          </motion.label>
        </div>
      </div>
      <AnimatePresence>
        {facePanelOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.16 }}
            className="theme-modal absolute right-4 top-[62px] z-40 w-[min(420px,calc(100vw-2rem))] overflow-hidden rounded-2xl p-4 backdrop-blur-xl"
          >
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-[color:var(--text-primary)]">Face Login Enrollment</p>
                <p className="mt-1 text-xs text-[color:var(--text-muted)]">Optional developer-side unlock. Admin can disable it from feature settings.</p>
              </div>
              <button type="button" onClick={() => setFacePanelOpen(false)} className="rounded-lg p-2 text-[color:var(--text-secondary)] transition hover:bg-[color:var(--surface-soft)] hover:text-[color:var(--text-primary)]" aria-label="Close face enrollment">
                <X size={16} />
              </button>
            </div>
            <FaceCapture mode="enroll" onSubmit={enrollFace} />
          </motion.div>
        )}
        {panelOpen && (
          <>
            {/* Backdrop overlay */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setPanelOpen(false)}
              className="fixed inset-0 z-[9998]"
              style={{
                background: "var(--modal-backdrop)",
                backdropFilter: "blur(8px)",
              }}
            />

            {/* Notification Panel */}
            <motion.div
              initial={{ opacity: 0, y: -20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.95 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className="notification-popover fixed right-6 top-20 z-[9999] w-full max-w-md overflow-hidden rounded-2xl"
              style={{
                background: "var(--card-bg)",
                border: "1px solid var(--border-color)",
                boxShadow: "var(--shadow)",
                backdropFilter: "blur(10px)",
                maxHeight: "calc(100vh - 120px)",
              }}
            >
              {/* Header */}
              <div className="flex items-center justify-between gap-3 border-b border-[color:var(--border-color)] px-4 py-4">
                <div>
                  <p className="text-sm font-bold text-[color:var(--text-primary)]">Notification Center</p>
                  <p className="text-xs font-semibold text-[color:var(--accent-primary)]">{unreadCount} live alerts</p>
                </div>
                <div className="flex items-center gap-2">
                  <motion.button
                    whileHover={{ scale: 1.1, rotate: 180 }}
                    whileTap={{ scale: 0.95 }}
                    type="button"
                    className="rounded-lg p-2 text-[color:var(--text-secondary)] transition-all hover:bg-[color:var(--surface-soft)] hover:text-[color:var(--text-primary)]"
                    aria-label="Refresh notifications"
                  >
                    <RefreshCw size={16} />
                  </motion.button>
                  <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.95 }}
                    type="button"
                    onClick={() => setPanelOpen(false)}
                    className="rounded-lg p-2 text-[color:var(--text-secondary)] transition-all hover:bg-[color:var(--surface-soft)] hover:text-[color:var(--text-primary)]"
                    aria-label="Close notifications"
                  >
                    <X size={16} />
                  </motion.button>
                </div>
              </div>

              {/* Notifications List */}
              <div className="overflow-y-auto p-3 space-y-2" style={{ maxHeight: "calc(100vh - 200px)" }}>
                {/* Live Events */}
                {events.filter((event) => event.type !== "connected").slice(0, 4).map((event, index) => (
                  <motion.div
                    key={`${event.type || "event"}-${index}`}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="group relative cursor-pointer rounded-xl border border-[color:var(--border-color)] p-3.5 transition-all hover:border-[color:var(--border-strong)] hover:bg-[color:var(--surface-soft)]"
                    style={{ background: "var(--table-row-bg)" }}
                  >
                    <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition duration-300 pointer-events-none" style={{
                      background: "radial-gradient(circle at top right, color-mix(in srgb, var(--accent-primary) 12%, transparent), transparent)",
                    }} />
                    <div className="relative">
                      <p className="text-sm font-bold leading-tight text-[color:var(--text-primary)]">{event.title || event.event || event.type || "Realtime update"}</p>
                      <p className="mt-1.5 text-xs leading-relaxed text-[color:var(--text-secondary)]">{event.message || event.project?.name || "Live platform event received."}</p>
                      <p className="mt-2 text-[10px] uppercase tracking-wider text-[color:var(--text-muted)]">Live Event</p>
                    </div>
                  </motion.div>
                ))}

                {/* Regular Notifications */}
                {notifications.map((item, idx) => (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: (events.filter((e) => e.type !== "connected").length + idx) * 0.05 }}
                    className={`group relative rounded-xl border transition-all cursor-pointer ${
                      item.is_read ? "border-[color:var(--border-color)] opacity-70" : "border-[color:var(--border-color)] hover:border-[color:var(--border-strong)] hover:bg-[color:var(--surface-soft)]"
                    }`}
                    style={{ background: "var(--table-row-bg)" }}
                  >
                    <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition duration-300 pointer-events-none" style={{
                      background: item.is_read
                        ? "transparent"
                        : "radial-gradient(circle at top right, color-mix(in srgb, var(--accent-secondary) 12%, transparent), transparent)",
                    }} />
                    <div className="relative p-3.5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-bold leading-tight text-[color:var(--text-primary)]">{item.title}</p>
                          <p className="mt-1.5 line-clamp-3 text-xs leading-relaxed text-[color:var(--text-secondary)]">{item.message}</p>
                          <p className="mt-2 text-[10px] uppercase tracking-wider text-[color:var(--text-muted)]">
                            {new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </p>
                        </div>
                        {!item.is_read && (
                          <motion.button
                            whileHover={{ scale: 1.15 }}
                            whileTap={{ scale: 0.9 }}
                            type="button"
                            onClick={() => markRead(item.id)}
                            className="flex-shrink-0 rounded-lg p-2 text-[color:var(--accent-primary)] transition-all hover:bg-[color:var(--surface-soft)]"
                            aria-label="Mark notification as read"
                          >
                            <CheckCheck size={16} />
                          </motion.button>
                        )}
                      </div>
                    </div>
                  </motion.div>
                ))}

                {!events.length && !notifications.length && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="rounded-xl border border-[color:var(--border-color)] p-6 text-center"
                    style={{ background: "var(--table-row-bg)" }}
                  >
                    <p className="text-sm text-[color:var(--text-muted)]">No notifications yet</p>
                  </motion.div>
                )}
              </div>

              {/* Footer */}
              <div className="border-t border-[color:var(--border-color)] p-3">
                <Link
                  to="/notifications"
                  onClick={() => setPanelOpen(false)}
                  className="inline-flex w-full items-center justify-center rounded-lg px-3 py-2.5 text-sm font-semibold transition-all"
                  style={{
                    background: "linear-gradient(135deg, color-mix(in srgb, var(--accent-secondary) 20%, transparent), color-mix(in srgb, var(--accent-primary) 16%, transparent))",
                    border: "1px solid color-mix(in srgb, var(--accent-secondary) 30%, transparent)",
                    color: "var(--text-primary)",
                  }}
                >
                  View All Notifications
                </Link>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
      <nav className="flex gap-1 overflow-x-auto border-t border-[color:var(--border-color)] px-3 py-2 lg:hidden">
        {mobileItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.label}
              to={item.to}
              className={({ isActive }) =>
                [
                  "theme-nav-item inline-flex min-w-fit items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition",
                  isActive ? "theme-nav-active text-[color:var(--text-primary)]" : "text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
                ].join(" ")
              }
            >
              <Icon size={15} />
              {item.label}
            </NavLink>
          );
        })}
      </nav>
    </header>
  );
}
