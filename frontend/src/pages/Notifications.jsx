import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Bell,
  BellOff,
  CheckCheck,
  CheckCircle2,
  Clock3,
  Mail,
  RefreshCw,
  Search,
  ShieldAlert,
  Volume2,
  VolumeX,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import useNotifications from "../hooks/useNotifications.js";

const filters = ["All", "Unread", "Critical", "Warning", "Read"];

const styles = {
  critical: {
    icon: ShieldAlert,
    badge: "Critical",
    border: "border-rose-300/35",
    bg: "bg-rose-400/10",
    text: "text-rose-100",
    glow: "shadow-rose-500/10"
  },
  warning: {
    icon: AlertTriangle,
    badge: "Warning",
    border: "border-amber-300/35",
    bg: "bg-amber-400/10",
    text: "text-amber-100",
    glow: "shadow-amber-500/10"
  },
  success: {
    icon: CheckCircle2,
    badge: "Success",
    border: "border-emerald-300/35",
    bg: "bg-emerald-400/10",
    text: "text-emerald-100",
    glow: "shadow-emerald-500/10"
  },
  info: {
    icon: Bell,
    badge: "Info",
    border: "border-cyan-300/35",
    bg: "bg-cyan-400/10",
    text: "text-cyan-100",
    glow: "shadow-cyan-500/10"
  }
};

function getTone(notification) {
  const text = `${notification.urgency || ""} ${notification.type || ""} ${notification.title || ""}`.toLowerCase();
  if (text.includes("critical") || text.includes("alert")) return "critical";
  if (text.includes("warning") || text.includes("expiry") || text.includes("disabled")) return "warning";
  if (text.includes("success") || text.includes("enabled") || text.includes("approved")) return "success";
  return "info";
}

function formatTime(value) {
  if (!value) return "Just now";
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDate(value) {
  if (!value) return "Live";
  return new Date(value).toLocaleDateString([], { day: "2-digit", month: "short", year: "numeric" });
}

export default function Notifications() {
  const { notifications, unreadCount, markRead, markAllRead, refresh: refreshNotifications } = useNotifications();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");
  const [soundOn, setSoundOn] = useState(() => localStorage.getItem("notificationSound") !== "muted");
  const [hiddenIds, setHiddenIds] = useState([]);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    localStorage.setItem("notificationSound", soundOn ? "on" : "muted");
  }, [soundOn]);

  const metrics = useMemo(() => {
    const critical = notifications.filter((item) => getTone(item) === "critical").length;
    const warning = notifications.filter((item) => getTone(item) === "warning").length;
    const emailFailed = notifications.filter((item) => item.is_sent_email === false && /email/i.test(`${item.type || ""} ${item.title || ""}`)).length;
    return { total: notifications.length, unread: unreadCount, critical, warning, emailFailed };
  }, [notifications, unreadCount]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return notifications.filter((item) => {
      if (hiddenIds.includes(item.id)) return false;
      const tone = getTone(item);
      const haystack = `${item.title || ""} ${item.message || ""} ${item.type || ""}`.toLowerCase();
      const matchesSearch = !needle || haystack.includes(needle);
      const matchesFilter =
        filter === "All" ||
        (filter === "Unread" && !item.is_read) ||
        (filter === "Read" && item.is_read) ||
        tone === filter.toLowerCase();
      return matchesSearch && matchesFilter;
    });
  }, [filter, hiddenIds, notifications, query]);

  function notify(title, message) {
    setToast({ title, message });
    if (soundOn && window.AudioContext) {
      const context = new window.AudioContext();
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      oscillator.connect(gain);
      gain.connect(context.destination);
      oscillator.frequency.value = 740;
      gain.gain.setValueAtTime(0.035, context.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.16);
      oscillator.start();
      oscillator.stop(context.currentTime + 0.16);
    }
    setTimeout(() => setToast(null), 2400);
  }

  async function refresh() {
    await refreshNotifications?.();
    notify("Notifications refreshed", "Latest alerts fetched from the server.");
  }

  function markEverythingRead() {
    markAllRead();
    notify("All notifications marked read", "Your notification inbox is clear.");
  }

  return (
    <main className="notifications-page relative -mx-4 -my-6 min-h-[calc(100vh-4rem)] overflow-hidden bg-[#050816] px-4 py-6 text-white sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_8%_8%,rgba(34,211,238,0.16),transparent_28%),radial-gradient(circle_at_92%_10%,rgba(168,85,247,0.18),transparent_32%),linear-gradient(135deg,#050816,#080b18_52%,#12091f)]" />
      <div className="pointer-events-none absolute inset-0 animated-grid opacity-20" />

      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            className="fixed right-6 top-24 z-50 rounded-lg border border-cyan-300/25 bg-slate-950/92 p-4 shadow-2xl shadow-cyan-500/20 backdrop-blur-xl"
          >
            <p className="text-sm font-bold text-white">{toast.title}</p>
            <p className="mt-1 text-xs text-slate-400">{toast.message}</p>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="relative mx-auto max-w-7xl space-y-5">
        <header className="rounded-lg border border-white/10 bg-slate-950/60 p-5 shadow-2xl shadow-cyan-950/20 backdrop-blur-2xl">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.16em] text-cyan-100">
                <span className="h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_14px_rgba(52,211,153,0.9)]" />
                Live Alerts
              </div>
              <h1 className="mt-3 text-3xl font-black tracking-tight text-white sm:text-4xl">Notification Center</h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                Realtime alerts for hosting, deployments, approvals, tickets, system health, and account activity.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <IconButton icon={RefreshCw} label="Refresh" onClick={refresh} />
              <IconButton icon={soundOn ? Volume2 : VolumeX} label={soundOn ? "Sound On" : "Muted"} onClick={() => setSoundOn((value) => !value)} />
              <IconButton icon={CheckCheck} label="Mark all read" onClick={markEverythingRead} />
            </div>
          </div>
        </header>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Metric title="Total Alerts" value={metrics.total} icon={Bell} tone="info" />
          <Metric title="Unread" value={metrics.unread} icon={BellOff} tone="warning" />
          <Metric title="Critical" value={metrics.critical} icon={ShieldAlert} tone="critical" />
          <Metric title="Email Failed" value={metrics.emailFailed} icon={Mail} tone="success" />
        </section>

        <section className="rounded-lg border border-white/10 bg-slate-950/58 p-4 shadow-2xl shadow-cyan-950/20 backdrop-blur-2xl">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-cyan-200" size={18} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search notifications..."
                className="h-12 w-full rounded-lg border border-white/10 bg-slate-950/70 pl-12 pr-4 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/50 focus:ring-4 focus:ring-cyan-300/10"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {filters.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setFilter(item)}
                  className={`rounded-lg px-3 py-2 text-xs font-bold transition ${
                    filter === item
                      ? "bg-cyan-300 text-slate-950 shadow-lg shadow-cyan-300/20"
                      : "border border-white/10 bg-white/[0.045] text-slate-400 hover:border-cyan-300/35 hover:text-white"
                  }`}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="space-y-3 pb-16">
          <AnimatePresence mode="popLayout">
            {filtered.map((item, index) => (
              <NotificationCard
                key={item.id}
                item={item}
                index={index}
                onRead={() => {
                  markRead(item.id);
                  notify("Notification marked read", item.title);
                }}
                onDismiss={() => {
                  setHiddenIds((ids) => [...ids, item.id]);
                  notify("Notification closed", item.title);
                }}
              />
            ))}
          </AnimatePresence>

          {!filtered.length && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-lg border border-dashed border-cyan-300/25 bg-slate-950/50 p-10 text-center shadow-2xl backdrop-blur-2xl"
            >
              <div className="mx-auto grid h-16 w-16 place-items-center rounded-lg border border-cyan-300/25 bg-cyan-300/10 text-cyan-100">
                <Bell size={28} />
              </div>
              <h2 className="mt-4 text-xl font-black text-white">No notifications found</h2>
              <p className="mt-2 text-sm text-slate-400">Try another filter or clear your search.</p>
            </motion.div>
          )}
        </section>
      </div>
    </main>
  );
}

function IconButton({ icon: Icon, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/[0.055] px-3 text-sm font-bold text-slate-200 transition hover:border-cyan-300/40 hover:bg-cyan-300/10 hover:text-white"
    >
      <Icon size={16} />
      {label}
    </button>
  );
}

function Metric({ title, value, icon: Icon, tone }) {
  const style = styles[tone] || styles.info;
  return (
    <motion.article
      whileHover={{ y: -4 }}
      className={`relative overflow-hidden rounded-lg border ${style.border} bg-slate-950/58 p-4 shadow-xl ${style.glow} backdrop-blur-2xl`}
    >
      <div className="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-white/10 blur-3xl" />
      <div className="relative flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-500">{title}</p>
          <p className="mt-3 text-3xl font-black text-white">{value}</p>
        </div>
        <span className={`grid h-12 w-12 place-items-center rounded-lg border ${style.border} ${style.bg} ${style.text}`}>
          <Icon size={21} />
        </span>
      </div>
    </motion.article>
  );
}

function NotificationCard({ item, index, onRead, onDismiss }) {
  const tone = getTone(item);
  const style = styles[tone] || styles.info;
  const Icon = style.icon;
  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ delay: index * 0.02 }}
      whileHover={{ y: -2 }}
      className={`group relative overflow-hidden rounded-lg border ${item.is_read ? "border-white/10" : style.border} bg-slate-950/58 p-4 shadow-xl ${style.glow} backdrop-blur-2xl`}
    >
      <div className="absolute inset-0 bg-gradient-to-r from-white/[0.035] via-transparent to-cyan-400/10 opacity-0 transition group-hover:opacity-100" />
      <div className="relative flex gap-4">
        <span className={`grid h-12 w-12 shrink-0 place-items-center rounded-lg border ${style.border} ${style.bg} ${style.text}`}>
          <Icon size={21} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-black text-white">{item.title}</h2>
            <Badge text={style.badge} style={style} />
            <Badge text={item.type || "app"} />
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-400">{item.message}</p>
          <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1"><Clock3 size={13} /> {formatTime(item.created_at)}</span>
            <span>{formatDate(item.created_at)}</span>
            <span>{item.sender_detail?.email || "System"}</span>
            <span>{item.is_read ? "Read" : "Unread"}</span>
          </div>
        </div>
        <div className="flex shrink-0 items-start gap-2">
          {!item.is_read ? (
            <button
              type="button"
              onClick={onRead}
              className="grid h-10 w-10 place-items-center rounded-lg border border-cyan-300/20 bg-cyan-300/10 text-cyan-100 transition hover:bg-cyan-300/20"
              aria-label="Mark notification as read"
              title="Mark read"
            >
              <CheckCheck size={17} />
            </button>
          ) : (
            <span className="grid h-10 w-10 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-500" title="Read">
              <CheckCheck size={17} />
            </span>
          )}
          <button type="button" onClick={onDismiss} className="grid h-10 w-10 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-400 transition hover:text-white" title="Close">
            <X size={17} />
          </button>
        </div>
      </div>
    </motion.article>
  );
}

function Badge({ text, style }) {
  const tone = style || styles.info;
  return <span className={`rounded-full border ${tone.border} ${tone.bg} px-2 py-1 text-[10px] font-black uppercase tracking-[0.12em] ${tone.text}`}>{text}</span>;
}
