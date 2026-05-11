import { AnimatePresence, motion } from "framer-motion";
import { Activity, Mic, MicOff, Minus, Network, Plus, Power, Server, Wifi, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../../api/client.js";
import { enterpriseApi } from "../../api/services.js";
import { useAuth } from "../../context/AuthContext.jsx";
import { canManage } from "../../utils/rbac.js";

function useVoiceCommands() {
  const navigate = useNavigate();
  const [listening, setListening] = useState(false);
  const [message, setMessage] = useState("");
  const recognitionRef = useRef(null);

  const commands = useMemo(() => [
    { keys: ["dashboard", "home"], path: "/dashboard" },
    { keys: ["project", "projects"], path: "/projects" },
    { keys: ["task", "tasks", "kanban"], path: "/tasks" },
    { keys: ["ticket", "tickets", "support"], path: "/tickets" },
    { keys: ["file", "files", "documents"], path: "/files" },
    { keys: ["report", "reports", "settings", "enterprise"], path: "/enterprise" },
    { keys: ["user", "users", "team"], path: "/users" },
    { keys: ["monitor", "monitoring", "server"], path: "/monitoring" }
  ], []);

  function start() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setMessage("Voice commands are not supported in this browser.");
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onstart = () => {
      setListening(true);
      setMessage("Listening for navigation command...");
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => {
      setListening(false);
      setMessage("Voice command failed. Try again.");
    };
    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript?.toLowerCase() || "";
      const target = commands.find((command) => command.keys.some((key) => transcript.includes(key)));
      if (target) {
        navigate(target.path);
        setMessage(`Opened ${target.path}`);
      } else {
        setMessage(`No command matched: ${transcript}`);
      }
    };
    recognitionRef.current = recognition;
    recognition.start();
  }

  function stop() {
    recognitionRef.current?.stop();
    setListening(false);
  }

  return { listening, message, start, stop };
}

function MiniGraph({ values = [] }) {
  const points = values.length ? values : [20, 44, 38, 62, 55, 70];
  const max = Math.max(...points, 1);
  const path = points.map((value, index) => {
    const x = (index / Math.max(points.length - 1, 1)) * 100;
    const y = 40 - (value / max) * 34;
    return `${index === 0 ? "M" : "L"}${x},${y}`;
  }).join(" ");
  return (
    <svg viewBox="0 0 100 42" className="h-16 w-full overflow-visible">
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export default function EnterpriseControls() {
  const { user } = useAuth();
  const voice = useVoiceCommands();
  const [networkOpen, setNetworkOpen] = useState(false);
  const [serverOpen, setServerOpen] = useState(false);
  const [samples, setSamples] = useState([]);
  const [server, setServer] = useState(null);

  useEffect(() => {
    if (!networkOpen) return undefined;
    let active = true;

    async function sampleNetwork() {
      const start = performance.now();
      try {
        await api.get("/analytics/performance/?days=1");
      } catch {
        // The panel still shows browser-level estimates if the API sample fails.
      }
      const latency = Math.max(1, Math.round(performance.now() - start));
      const connection = navigator.connection || {};
      const downlink = Number(connection.downlink || 80);
      const upload = Math.max(8, Math.round(downlink * 0.42));
      if (active) {
        setSamples((items) => [...items.slice(-17), { latency, download: Math.round(downlink * 100) / 100, upload }]);
      }
    }

    sampleNetwork();
    const timer = window.setInterval(sampleNetwork, 3000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [networkOpen]);

  useEffect(() => {
    if (!serverOpen || !canManage(user)) return undefined;
    let active = true;

    async function loadServer() {
      const { data } = await enterpriseApi.serverLive();
      if (active) setServer(data);
    }

    loadServer();
    const timer = window.setInterval(loadServer, 5000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [serverOpen, user]);

  async function controlServer(payload) {
    if (!server?.id) return;
    const { data } = await enterpriseApi.controlServer(server.id, payload);
    setServer(data);
  }

  const current = samples[samples.length - 1] || { latency: 0, download: 0, upload: 0 };

  return (
    <div className="relative flex items-center gap-2">
      <button type="button" onClick={() => setNetworkOpen(true)} className="theme-control rounded-lg p-2 text-slate-300 transition hover:text-white" aria-label="Open network speed monitor">
        <Network size={18} />
      </button>
      {canManage(user) && (
        <button type="button" onClick={() => setServerOpen(true)} className="theme-control rounded-lg p-2 text-slate-300 transition hover:text-white" aria-label="Open server control">
          <Server size={18} />
        </button>
      )}
      <button type="button" onClick={voice.listening ? voice.stop : voice.start} className={`theme-control rounded-lg p-2 transition ${voice.listening ? "text-rose-200" : "text-slate-300 hover:text-white"}`} aria-label="Toggle voice assistant">
        {voice.listening ? <MicOff size={18} /> : <Mic size={18} />}
      </button>
      <AnimatePresence>
        {voice.message && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} className="absolute right-0 top-12 z-50 w-72 rounded-lg border border-white/10 bg-[color:var(--shell-bg)] p-3 text-xs text-slate-300 shadow-2xl">
            {voice.message}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {networkOpen && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 bg-black/70 p-4">
            <motion.div initial={{ opacity: 0, y: 16, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 12, scale: 0.98 }} className="mx-auto mt-20 max-w-xl rounded-lg border border-white/10 bg-[color:var(--app-bg)] p-5 shadow-2xl">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-white">Network Speed Monitor</h2>
                  <p className="mt-1 text-sm text-slate-500">Live upload, download, latency, and connection graph.</p>
                </div>
                <button type="button" onClick={() => setNetworkOpen(false)} className="rounded-lg p-2 text-slate-400 hover:bg-white/10 hover:text-white" aria-label="Close network monitor"><X size={18} /></button>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><Wifi className="text-teal-200" size={18} /><p className="mt-3 text-2xl font-semibold text-white">{current.download}</p><p className="text-xs text-slate-500">Mbps download</p></div>
                <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><Activity className="text-sky-300" size={18} /><p className="mt-3 text-2xl font-semibold text-white">{current.upload}</p><p className="text-xs text-slate-500">Mbps upload</p></div>
                <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><Network className="text-amber-200" size={18} /><p className="mt-3 text-2xl font-semibold text-white">{current.latency}</p><p className="text-xs text-slate-500">ms latency</p></div>
              </div>
              <div className="mt-5 rounded-lg border border-white/10 bg-white/[0.035] p-4">
                <MiniGraph values={samples.map((item) => item.download)} />
              </div>
            </motion.div>
          </motion.div>
        )}

        {serverOpen && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 bg-black/70 p-4">
            <motion.div initial={{ opacity: 0, y: 16, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 12, scale: 0.98 }} className="mx-auto mt-16 max-w-2xl rounded-lg border border-white/10 bg-[color:var(--app-bg)] p-5 shadow-2xl">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold text-white">Server Control Center</h2>
                  <p className="mt-1 text-sm text-slate-500">Storage, files, active users, requests, uptime, health, and scale control.</p>
                </div>
                <button type="button" onClick={() => setServerOpen(false)} className="rounded-lg p-2 text-slate-400 hover:bg-white/10 hover:text-white" aria-label="Close server control"><X size={18} /></button>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><p className="text-xs uppercase tracking-[0.14em] text-slate-500">Health</p><p className="mt-3 text-xl font-semibold text-white">{server?.health || "Loading"}</p></div>
                <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><p className="text-xs uppercase tracking-[0.14em] text-slate-500">Storage</p><p className="mt-3 text-xl font-semibold text-white">{server?.storage_percent || 0}%</p></div>
                <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><p className="text-xs uppercase tracking-[0.14em] text-slate-500">Active Users</p><p className="mt-3 text-xl font-semibold text-white">{server?.active_users || 0}</p></div>
                <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><p className="text-xs uppercase tracking-[0.14em] text-slate-500">Files</p><p className="mt-3 text-xl font-semibold text-white">{server?.file_count || 0}</p></div>
                <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><p className="text-xs uppercase tracking-[0.14em] text-slate-500">Incoming</p><p className="mt-3 text-xl font-semibold text-white">{server?.incoming_requests || 0}</p></div>
                <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><p className="text-xs uppercase tracking-[0.14em] text-slate-500">Outgoing</p><p className="mt-3 text-xl font-semibold text-white">{server?.outgoing_requests || 0}</p></div>
              </div>
              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.035] p-4">
                <div>
                  <p className="text-sm font-medium text-white">Server {server?.is_enabled ? "ON" : "OFF"}</p>
                  <p className="mt-1 text-xs text-slate-500">Scale units: {server?.scale_units || 1}</p>
                </div>
                <div className="flex gap-2">
                  <button type="button" onClick={() => controlServer({ is_enabled: !server?.is_enabled })} className="inline-flex items-center gap-2 rounded-lg bg-white/10 px-3 py-2 text-sm text-white hover:bg-white/15"><Power size={16} />Toggle</button>
                  <button type="button" onClick={() => controlServer({ scale_units: Math.max(1, (server?.scale_units || 1) - 1) })} className="rounded-lg bg-white/10 p-2 text-white hover:bg-white/15" aria-label="Scale down"><Minus size={16} /></button>
                  <button type="button" onClick={() => controlServer({ scale_units: (server?.scale_units || 1) + 1 })} className="rounded-lg bg-white/10 p-2 text-white hover:bg-white/15" aria-label="Scale up"><Plus size={16} /></button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
