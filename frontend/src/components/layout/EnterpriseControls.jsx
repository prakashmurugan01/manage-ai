import { AnimatePresence, motion } from "framer-motion";
import { Activity, Mic, MicOff, Network, Wifi, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { enterpriseApi } from "../../api/services.js";

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

const DOWNLOAD_PROBE_BYTES = 96 * 1024;
const UPLOAD_PROBE_BYTES = 48 * 1024;
const SAMPLE_LIMIT = 48;
const CLOSED_SAMPLE_MS = 2000;
const OPEN_SAMPLE_MS = 1000;
const UPLOAD_PROBE_PAYLOAD = "0".repeat(UPLOAD_PROBE_BYTES);

function numeric(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function roundMetric(value) {
  return Math.round(numeric(value) * 100) / 100;
}

function metricText(value) {
  const parsed = numeric(value);
  if (parsed >= 100) return String(Math.round(parsed));
  if (parsed >= 10) return parsed.toFixed(1).replace(/\.0$/, "");
  return parsed.toFixed(2).replace(/\.?0+$/, "");
}

function mbpsFromBytes(bytes, elapsedMs) {
  if (!bytes || !elapsedMs) return 0;
  return roundMetric((bytes * 8) / (elapsedMs / 1000) / 1000000);
}

function getConnection() {
  return navigator.connection || navigator.mozConnection || navigator.webkitConnection || {};
}

function secondsAgo(value) {
  if (!value) return "starting";
  const seconds = Math.max(0, Math.round((Date.now() - value) / 1000));
  return seconds <= 1 ? "now" : `${seconds}s ago`;
}

function DetailMetric({ label, value }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 truncate text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

async function timedRequest(factory) {
  const started = performance.now();
  const response = await factory();
  return { response, elapsed: Math.max(1, performance.now() - started) };
}

export default function EnterpriseControls() {
  const voice = useVoiceCommands();
  const [networkOpen, setNetworkOpen] = useState(false);
  const [samples, setSamples] = useState([]);
  const [networkState, setNetworkState] = useState({
    online: typeof navigator === "undefined" ? true : navigator.onLine !== false,
    loading: false,
    lastUpdated: null,
    source: "warming up",
    error: ""
  });
  const sampleSequence = useRef(0);

  const sampleNetwork = useCallback(async () => {
    const sequence = sampleSequence.current + 1;
    sampleSequence.current = sequence;
    const connection = getConnection();
    const online = typeof navigator === "undefined" ? true : navigator.onLine !== false;
    setNetworkState((state) => ({ ...state, online, loading: true, error: "" }));

    const browserDownload = roundMetric(connection.downlink || 0);
    const browserUpload = browserDownload ? roundMetric(browserDownload * 0.42) : 0;
    const browserLatency = Math.max(0, Math.round(connection.rtt || 0));

    const [liveResult, downloadResult, uploadResult] = await Promise.allSettled([
      timedRequest(() => enterpriseApi.networkLive()),
      timedRequest(() => enterpriseApi.networkProbeDownload(DOWNLOAD_PROBE_BYTES)),
      timedRequest(() => enterpriseApi.networkProbeUpload(UPLOAD_PROBE_PAYLOAD))
    ]);

    if (sampleSequence.current !== sequence) return;

    const liveSample = liveResult.status === "fulfilled" ? liveResult.value : null;
    const downloadSample = downloadResult.status === "fulfilled" ? downloadResult.value : null;
    const uploadSample = uploadResult.status === "fulfilled" ? uploadResult.value : null;
    const serverCurrent = liveSample?.response?.data?.current || {};
    const downloadBytes = numeric(downloadSample?.response?.data?.bytes, DOWNLOAD_PROBE_BYTES);
    const uploadBytes = numeric(uploadSample?.response?.data?.bytes, UPLOAD_PROBE_BYTES);
    const measuredDownload = mbpsFromBytes(downloadBytes, downloadSample?.elapsed || 0);
    const measuredUpload = mbpsFromBytes(uploadBytes, uploadSample?.elapsed || 0);
    const latencyCandidates = [liveSample?.elapsed, downloadSample?.elapsed, uploadSample?.elapsed].filter(Boolean);
    const measuredLatency = latencyCandidates.length ? Math.round(Math.min(...latencyCandidates)) : 0;

    const nextSample = {
      at: Date.now(),
      online,
      download: measuredDownload || browserDownload || numeric(serverCurrent.download_mbps),
      upload: measuredUpload || browserUpload || numeric(serverCurrent.upload_mbps),
      latency: measuredLatency || browserLatency || numeric(serverCurrent.latency_ms),
      serverDownload: numeric(serverCurrent.download_mbps),
      serverUpload: numeric(serverCurrent.upload_mbps),
      browserDownload,
      browserUpload,
      packetLoss: numeric(serverCurrent.packet_loss_percent),
      rps: numeric(serverCurrent.requests_per_second),
      health: numeric(serverCurrent.health_score, online ? 100 : 0)
    };

    setSamples((items) => [...items.slice(-(SAMPLE_LIMIT - 1)), nextSample]);
    setNetworkState({
      online,
      loading: false,
      lastUpdated: nextSample.at,
      source: measuredDownload || measuredUpload ? "live probe" : liveSample ? "server feed" : "browser estimate",
      error: liveResult.status === "rejected" && downloadResult.status === "rejected" && uploadResult.status === "rejected" ? "Live network fetch failed." : ""
    });
  }, []);

  useEffect(() => {
    sampleNetwork();
    const timer = window.setInterval(sampleNetwork, networkOpen ? OPEN_SAMPLE_MS : CLOSED_SAMPLE_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [networkOpen, sampleNetwork]);

  useEffect(() => {
    const connection = getConnection();
    const handleVisibility = () => {
      if (document.visibilityState === "visible") sampleNetwork();
    };
    window.addEventListener("online", sampleNetwork);
    window.addEventListener("offline", sampleNetwork);
    window.addEventListener("focus", sampleNetwork);
    document.addEventListener("visibilitychange", handleVisibility);
    connection.addEventListener?.("change", sampleNetwork);
    return () => {
      window.removeEventListener("online", sampleNetwork);
      window.removeEventListener("offline", sampleNetwork);
      window.removeEventListener("focus", sampleNetwork);
      document.removeEventListener("visibilitychange", handleVisibility);
      connection.removeEventListener?.("change", sampleNetwork);
    };
  }, [sampleNetwork]);

  const current = samples[samples.length - 1] || { latency: 0, download: 0, upload: 0 };

  return (
    <div className="relative flex items-center gap-2">
      <button type="button" onClick={() => { setNetworkOpen(true); sampleNetwork(); }} className="theme-control relative rounded-lg p-2 text-slate-300 transition hover:text-white" aria-label="Open network speed monitor">
        <Network size={18} />
        <span className={`absolute right-1 top-1 h-1.5 w-1.5 rounded-full ${networkState.online ? "bg-teal-300" : "bg-rose-400"}`} />
      </button>
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
                  <p className="mt-1 text-sm text-slate-500">{networkState.online ? "Online" : "Offline"} - {networkState.source} - updated {secondsAgo(networkState.lastUpdated)}</p>
                </div>
                <button type="button" onClick={() => setNetworkOpen(false)} className="rounded-lg p-2 text-slate-400 hover:bg-white/10 hover:text-white" aria-label="Close network monitor"><X size={18} /></button>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><Wifi className="text-teal-200" size={18} /><p className="mt-3 text-2xl font-semibold text-white">{metricText(current.download)}</p><p className="text-xs text-slate-500">Mbps download</p></div>
                <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><Activity className="text-sky-300" size={18} /><p className="mt-3 text-2xl font-semibold text-white">{metricText(current.upload)}</p><p className="text-xs text-slate-500">Mbps upload</p></div>
                <div className="rounded-lg border border-white/10 bg-white/[0.04] p-4"><Network className="text-amber-200" size={18} /><p className="mt-3 text-2xl font-semibold text-white">{Math.round(numeric(current.latency))}</p><p className="text-xs text-slate-500">ms latency</p></div>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-4">
                <DetailMetric label="Server feed" value={`${metricText(current.serverDownload)} / ${metricText(current.serverUpload)} Mbps`} />
                <DetailMetric label="Browser link" value={`${metricText(current.browserDownload)} / ${metricText(current.browserUpload)} Mbps`} />
                <DetailMetric label="Packet loss" value={`${metricText(current.packetLoss)}%`} />
                <DetailMetric label="Health" value={`${Math.round(numeric(current.health))}%`} />
              </div>
              <div className="mt-5 rounded-lg border border-white/10 bg-white/[0.035] p-4">
                <MiniGraph values={samples.map((item) => item.download)} />
              </div>
              {networkState.error && <p className="mt-3 rounded-lg border border-rose-400/20 bg-rose-500/10 p-3 text-sm text-rose-100">{networkState.error}</p>}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
