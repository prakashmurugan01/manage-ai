import { AnimatePresence, motion } from "framer-motion";
import { Bell, CheckCheck, Moon, ScanFace, Search, Sun, SunMedium, X } from "lucide-react";
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
  { value: THEMES.WHITE, label: "White", icon: Sun }
];

export default function Topbar({ events = [] }) {
  const { user } = useAuth();
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

  return (
    <header className="app-topbar sticky top-0 z-30 border-b backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <div className="theme-control hidden w-full max-w-md items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-400 md:flex">
          <Search size={16} />
          <span>Search projects, tasks, files</span>
        </div>
        <div className="flex flex-1 items-center justify-end gap-3">
          <EnterpriseControls />
          <div className="theme-control hidden rounded-lg p-1 sm:flex">
            {themeItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.value}
                  type="button"
                  title={`${item.label} mode`}
                  onClick={() => setTheme(item.value)}
                  className={`inline-flex h-8 w-8 items-center justify-center rounded-md transition ${theme === item.value ? "bg-white/15 text-teal-200" : "text-slate-400 hover:bg-white/10 hover:text-white"}`}
                >
                  <Icon size={16} />
                </button>
              );
            })}
          </div>
          <button type="button" onClick={() => setPanelOpen((open) => !open)} className="theme-control relative rounded-lg p-2 text-slate-300 transition hover:text-white" aria-label="Open notifications">
            <Bell size={18} />
            {unreadCount > 0 && (
              <span className="absolute -right-1 -top-1 grid min-h-4 min-w-4 place-items-center rounded-full bg-rose-400 px-1 text-[10px] font-semibold text-white">
                {Math.min(unreadCount, 9)}
              </span>
            )}
          </button>
          <button type="button" onClick={() => setFacePanelOpen((open) => !open)} className="theme-control rounded-lg p-2 text-slate-300 transition hover:text-white" aria-label="Enroll face login">
            <ScanFace size={18} />
          </button>
          <div className="text-right">
            <p className="text-sm font-medium text-white">{user?.full_name || user?.email}</p>
            <p className="text-xs text-slate-400">{ROLE_LABELS[user?.role]}</p>
          </div>
        </div>
      </div>
      <AnimatePresence>
        {facePanelOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.16 }}
            className="absolute right-4 top-[62px] z-40 w-[min(420px,calc(100vw-2rem))] overflow-hidden rounded-lg border border-white/10 bg-[color:var(--shell-bg)] p-4 shadow-2xl backdrop-blur"
          >
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Face Login Enrollment</p>
                <p className="mt-1 text-xs text-slate-500">Optional developer-side unlock. Admin can disable it from feature settings.</p>
              </div>
              <button type="button" onClick={() => setFacePanelOpen(false)} className="rounded-lg p-2 text-slate-400 transition hover:bg-white/10 hover:text-white" aria-label="Close face enrollment">
                <X size={16} />
              </button>
            </div>
            <FaceCapture mode="enroll" onSubmit={enrollFace} />
          </motion.div>
        )}
        {panelOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: 0.16 }}
            className="absolute right-4 top-[62px] z-40 w-[min(420px,calc(100vw-2rem))] overflow-hidden rounded-lg border border-white/10 bg-[color:var(--shell-bg)] shadow-2xl backdrop-blur"
          >
            <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
              <div>
                <p className="text-sm font-semibold text-white">Notification Center</p>
                <p className="text-xs text-slate-500">{unreadCount} live alerts</p>
              </div>
              <button type="button" onClick={() => setPanelOpen(false)} className="rounded-lg p-2 text-slate-400 transition hover:bg-white/10 hover:text-white" aria-label="Close notifications">
                <X size={16} />
              </button>
            </div>
            <div className="max-h-[70vh] overflow-y-auto p-3">
              {events.filter((event) => event.type !== "connected").slice(0, 4).map((event, index) => (
                <div key={`${event.type || "event"}-${index}`} className="mb-2 rounded-lg border border-teal-300/20 bg-teal-300/10 p-3">
                  <p className="text-sm font-medium text-white">{event.title || event.event || event.type || "Realtime update"}</p>
                  <p className="mt-1 text-xs text-teal-100/80">{event.message || event.project?.name || "Live platform event received."}</p>
                </div>
              ))}
              {notifications.map((item) => (
                <div key={item.id} className={`mb-2 rounded-lg border border-white/10 bg-white/[0.04] p-3 ${item.is_read ? "opacity-70" : ""}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-white">{item.title}</p>
                      <p className="mt-1 line-clamp-2 text-xs text-slate-400">{item.message}</p>
                      <p className="mt-2 text-[11px] uppercase tracking-[0.12em] text-slate-500">{new Date(item.created_at).toLocaleString()}</p>
                    </div>
                    {!item.is_read && (
                      <button type="button" onClick={() => markRead(item.id)} className="rounded-lg p-2 text-slate-400 transition hover:bg-white/10 hover:text-white" aria-label="Mark notification as read">
                        <CheckCheck size={15} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
              {!events.length && !notifications.length && <p className="rounded-lg bg-white/[0.04] p-4 text-sm text-slate-500">No notifications yet.</p>}
            </div>
            <div className="border-t border-white/10 p-3">
              <Link to="/notifications" onClick={() => setPanelOpen(false)} className="inline-flex w-full items-center justify-center rounded-lg bg-white/10 px-3 py-2 text-sm font-medium text-white transition hover:bg-white/15">
                View all notifications
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <nav className="flex gap-1 overflow-x-auto border-t border-white/10 px-3 py-2 lg:hidden">
        {mobileItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.label}
              to={item.to}
              className={({ isActive }) =>
                [
                  "theme-nav-item inline-flex min-w-fit items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition",
                  isActive ? "theme-nav-active text-white" : "text-slate-400 hover:text-white"
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
