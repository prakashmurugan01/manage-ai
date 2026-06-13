import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { createPortal } from "react-dom";
import { useSearchParams } from "react-router-dom";
import {
  Activity, ArrowDownToLine, Battery, CheckCircle2, Circle,
  Copy, Cpu, Download, File, FileArchive, FileCode, FileSearch,
  FileText, Folder, FolderPlus, HardDrive, Image, Keyboard,
  Layers, Lock, Maximize2, Monitor, MousePointer2, Pause, Play,
  Plus, Power, RefreshCw, RotateCcw, Search, ShieldCheck,
  SlidersHorizontal, Square, Terminal, Trash2, Upload, Wifi,
  WifiOff, X, XCircle, Zap, ChevronRight, AlertTriangle, Cpu as CpuIcon,
  MemoryStick, Clock, User, Hash
} from "lucide-react";
import { remoteAccessApi } from "../api/services.js";
import { apiErrorMessage } from "../api/client.js";

// ─── constants ────────────────────────────────────────────────────────────────
const TABS = ["desktop", "terminal", "processes", "files"];

const PERMISSIONS = [
  { value: "VIEW",    label: "View only",       detail: "Live screen without input" },
  { value: "CONTROL", label: "Full control",     detail: "Screen, mouse & keyboard" },
  { value: "FILES",   label: "File access",      detail: "Browse and transfer disks" },
  { value: "ADMIN",   label: "Desktop + disk",   detail: "Full approved session" },
];

const PROCESS_SIGNALS = ["TERMINATE", "KILL", "SUSPEND", "RESUME"];
const INITIAL_REGISTER_DEVICE_FORM = { name: "", hostname: "", notes: "", platform: "Windows" };

// ─── URL helpers ──────────────────────────────────────────────────────────────
function absoluteApiBaseUrl() {
  const configured = import.meta.env.VITE_API_BASE_URL || "/api";
  if (/^https?:\/\//i.test(configured)) return configured;
  return `${window.location.origin}${configured.startsWith("/") ? configured : `/${configured}`}`;
}
function httpToWs(v) { return v.replace(/^http/i, "ws"); }
function wsUrl(path) {
  const root  = httpToWs(absoluteApiBaseUrl().replace(/\/api\/?$/, ""));
  const token = localStorage.getItem("accessToken");
  return `${root}${path}${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}
function defaultAgentServerUrl() {
  const configured = (import.meta.env.VITE_AGENT_SERVER_URL || "").trim();
  if (configured) return configured.replace(/\/$/, "");
  return httpToWs(absoluteApiBaseUrl().replace(/\/api\/?$/, "")).replace(/\/$/, "");
}
function agentCommand(token, serverUrl = defaultAgentServerUrl()) {
  return `python backend/agents/remote_agent.py --server ${serverUrl} --token ${token}`;
}
function clientAccessUrl(token) {
  return `${window.location.origin}/remote-access?token=${encodeURIComponent(token)}`;
}
function normalizeToken(value) {
  const raw = (value || "").trim();
  if (!raw) return "";
  try {
    const parsed = new URL(raw);
    return parsed.searchParams.get("token") || parsed.searchParams.get("connection") || raw;
  } catch { return raw; }
}
function normalizeFileResult(result = {}) {
  const entries = [...(result.entries || [])].sort((a, b) => {
    if (Boolean(a.drive) !== Boolean(b.drive)) return a.drive ? -1 : 1;
    if (Boolean(a.is_dir) !== Boolean(b.is_dir)) return a.is_dir ? -1 : 1;
    return String(a.name || "").localeCompare(String(b.name || ""));
  });
  return { path: result.path || "", entries };
}
function formatBytes(bytes = 0) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** i).toFixed(i ? 1 : 0)} ${units[i]}`;
}
function formatDuration(seconds = 0) {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0s";
  if (seconds < 60) return `${Math.ceil(seconds)}s`;
  return `${Math.floor(seconds / 60)}m ${Math.ceil(seconds % 60)}s`;
}
function safeDownloadName(v = "download") {
  return String(v).replace(/[<>:"/\\|?*]+/g, "_").trim() || "download";
}
function buildBreadcrumbs(path = "") {
  if (!path || path === "Drives") return path === "Drives" ? [{ label: "Drives", path: "" }] : [];
  if (path.startsWith("shell:")) {
    const parts = path.replace(/^shell:/, "").split("/").filter(Boolean);
    return parts.map((part, i) => ({
      label: i === 0 ? "Portable Device" : part.startsWith("@") ? `Folder ${i}` : part,
      path:  `shell:${parts.slice(0, i + 1).join("/")}`,
    }));
  }
  const normalized = path.replace(/\//g, "\\");
  const parts = normalized.split("\\").filter(Boolean);
  return parts.map((part, i) => {
    const prefix    = parts.slice(0, i + 1).join("\\");
    const crumbPath = /^[A-Z]:$/i.test(parts[0]) ? `${prefix}\\` : prefix;
    return { label: part, path: crumbPath };
  });
}
function fileIcon(item) {
  const type = item.type || "", name = item.name || "";
  if (type.startsWith("image/"))                                 return Image;
  if (type.includes("zip") || /\.(zip|rar|7z|tar|gz)$/i.test(name)) return FileArchive;
  if (/\.(js|ts|py|go|rs|java|c|cpp|sh)$/i.test(name))          return FileCode;
  if (type.startsWith("text/") || /\.(txt|md|json|csv|log)$/i.test(name)) return FileText;
  return File;
}

// ══════════════════════════════════════════════════════════════════════════════
// ROOT COMPONENT
// ══════════════════════════════════════════════════════════════════════════════
export default function RemoteAccess() {
  const qc = useQueryClient();
  const [searchParams] = useSearchParams();
  const urlToken = normalizeToken(searchParams.get("token") || searchParams.get("connection"));

  // ── device / session state ─────────────────────────────────────────────────
  const [selectedDevice,  setSelectedDevice]  = useState(null);
  const [selectedSession, setSelectedSession] = useState(null);
  const [permission,      setPermission]      = useState("VIEW");
  const [agentServer,     setAgentServer]     = useState(
    () => localStorage.getItem("remoteAgentServerUrl") || defaultAgentServerUrl()
  );
  const [streamSettings, setStreamSettings] = useState({ fps: 12, quality: 76, max_width: 1600 });
  const [turboMode,       setTurboMode]      = useState(false);

  // ── screen ─────────────────────────────────────────────────────────────────
  const [frame,         setFrame]         = useState("");
  const [hasCanvasFrame,setHasCanvasFrame] = useState(false);
  const [streamStats,   setStreamStats]   = useState({ fps: 0, latency: 0, mode: "idle" });
  const [monitors,      setMonitors]      = useState([]);
  const [activeMonitor, setActiveMonitor] = useState(1);

  // ── tab navigation ─────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState("desktop");

  // ── terminal state ─────────────────────────────────────────────────────────
  const [terminals,       setTerminals]       = useState([]);   // [{id, title, alive, output}]
  const [activeTerminalId,setActiveTerminalId] = useState(null);
  const [termInput,       setTermInput]       = useState("");

  // ── process state ──────────────────────────────────────────────────────────
  const [processes,      setProcesses]      = useState([]);
  const [processSearch,  setProcessSearch]  = useState("");
  const [processSort,    setProcessSort]    = useState("cpu");
  const [selectedPid,    setSelectedPid]    = useState(null);
  const [processDetails, setProcessDetails] = useState(null);

  // ── file state ─────────────────────────────────────────────────────────────
  const [fileState,     setFileState]     = useState({ path: "", entries: [], loading: false });
  const [fileSearch,    setFileSearch]    = useState("");
  const [searchResults, setSearchResults] = useState(null);

  // ── transfer state ─────────────────────────────────────────────────────────
  const [transferItems, setTransferItems] = useState(() => {
    try { return JSON.parse(localStorage.getItem("remoteTransferHistory") || "[]"); }
    catch { return []; }
  });

  // ── events ─────────────────────────────────────────────────────────────────
  const [events,       setEvents]       = useState([]);
  const [socketStatus, setSocketStatus] = useState("connecting");

  // ── refs ───────────────────────────────────────────────────────────────────
  const screenRef            = useRef(null);
  const canvasRef            = useRef(null);
  const controlSocketRef     = useRef(null);
  const downloadJobsRef      = useRef({});
  const remoteDownloadBuffers= useRef({});
  const frameStatsRef        = useRef({ count: 0, started: performance.now(), lastMove: 0 });
  const termOutputRefs       = useRef({});   // id → div ref for autoscroll
  const termInputRef         = useRef(null);

  // ── persistence ────────────────────────────────────────────────────────────
  useEffect(() => { localStorage.setItem("remoteAgentServerUrl", agentServer); }, [agentServer]);
  useEffect(() => {
    localStorage.setItem("remoteTransferHistory", JSON.stringify(transferItems.slice(0, 30)));
  }, [transferItems]);

  // ── dashboard query ────────────────────────────────────────────────────────
  const dashboard = useQuery({
    queryKey: ["remote-access-dashboard"],
    queryFn:  () => remoteAccessApi.dashboard().then(r => r.data),
    refetchInterval: 15000,
  });

  const data     = dashboard.data || {};
  const devices  = data.devices  || [];
  const sessions = data.sessions || [];
  const logs     = data.logs     || [];
  const summary  = data.summary  || {};

  const activeDevice  = selectedDevice || devices[0];
  const refreshed     = selectedSession
    ? sessions.find(s => s.id === selectedSession.id) || selectedSession
    : null;
  const activeSession = (refreshed?.status === "ACTIVE" ? refreshed : null)
    || sessions.find(s => s.status === "ACTIVE")
    || refreshed
    || sessions.find(s => s.status === "REQUESTED")
    || null;

  const canFiles   = activeSession && ["FILES", "ADMIN"].includes(activeSession.permission);
  const canControl = activeSession && ["CONTROL", "ADMIN"].includes(activeSession.permission);
  const telemetry  = activeDevice?.metadata?.telemetry || {};

  // ── mutations ──────────────────────────────────────────────────────────────
  const requestSession = useMutation({
    mutationFn: ({ device, mode }) =>
      remoteAccessApi.requestSession(device.id, {
        permission: mode, offer: { stream: streamSettings },
      }),
    onSuccess: ({ data }) => {
      setSelectedSession(data);
      pushEvent("Session request sent", "Waiting for approval on target laptop.");
      qc.invalidateQueries({ queryKey: ["remote-access-dashboard"] });
    },
    onError: err => pushEvent("Connection failed", apiErrorMessage(err, "Could not request session.")),
  });

  const connectToken = useMutation({
    mutationFn: ({ token, mode }) => {
      const device = devices.find(d => d.token === token);
      if (device?.status === "OFFLINE") {
        const err = new Error("Target agent is offline.");
        err.offlineDevice = device;
        throw err;
      }
      return remoteAccessApi.connectToken({ token, permission: mode, offer: { stream: streamSettings } });
    },
    onSuccess: ({ data }) => {
      setSelectedSession(data);
      pushEvent("Token request sent", "Waiting for manual approval on the target laptop.");
      qc.invalidateQueries({ queryKey: ["remote-access-dashboard"] });
    },
    onError: err => pushEvent("Token connect failed", apiErrorMessage(err, "Token could not be used.")),
  });

  const disconnect = useMutation({
    mutationFn: id => remoteAccessApi.disconnect(id),
    onSuccess: () => {
      setSelectedSession(null); setFrame(""); setHasCanvasFrame(false);
      setTerminals([]); setActiveTerminalId(null); setProcesses([]);
      qc.invalidateQueries({ queryKey: ["remote-access-dashboard"] });
    },
  });

  const removeDevice = useMutation({
    mutationFn: id => remoteAccessApi.removeDevice(id),
    onSuccess: () => {
      setSelectedDevice(null);
      qc.invalidateQueries({ queryKey: ["remote-access-dashboard"] });
    },
  });

  // ── helpers ────────────────────────────────────────────────────────────────
  function pushEvent(type, detail) {
    setEvents(prev => [{ type, detail }, ...prev].slice(0, 15));
  }

  const upsertTransferItem = useCallback((key, patch) => {
    setTransferItems(prev => {
      const idx  = prev.findIndex(i => i.key === key || (patch.transferId && i.transferId === patch.transferId));
      const next = { ...(idx >= 0 ? prev[idx] : { key }), ...patch, updatedAt: Date.now() };
      if (idx >= 0) return [next, ...prev.filter((_, i) => i !== idx)].slice(0, 30);
      return [next, ...prev].slice(0, 30);
    });
  }, []);

  // ── main WebSocket (dashboard events) ─────────────────────────────────────
  useEffect(() => {
    const socket = new WebSocket(wsUrl("/ws/remote-access/"));
    socket.onopen  = () => setSocketStatus("connected");
    socket.onerror = () => setSocketStatus("error");
    socket.onclose = () => setSocketStatus("closed");
    socket.onmessage = ev => {
      if (ev.data instanceof Blob) { renderBinaryFrame(ev.data); return; }
      const msg = JSON.parse(ev.data);
      routeMessage(msg);
    };
    return () => socket.close();
  }, []);

  // ── session control WebSocket ──────────────────────────────────────────────
  useEffect(() => {
    if (!activeSession?.token) return;
    const socket = new WebSocket(wsUrl("/ws/remote-access/"));
    socket.binaryType = "blob";
    controlSocketRef.current = socket;
    socket.onopen    = () => socket.send(JSON.stringify({ type: "join.session", session_token: activeSession.token }));
    socket.onmessage = ev => {
      if (ev.data instanceof Blob) { renderBinaryFrame(ev.data); return; }
      routeMessage(JSON.parse(ev.data));
    };
    return () => {
      if (controlSocketRef.current === socket) controlSocketRef.current = null;
      socket.close();
    };
  }, [activeSession?.token]);

  // ── message router ─────────────────────────────────────────────────────────
  function routeMessage(msg) {
    const { type } = msg;
    if (type === "screen.frame")        { setFrame(`data:image/jpeg;base64,${msg.image}`); return; }
    if (type === "file.result")         { handleFileResult(msg); return; }
    if (type === "transfer.progress")   { handleTransferMsg(msg, true); return; }
    if (type === "clipboard.data")      { receiveClipboard(msg.text || ""); return; }
    if (type === "device.storage.changed") {
      setFileState(prev => prev.path === "Drives" || !prev.path
        ? { path: "Drives", entries: msg.drives || [], loading: false } : prev);
      pushEvent("USB/storage changed", msg.message || "Storage refreshed.");
      return;
    }
    if (type === "agent.error")         { handleAgentError(msg); return; }
    if (type === "session.approved")    {
      if (msg.monitors?.length) setMonitors(msg.monitors);
      if (msg.session) setSelectedSession(msg.session);
      return;
    }
    // Process snapshot (background broadcast)
    if (type === "process.snapshot")    { setProcesses(msg.processes || []); return; }
    if (type === "process.list")        { setProcesses(msg.processes || []); return; }
    if (type === "process.details")     { setProcessDetails(msg.details); return; }
    if (type === "process.killed")      { pushEvent("Process killed", `PID ${msg.result?.pid} — ${msg.result?.name}`); return; }
    // Terminal
    if (type === "terminal.created")    { handleTerminalCreated(msg); return; }
    if (type === "terminal.output")     { handleTerminalOutput(msg); return; }
    if (type === "terminal.closed")     { handleTerminalClosed(msg); return; }
    if (type === "terminal.list")       { /* handled inline */ return; }
    // Monitor
    if (type === "monitor.selected")    {
      setActiveMonitor(msg.monitor?.index ?? 1);
      pushEvent("Monitor switched", msg.monitor?.label || "");
      return;
    }
    if (type === "screenshot.annotated") { setFrame(`data:image/jpeg;base64,${msg.image}`); return; }
    // Generic session/device events
    if (type?.includes("session") || type?.includes("device")) {
      if (msg.session) setSelectedSession(msg.session);
      pushEvent(type, msg.message || "Update");
      qc.invalidateQueries({ queryKey: ["remote-access-dashboard"] });
    }
  }

  // ── file result handler ───────────────────────────────────────────────────
  function handleFileResult(msg) {
    const { action, result } = msg;
    if (action === "list" || action === "drives")
      setFileState({ ...normalizeFileResult(result), loading: false });
    else if (action === "search")
      setSearchResults(result);
    else
      pushEvent(`File: ${action}`, result?.error || result?.deleted || result?.created || "Done");
  }

  // ── terminal handlers ──────────────────────────────────────────────────────
  function handleTerminalCreated(msg) {
    setTerminals(prev => [
      ...prev.filter(t => t.id !== msg.terminal_id),
      { id: msg.terminal_id, title: msg.title || "Terminal", alive: true, output: "" },
    ]);
    setActiveTerminalId(msg.terminal_id);
    pushEvent("Terminal opened", msg.title || msg.terminal_id);
  }
  function handleTerminalOutput(msg) {
    setTerminals(prev => prev.map(t =>
      t.id === msg.terminal_id
        ? { ...t, output: (t.output + msg.data).slice(-60000) }
        : t
    ));
    // Auto-scroll
    const el = termOutputRefs.current[msg.terminal_id];
    if (el) requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
  }
  function handleTerminalClosed(msg) {
    setTerminals(prev => prev.map(t =>
      t.id === msg.terminal_id ? { ...t, alive: false } : t
    ));
    pushEvent("Terminal closed", `Exit ${msg.exit_code ?? "?"}`);
  }

  // ── binary frame renderer ──────────────────────────────────────────────────
  async function renderBinaryFrame(blob) {
    const buffer     = await blob.arrayBuffer();
    const view       = new DataView(buffer);
    const headerLen  = view.getUint32(0);
    const header     = JSON.parse(new TextDecoder().decode(buffer.slice(4, 4 + headerLen)));
    if (header.type === "transfer.chunk.binary") {
      mergeChunk({ ...header, chunkBytes: new Uint8Array(buffer.slice(4 + headerLen)) });
      return;
    }
    if (header.type !== "screen.frame.binary") return;
    const imageBlob = new Blob([buffer.slice(4 + headerLen)], { type: "image/jpeg" });
    const bitmap    = await createImageBitmap(imageBlob);
    const canvas    = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: false });
    if (canvas.width !== header.screen_width || canvas.height !== header.screen_height || header.full) {
      canvas.width  = header.screen_width;
      canvas.height = header.screen_height;
      if (header.full) { ctx.fillStyle = "#020617"; ctx.fillRect(0, 0, canvas.width, canvas.height); }
    }
    ctx.drawImage(bitmap, header.x, header.y, header.width, header.height);
    bitmap.close?.();
    setHasCanvasFrame(true);
    const now   = performance.now();
    const stats = frameStatsRef.current;
    stats.count += 1;
    if (now - stats.started >= 1000) {
      setStreamStats({
        fps:     Math.round((stats.count * 1000) / (now - stats.started)),
        latency: Math.max(0, Math.round(Date.now() - header.ts * 1000)),
        mode:    header.full ? "full" : "delta",
      });
      stats.count = 0; stats.started = now;
    }
  }

  // ── control helpers ────────────────────────────────────────────────────────
  function sendControl(command, payload) {
    if (!activeSession || !canControl) return;
    const socket = controlSocketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "session.command", session_token: activeSession.token, command, payload }));
      return;
    }
    remoteAccessApi.command(activeSession.id, { command, payload });
  }

  function sendAgentMsg(type, extra = {}) {
    const socket = controlSocketRef.current;
    if (socket?.readyState === WebSocket.OPEN)
      socket.send(JSON.stringify({ type, session_token: activeSession?.token, ...extra }));
  }

  function requestFiles(action, payload = {}) {
    if (!activeSession) return;
    setFileState(prev => ({ ...prev, loading: true }));
    remoteAccessApi.files(activeSession.id, { action, payload }).catch(err => {
      setFileState(prev => ({ ...prev, loading: false }));
      pushEvent("File command failed", apiErrorMessage(err, "Command failed."));
    });
  }

  // ── monitor switcher ───────────────────────────────────────────────────────
  function switchMonitor(index) {
    if (!activeSession) return;
    sendAgentMsg("monitor.select", { monitor_index: index });
    setActiveMonitor(index);
  }

  // ── terminal actions ───────────────────────────────────────────────────────
  function openTerminal() {
    if (!activeSession) return;
    const id = `term-${Date.now()}`;
    sendAgentMsg("terminal.command", {
      action: "create", terminal_id: id,
      payload: { cols: 120, rows: 36, title: `Shell ${terminals.length + 1}` },
    });
  }
  function closeTerminal(id) {
    sendAgentMsg("terminal.command", { action: "close", terminal_id: id });
    setTerminals(prev => prev.filter(t => t.id !== id));
    if (activeTerminalId === id)
      setActiveTerminalId(terminals.find(t => t.id !== id)?.id || null);
  }
  function sendTerminalInput(id, data) {
    sendAgentMsg("terminal.command", { action: "input", terminal_id: id, payload: { data } });
  }
  function handleTermInputKey(e) {
    if (!activeTerminalId) return;
    if (e.key === "Enter") {
      sendTerminalInput(activeTerminalId, termInput + "\n");
      setTermInput("");
    } else if (e.key === "Tab") {
      e.preventDefault();
      sendTerminalInput(activeTerminalId, "\t");
    } else if (e.ctrlKey && e.key === "c") {
      sendTerminalInput(activeTerminalId, "\x03");
    } else if (e.ctrlKey && e.key === "l") {
      e.preventDefault();
      setTerminals(prev => prev.map(t => t.id === activeTerminalId ? { ...t, output: "" } : t));
    }
  }

  // ── process actions ────────────────────────────────────────────────────────
  function killProcess(pid, sig = "TERMINATE") {
    if (!activeSession) return;
    sendAgentMsg("process.command", { action: "kill", payload: { pid, signal: sig } });
  }
  function fetchProcessDetails(pid) {
    if (!activeSession) return;
    setProcessDetails(null);
    setSelectedPid(pid);
    sendAgentMsg("process.command", { action: "details", payload: { pid } });
  }
  function refreshProcesses() {
    if (!activeSession) return;
    sendAgentMsg("process.command", { action: "list" });
  }

  // ── clipboard ──────────────────────────────────────────────────────────────
  async function receiveClipboard(text) {
    try {
      await navigator.clipboard?.writeText(text || "");
      pushEvent("Clipboard synced", "Remote clipboard copied locally.");
    } catch { pushEvent("Clipboard ready", "Permission blocked auto-write."); }
  }

  // ── mouse / keyboard screen handlers ──────────────────────────────────────
  const pointerRatios = e => {
    const box = screenRef.current.getBoundingClientRect();
    return {
      x_ratio: Math.max(0, Math.min(1, (e.clientX - box.left) / box.width)),
      y_ratio: Math.max(0, Math.min(1, (e.clientY - box.top)  / box.height)),
    };
  };
  const pBtn = e => e.button === 2 ? "right" : e.button === 1 ? "middle" : "left";
  const handleScreenClick       = e => { if (!screenRef.current || !canControl) return; screenRef.current.focus(); sendControl("mouse", { action: "click",  button: pBtn(e), ...pointerRatios(e) }); };
  const handleScreenContextMenu = e => { if (!screenRef.current || !canControl) return; e.preventDefault(); screenRef.current.focus(); sendControl("mouse", { action: "click", button: "right", ...pointerRatios(e) }); };
  const handleScreenMouseMove   = e => { if (!canControl) return; const now = performance.now(); if (now - frameStatsRef.current.lastMove < 25) return; frameStatsRef.current.lastMove = now; sendControl("mouse", { action: "move",  ...pointerRatios(e) }); };
  const handleScreenMouseDown   = e => { if (!canControl) return; screenRef.current?.focus(); sendControl("mouse", { action: "down",  button: pBtn(e), ...pointerRatios(e) }); };
  const handleScreenMouseUp     = e => { if (!canControl) return; sendControl("mouse", { action: "up",    button: pBtn(e), ...pointerRatios(e) }); };
  const handleScreenWheel       = e => { if (!canControl) return; e.preventDefault(); sendControl("mouse", { action: "scroll", delta: e.deltaY > 0 ? -5 : 5 }); };
  const handleScreenKeyDown     = async e => {
    if (!canControl) return;
    e.preventDefault();
    const mods = { ctrlKey: "ctrl", altKey: "alt", shiftKey: "shift", metaKey: "win" };
    const modifiers = Object.entries(mods).filter(([f]) => e[f]).map(([, v]) => v);
    const special = { Control:"ctrl", Shift:"shift", Alt:"alt", Meta:"win", Backspace:"backspace", Tab:"tab", Enter:"enter", Escape:"esc", Delete:"delete", ArrowUp:"up", ArrowDown:"down", ArrowLeft:"left", ArrowRight:"right", Home:"home", End:"end", PageUp:"pageup", PageDown:"pagedown", " ":"space" };
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "v") {
      const text = await navigator.clipboard?.readText?.().catch(() => "");
      if (text) sendControl("clipboard.set", { text });
      sendControl("keyboard", { key: "v", modifiers: ["ctrl"], event: "press" });
      return;
    }
    if ((e.ctrlKey || e.metaKey) && ["c","x"].includes(e.key.toLowerCase())) {
      sendControl("keyboard", { key: e.key.toLowerCase(), modifiers: ["ctrl"], event: "press" });
      window.setTimeout(() => sendControl("clipboard.get", {}), 250);
      return;
    }
    if (["Control","Shift","Alt","Meta"].includes(e.key)) { sendControl("keyboard", { key: special[e.key], event: "down" }); return; }
    if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) { sendControl("keyboard", { text: e.key }); return; }
    sendControl("keyboard", { key: special[e.key] || e.key.toLowerCase(), modifiers, event: "down" });
  };
  const handleScreenKeyUp = e => {
    if (!canControl) return;
    const special = { Control:"ctrl", Shift:"shift", Alt:"alt", Meta:"win" };
    if (special[e.key]) { e.preventDefault(); sendControl("keyboard", { key: special[e.key], event: "up" }); }
  };

  // ── transfer helpers (same as v2) ──────────────────────────────────────────
  function handleTransferMsg(msg, allowRaw = false) {
    if (msg.transfer) { mergeTransferUpdate(msg.transfer); return; }
    if (!allowRaw || !msg.transfer_id) return;
    mergeChunk(msg);
  }
  function handleAgentError(msg) {
    if (msg.transfer_id) {
      const id = String(msg.transfer_id);
      const job = remoteDownloadBuffers.current[id];
      if (job) {
        delete remoteDownloadBuffers.current[id];
        upsertTransferItem(job.key, {
          status: "failed",
          error: msg.message || "Transfer failed.",
          eta: 0,
          speed: 0,
        });
      }
    }
    pushEvent("Agent error", msg.message);
  }
  function mergeTransferUpdate(transfer) {
    const key     = `server-${transfer.id}`;
    const percent = Math.round(Number(transfer.progress_percent || 0));
    upsertTransferItem(key, {
      key, transferId: transfer.id,
      name: transfer.original_name || transfer.source_path || transfer.stored_name,
      size: transfer.size_bytes, type: transfer.content_type,
      percent, status: transfer.status === "COMPLETED" ? "completed" : transfer.status === "FAILED" ? "failed" : "uploading",
      uploadedBytes: transfer.transferred_bytes,
      downloadReady: transfer.status === "COMPLETED",
      error: transfer.error || "",
    });
  }
  function decodeB64(v) {
    const bin = atob(v || ""), bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes;
  }
  function saveBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a   = document.createElement("a");
    a.href = url; a.download = filename || "download";
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function mergeChunk(msg) {
    const id = String(msg.transfer_id);
    const job = remoteDownloadBuffers.current[id];
    if (!job) return;
    if (msg.total) job.total = Number(msg.total);
    if (msg.name)  job.name  = msg.name;
    if (msg.packaging) {
      upsertTransferItem(job.key, {
        name: msg.name || job.name,
        status: "packaging",
        packagingLabel: msg.label || (job.isFolder ? "Compressing..." : "Preparing..."),
        percent: 0,
        uploadedBytes: 0,
      });
      return;
    }
    const bytes = Number(msg.bytes || job.received || 0);
    if (msg.chunkBytes && bytes > job.received) { job.chunks.push(msg.chunkBytes); job.received = bytes; }
    else if (msg.chunk && bytes > job.received) { job.chunks.push(decodeB64(msg.chunk)); job.received = bytes; }
    const elapsed = Math.max((performance.now() - job.startedAt) / 1000, 0.1);
    const speed   = job.received / elapsed;
    upsertTransferItem(job.key, {
      percent: job.total ? Math.min(99, Math.round((job.received / job.total) * 100)) : 0,
      name: job.name, size: job.total || job.size || 0,
      uploadedBytes: job.received, speed,
      eta: speed && job.total ? Math.max(0, (job.total - job.received) / speed) : 0,
      status: msg.complete ? "completed" : "downloading",
    });
    if (msg.complete) {
      const blob = new Blob(job.chunks, { type: "application/octet-stream" });
      saveBlob(blob, job.name);
      delete remoteDownloadBuffers.current[id];
      upsertTransferItem(job.key, { percent: 100, eta: 0, status: "completed", downloadStatus: "saved" });
      pushEvent("Download completed", job.name);
    }
  }
  async function startRemoteDownload(entry) {
    if (!activeSession || !entry) return;
    const isFolder    = Boolean(entry.is_dir || entry.drive);
    const baseName    = safeDownloadName(entry.name || entry.path || "download");
    const downloadName= isFolder ? `${baseName.replace(/\.zip$/i, "")}.zip` : baseName;
    const key         = `remote-${entry.path}-${Date.now()}`;
    upsertTransferItem(key, { key, name: downloadName, size: entry.size || 0, percent: 0, speed: 0, eta: 0, status: "queued", uploadedBytes: 0 });
    try {
      const { data: transfer } = await remoteAccessApi.createTransfer({
        session: activeSession.id, direction: "DOWNLOAD",
        source_path: entry.path, target_path: "",
        original_name: downloadName,
        content_type:  isFolder ? "application/zip" : "application/octet-stream",
        size_bytes: entry.size || 0, chunk_size: 1024 * 1024,
      });
      remoteDownloadBuffers.current[String(transfer.id)] = {
        key, name: downloadName, total: entry.size || transfer.size_bytes || 0,
        received: 0, chunks: [], startedAt: performance.now(), isFolder,
      };
      upsertTransferItem(key, { transferId: transfer.id, status: "downloading" });
      pushEvent(isFolder ? "Folder download started" : "Download started", downloadName);
    } catch (err) {
      upsertTransferItem(key, { status: "failed", error: apiErrorMessage(err, "Could not start download.") });
    }
  }
  async function downloadTransferItem(item) {
    if (!item.transferId) return;
    const jobKey = String(item.transferId);
    const existing = downloadJobsRef.current[jobKey] || { chunks: [], received: 0, total: item.size || 0 };
    const controller = new AbortController();
    downloadJobsRef.current[jobKey] = { ...existing, controller };
    upsertTransferItem(item.key, { downloadStatus: "downloading", downloadPercent: 0 });
    try {
      const headers = {};
      const token = localStorage.getItem("accessToken");
      if (token) headers.Authorization = `Bearer ${token}`;
      if (existing.received > 0) headers.Range = `bytes=${existing.received}-`;
      const res = await fetch(remoteAccessApi.transferDownloadUrl(item.transferId), { headers, signal: controller.signal });
      if (!res.ok && res.status !== 206) throw new Error(`HTTP ${res.status}`);
      const total  = Number(res.headers.get("Content-Length") || existing.total || item.size || 0);
      const reader = res.body.getReader();
      let received = existing.received;
      const chunks = existing.chunks;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value); received += value.length;
        upsertTransferItem(item.key, { downloadStatus: "downloading", downloadPercent: total ? Math.round((received/total)*100) : 0 });
      }
      const blob = new Blob(chunks, { type: item.type || "application/octet-stream" });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a"); a.href = url; a.download = item.name || "download"; a.click();
      URL.revokeObjectURL(url);
      delete downloadJobsRef.current[jobKey];
      upsertTransferItem(item.key, { downloadStatus: "complete", downloadPercent: 100 });
    } catch (err) {
      if (err.name === "AbortError") { upsertTransferItem(item.key, { downloadStatus: "paused" }); return; }
      upsertTransferItem(item.key, { downloadStatus: "failed", error: err.message });
    }
  }
  function pauseDownload(item) {
    downloadJobsRef.current[String(item.transferId)]?.controller?.abort();
  }
  async function uploadSingleFile(file, path) {
    const chunkSize  = 2 * 1024 * 1024;
    const targetPath = path && path !== "Drives" ? path : "";
    const key        = `${file.name}-${file.size}-${Date.now()}`;
    upsertTransferItem(key, { key, name: file.name, size: file.size, percent: 0, speed: 0, eta: 0, status: "starting", uploadedBytes: 0 });
    try {
      const { data: transfer } = await remoteAccessApi.initiateUpload({
        session: activeSession.id, name: file.name, size_bytes: file.size,
        content_type: file.type || "application/octet-stream",
        chunk_size: chunkSize, target_path: targetPath,
      });
      const statusRes = await remoteAccessApi.uploadStatus(transfer.id);
      const missing   = new Set(statusRes.data.missing_chunks || Array.from({ length: transfer.total_chunks }, (_, i) => i));
      const started   = performance.now();
      for (let i = 0; i < transfer.total_chunks; i++) {
        if (!missing.has(i)) continue;
        const start = i * chunkSize, end = Math.min(file.size, start + chunkSize);
        const fd    = new FormData();
        fd.append("chunk_index", String(i));
        fd.append("chunk", file.slice(start, end), file.name);
        const res  = await remoteAccessApi.uploadChunk(transfer.id, fd);
        const done = Math.min(file.size, end);
        const elapsed = Math.max((performance.now() - started) / 1000, 0.1);
        const speed   = done / elapsed;
        upsertTransferItem(key, {
          transferId: transfer.id,
          percent: Math.round((done / Math.max(file.size, 1)) * 100),
          uploadedBytes: done, speed,
          eta: speed ? Math.max(0, (file.size - done) / speed) : 0,
          status: res.data.status === "COMPLETED" ? "completed" : "uploading",
          downloadReady: res.data.status === "COMPLETED",
        });
      }
      upsertTransferItem(key, { transferId: transfer.id, percent: 100, eta: 0, status: "completed", downloadReady: true });
      pushEvent("Upload completed", file.name);
    } catch (err) {
      upsertTransferItem(key, { status: "failed", error: apiErrorMessage(err, "Upload failed.") });
    }
  }
  function uploadFiles(files, path) {
    if (!activeSession || !files?.length) return;
    Array.from(files).forEach(f => uploadSingleFile(f, path));
  }

  // ── enable turbo ──────────────────────────────────────────────────────────
  const enableTurbo = () => setTurboMode(v => {
    const next = !v;
    setStreamSettings(next ? { fps: 30, quality: 82, max_width: 1600 } : { fps: 12, quality: 76, max_width: 1600 });
    return next;
  });

  // ── filtered processes ────────────────────────────────────────────────────
  const filteredProcesses = processes
    .filter(p => !processSearch || p.name.toLowerCase().includes(processSearch.toLowerCase()) || p.cmd.toLowerCase().includes(processSearch.toLowerCase()))
    .sort((a, b) => processSort === "cpu" ? b.cpu - a.cpu : processSort === "mem" ? b.mem - a.mem : a.name.localeCompare(b.name));

  // ─────────────────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen space-y-5 bg-[#06090f] p-4 text-slate-200 sm:p-6">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="relative overflow-hidden rounded-2xl border border-cyan-400/15 bg-slate-950/80 p-5 shadow-2xl shadow-cyan-950/40 backdrop-blur-2xl">
        <div className="pointer-events-none absolute inset-0" style={{ backgroundImage: "repeating-linear-gradient(0deg,transparent,transparent 39px,rgba(56,189,248,0.04) 39px,rgba(56,189,248,0.04) 40px),repeating-linear-gradient(90deg,transparent,transparent 39px,rgba(56,189,248,0.04) 39px,rgba(56,189,248,0.04) 40px)" }} />
        <div className="pointer-events-none absolute -right-20 -top-20 h-72 w-72 rounded-full bg-violet-500/15 blur-3xl" />
        <div className="pointer-events-none absolute -left-10 bottom-0 h-48 w-48 rounded-full bg-cyan-500/10 blur-2xl" />
        <div className="relative flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge icon={ShieldCheck} text="Secure Desktop Agent" color="cyan" />
              <Badge icon={Lock}        text="Approval Gated"        color="violet" />
              <Badge icon={socketStatus === "connected" ? Wifi : WifiOff}
                     text={`WebSocket: ${socketStatus}`}
                     color={socketStatus === "connected" ? "green" : "amber"} />
            </div>
            <h1 className="mt-3 bg-gradient-to-r from-cyan-200 via-white to-violet-200 bg-clip-text text-3xl font-black tracking-tight text-transparent sm:text-4xl">
              Remote Access Command Center
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              Multi-monitor streaming · Interactive terminal shell · Process manager · Full-drive transfers
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={enableTurbo} className={`flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-bold transition ${turboMode ? "border-fuchsia-400/60 bg-fuchsia-400/15 text-fuchsia-100" : "border-white/10 bg-white/[0.04] text-slate-200 hover:border-cyan-300/40"}`}>
              <Zap size={15} /> Turbo {turboMode ? "ON" : "OFF"}
            </button>
            <RegisterDevice agentServer={agentServer} onCreated={() => qc.invalidateQueries({ queryKey: ["remote-access-dashboard"] })} />
          </div>
        </div>
      </header>

      {/* ── Metric strip ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricCard icon={Monitor}         label="Devices"      value={summary.devices        || 0} />
        <MetricCard icon={Wifi}            label="Online"       value={summary.online         || 0} color="green" />
        <MetricCard icon={Activity}        label="Live Sessions" value={summary.active_sessions || 0} color="cyan" />
        <MetricCard icon={ArrowDownToLine} label="Transfers"    value={summary.transfers      || 0} color="amber" />
      </div>

      {/* ── Telemetry strip ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <TelemetryBar icon={Cpu}         label="CPU"     value={telemetry.cpu}     color="cyan"   />
        <TelemetryBar icon={Activity}    label="RAM"     value={telemetry.ram}     color="violet" />
        <TelemetryBar icon={HardDrive}   label="Disk"    value={telemetry.disk}    color="amber"  />
        <TelemetryBar icon={Battery}     label="Battery" value={telemetry.battery} color="green"  />
      </div>

      {/* ── Main grid ──────────────────────────────────────────────────────── */}
      <div className="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">

        {/* ── Left sidebar ─────────────────────────────────────────────────── */}
        <div className="space-y-4">

          {/* Agent network */}
          <Panel title="Agent Network">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500">Server URL</label>
            <input value={agentServer} onChange={e => setAgentServer(e.target.value.trim())}
              placeholder="ws://192.168.1.10:8001"
              className="mt-1 w-full rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/60" />
          </Panel>

          {/* Devices */}
          <Panel title="Connected Devices" action={
            <button onClick={() => dashboard.refetch()} className="rounded-lg border border-white/10 bg-white/[0.04] p-2 text-slate-300 hover:border-cyan-300/40">
              <RefreshCw size={15} />
            </button>
          }>
            <div className="space-y-3">
              {devices.map(device => (
                <DeviceCard key={device.id} device={device} active={activeDevice?.id === device.id}
                  agentServer={agentServer}
                  onClick={() => setSelectedDevice(device)}
                  onRemove={() => removeDevice.mutate(device.id)} />
              ))}
              {!devices.length && <Empty title="No devices yet" detail="Register a device and run the agent." />}
            </div>
          </Panel>

          {/* Connection request */}
          {activeDevice && (
            <Panel title="Connection Request">
              <div className="space-y-3">
                <div className="grid gap-2">
                  {PERMISSIONS.map(p => (
                    <button key={p.value} onClick={() => setPermission(p.value)}
                      className={`rounded-lg border px-3 py-2 text-left text-sm transition ${permission === p.value ? "border-cyan-300/60 bg-cyan-300/10" : "border-white/10 bg-white/[0.03] hover:border-white/20"}`}>
                      <span className="block font-semibold text-white">{p.label}</span>
                      <span className="text-xs text-slate-500">{p.detail}</span>
                    </button>
                  ))}
                </div>
                {/* Stream settings */}
                <details className="rounded-lg border border-white/10">
                  <summary className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm font-medium text-slate-300">
                    <SlidersHorizontal size={14} /> Stream settings
                  </summary>
                  <div className="space-y-3 px-3 pb-3 text-xs text-slate-400">
                    <SliderRow label="FPS" min={4} max={30} value={streamSettings.fps}
                      onChange={v => setStreamSettings(p => ({ ...p, fps: v }))} />
                    <SliderRow label="Quality" min={45} max={92} value={streamSettings.quality}
                      onChange={v => setStreamSettings(p => ({ ...p, quality: v }))} />
                    <label>Max Width
                      <select value={streamSettings.max_width}
                        onChange={e => setStreamSettings(p => ({ ...p, max_width: Number(e.target.value) }))}
                        className="ml-2 rounded border border-white/10 bg-slate-900 px-2 py-1 text-slate-100">
                        {[1280, 1600, 1920].map(w => <option key={w} value={w}>{w}</option>)}
                      </select>
                    </label>
                  </div>
                </details>
                {activeDevice.status === "OFFLINE" && (
                  <Notice tone="amber" title="Agent offline" detail="Start the agent on the target machine first." />
                )}
                <button disabled={requestSession.isPending || activeDevice.status === "OFFLINE"}
                  onClick={() => requestSession.mutate({ device: activeDevice, mode: permission })}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-400 px-4 py-2.5 text-sm font-bold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50 hover:bg-cyan-300 transition">
                  <Power size={15} /> Connect
                </button>
              </div>
            </Panel>
          )}

          {/* Token connect */}
          <TokenConnect initialToken={urlToken} devices={devices} agentServer={agentServer}
            permission={permission} setPermission={setPermission}
            pending={connectToken.isPending}
            onConnect={token => connectToken.mutate({ token: normalizeToken(token), mode: permission })} />

          {/* Events */}
          <Panel title="Activity">
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {[...events, ...logs.map(l => ({ type: l.action, detail: l.message }))].slice(0, 12).map((e, i) => (
                <div key={i} className="flex gap-2 rounded-lg border border-white/5 bg-white/[0.025] p-2">
                  <Circle className="mt-1 shrink-0 text-cyan-400" size={8} fill="currentColor" />
                  <div className="min-w-0">
                    <p className="truncate text-xs font-medium text-white">{e.type}</p>
                    <p className="truncate text-[11px] text-slate-500">{e.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        {/* ── Main right panel ─────────────────────────────────────────────── */}
        <div className="space-y-4">

          {/* Session strip */}
          {activeSession && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-slate-900/60 px-4 py-3">
              <div className="flex flex-wrap items-center gap-3">
                <SessionPill session={activeSession} />
                <span className="text-xs text-slate-500">
                  {streamStats.fps} FPS · {streamStats.latency} ms · {streamStats.mode}
                </span>
                {monitors.length > 1 && (
                  <div className="flex items-center gap-1">
                    <Layers size={13} className="text-slate-500" />
                    {monitors.map(m => (
                      <button key={m.index} onClick={() => switchMonitor(m.index)}
                        title={m.label}
                        className={`rounded px-2 py-0.5 text-xs transition ${activeMonitor === m.index ? "bg-cyan-400/20 text-cyan-100 border border-cyan-400/40" : "text-slate-400 hover:text-white border border-transparent"}`}>
                        {m.index === 0 ? "All" : `M${m.index}`}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <button onClick={() => disconnect.mutate(activeSession.id)}
                className="flex items-center gap-1.5 rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-200 hover:border-red-400/60 transition">
                <Square size={12} /> Disconnect
              </button>
            </div>
          )}

          {/* ── Tab navigation ─────────────────────────────────────────────── */}
          <div className="flex gap-1 rounded-xl border border-white/10 bg-slate-950/60 p-1">
            {[
              { id: "desktop",   icon: Monitor,   label: "Desktop"   },
              { id: "terminal",  icon: Terminal,  label: "Terminal"  },
              { id: "processes", icon: Activity,  label: "Processes" },
              { id: "files",     icon: HardDrive, label: "Files"     },
            ].map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition ${activeTab === tab.id ? "bg-slate-800 text-white shadow" : "text-slate-500 hover:text-slate-200"}`}>
                <tab.icon size={14} /> {tab.label}
              </button>
            ))}
          </div>

          {/* ── Desktop tab ────────────────────────────────────────────────── */}
          {activeTab === "desktop" && (
            <div ref={screenRef} tabIndex={0}
              onClick={handleScreenClick} onContextMenu={handleScreenContextMenu}
              onMouseMove={handleScreenMouseMove} onMouseDown={handleScreenMouseDown}
              onMouseUp={handleScreenMouseUp} onWheel={handleScreenWheel}
              onKeyDown={handleScreenKeyDown} onKeyUp={handleScreenKeyUp}
              className="relative aspect-video overflow-hidden rounded-xl border border-white/10 bg-slate-950 outline-none focus:border-cyan-300/50">
              {frame ? <img src={frame} alt="Remote desktop" className="h-full w-full object-contain" /> : null}
              <canvas ref={canvasRef} className={`h-full w-full object-contain ${frame ? "hidden" : "block"}`} />
              {!frame && !hasCanvasFrame && <DesktopPlaceholder session={activeSession} />}
              <div className="absolute bottom-3 left-3 flex gap-2">
                <ControlBtn disabled={!canControl} icon={MousePointer2} title="Mouse control" />
                <ControlBtn disabled={!canControl} icon={Keyboard} title="Keyboard control" />
                <ControlBtn icon={Maximize2} title="Fullscreen" onClick={() => screenRef.current?.requestFullscreen?.()} />
              </div>
              {monitors.length > 1 && activeSession && (
                <div className="absolute right-3 top-3 flex gap-1">
                  {monitors.map(m => (
                    <button key={m.index} onClick={e => { e.stopPropagation(); switchMonitor(m.index); }}
                      className={`rounded px-2 py-0.5 text-xs backdrop-blur transition ${activeMonitor === m.index ? "bg-cyan-400/30 text-cyan-100" : "bg-black/50 text-slate-300 hover:bg-white/10"}`}>
                      {m.index === 0 ? "All" : `M${m.index}`}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Terminal tab ────────────────────────────────────────────────── */}
          {activeTab === "terminal" && (
            <div className="rounded-xl border border-white/10 bg-slate-950/80 overflow-hidden">
              {/* Terminal tabs bar */}
              <div className="flex items-center gap-1 border-b border-white/10 bg-slate-950/60 px-3 py-2">
                {terminals.map(t => (
                  <div key={t.id}
                    onClick={() => setActiveTerminalId(t.id)}
                    className={`flex items-center gap-2 rounded-md px-3 py-1 text-xs cursor-pointer select-none transition ${activeTerminalId === t.id ? "bg-slate-800 text-white" : "text-slate-500 hover:text-slate-300"}`}>
                    <Terminal size={11} className={t.alive ? "text-green-400" : "text-red-400"} />
                    {t.title}
                    <button onClick={e => { e.stopPropagation(); closeTerminal(t.id); }}
                      className="ml-1 rounded text-slate-500 hover:text-red-300">
                      <XCircle size={11} />
                    </button>
                  </div>
                ))}
                <button onClick={openTerminal} disabled={!activeSession}
                  className="ml-auto flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-semibold text-slate-200 hover:border-cyan-300/40 disabled:opacity-40 transition">
                  <Plus size={12} /> New Shell
                </button>
              </div>

              {/* Terminal output */}
              {terminals.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-4 py-16">
                  <Terminal className="text-slate-600" size={40} />
                  <p className="text-sm font-medium text-slate-400">No active terminal</p>
                  <p className="text-xs text-slate-600">Start a session and click &quot;New Shell&quot;</p>
                  {activeSession && (
                    <button onClick={openTerminal}
                      className="flex items-center gap-2 rounded-lg bg-cyan-400 px-4 py-2 text-sm font-bold text-slate-950 hover:bg-cyan-300 transition">
                      <Plus size={14} /> Open Terminal
                    </button>
                  )}
                </div>
              ) : (() => {
                const activeTerm = terminals.find(t => t.id === activeTerminalId);
                return (
                  <div className="flex flex-col" style={{ height: "480px" }}>
                    <div ref={el => { if (el && activeTerminalId) termOutputRefs.current[activeTerminalId] = el; }}
                      className="flex-1 overflow-y-auto bg-[#0a0d13] p-3 font-mono text-xs leading-relaxed text-green-300"
                      style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                      {activeTerm?.output || <span className="text-slate-600">Waiting for shell output…</span>}
                    </div>
                    {/* Input line */}
                    <div className="flex items-center gap-2 border-t border-white/10 bg-slate-900/80 px-3 py-2">
                      <span className="font-mono text-xs text-cyan-400">$</span>
                      <input ref={termInputRef}
                        value={termInput}
                        onChange={e => setTermInput(e.target.value)}
                        onKeyDown={handleTermInputKey}
                        placeholder="Type command… (Enter to run, Ctrl+C to interrupt)"
                        disabled={!activeTerm?.alive}
                        className="flex-1 bg-transparent font-mono text-xs text-white outline-none placeholder:text-slate-600 disabled:opacity-40" />
                      <button onClick={() => { if (activeTerminalId) { sendTerminalInput(activeTerminalId, termInput + "\n"); setTermInput(""); } }}
                        disabled={!activeTerm?.alive || !termInput}
                        className="rounded border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-slate-300 disabled:opacity-30 hover:border-cyan-300/40 transition">
                        Run
                      </button>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {/* ── Process manager tab ─────────────────────────────────────────── */}
          {activeTab === "processes" && (
            <div className="rounded-xl border border-white/10 bg-slate-950/80 overflow-hidden">
              {/* Toolbar */}
              <div className="flex flex-wrap items-center gap-2 border-b border-white/10 bg-slate-950/60 px-4 py-3">
                <div className="flex flex-1 items-center gap-2 rounded-lg border border-white/10 bg-slate-900 px-3 py-1.5">
                  <Search size={13} className="shrink-0 text-slate-500" />
                  <input value={processSearch} onChange={e => setProcessSearch(e.target.value)}
                    placeholder="Search processes…"
                    className="flex-1 bg-transparent text-xs text-white outline-none placeholder:text-slate-600" />
                </div>
                <div className="flex gap-1 text-xs">
                  {[["cpu","CPU"],["mem","Mem"],["name","Name"]].map(([k,l]) => (
                    <button key={k} onClick={() => setProcessSort(k)}
                      className={`rounded-lg px-2 py-1.5 font-semibold transition ${processSort === k ? "bg-cyan-400/15 text-cyan-200" : "text-slate-500 hover:text-slate-200"}`}>
                      {l}
                    </button>
                  ))}
                </div>
                <button onClick={refreshProcesses} disabled={!activeSession}
                  className="rounded-lg border border-white/10 bg-white/[0.04] p-2 text-slate-300 hover:border-cyan-300/40 disabled:opacity-40 transition">
                  <RefreshCw size={14} />
                </button>
                <span className="text-xs text-slate-600">{processes.length} procs</span>
              </div>

              {/* Process table */}
              <div className="overflow-auto" style={{ maxHeight: "520px" }}>
                {!activeSession ? (
                  <div className="py-16 text-center">
                    <Activity className="mx-auto text-slate-600" size={36} />
                    <p className="mt-3 text-sm text-slate-400">Connect a session to view processes</p>
                  </div>
                ) : filteredProcesses.length === 0 ? (
                  <div className="py-12 text-center text-sm text-slate-500">
                    {processes.length ? "No matching processes" : "Waiting for process snapshot…"}
                  </div>
                ) : (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-white/10 bg-slate-950/60 text-slate-500 text-left">
                        <th className="px-4 py-2 font-semibold">PID</th>
                        <th className="px-4 py-2 font-semibold">Name</th>
                        <th className="px-4 py-2 font-semibold text-right">CPU%</th>
                        <th className="px-4 py-2 font-semibold text-right">Memory</th>
                        <th className="px-4 py-2 font-semibold">Status</th>
                        <th className="px-4 py-2 font-semibold">User</th>
                        <th className="px-4 py-2 font-semibold">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredProcesses.map(p => (
                        <tr key={p.pid}
                          onClick={() => fetchProcessDetails(p.pid)}
                          className={`cursor-pointer border-b border-white/5 transition hover:bg-white/[0.035] ${selectedPid === p.pid ? "bg-cyan-400/[0.07]" : ""}`}>
                          <td className="px-4 py-1.5 font-mono text-slate-400">{p.pid}</td>
                          <td className="max-w-[200px] truncate px-4 py-1.5 font-medium text-white">{p.name}</td>
                          <td className="px-4 py-1.5 text-right">
                            <span className={`font-mono font-bold ${p.cpu > 20 ? "text-red-300" : p.cpu > 5 ? "text-amber-300" : "text-slate-300"}`}>
                              {p.cpu.toFixed(1)}
                            </span>
                          </td>
                          <td className="px-4 py-1.5 text-right font-mono text-slate-300">{formatBytes(p.mem)}</td>
                          <td className="px-4 py-1.5">
                            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${p.status === "running" ? "bg-green-400/15 text-green-300" : p.status === "sleeping" ? "bg-slate-700 text-slate-400" : "bg-amber-400/15 text-amber-300"}`}>
                              {p.status}
                            </span>
                          </td>
                          <td className="max-w-[100px] truncate px-4 py-1.5 text-slate-500">{p.user}</td>
                          <td className="px-4 py-1.5">
                            <div className="flex items-center gap-1">
                              <button onClick={e => { e.stopPropagation(); killProcess(p.pid, "TERMINATE"); }}
                                title="Terminate" className="rounded border border-red-400/25 bg-red-400/10 px-1.5 py-0.5 text-red-200 hover:border-red-400/60 transition">
                                <XCircle size={11} />
                              </button>
                              <button onClick={e => { e.stopPropagation(); killProcess(p.pid, "KILL"); }}
                                title="Force kill" className="rounded border border-orange-400/25 bg-orange-400/10 px-1.5 py-0.5 text-orange-200 hover:border-orange-400/60 transition">
                                <AlertTriangle size={11} />
                              </button>
                              <button onClick={e => { e.stopPropagation(); killProcess(p.pid, p.status === "stopped" ? "RESUME" : "SUSPEND"); }}
                                title={p.status === "stopped" ? "Resume" : "Suspend"}
                                className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-slate-300 hover:border-cyan-300/40 transition">
                                {p.status === "stopped" ? <Play size={11} /> : <Pause size={11} />}
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {/* Process detail drawer */}
              {processDetails && (
                <div className="border-t border-white/10 bg-slate-900/80 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-sm font-bold text-white">{processDetails.name} <span className="text-slate-500">({processDetails.pid})</span></h3>
                    <button onClick={() => setProcessDetails(null)} className="text-slate-500 hover:text-white">
                      <XCircle size={16} />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
                    {[
                      ["Exe",        processDetails.exe || "—"],
                      ["Status",     processDetails.status],
                      ["CPU",        `${processDetails.cpu?.toFixed(1)}%`],
                      ["RSS",        formatBytes(processDetails.mem_rss)],
                      ["VMS",        formatBytes(processDetails.mem_vms)],
                      ["Threads",    processDetails.threads],
                      ["Connections", processDetails.connections],
                      ["Open Files", processDetails.open_files],
                      ["User",       processDetails.user],
                      ["Parent PID", processDetails.parent_pid],
                      ["Nice",       processDetails.nice],
                      ["Started",    processDetails.started ? new Date(processDetails.started * 1000).toLocaleString() : "—"],
                    ].map(([k, v]) => (
                      <div key={k} className="rounded-lg border border-white/10 bg-white/[0.03] p-2">
                        <p className="text-[10px] uppercase tracking-wider text-slate-500">{k}</p>
                        <p className="mt-0.5 truncate font-mono font-medium text-slate-200">{v}</p>
                      </div>
                    ))}
                  </div>
                  {processDetails.cmdline && (
                    <div className="mt-2 rounded-lg border border-white/10 bg-slate-950/60 p-2">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500">Command</p>
                      <p className="mt-1 break-all font-mono text-xs text-slate-300">{processDetails.cmdline}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ── Files tab ───────────────────────────────────────────────────── */}
          {activeTab === "files" && (
            <div className="rounded-xl border border-white/10 bg-slate-950/80">
              {/* Toolbar */}
              <div className="flex flex-wrap items-center gap-2 border-b border-white/10 bg-slate-950/60 px-4 py-3">
                <div className="flex flex-wrap items-center gap-1 text-xs text-slate-400">
                  {buildBreadcrumbs(fileState.path).map((crumb, i) => (
                    <button key={i} onClick={() => crumb.path && requestFiles("list", { path: crumb.path })}
                      className="flex items-center gap-1 rounded px-1 text-slate-300 hover:text-cyan-300 transition">
                      {i > 0 && <ChevronRight size={11} className="text-slate-600" />}
                      {crumb.label}
                    </button>
                  ))}
                  {fileState.loading && <span className="text-cyan-400 animate-pulse">Loading…</span>}
                </div>
                <div className="ml-auto flex items-center gap-2">
                  <div className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-slate-900 px-2.5 py-1.5 text-xs">
                    <Search size={11} className="text-slate-500" />
                    <input value={fileSearch} onChange={e => setFileSearch(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === "Enter" && fileSearch.trim())
                          requestFiles("search", { root: fileState.path || "/", query: fileSearch.trim() });
                      }}
                      placeholder="Search… (Enter)"
                      className="w-28 bg-transparent text-slate-200 outline-none placeholder:text-slate-600" />
                  </div>
                  <button onClick={() => requestFiles("drives")} disabled={!canFiles}
                    className="rounded-lg border border-white/10 bg-white/[0.04] p-2 text-slate-300 hover:border-cyan-300/40 disabled:opacity-40 transition" title="Show drives">
                    <HardDrive size={14} />
                  </button>
                  <label className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-xs text-slate-200 hover:border-cyan-300/40 transition" title="Upload files">
                    <Upload size={13} /> Upload
                    <input type="file" multiple className="hidden" onChange={e => { uploadFiles(e.target.files, fileState.path); e.target.value = ""; }} />
                  </label>
                </div>
              </div>

              {/* Search results */}
              {searchResults && (
                <div className="border-b border-white/10 bg-slate-900/40 px-4 py-3">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-xs font-semibold text-cyan-300">
                      Search: &quot;{searchResults.query}&quot; — {searchResults.count} results
                    </p>
                    <button onClick={() => setSearchResults(null)} className="text-xs text-slate-500 hover:text-white">Clear</button>
                  </div>
                  <div className="max-h-48 overflow-y-auto space-y-1">
                    {(searchResults.results || []).map(item => (
                      <div key={item.path} className="flex items-center justify-between gap-2 rounded-lg border border-white/5 bg-white/[0.025] px-3 py-1.5 text-xs">
                        <div className="flex min-w-0 items-center gap-2">
                          {item.is_dir ? <Folder size={13} className="shrink-0 text-cyan-400" /> : <File size={13} className="shrink-0 text-slate-400" />}
                          <span className="truncate text-white">{item.path}</span>
                        </div>
                        <div className="flex shrink-0 gap-1">
                          {!item.is_dir && (
                            <button onClick={() => startRemoteDownload(item)}
                              className="rounded border border-cyan-300/25 bg-cyan-300/10 px-1.5 py-0.5 text-cyan-100 hover:border-cyan-300/50">
                              <Download size={11} />
                            </button>
                          )}
                          <button onClick={() => requestFiles("list", { path: item.is_dir ? item.path : item.path.replace(/[^/\\]*$/, "") })}
                            className="rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-slate-200 hover:border-white/20">
                            <Folder size={11} />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Not connected notice */}
              {!canFiles && (
                <div className="p-8 text-center">
                  <HardDrive className="mx-auto text-slate-600" size={36} />
                  <p className="mt-3 text-sm font-medium text-slate-300">File permission required</p>
                  <p className="mt-1 text-xs text-slate-500">Start a File access or Desktop + disk session.</p>
                </div>
              )}

              {/* Transfer rows */}
              {canFiles && transferItems.length > 0 && (
                <div className="space-y-2 border-b border-white/10 p-3">
                  {transferItems.slice(0, 5).map(item => (
                    <TransferRow key={item.key || item.transferId} item={item}
                      onDownload={downloadTransferItem} onPause={pauseDownload} />
                  ))}
                </div>
              )}

              {/* File list */}
              {canFiles && (
                <div className="max-h-[480px] overflow-y-auto">
                  {/* Drive grid when at root */}
                  {(fileState.path === "Drives" || !fileState.path) && fileState.entries.filter(e => e.drive).length > 0 && (
                    <div className="grid gap-3 p-3 sm:grid-cols-2 lg:grid-cols-3">
                      {fileState.entries.filter(e => e.drive).map(drive => (
                        <DriveCard key={drive.path} drive={drive}
                          onOpen={() => requestFiles("list", { path: drive.path })}
                          onDownload={() => startRemoteDownload(drive)} />
                      ))}
                    </div>
                  )}
                  {/* Regular file list */}
                  {fileState.entries.filter(e => !e.drive).map(entry => (
                    <div key={entry.path}
                      className="grid items-center gap-3 border-b border-white/5 px-4 py-2 text-xs last:border-b-0 hover:bg-white/[0.025]"
                      style={{ gridTemplateColumns: "1fr auto auto auto" }}>
                      <button onClick={() => entry.is_dir && requestFiles("list", { path: entry.path })}
                        className="flex min-w-0 items-center gap-2 text-left">
                        {entry.is_dir
                          ? <Folder size={15} className="shrink-0 text-cyan-400" />
                          : <File   size={15} className="shrink-0 text-slate-500" />}
                        <span className="truncate font-medium text-slate-200">{entry.name}</span>
                      </button>
                      <span className="text-slate-600">{entry.is_dir ? "—" : formatBytes(entry.size)}</span>
                      <button onClick={() => startRemoteDownload(entry)}
                        className="flex items-center gap-1 rounded border border-white/10 bg-white/[0.04] px-2 py-1 text-cyan-200 hover:border-cyan-300/40 transition">
                        <Download size={11} /> DL
                      </button>
                      <button disabled={entry.is_dir} onClick={() => requestFiles("delete", { path: entry.path })}
                        className="rounded border border-white/5 bg-white/[0.02] p-1 text-red-400 disabled:text-slate-700 hover:border-red-400/30 transition">
                        <Trash2 size={11} />
                      </button>
                    </div>
                  ))}
                  {canFiles && !fileState.loading && !fileState.entries.length && (
                    <div className="p-8 text-center">
                      <Empty title="Empty directory" detail="No files found in this location." />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// SMALL COMPONENTS
// ══════════════════════════════════════════════════════════════════════════════

function Badge({ icon: Icon, text, color = "slate" }) {
  const colors = {
    cyan:   "border-cyan-300/20 bg-cyan-300/10 text-cyan-100",
    violet: "border-violet-300/20 bg-violet-300/10 text-violet-100",
    green:  "border-emerald-300/20 bg-emerald-300/10 text-emerald-100",
    amber:  "border-amber-300/20 bg-amber-300/10 text-amber-100",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-[0.15em] ${colors[color] || colors.cyan}`}>
      <Icon size={11} /> {text}
    </span>
  );
}

function MetricCard({ icon: Icon, label, value, color = "slate" }) {
  const tones = { slate: "text-slate-300", green: "text-emerald-300", cyan: "text-cyan-300", amber: "text-amber-300" };
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/60 p-4">
      <Icon className={tones[color]} size={18} />
      <p className="mt-2 text-2xl font-black text-white">{value}</p>
      <p className="text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
    </div>
  );
}

function TelemetryBar({ icon: Icon, label, value, color = "cyan" }) {
  const numeric = value === null || value === undefined ? null : Number(value);
  const safe    = numeric === null || isNaN(numeric) ? 0 : Math.max(0, Math.min(100, numeric));
  const colors  = {
    cyan:   "text-cyan-300  bg-cyan-300/10  border-cyan-300/20  fill-cyan-300",
    violet: "text-violet-300 bg-violet-300/10 border-violet-300/20 fill-violet-300",
    amber:  "text-amber-300  bg-amber-300/10  border-amber-300/20  fill-amber-300",
    green:  "text-emerald-300 bg-emerald-300/10 border-emerald-300/20 fill-emerald-300",
  };
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/60 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className={`grid h-9 w-9 place-items-center rounded-lg border ${colors[color]}`}><Icon size={16} /></span>
        <span className="text-lg font-black text-white">{numeric === null || isNaN(numeric) ? "n/a" : `${Math.round(numeric)}%`}</span>
      </div>
      <p className="mt-2 text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
      <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-slate-800">
        <div className={`h-full ${colors[color].split(" ").find(c => c.startsWith("bg-")) || "bg-cyan-300"}`} style={{ width: `${safe}%` }} />
      </div>
    </div>
  );
}

function Panel({ title, action, children }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/70 p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-white">{title}</h2>
        {action}
      </div>
      {children}
    </div>
  );
}

function Notice({ tone = "amber", title, detail }) {
  const t = {
    amber: "border-amber-300/25 bg-amber-300/10 text-amber-100",
    green: "border-emerald-300/25 bg-emerald-300/10 text-emerald-100",
    red:   "border-red-300/25 bg-red-300/10 text-red-100",
  };
  return (
    <div className={`rounded-lg border px-3 py-2 text-xs ${t[tone]}`}>
      <p className="font-bold">{title}</p>
      {detail && <p className="mt-0.5 opacity-75">{detail}</p>}
    </div>
  );
}

function SliderRow({ label, min, max, value, onChange }) {
  return (
    <label className="flex items-center gap-3">
      <span className="w-14 shrink-0">{label}</span>
      <input type="range" min={min} max={max} value={value} onChange={e => onChange(Number(e.target.value))} className="flex-1" />
      <span className="w-8 text-right text-cyan-300">{value}</span>
    </label>
  );
}

function DeviceCard({ device, active, agentServer, onClick, onRemove }) {
  const online = device.status === "ONLINE" || device.status === "BUSY";
  return (
    <div role="button" tabIndex={0} onClick={onClick} onKeyDown={e => e.key === "Enter" && onClick()}
      className={`rounded-xl border p-4 text-left transition cursor-pointer ${active ? "border-cyan-300/50 bg-cyan-300/10" : "border-white/10 bg-white/[0.03] hover:border-white/20"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-bold text-white">{device.name}</p>
          <p className="mt-0.5 text-xs text-slate-500">{device.hostname || "Awaiting heartbeat"}</p>
        </div>
        <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-bold ${online ? "bg-emerald-400/10 text-emerald-200" : "bg-slate-700 text-slate-400"}`}>
          {online ? <Wifi size={10} /> : <WifiOff size={10} />} {device.status}
        </span>
      </div>
      {/* Capabilities badges */}
      {device.capabilities && (
        <div className="mt-2 flex flex-wrap gap-1">
          {device.capabilities.multi_monitor && <span className="rounded-full bg-violet-400/10 px-2 py-0.5 text-[10px] font-bold text-violet-300">Multi-monitor</span>}
          {device.capabilities.terminal && <span className="rounded-full bg-cyan-400/10 px-2 py-0.5 text-[10px] font-bold text-cyan-300">Terminal</span>}
          {device.capabilities.process_manager && <span className="rounded-full bg-amber-400/10 px-2 py-0.5 text-[10px] font-bold text-amber-300">Processes</span>}
        </div>
      )}
      <div className="mt-3 rounded-lg border border-white/10 bg-black/20 p-2">
        <p className="text-[10px] uppercase tracking-wider text-slate-500">Token</p>
        <code className="mt-0.5 block truncate text-[11px] text-cyan-200">{device.token}</code>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-1.5">
        <TinyBtn onClick={() => navigator.clipboard?.writeText(device.token)} icon={Copy} label="Token" />
        <TinyBtn onClick={() => navigator.clipboard?.writeText(agentCommand(device.token, agentServer))} icon={Copy} label="Agent cmd" />
        <TinyBtn onClick={() => navigator.clipboard?.writeText(clientAccessUrl(device.token))} icon={Copy} label="Client URL" />
        <TinyBtn danger onClick={onRemove} icon={Trash2} label="Delete" />
      </div>
    </div>
  );
}

function TinyBtn({ icon: Icon, label, onClick, danger = false }) {
  return (
    <button type="button" onClick={e => { e.stopPropagation(); onClick?.(); }}
      className={`flex items-center justify-center gap-1 rounded-lg border px-2 py-1.5 text-[11px] font-semibold transition ${danger ? "border-red-300/20 bg-red-400/10 text-red-200 hover:border-red-300/40" : "border-white/10 bg-white/[0.04] text-slate-300 hover:border-cyan-300/30"}`}>
      <Icon size={11} /> {label}
    </button>
  );
}

function SessionPill({ session }) {
  const active = session.status === "ACTIVE";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold ${active ? "bg-emerald-400/10 text-emerald-200" : "bg-amber-400/10 text-amber-200"}`}>
      {active ? <CheckCircle2 size={12} /> : <RefreshCw size={12} />}
      {session.status} · {session.permission}
    </span>
  );
}

function ControlBtn({ icon: Icon, title, disabled, onClick }) {
  return (
    <button disabled={disabled} onClick={onClick} title={title}
      className="rounded-lg border border-white/10 bg-slate-950/90 p-2 text-slate-300 disabled:opacity-40 hover:border-cyan-300/40 transition">
      <Icon size={15} />
    </button>
  );
}

function DesktopPlaceholder({ session }) {
  return (
    <div className="grid h-full place-items-center p-8 text-center">
      <Monitor className="mx-auto text-slate-700" size={48} />
      <p className="mt-3 text-sm font-bold text-slate-300">
        {session ? "Waiting for frames" : "No active session"}
      </p>
      <p className="mt-1 text-xs text-slate-600">
        {session ? "Approval required on target machine." : "Connect a device to start streaming."}
      </p>
    </div>
  );
}

function DriveCard({ drive, onOpen, onDownload }) {
  const percent = Math.max(0, Math.min(100, Number(drive.usage_percent || 0)));
  const isWarn  = drive.health === "warning", isCrit = drive.health === "critical";
  return (
    <div onClick={onOpen} className="cursor-pointer rounded-xl border border-white/10 bg-slate-900/60 p-3 transition hover:border-cyan-300/30 hover:-translate-y-0.5">
      <div className="flex items-center justify-between gap-2">
        <HardDrive size={16} className="text-cyan-400" />
        <span className={`rounded-full px-2 py-0.5 text-[10px] font-black uppercase ${isCrit ? "bg-red-400/15 text-red-200" : isWarn ? "bg-amber-400/15 text-amber-200" : "bg-emerald-400/15 text-emerald-200"}`}>
          {drive.health}
        </span>
      </div>
      <p className="mt-2 truncate text-sm font-bold text-white">{drive.name}</p>
      <p className="text-[10px] uppercase tracking-wider text-slate-600">{drive.category}</p>
      <div className="mt-3">
        <div className="flex justify-between text-[10px] text-slate-500 mb-1">
          <span>{formatBytes(drive.free)} free</span>
          <span>{formatBytes(drive.total)}</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
          <div className={`h-full ${isCrit ? "bg-red-400" : isWarn ? "bg-amber-400" : "bg-cyan-400"}`} style={{ width: `${percent}%` }} />
        </div>
      </div>
      <div className="mt-2 flex justify-end">
        <button onClick={e => { e.stopPropagation(); onDownload?.(); }}
          className="flex items-center gap-1 rounded border border-cyan-300/25 bg-cyan-300/10 px-2 py-0.5 text-[10px] text-cyan-100 hover:border-cyan-300/50 transition">
          <Download size={10} /> ZIP
        </button>
      </div>
    </div>
  );
}

function TransferRow({ item, onDownload, onPause }) {
  const pct    = Math.max(0, Math.min(100, item.percent || 0));
  const failed = item.status === "failed";
  const active = ["starting","uploading","downloading","packaging"].includes(item.status);
  const FIcon  = fileIcon(item);
  return (
    <div className="rounded-lg border border-white/10 bg-slate-900/60 p-2.5">
      <div className="flex items-start gap-2.5">
        <FIcon className={`mt-0.5 shrink-0 ${failed ? "text-red-300" : "text-cyan-300"}`} size={15} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <p className="truncate text-xs font-medium text-white">{item.name}</p>
            <span className="text-[10px] text-slate-500 shrink-0">{pct}%</span>
          </div>
          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-slate-800">
            <div className={`h-full ${failed ? "bg-red-400" : "bg-cyan-400"}`} style={{ width: `${pct}%` }} />
          </div>
          <div className="mt-1 flex flex-wrap gap-3 text-[10px] text-slate-500">
            <span>{formatBytes(item.uploadedBytes || 0)} / {formatBytes(item.size || 0)}</span>
            {item.status === "packaging" && <span className="text-amber-300">{item.packagingLabel || "Preparing..."}</span>}
            {active && item.status !== "packaging" && <span>{formatBytes(item.speed || 0)}/s</span>}
            {active && <span>ETA {formatDuration(item.eta || 0)}</span>}
            {item.error && <span className="text-red-300">{item.error}</span>}
          </div>
        </div>
        {item.downloadReady && (
          item.downloadStatus === "downloading"
            ? <button onClick={() => onPause?.(item)} className="rounded border border-white/10 bg-white/[0.04] p-1.5 text-slate-300 hover:border-cyan-300/40 transition"><Pause size={12} /></button>
            : <button onClick={() => onDownload?.(item)} className="rounded border border-white/10 bg-white/[0.04] p-1.5 text-slate-300 hover:border-cyan-300/40 transition">
                {item.downloadStatus === "paused" ? <Play size={12} /> : <Download size={12} />}
              </button>
        )}
      </div>
    </div>
  );
}

function Empty({ title, detail }) {
  return (
    <div className="rounded-xl border border-dashed border-white/10 bg-white/[0.015] p-6 text-center">
      <p className="font-medium text-slate-300">{title}</p>
      <p className="mt-1 text-xs text-slate-600">{detail}</p>
    </div>
  );
}

// ── Token connect ─────────────────────────────────────────────────────────────
function TokenConnect({ initialToken = "", devices = [], agentServer, permission, setPermission, pending, onConnect }) {
  const [token, setToken] = useState(initialToken);
  useEffect(() => { if (initialToken) setToken(initialToken); }, [initialToken]);
  const clean        = normalizeToken(token);
  const knownDevice  = devices.find(d => d.token === clean);
  const offlineDevice= knownDevice?.status === "OFFLINE" ? knownDevice : null;
  return (
    <Panel title="Connect by Token">
      <div className="space-y-3">
        <input value={token} onChange={e => setToken(e.target.value)}
          placeholder="Paste token or URL…"
          className="w-full rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/60" />
        <select value={permission} onChange={e => setPermission(e.target.value)}
          className="w-full rounded-lg border border-white/10 bg-slate-900 px-3 py-2 text-sm text-slate-200">
          {PERMISSIONS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
        </select>
        {offlineDevice && (
          <Notice tone="amber" title="Device offline"
            detail={`Run: ${agentCommand(offlineDevice.token, agentServer)}`} />
        )}
        <button disabled={!clean || pending || Boolean(offlineDevice)}
          onClick={() => onConnect(clean)}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-bold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50 hover:bg-slate-100 transition">
          <Power size={14} /> Send Approval Request
        </button>
      </div>
    </Panel>
  );
}

// ── Register device modal ─────────────────────────────────────────────────────
function RegisterDevice({ agentServer, onCreated }) {
  const [open,       setOpen]       = useState(false);
  const [form,       setForm]       = useState(INITIAL_REGISTER_DEVICE_FORM);
  const [token,      setToken]      = useState("");
  const [error,      setError]      = useState("");
  const [submitting, setSubmitting] = useState(false);
  const dialogRef    = useRef(null);
  const nameInputRef = useRef(null);
  const triggerRef   = useRef(null);

  const closeModal = useCallback(() => setOpen(false), []);
  const openModal = () => {
    setForm(INITIAL_REGISTER_DEVICE_FORM);
    setToken("");
    setError("");
    setSubmitting(false);
    setOpen(true);
  };

  useEffect(() => {
    if (!open) return undefined;

    const previousOverflow = document.body.style.overflow;
    const previousActiveElement = document.activeElement;
    const focusFrame = requestAnimationFrame(() => nameInputRef.current?.focus());
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
      cancelAnimationFrame(focusFrame);
      if (previousActiveElement instanceof HTMLElement) previousActiveElement.focus();
    };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;

    const focusableSelector = [
      "a[href]",
      "button:not([disabled])",
      "input:not([disabled])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "[tabindex]:not([tabindex='-1'])",
    ].join(",");

    const handleKeyDown = event => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeModal();
        return;
      }

      if (event.key !== "Tab" || !dialogRef.current) return;

      const focusable = Array.from(dialogRef.current.querySelectorAll(focusableSelector))
        .filter(el => !el.hasAttribute("disabled") && el.getAttribute("aria-hidden") !== "true");

      if (!focusable.length) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [closeModal, open]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.name.trim() || submitting) return;

    setError("");
    setToken("");
    setSubmitting(true);

    try {
      const payload = {
        name: form.name.trim(),
        hostname: form.hostname.trim(),
        platform: form.platform,
        metadata: form.notes.trim() ? { registration_notes: form.notes.trim() } : {},
      };
      const res = await remoteAccessApi.createDevice(payload);
      setToken(res.data.token);
      onCreated?.();
    } catch (err) {
      setError(apiErrorMessage(err, "Could not create device."));
    } finally {
      setSubmitting(false);
    }
  }

  const modalTitleId = "register-desktop-agent-title";
  const modalDescriptionId = "register-desktop-agent-description";
  const nameFieldId = "register-device-name";
  const hostnameFieldId = "register-device-hostname";
  const notesFieldId = "register-device-notes";

  const modal = typeof document !== "undefined" ? createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/75 p-4 backdrop-blur-[8px] sm:p-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
          onMouseDown={event => {
            if (event.target === event.currentTarget) closeModal();
          }}
        >
          <motion.form
            ref={dialogRef}
            onSubmit={handleSubmit}
            role="dialog"
            aria-modal="true"
            aria-labelledby={modalTitleId}
            aria-describedby={modalDescriptionId}
            aria-busy={submitting}
            className="flex max-h-[calc(100vh-32px)] w-[550px] max-w-[95vw] flex-col overflow-hidden rounded-[24px] border border-white/[0.08] bg-[#090f1f] text-white shadow-[0_32px_120px_rgba(139,92,246,0.26),0_18px_60px_rgba(0,0,0,0.58),inset_0_1px_0_rgba(255,255,255,0.08)] outline-none sm:max-h-[calc(100vh-48px)]"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
          >
            <p id={modalDescriptionId} className="sr-only">
              Register a desktop agent and generate a secure token for the remote access service.
            </p>

            <header className="flex shrink-0 items-center justify-between gap-4 border-b border-white/[0.08] px-5 py-5 sm:px-8 sm:py-6">
              <div className="flex min-w-0 items-center gap-3">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-violet-300/20 bg-violet-300/10 text-violet-100 shadow-[0_0_28px_rgba(139,92,246,0.24)]" aria-hidden="true">
                  <Monitor size={21} />
                </span>
                <h2 id={modalTitleId} className="truncate text-xl font-black text-white">
                  Register Desktop Agent
                </h2>
              </div>
              <button
                type="button"
                onClick={closeModal}
                aria-label="Close register desktop agent modal"
                className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-white/10 bg-white/[0.05] text-white/65 transition hover:border-white/20 hover:bg-white/[0.09] hover:text-white focus:outline-none focus:ring-4 focus:ring-violet-400/25"
              >
                <X size={18} />
              </button>
            </header>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-6 sm:px-8">
              <div className="space-y-6">
                <label className="block" htmlFor={nameFieldId}>
                  <span className="mb-2 block text-xs font-bold uppercase text-white/60">Device Name</span>
                  <input
                    ref={nameInputRef}
                    id={nameFieldId}
                    value={form.name}
                    onChange={e => setForm({ ...form, name: e.target.value })}
                    placeholder="Device name"
                    autoComplete="off"
                    className="h-[52px] w-full rounded-[14px] border border-white/10 bg-white/[0.055] px-4 text-sm font-semibold text-white outline-none transition placeholder:text-white/50 hover:border-white/20 focus:border-[#8B5CF6] focus:bg-white/[0.075] focus:shadow-[0_0_0_4px_rgba(139,92,246,0.18),0_0_30px_rgba(139,92,246,0.22)]"
                  />
                </label>

                <label className="block" htmlFor={hostnameFieldId}>
                  <span className="mb-2 block text-xs font-bold uppercase text-white/60">Hostname</span>
                  <input
                    id={hostnameFieldId}
                    value={form.hostname}
                    onChange={e => setForm({ ...form, hostname: e.target.value })}
                    placeholder="Hostname"
                    autoComplete="off"
                    className="h-[52px] w-full rounded-[14px] border border-white/10 bg-white/[0.055] px-4 text-sm font-semibold text-white outline-none transition placeholder:text-white/50 hover:border-white/20 focus:border-[#8B5CF6] focus:bg-white/[0.075] focus:shadow-[0_0_0_4px_rgba(139,92,246,0.18),0_0_30px_rgba(139,92,246,0.22)]"
                  />
                </label>

                <label className="block" htmlFor={notesFieldId}>
                  <span className="mb-2 block text-xs font-bold uppercase text-white/60">Optional Notes</span>
                  <textarea
                    id={notesFieldId}
                    value={form.notes}
                    onChange={e => setForm({ ...form, notes: e.target.value })}
                    placeholder="Deployment notes, owner, location, or access context"
                    rows={4}
                    className="min-h-24 w-full resize-none rounded-[14px] border border-white/10 bg-white/[0.055] px-4 py-3 text-sm font-semibold leading-6 text-white outline-none transition placeholder:text-white/50 hover:border-white/20 focus:border-[#8B5CF6] focus:bg-white/[0.075] focus:shadow-[0_0_0_4px_rgba(139,92,246,0.18),0_0_30px_rgba(139,92,246,0.22)]"
                  />
                </label>

                {error && (
                  <div role="alert" className="rounded-[14px] border border-red-300/25 bg-red-400/10 px-4 py-3 text-sm font-semibold text-red-100">
                    {error}
                  </div>
                )}

                {token && (
                  <div aria-live="polite" className="rounded-[18px] border border-violet-300/20 bg-violet-300/[0.07] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
                    <p className="mb-2 text-[11px] font-bold uppercase text-violet-200/80">Agent command</p>
                    <code className="block max-h-28 overflow-y-auto break-all rounded-[14px] border border-white/10 bg-black/30 p-3 text-xs leading-5 text-slate-100">
                      {agentCommand(token, agentServer)}
                    </code>
                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                      <button type="button" onClick={() => navigator.clipboard?.writeText(token)}
                        className="flex h-10 items-center justify-center gap-1.5 rounded-[12px] border border-white/10 bg-white/[0.04] text-xs font-bold text-violet-100 transition hover:border-violet-300/40 hover:bg-violet-300/10 focus:outline-none focus:ring-4 focus:ring-violet-400/20">
                        <Copy size={13} /> Token
                      </button>
                      <button type="button" onClick={() => navigator.clipboard?.writeText(agentCommand(token, agentServer))}
                        className="flex h-10 items-center justify-center gap-1.5 rounded-[12px] border border-white/10 bg-white/[0.04] text-xs font-bold text-violet-100 transition hover:border-violet-300/40 hover:bg-violet-300/10 focus:outline-none focus:ring-4 focus:ring-violet-400/20">
                        <Copy size={13} /> Command
                      </button>
                      <button type="button" onClick={() => navigator.clipboard?.writeText(clientAccessUrl(token))}
                        className="flex h-10 items-center justify-center gap-1.5 rounded-[12px] border border-white/10 bg-white/[0.04] text-xs font-bold text-violet-100 transition hover:border-violet-300/40 hover:bg-violet-300/10 focus:outline-none focus:ring-4 focus:ring-violet-400/20">
                        <Copy size={13} /> URL
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <footer className="grid shrink-0 gap-3 border-t border-white/[0.08] bg-[#090f1f]/95 px-5 py-5 sm:grid-cols-2 sm:px-8 sm:py-6">
              <button
                type="button"
                onClick={closeModal}
                className="h-12 rounded-[14px] border border-white/10 bg-white/[0.045] px-5 text-sm font-bold text-white/75 transition hover:border-white/20 hover:bg-white/[0.075] hover:text-white focus:outline-none focus:ring-4 focus:ring-white/10 sm:order-1"
              >
                Cancel
              </button>
              <button
                disabled={!form.name.trim() || submitting}
                className="h-12 rounded-[14px] bg-gradient-to-r from-[#8B5CF6] to-[#A855F7] px-5 text-sm font-black text-white shadow-[0_14px_40px_rgba(139,92,246,0.28)] transition duration-200 hover:scale-[1.02] hover:shadow-[0_18px_54px_rgba(168,85,247,0.42)] focus:outline-none focus:ring-4 focus:ring-[#8B5CF6]/30 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100 disabled:hover:shadow-[0_14px_40px_rgba(139,92,246,0.28)] sm:order-2"
              >
                {submitting ? "Registering..." : "Register Agent"}
              </button>
            </footer>
          </motion.form>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  ) : null;

  return (
    <>
      <button ref={triggerRef} type="button" onClick={openModal}
        className="flex items-center gap-2 rounded-lg bg-violet-500 px-4 py-2 text-sm font-bold text-white shadow-[0_12px_34px_rgba(139,92,246,0.24)] transition hover:scale-[1.02] hover:bg-violet-400 hover:shadow-[0_18px_44px_rgba(168,85,247,0.34)] focus:outline-none focus:ring-4 focus:ring-violet-400/25">
        <Plus size={14} /> Register Agent
      </button>
      {modal}
    </>
  );
}
