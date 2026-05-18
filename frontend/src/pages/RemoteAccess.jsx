import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  Activity,
  ArrowDownToLine,
  CheckCircle2,
  Circle,
  Copy,
  Download,
  File,
  FileArchive,
  FileText,
  Folder,
  HardDrive,
  Image,
  Keyboard,
  Maximize2,
  Monitor,
  MousePointer2,
  Pause,
  Play,
  Plus,
  Power,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  Upload,
  Wifi,
  WifiOff,
  XCircle
} from "lucide-react";
import { remoteAccessApi } from "../api/services.js";
import { apiErrorMessage } from "../api/client.js";

const permissions = [
  { value: "VIEW", label: "View only", detail: "Live screen without input" },
  { value: "CONTROL", label: "Full control", detail: "Screen, mouse, and keyboard" },
  { value: "FILES", label: "File access", detail: "Browse and transfer disks" },
  { value: "ADMIN", label: "Desktop + disk", detail: "Full approved session" }
];

function absoluteApiBaseUrl() {
  const configured = import.meta.env.VITE_API_BASE_URL || "/api";
  if (/^https?:\/\//i.test(configured)) return configured;
  return `${window.location.origin}${configured.startsWith("/") ? configured : `/${configured}`}`;
}

function httpToWs(value) {
  return value.replace(/^http/i, "ws");
}

function wsUrl(path) {
  const root = httpToWs(absoluteApiBaseUrl().replace(/\/api\/?$/, ""));
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
  } catch {
    return raw;
  }
}

export default function RemoteAccess() {
  const qc = useQueryClient();
  const [searchParams] = useSearchParams();
  const urlToken = normalizeToken(searchParams.get("token") || searchParams.get("connection"));
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [selectedSession, setSelectedSession] = useState(null);
  const [permission, setPermission] = useState("VIEW");
  const [frame, setFrame] = useState("");
  const [hasCanvasFrame, setHasCanvasFrame] = useState(false);
  const [fileState, setFileState] = useState({ path: "", entries: [], loading: false });
  const [events, setEvents] = useState([]);
  const [socketStatus, setSocketStatus] = useState("connecting");
  const [agentServer, setAgentServer] = useState(() => localStorage.getItem("remoteAgentServerUrl") || defaultAgentServerUrl());
  const [streamSettings, setStreamSettings] = useState({ fps: 12, quality: 76, max_width: 1600 });
  const [streamStats, setStreamStats] = useState({ fps: 0, latency: 0, mode: "idle" });
  const [transferItems, setTransferItems] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("remoteTransferHistory") || "[]");
    } catch {
      return [];
    }
  });
  const screenRef = useRef(null);
  const canvasRef = useRef(null);
  const controlSocketRef = useRef(null);
  const downloadJobsRef = useRef({});
  const remoteDownloadBuffersRef = useRef({});
  const frameStatsRef = useRef({ count: 0, started: performance.now(), lastMove: 0, mouseDown: false });

  useEffect(() => {
    localStorage.setItem("remoteAgentServerUrl", agentServer);
  }, [agentServer]);

  useEffect(() => {
    localStorage.setItem("remoteTransferHistory", JSON.stringify(transferItems.slice(0, 30)));
  }, [transferItems]);

  const dashboard = useQuery({
    queryKey: ["remote-access-dashboard"],
    queryFn: () => remoteAccessApi.dashboard().then((r) => r.data),
    refetchInterval: 15000
  });

  const requestSession = useMutation({
    mutationFn: ({ device, mode }) => remoteAccessApi.requestSession(device.id, { permission: mode, offer: { stream: streamSettings } }),
    onSuccess: ({ data }) => {
      setSelectedSession(data);
      setEvents((prev) => [{ type: "Session request sent", detail: "Waiting for approval on target laptop." }, ...prev].slice(0, 12));
      qc.invalidateQueries({ queryKey: ["remote-access-dashboard"] });
    },
    onError: (error) => setEvents((prev) => [{ type: "Connection failed", detail: apiErrorMessage(error, "Could not request remote session.") }, ...prev].slice(0, 12))
  });

  const connectToken = useMutation({
    mutationFn: ({ token, mode }) => {
      const device = devices.find((item) => item.token === token);
      if (device?.status === "OFFLINE") {
        const error = new Error("The target agent is offline. Run the agent command first, then try again.");
        error.offlineDevice = device;
        throw error;
      }
      return remoteAccessApi.connectToken({ token, permission: mode, offer: { stream: streamSettings } });
    },
    onSuccess: ({ data }) => {
      setSelectedSession(data);
      setEvents((prev) => [{ type: "Token request sent", detail: "Waiting for manual approval on the target laptop." }, ...prev].slice(0, 12));
      qc.invalidateQueries({ queryKey: ["remote-access-dashboard"] });
    },
    onError: (error) => {
      const device = error.offlineDevice || error.response?.data?.device;
      const command = device?.token ? ` Run: ${agentCommand(device.token, agentServer)}` : "";
      setEvents((prev) => [{ type: "Token connect failed", detail: `${apiErrorMessage(error, "The token could not be used.")}${command}` }, ...prev].slice(0, 12));
    }
  });

  const disconnect = useMutation({
    mutationFn: (sessionId) => remoteAccessApi.disconnect(sessionId),
    onSuccess: () => {
      setSelectedSession(null);
      setFrame("");
      setHasCanvasFrame(false);
      qc.invalidateQueries({ queryKey: ["remote-access-dashboard"] });
    }
  });

  const removeDevice = useMutation({
    mutationFn: (deviceId) => remoteAccessApi.removeDevice(deviceId),
    onSuccess: () => {
      setSelectedDevice(null);
      qc.invalidateQueries({ queryKey: ["remote-access-dashboard"] });
    },
    onError: (error) => setEvents((prev) => [{ type: "Delete failed", detail: apiErrorMessage(error, "Could not delete remote device.") }, ...prev].slice(0, 12))
  });

  useEffect(() => {
    const socket = new WebSocket(wsUrl("/ws/remote-access/"));
    socket.onopen = () => setSocketStatus("connected");
    socket.onerror = () => setSocketStatus("error");
    socket.onclose = () => setSocketStatus("closed");
    socket.onmessage = (event) => {
      if (event.data instanceof Blob) {
        renderBinaryFrame(event.data);
        return;
      }
      const message = JSON.parse(event.data);
      if (message.type === "screen.frame") setFrame(`data:image/jpeg;base64,${message.image}`);
      if (message.type === "file.result") setFileState({ path: message.result?.path || "", entries: message.result?.entries || [], loading: false });
      if (message.type === "transfer.progress") handleTransferMessage(message, false);
      if (message.type === "agent.error") setEvents((prev) => [{ type: "Agent error", detail: message.message }, ...prev].slice(0, 12));
      if (message.type?.startsWith("session.") && message.session) setSelectedSession(message.session);
      if (message.type?.includes("device") || message.type?.includes("session") || message.type?.includes("file") || message.type?.includes("transfer")) {
        setEvents((prev) => [{ type: message.type, detail: message.message || message.session?.device_name || "Realtime update" }, ...prev].slice(0, 12));
        qc.invalidateQueries({ queryKey: ["remote-access-dashboard"] });
      }
    };
    return () => socket.close();
  }, [qc]);

  useEffect(() => {
    if (!selectedSession?.token) return;
    const socket = new WebSocket(wsUrl("/ws/remote-access/"));
    socket.binaryType = "blob";
    controlSocketRef.current = socket;
    socket.onopen = () => socket.send(JSON.stringify({ type: "join.session", session_token: selectedSession.token }));
    socket.onmessage = (event) => {
      if (event.data instanceof Blob) {
        renderBinaryFrame(event.data);
        return;
      }
      const message = JSON.parse(event.data);
      if (message.type === "screen.frame") setFrame(`data:image/jpeg;base64,${message.image}`);
      if (message.type === "file.result") setFileState({ path: message.result?.path || "", entries: message.result?.entries || [], loading: false });
      if (message.type === "transfer.progress") handleTransferMessage(message, true);
      if (message.type === "agent.error") setEvents((prev) => [{ type: "Agent error", detail: message.message }, ...prev].slice(0, 12));
    };
    return () => {
      if (controlSocketRef.current === socket) controlSocketRef.current = null;
      socket.close();
    };
  }, [selectedSession?.token]);

  const renderBinaryFrame = async (blob) => {
    const buffer = await blob.arrayBuffer();
    const view = new DataView(buffer);
    const headerLength = view.getUint32(0);
    const header = JSON.parse(new TextDecoder().decode(buffer.slice(4, 4 + headerLength)));
    const imageBlob = new Blob([buffer.slice(4 + headerLength)], { type: "image/jpeg" });
    const bitmap = await createImageBitmap(imageBlob);
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d", { alpha: false });
    if (canvas.width !== header.screen_width || canvas.height !== header.screen_height || header.full) {
      canvas.width = header.screen_width;
      canvas.height = header.screen_height;
      if (header.full) context.fillStyle = "#020617";
      if (header.full) context.fillRect(0, 0, canvas.width, canvas.height);
    }
    context.drawImage(bitmap, header.x, header.y, header.width, header.height);
    bitmap.close?.();
    setHasCanvasFrame(true);
    const now = performance.now();
    const stats = frameStatsRef.current;
    stats.count += 1;
    if (now - stats.started >= 1000) {
      setStreamStats({ fps: Math.round((stats.count * 1000) / (now - stats.started)), latency: Math.max(0, Math.round(Date.now() - header.ts * 1000)), mode: header.full ? "full" : "delta" });
      stats.count = 0;
      stats.started = now;
    }
  };

  const data = dashboard.data || {};
  const devices = data.devices || [];
  const sessions = data.sessions || [];
  const logs = data.logs || [];
  const summary = data.summary || {};
  const activeDevice = selectedDevice || devices[0];
  const refreshedSelectedSession = selectedSession ? sessions.find((session) => session.id === selectedSession.id) || selectedSession : null;
  const activeSession = (refreshedSelectedSession?.status === "ACTIVE" ? refreshedSelectedSession : null) || sessions.find((session) => session.status === "ACTIVE") || refreshedSelectedSession || sessions.find((session) => session.status === "REQUESTED") || null;
  const canFiles = activeSession && ["FILES", "ADMIN"].includes(activeSession.permission);
  const canControl = activeSession && ["CONTROL", "ADMIN"].includes(activeSession.permission);
  const screenUnavailable = activeDevice && activeDevice.capabilities?.screen === false;
  const controlUnavailable = activeDevice && activeDevice.capabilities?.control === false;

  const requestFiles = (action, payload = {}) => {
    if (!activeSession) return;
    setFileState((prev) => ({ ...prev, loading: true }));
    remoteAccessApi.files(activeSession.id, { action, payload }).catch((error) => {
      setFileState((prev) => ({ ...prev, loading: false }));
      setEvents((prev) => [{ type: "File command failed", detail: apiErrorMessage(error, "The file command failed.") }, ...prev].slice(0, 12));
    });
  };

  const upsertTransferItem = (key, patch) => {
    setTransferItems((prev) => {
      const index = prev.findIndex((item) => item.key === key || (patch.transferId && item.transferId === patch.transferId));
      const nextItem = { ...(index >= 0 ? prev[index] : { key }), ...patch, updatedAt: Date.now() };
      if (index >= 0) return [nextItem, ...prev.filter((_, itemIndex) => itemIndex !== index)].slice(0, 30);
      return [nextItem, ...prev].slice(0, 30);
    });
  };

  const mergeTransferUpdate = (transfer) => {
    const key = `server-${transfer.id}`;
    const percent = Math.round(Number(transfer.progress_percent || 0));
    upsertTransferItem(key, {
      key,
      transferId: transfer.id,
      name: transfer.original_name || transfer.source_path || transfer.stored_name,
      size: transfer.size_bytes,
      type: transfer.content_type,
      percent,
      status: transfer.status === "COMPLETED" ? "completed" : transfer.status === "FAILED" ? "failed" : "uploading",
      uploadedBytes: transfer.transferred_bytes,
      downloadReady: transfer.status === "COMPLETED",
      error: transfer.error || ""
    });
  };

  const handleTransferMessage = (message, allowRawDownload = false) => {
    if (message.transfer) {
      mergeTransferUpdate(message.transfer);
      return;
    }
    if (!allowRawDownload || !message.transfer_id) return;
    mergeRemoteDownloadChunk(message);
  };

  const decodeBase64Chunk = (value) => {
    const binary = atob(value || "");
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    return bytes;
  };

  const saveBlob = (blob, filename) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || "download";
    link.click();
    URL.revokeObjectURL(url);
  };

  const mergeRemoteDownloadChunk = (message) => {
    const transferId = String(message.transfer_id);
    const job = remoteDownloadBuffersRef.current[transferId];
    if (!job) return;
    const bytes = Number(message.bytes || job.received || 0);
    if (message.chunk && bytes > job.received) {
      job.chunks.push(decodeBase64Chunk(message.chunk));
      job.received = bytes;
    }
    const elapsedSeconds = Math.max((performance.now() - job.startedAt) / 1000, 0.1);
    const speed = job.received / elapsedSeconds;
    const eta = speed && job.total ? Math.max(0, (job.total - job.received) / speed) : 0;
    upsertTransferItem(job.key, {
      percent: job.total ? Math.min(99, Math.round((job.received / job.total) * 100)) : 0,
      uploadedBytes: job.received,
      speed,
      eta,
      status: message.complete ? "completed" : "downloading"
    });
    if (message.complete) {
      const blob = new Blob(job.chunks, { type: "application/octet-stream" });
      saveBlob(blob, job.name);
      delete remoteDownloadBuffersRef.current[transferId];
      upsertTransferItem(job.key, { percent: 100, eta: 0, status: "completed", downloadStatus: "saved" });
      setEvents((prev) => [{ type: "Download completed", detail: job.name }, ...prev].slice(0, 12));
    }
  };

  const retryOperation = async (operation, attempts = 3) => {
    let lastError;
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      try {
        return await operation(attempt);
      } catch (error) {
        lastError = error;
        if (attempt < attempts) await new Promise((resolve) => setTimeout(resolve, 500 * attempt));
      }
    }
    throw lastError;
  };

  const uploadFiles = async (files, path) => {
    if (!activeSession || !files?.length) return;
    const queue = Array.from(files);
    const workers = Array.from({ length: Math.min(3, queue.length) }, async () => {
      while (queue.length) {
        const file = queue.shift();
        await uploadSingleFile(file, path);
      }
    });
    await Promise.all(workers);
  };

  const uploadSingleFile = async (file, path) => {
    const chunkSize = 2 * 1024 * 1024;
    const targetPath = path && path !== "Drives" ? path : "";
    const key = `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(16).slice(2)}`;
    const startedAt = performance.now();
    upsertTransferItem(key, { key, name: file.webkitRelativePath || file.name, size: file.size, type: file.type, percent: 0, speed: 0, eta: 0, status: "starting", uploadedBytes: 0 });
    setEvents((prev) => [{ type: "Upload started", detail: file.webkitRelativePath || file.name }, ...prev].slice(0, 12));
    try {
      const { data: transfer } = await remoteAccessApi.initiateUpload({
        session: activeSession.id,
        name: file.webkitRelativePath || file.name,
        size_bytes: file.size,
        content_type: file.type || "application/octet-stream",
        chunk_size: chunkSize,
        target_path: targetPath
      });
      const statusResponse = await remoteAccessApi.uploadStatus(transfer.id);
      const missing = new Set(statusResponse.data.missing_chunks || Array.from({ length: transfer.total_chunks }, (_, index) => index));
      upsertTransferItem(key, { transferId: transfer.id, status: "uploading", totalChunks: transfer.total_chunks });
      for (let index = 0; index < transfer.total_chunks; index += 1) {
        if (!missing.has(index)) continue;
        const start = index * chunkSize;
        const end = Math.min(file.size, start + chunkSize);
        const formData = new FormData();
        formData.append("chunk_index", String(index));
        formData.append("chunk", file.slice(start, end), file.name);
        const response = await retryOperation(() => remoteAccessApi.uploadChunk(transfer.id, formData));
        const uploadedBytes = Math.min(file.size, end);
        const elapsedSeconds = Math.max((performance.now() - startedAt) / 1000, 0.1);
        const speed = uploadedBytes / elapsedSeconds;
        const eta = speed ? Math.max(0, (file.size - uploadedBytes) / speed) : 0;
        upsertTransferItem(key, {
          transferId: transfer.id,
          percent: Math.round((uploadedBytes / Math.max(file.size, 1)) * 100),
          uploadedBytes,
          speed,
          eta,
          status: response.data.status === "COMPLETED" ? "completed" : "uploading",
          downloadReady: response.data.status === "COMPLETED"
        });
      }
      upsertTransferItem(key, { transferId: transfer.id, percent: 100, eta: 0, status: "completed", downloadReady: true });
      setEvents((prev) => [{ type: "Upload completed", detail: file.webkitRelativePath || file.name }, ...prev].slice(0, 12));
    } catch (error) {
      upsertTransferItem(key, { status: "failed", error: apiErrorMessage(error, "Upload failed. Retrying is available from history.") });
      setEvents((prev) => [{ type: "Upload failed", detail: apiErrorMessage(error, file.name) }, ...prev].slice(0, 12));
    }
  };

  const startRemoteFileDownload = async (entry) => {
    if (!activeSession || !entry || entry.is_dir) return;
    const key = `remote-download-${entry.path}-${Date.now()}`;
    upsertTransferItem(key, {
      key,
      name: entry.name,
      size: entry.size || 0,
      type: "application/octet-stream",
      percent: 0,
      speed: 0,
      eta: 0,
      status: "queued",
      uploadedBytes: 0
    });
    try {
      const { data: transfer } = await remoteAccessApi.createTransfer({
        session: activeSession.id,
        direction: "DOWNLOAD",
        source_path: entry.path,
        target_path: "",
        original_name: entry.name,
        content_type: "application/octet-stream",
        size_bytes: entry.size || 0,
        chunk_size: 512 * 1024
      });
      remoteDownloadBuffersRef.current[String(transfer.id)] = {
        key,
        name: entry.name,
        total: entry.size || transfer.size_bytes || 0,
        received: 0,
        chunks: [],
        startedAt: performance.now()
      };
      upsertTransferItem(key, { transferId: transfer.id, status: "downloading" });
      setEvents((prev) => [{ type: "Download started", detail: entry.name }, ...prev].slice(0, 12));
    } catch (error) {
      upsertTransferItem(key, { status: "failed", error: apiErrorMessage(error, "Could not start download.") });
      setEvents((prev) => [{ type: "Download failed", detail: apiErrorMessage(error, entry.name) }, ...prev].slice(0, 12));
    }
  };

  const downloadTransferItem = async (item) => {
    if (!item.transferId) return;
    const jobKey = String(item.transferId);
    const existing = downloadJobsRef.current[jobKey] || { chunks: [], received: 0, total: item.size || 0 };
    const controller = new AbortController();
    downloadJobsRef.current[jobKey] = { ...existing, controller, paused: false };
    upsertTransferItem(item.key, { downloadStatus: "downloading", downloadPercent: existing.total ? Math.round((existing.received / existing.total) * 100) : 0 });
    try {
      const headers = {};
      const token = localStorage.getItem("accessToken");
      if (token) headers.Authorization = `Bearer ${token}`;
      if (existing.received > 0) headers.Range = `bytes=${existing.received}-`;
      const response = await fetch(remoteAccessApi.transferDownloadUrl(item.transferId), { headers, signal: controller.signal });
      if (!response.ok && response.status !== 206) throw new Error(`Download failed with HTTP ${response.status}`);
      const contentRange = response.headers.get("Content-Range");
      const total = contentRange ? Number(contentRange.split("/").pop()) : Number(response.headers.get("Content-Length") || existing.total || item.size || 0);
      const reader = response.body.getReader();
      let received = existing.received;
      const chunks = existing.chunks;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        received += value.length;
        downloadJobsRef.current[jobKey] = { ...downloadJobsRef.current[jobKey], chunks, received, total };
        upsertTransferItem(item.key, { downloadStatus: "downloading", downloadPercent: total ? Math.round((received / total) * 100) : 0 });
      }
      const blob = new Blob(chunks, { type: item.type || "application/octet-stream" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = item.name || "download";
      link.click();
      URL.revokeObjectURL(url);
      delete downloadJobsRef.current[jobKey];
      upsertTransferItem(item.key, { downloadStatus: "complete", downloadPercent: 100 });
    } catch (error) {
      if (error.name === "AbortError") {
        upsertTransferItem(item.key, { downloadStatus: "paused" });
        return;
      }
      upsertTransferItem(item.key, { downloadStatus: "failed", error: error.message });
    }
  };

  const pauseDownload = (item) => {
    const job = downloadJobsRef.current[String(item.transferId)];
    job?.controller?.abort();
  };

  const sendControl = (command, payload) => {
    if (!activeSession || !canControl) return;
    const socket = controlSocketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "session.command", session_token: activeSession.token, command, payload }));
      return;
    }
    remoteAccessApi.command(activeSession.id, { command, payload });
  };

  const handleScreenClick = (event) => {
    if (!screenRef.current || !canControl) return;
    screenRef.current.focus();
    const box = screenRef.current.getBoundingClientRect();
    const xRatio = Math.max(0, Math.min(1, (event.clientX - box.left) / box.width));
    const yRatio = Math.max(0, Math.min(1, (event.clientY - box.top) / box.height));
    sendControl("mouse", { action: "click", x_ratio: xRatio, y_ratio: yRatio });
  };

  const handleScreenMouseMove = (event) => {
    if (!screenRef.current || !canControl) return;
    const stats = frameStatsRef.current;
    const now = performance.now();
    if (now - stats.lastMove < 25) return;
    stats.lastMove = now;
    const box = screenRef.current.getBoundingClientRect();
    const xRatio = Math.max(0, Math.min(1, (event.clientX - box.left) / box.width));
    const yRatio = Math.max(0, Math.min(1, (event.clientY - box.top) / box.height));
    sendControl("mouse", { action: "move", x_ratio: xRatio, y_ratio: yRatio });
  };

  const handleScreenMouseDown = (event) => {
    if (!screenRef.current || !canControl) return;
    screenRef.current.focus();
    frameStatsRef.current.mouseDown = true;
    const box = screenRef.current.getBoundingClientRect();
    sendControl("mouse", { action: "down", x_ratio: (event.clientX - box.left) / box.width, y_ratio: (event.clientY - box.top) / box.height });
  };

  const handleScreenMouseUp = (event) => {
    if (!screenRef.current || !canControl) return;
    frameStatsRef.current.mouseDown = false;
    const box = screenRef.current.getBoundingClientRect();
    sendControl("mouse", { action: "up", x_ratio: (event.clientX - box.left) / box.width, y_ratio: (event.clientY - box.top) / box.height });
  };

  const handleScreenWheel = (event) => {
    if (!canControl) return;
    event.preventDefault();
    sendControl("mouse", { action: "scroll", delta: event.deltaY > 0 ? -5 : 5 });
  };

  const handleScreenKeyDown = (event) => {
    if (!canControl) return;
    event.preventDefault();
    const modifierMap = { ctrlKey: "ctrl", altKey: "alt", shiftKey: "shift", metaKey: "win" };
    const modifiers = Object.entries(modifierMap).filter(([flag]) => event[flag]).map(([, value]) => value);
    const specialKeys = {
      Backspace: "backspace",
      Tab: "tab",
      Enter: "enter",
      Escape: "esc",
      Delete: "delete",
      ArrowUp: "up",
      ArrowDown: "down",
      ArrowLeft: "left",
      ArrowRight: "right",
      Home: "home",
      End: "end",
      PageUp: "pageup",
      PageDown: "pagedown",
      " ": "space"
    };
    if (event.key.length === 1 && !event.ctrlKey && !event.altKey && !event.metaKey) {
      sendControl("keyboard", { text: event.key });
      return;
    }
    const key = specialKeys[event.key] || event.key.toLowerCase();
    sendControl("keyboard", { key, modifiers, event: "down" });
  };

  const handleScreenKeyUp = (event) => {
    if (!canControl) return;
    const specialKeys = { Control: "ctrl", Shift: "shift", Alt: "alt", Meta: "win" };
    if (specialKeys[event.key]) {
      event.preventDefault();
      sendControl("keyboard", { key: specialKeys[event.key], event: "up" });
    }
  };

  return (
    <div className="space-y-5 text-[color:var(--text)]">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">
            <ShieldCheck size={16} /> Secure desktop agent
          </div>
          <h1 className="mt-2 text-3xl font-semibold text-[color:var(--text-strong)]">Remote Access Command Center</h1>
          <p className="mt-2 max-w-3xl text-sm text-[color:var(--text-muted)]">
            Agent-approved remote desktop, disk browsing, and chunked transfer controls for laptop-to-laptop operations.
          </p>
        </div>
        <RegisterDevice agentServer={agentServer} onCreated={() => qc.invalidateQueries({ queryKey: ["remote-access-dashboard"] })} />
      </header>

      {dashboard.isError && <Notice tone="red" title="Remote Access API is not responding" detail={apiErrorMessage(dashboard.error, "Check that the Django backend is running and migrations are applied.")} />}
      <Notice tone={socketStatus === "connected" ? "green" : "amber"} title={`Realtime channel: ${socketStatus}`} detail={socketStatus === "connected" ? "Dashboard events, agent approvals, frames, and file results will update live." : "If this stays disconnected, restart the backend with Daphne/Channels enabled."} />

      <section className="grid gap-3 md:grid-cols-4">
        <Metric icon={Monitor} label="Devices" value={summary.devices || 0} />
        <Metric icon={Wifi} label="Online" value={summary.online || 0} tone="green" />
        <Metric icon={Activity} label="Live sessions" value={summary.active_sessions || 0} tone="cyan" />
        <Metric icon={ArrowDownToLine} label="Transfers" value={summary.transfers || 0} tone="amber" />
      </section>

      <section className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Panel title="Agent Network">
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Desktop agent server URL</label>
              <input value={agentServer} onChange={(event) => setAgentServer(event.target.value.trim())} placeholder="ws://192.168.1.10:8001" className="w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300" />
              <p className="text-xs text-slate-500">Use 127.0.0.1 only on this PC. For another device, use this PC&apos;s LAN IP, for example ws://192.168.1.10:8001. For hosting, use your public wss:// domain.</p>
            </div>
          </Panel>

          <Panel title="Connected Devices" action={<button onClick={() => dashboard.refetch()} className="rounded-md border border-white/10 bg-white/[0.04] p-2 text-slate-200 hover:border-cyan-300/50"><RefreshCw size={16} /></button>}>
            <div className="space-y-3">
              {devices.map((device) => (
                <div key={device.id} role="button" tabIndex={0} onClick={() => setSelectedDevice(device)} onKeyDown={(event) => event.key === "Enter" && setSelectedDevice(device)} className={`w-full rounded-lg border p-4 text-left transition ${activeDevice?.id === device.id ? "border-cyan-300 bg-cyan-300/10" : "border-white/10 bg-white/[0.035] hover:border-white/25"}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-white">{device.name}</p>
                      <p className="mt-1 text-xs text-slate-400">{device.hostname || "Awaiting agent heartbeat"}</p>
                    </div>
                    <Status value={device.status} />
                  </div>
                  <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                    <HardDrive size={14} /> {device.platform || "Unknown platform"}
                  </div>
                  <div className="mt-3 rounded-md border border-white/10 bg-black/20 p-2">
                    <p className="text-[11px] uppercase tracking-wide text-slate-500">Connection token</p>
                    <code className="mt-1 block truncate text-xs text-cyan-100">{device.token}</code>
                  </div>
                  {device.status === "OFFLINE" && (
                    <p className="mt-2 text-xs text-amber-200">Start the desktop agent with this token before connecting.</p>
                  )}
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <TinyAction onClick={() => navigator.clipboard?.writeText(device.token)} icon={Copy} label="Token" />
                    <TinyAction onClick={() => navigator.clipboard?.writeText(agentCommand(device.token, agentServer))} icon={Copy} label="Agent cmd" />
                    <TinyAction onClick={() => navigator.clipboard?.writeText(clientAccessUrl(device.token))} icon={Copy} label="Client URL" />
                    <TinyAction danger onClick={() => removeDevice.mutate(device.id)} icon={Trash2} label="Delete" />
                  </div>
                </div>
              ))}
              {!devices.length && <Empty title="No devices yet" detail="Register a device, then start the desktop agent with its token." />}
            </div>
          </Panel>

          {activeDevice && (
            <Panel title="Connection Request">
              <div className="space-y-3">
                <div className="grid gap-2">
                  {permissions.map((item) => (
                    <button key={item.value} onClick={() => setPermission(item.value)} className={`rounded-lg border px-3 py-2 text-left ${permission === item.value ? "border-cyan-300 bg-cyan-300/10" : "border-white/10 bg-white/[0.03]"}`}>
                      <span className="block text-sm font-medium text-white">{item.label}</span>
                      <span className="text-xs text-slate-500">{item.detail}</span>
                    </button>
                  ))}
                </div>
                <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                  <div className="mb-3 flex items-center gap-2 text-sm font-medium text-white"><SlidersHorizontal size={15} /> Stream</div>
                  <div className="grid gap-3 text-xs text-slate-400">
                    <label>FPS <input type="range" min="4" max="20" value={streamSettings.fps} onChange={(event) => setStreamSettings((prev) => ({ ...prev, fps: Number(event.target.value) }))} className="w-full" /> <span className="text-cyan-100">{streamSettings.fps}</span></label>
                    <label>Quality <input type="range" min="45" max="90" value={streamSettings.quality} onChange={(event) => setStreamSettings((prev) => ({ ...prev, quality: Number(event.target.value) }))} className="w-full" /> <span className="text-cyan-100">{streamSettings.quality}</span></label>
                    <label>Width
                      <select value={streamSettings.max_width} onChange={(event) => setStreamSettings((prev) => ({ ...prev, max_width: Number(event.target.value) }))} className="mt-1 w-full rounded-md border border-white/10 bg-slate-900 px-2 py-1 text-slate-100">
                        <option value={1280}>1280</option>
                        <option value={1600}>1600</option>
                        <option value={1920}>1920</option>
                      </select>
                    </label>
                  </div>
                </div>
                {activeDevice.status === "OFFLINE" && (
                  <div className="rounded-md border border-amber-300/25 bg-amber-300/10 p-3 text-xs text-amber-100">
                    This device is registered but the desktop agent is not connected. Copy the agent command from the device card and run it on the target laptop.
                  </div>
                )}
                {(screenUnavailable || controlUnavailable) && (
                  <div className="rounded-md border border-amber-300/25 bg-amber-300/10 p-3 text-xs text-amber-100">
                    This agent is connected but missing desktop dependencies. Run pip install websockets mss pillow pyautogui on the target PC, then restart the agent.
                  </div>
                )}
                <button disabled={requestSession.isPending || activeDevice.status === "OFFLINE"} onClick={() => requestSession.mutate({ device: activeDevice, mode: permission })} className="flex w-full items-center justify-center gap-2 rounded-md bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50">
                  <Power size={16} /> Connect
                </button>
              </div>
            </Panel>
          )}

          <TokenConnect initialToken={urlToken} devices={devices} agentServer={agentServer} permission={permission} setPermission={setPermission} pending={connectToken.isPending} onConnect={(token) => connectToken.mutate({ token: normalizeToken(token), mode: permission })} />

          {!devices.length && <AgentSetup agentServer={agentServer} />}
        </div>

        <div className="space-y-5">
          <Panel title="Remote Desktop" action={<div className="flex items-center gap-2">{activeSession && <SessionPill session={activeSession} />}<span className="rounded-full bg-white/[0.06] px-3 py-1 text-xs text-slate-300">{streamStats.fps} FPS · {streamStats.latency} ms · {streamStats.mode}</span></div>}>
            <div ref={screenRef} tabIndex={0} onClick={handleScreenClick} onMouseMove={handleScreenMouseMove} onMouseDown={handleScreenMouseDown} onMouseUp={handleScreenMouseUp} onWheel={handleScreenWheel} onKeyDown={handleScreenKeyDown} onKeyUp={handleScreenKeyUp} className="relative aspect-video overflow-hidden rounded-lg border border-white/10 bg-slate-950 outline-none focus:border-cyan-300/60">
              {frame ? <img src={frame} alt="Remote desktop stream" className="h-full w-full object-contain" /> : null}
              <canvas ref={canvasRef} className={`h-full w-full object-contain ${frame ? "hidden" : "block"}`} />
              {!frame && !hasCanvasFrame ? <DesktopPlaceholder session={activeSession} /> : null}
              <div className="absolute bottom-3 left-3 flex gap-2">
                <ControlButton disabled={!canControl} icon={MousePointer2} label="Mouse" />
                <ControlButton disabled={!canControl} icon={Keyboard} label="Keyboard" onClick={() => sendControl("keyboard", { key: "enter" })} />
                <ControlButton icon={Maximize2} label="Fullscreen" onClick={() => screenRef.current?.requestFullscreen?.()} />
              </div>
              {activeSession && (
                <button onClick={() => disconnect.mutate(activeSession.id)} className="absolute right-3 top-3 rounded-md border border-red-400/30 bg-red-500/15 px-3 py-1.5 text-xs font-semibold text-red-100">
                  Disconnect
                </button>
              )}
            </div>
          </Panel>

          <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
            <Panel title="Disk Explorer" action={canFiles && <button onClick={() => requestFiles("drives")} className="rounded-md border border-white/10 bg-white/[0.04] p-2 text-slate-200 hover:border-cyan-300/50"><HardDrive size={16} /></button>}>
              {!canFiles ? (
                <Empty title="File permission required" detail="Start a File access or Desktop + disk session to browse remote drives." />
              ) : (
                <FileExplorer
                  state={fileState}
                  transfers={transferItems}
                  onOpen={(path) => requestFiles("list", { path })}
                  onUpload={(files) => uploadFiles(files, fileState.path)}
                  onDelete={(path) => requestFiles("delete", { path })}
                  onDownload={downloadTransferItem}
                  onEntryDownload={startRemoteFileDownload}
                  onPauseDownload={pauseDownload}
                />
              )}
            </Panel>

            <Panel title="Activity Timeline">
              <div className="space-y-3">
                {[...events, ...logs.map((log) => ({ type: log.action, detail: log.message }))].slice(0, 10).map((event, index) => (
                  <div key={`${event.type}-${index}`} className="flex gap-3 rounded-lg border border-white/10 bg-white/[0.03] p-3">
                    <Circle className="mt-1 text-cyan-300" size={10} fill="currentColor" />
                    <div>
                      <p className="text-sm font-medium text-white">{event.type}</p>
                      <p className="mt-1 text-xs text-slate-500">{event.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </section>
        </div>
      </section>
    </div>
  );
}

function RegisterDevice({ agentServer, onCreated }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", hostname: "", platform: "Windows", capabilities: { screen: true, files: true, control: true } });
  const [createdToken, setCreatedToken] = useState("");
  const [error, setError] = useState("");
  const dashboardUrl = `${window.location.origin}/remote-access?token=${encodeURIComponent(createdToken)}`;
  return (
    <>
      <button onClick={() => setOpen(true)} className="flex items-center gap-2 rounded-md bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950"><Plus size={16} /> Register Agent</button>
      {open && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4">
          <form onSubmit={async (event) => { event.preventDefault(); setError(""); try { const response = await remoteAccessApi.createDevice(form); setCreatedToken(response.data.token); onCreated?.(); } catch (err) { setError(apiErrorMessage(err, "Could not create the remote device.")); } }} className="w-full max-w-lg rounded-lg border border-white/10 bg-slate-950 p-5 shadow-2xl">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Register Desktop Agent</h2>
              <button type="button" onClick={() => setOpen(false)} className="text-slate-400"><XCircle size={18} /></button>
            </div>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Device name" className="mt-4 w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white" />
            <input value={form.hostname} onChange={(e) => setForm({ ...form, hostname: e.target.value })} placeholder="Hostname" className="mt-3 w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white" />
            <button disabled={!form.name.trim()} className="mt-4 w-full rounded-md bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50">Create secure token</button>
            {error && <p className="mt-3 rounded-md border border-red-300/25 bg-red-300/10 p-2 text-xs text-red-100">{error}</p>}
            {createdToken && (
              <div className="mt-4 rounded-lg border border-cyan-300/25 bg-cyan-300/10 p-3">
                <p className="text-xs uppercase tracking-wide text-cyan-200">Agent launch command</p>
                <code className="mt-2 block break-all rounded bg-slate-950 p-3 text-xs text-slate-200">{agentCommand(createdToken, agentServer)}</code>
                <p className="mt-3 text-xs uppercase tracking-wide text-cyan-200">Client access URL</p>
                <code className="mt-2 block break-all rounded bg-slate-950 p-3 text-xs text-slate-200">{dashboardUrl}</code>
                <div className="mt-2 flex flex-wrap gap-3">
                  <button type="button" onClick={() => navigator.clipboard?.writeText(createdToken)} className="flex items-center gap-2 text-xs text-cyan-200"><Copy size={13} /> Copy token</button>
                  <button type="button" onClick={() => navigator.clipboard?.writeText(agentCommand(createdToken, agentServer))} className="flex items-center gap-2 text-xs text-cyan-200"><Copy size={13} /> Copy command</button>
                  <button type="button" onClick={() => navigator.clipboard?.writeText(dashboardUrl)} className="flex items-center gap-2 text-xs text-cyan-200"><Copy size={13} /> Copy URL</button>
                </div>
              </div>
            )}
          </form>
        </div>
      )}
    </>
  );
}

function TokenConnect({ initialToken = "", devices = [], agentServer, permission, setPermission, pending, onConnect }) {
  const [token, setToken] = useState(initialToken);
  useEffect(() => {
    if (initialToken) setToken(initialToken);
  }, [initialToken]);
  const cleanToken = normalizeToken(token);
  const knownDevice = devices.find((device) => device.token === cleanToken);
  const offlineDevice = knownDevice?.status === "OFFLINE" ? knownDevice : null;
  return (
    <Panel title="Connect By Token">
      <div className="space-y-3">
        <input value={token} onChange={(event) => setToken(event.target.value)} placeholder="Paste token or /remote-access?token=..." className="w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300" />
        <select value={permission} onChange={(event) => setPermission(event.target.value)} className="w-full rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-sm text-white">
          {permissions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
        {cleanToken && cleanToken !== token.trim() && <p className="rounded-md border border-cyan-300/20 bg-cyan-300/10 p-2 text-xs text-cyan-100">Using token: {cleanToken}</p>}
        {offlineDevice && (
          <div className="rounded-md border border-amber-300/25 bg-amber-300/10 p-3 text-xs text-amber-100">
            <p className="font-semibold">This token belongs to an offline device.</p>
            <code className="mt-2 block break-all rounded bg-slate-950/80 p-2 text-[11px] text-cyan-100">{agentCommand(offlineDevice.token, agentServer)}</code>
            <button type="button" onClick={() => navigator.clipboard?.writeText(agentCommand(offlineDevice.token, agentServer))} className="mt-2 inline-flex items-center gap-1 text-cyan-100">
              <Copy size={12} /> Copy agent command
            </button>
          </div>
        )}
        <button disabled={!cleanToken || pending || Boolean(offlineDevice)} onClick={() => onConnect(cleanToken)} className="flex w-full items-center justify-center gap-2 rounded-md bg-white px-4 py-2 text-sm font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50">
          <Power size={16} /> Send Approval Request
        </button>
      </div>
    </Panel>
  );
}

function AgentSetup({ agentServer }) {
  return (
    <Panel title="Quick Setup">
      <div className="space-y-3 text-sm text-slate-300">
        <p>1. Click Register Agent and create a secure token.</p>
        <p>2. On the target laptop, install agent dependencies:</p>
        <code className="block break-all rounded-md bg-black/40 p-3 text-xs text-cyan-100">pip install websockets mss pillow pyautogui</code>
        <p>3. For another device on the same network, start Django with 0.0.0.0, then open the site with this computer&apos;s LAN IP. Do not open 0.0.0.0 in the browser.</p>
        <code className="block break-all rounded-md bg-black/40 p-3 text-xs text-cyan-100">python manage.py runserver 0.0.0.0:8001</code>
        <p>Browser URL examples:</p>
        <code className="block break-all rounded-md bg-black/40 p-3 text-xs text-cyan-100">http://127.0.0.1:8001 on this PC, or http://YOUR_LAN_IP:8001 from another device</code>
        <p>Agent server example:</p>
        <code className="block break-all rounded-md bg-black/40 p-3 text-xs text-cyan-100">ws://YOUR_LAN_IP:8001</code>
        <p>Current agent server:</p>
        <code className="block break-all rounded-md bg-black/40 p-3 text-xs text-cyan-100">{agentServer}</code>
      </div>
    </Panel>
  );
}

function FileExplorer({ state, transfers, onOpen, onUpload, onDelete, onDownload, onEntryDownload, onPauseDownload }) {
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef(null);
  const folderInputRef = useRef(null);
  const submitFiles = (fileList) => {
    const files = Array.from(fileList || []).filter((file) => file.size > 0);
    if (files.length) onUpload?.(files);
  };
  const handleDrop = (event) => {
    event.preventDefault();
    setDragActive(false);
    submitFiles(event.dataTransfer.files);
  };
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <HardDrive size={14} />
          {state.path || "Select a drive"}
          {state.loading && <span className="text-cyan-300">Loading...</span>}
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => inputRef.current?.click()} className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-slate-200 hover:border-cyan-300/40">
            <Upload size={13} /> Files
          </button>
          <button type="button" onClick={() => folderInputRef.current?.click()} className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-slate-200 hover:border-cyan-300/40">
            <Folder size={13} /> Folder
          </button>
          <input ref={inputRef} type="file" multiple className="hidden" onChange={(event) => { submitFiles(event.target.files); event.target.value = ""; }} />
          <input ref={folderInputRef} type="file" multiple webkitdirectory="" className="hidden" onChange={(event) => { submitFiles(event.target.files); event.target.value = ""; }} />
        </div>
      </div>

      <div
        onDragEnter={(event) => { event.preventDefault(); setDragActive(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => { if (event.currentTarget === event.target) setDragActive(false); }}
        onDrop={handleDrop}
        className={`mb-3 rounded-lg border border-dashed p-4 transition ${dragActive ? "border-cyan-300 bg-cyan-300/15 shadow-lg shadow-cyan-950/30" : "border-white/10 bg-white/[0.025]"}`}
      >
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-cyan-300/10 text-cyan-200">
            <Upload size={18} />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-white">Drop files or folders to upload instantly</p>
            <p className="mt-1 text-xs text-slate-500">Binary chunks, automatic retry, resumable status, and live speed tracking.</p>
          </div>
        </div>
      </div>

      {transfers?.length ? (
        <div className="mb-3 space-y-2">
          {transfers.slice(0, 6).map((item) => (
            <TransferRow key={item.key || item.transferId} item={item} onDownload={onDownload} onPauseDownload={onPauseDownload} />
          ))}
        </div>
      ) : null}

      <div className="max-h-[420px] overflow-auto rounded-lg border border-white/10">
        {(state.entries || []).map((entry) => (
          <div key={entry.path} className="grid grid-cols-[minmax(0,1fr)_auto_auto_auto] items-center gap-3 border-b border-white/5 px-3 py-2 text-sm last:border-b-0">
            <button onClick={() => entry.is_dir && onOpen(entry.path)} className="flex min-w-0 items-center gap-2 text-left text-slate-200">
              {entry.is_dir ? <Folder size={16} className="text-cyan-300" /> : <File size={16} className="text-slate-400" />}
              <span className="truncate">{entry.name}</span>
            </button>
            <span className="text-xs text-slate-500">{entry.is_dir ? "Folder" : formatBytes(entry.size)}</span>
            <button
              disabled={entry.is_dir}
              onClick={() => onEntryDownload?.(entry)}
              title={entry.is_dir ? "Open folder to download files" : "Download file"}
              className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-cyan-100 hover:border-cyan-300/40 disabled:cursor-not-allowed disabled:border-transparent disabled:bg-transparent disabled:text-slate-600"
            >
              <Download size={13} /> Download
            </button>
            <button disabled={entry.is_dir} onClick={() => onDelete(entry.path)} className="text-xs text-red-300 disabled:text-slate-600">Delete</button>
          </div>
        ))}
        {!state.entries?.length && <div className="p-6"><Empty title="No directory loaded" detail="Use the drive button to ask the agent for available disks." /></div>}
      </div>
    </div>
  );
}

function TransferRow({ item, onDownload, onPauseDownload }) {
  const percent = Math.max(0, Math.min(100, item.percent || 0));
  const failed = item.status === "failed";
  const active = ["starting", "uploading"].includes(item.status);
  const Icon = fileIcon(item);
  return (
    <div className="rounded-lg border border-white/10 bg-slate-900/70 p-3">
      <div className="flex items-start gap-3">
        <Icon className={failed ? "text-red-300" : "text-cyan-300"} size={18} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <p className="truncate text-sm font-medium text-white">{item.name}</p>
            <span className="text-xs text-slate-400">{percent}%</span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded bg-slate-800">
            <div className={`h-full ${failed ? "bg-red-300" : "bg-cyan-300"}`} style={{ width: `${percent}%` }} />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
            <span>{formatBytes(item.uploadedBytes || 0)} / {formatBytes(item.size || 0)}</span>
            {active && <span>{formatBytes(item.speed || 0)}/s</span>}
            {active && <span>ETA {formatDuration(item.eta || 0)}</span>}
            {item.downloadStatus && <span>Download {item.downloadStatus}{item.downloadPercent ? ` ${item.downloadPercent}%` : ""}</span>}
            {item.error && <span className="text-red-300">{item.error}</span>}
          </div>
        </div>
        {item.downloadReady && (
          <div className="flex gap-1">
            {item.downloadStatus === "downloading" ? (
              <button type="button" onClick={() => onPauseDownload?.(item)} title="Pause download" className="rounded-md border border-white/10 bg-white/[0.04] p-2 text-slate-200 hover:border-cyan-300/40">
                <Pause size={14} />
              </button>
            ) : (
              <button type="button" onClick={() => onDownload?.(item)} title={item.downloadStatus === "paused" ? "Resume download" : "Download"} className="rounded-md border border-white/10 bg-white/[0.04] p-2 text-slate-200 hover:border-cyan-300/40">
                {item.downloadStatus === "paused" ? <Play size={14} /> : <Download size={14} />}
              </button>
            )}
          </div>
        )}
        {failed && <RotateCcw className="mt-2 text-slate-500" size={14} />}
      </div>
    </div>
  );
}

function Metric({ icon: Icon, label, value, tone = "slate" }) {
  const tones = { slate: "text-slate-300", green: "text-emerald-300", cyan: "text-cyan-300", amber: "text-amber-300" };
  return <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4"><Icon className={tones[tone]} size={20} /><p className="mt-3 text-2xl font-semibold text-white">{value}</p><p className="text-xs text-slate-500">{label}</p></div>;
}

function TinyAction({ icon: Icon, label, onClick, danger = false }) {
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onClick?.();
      }}
      className={`flex items-center justify-center gap-1 rounded-md border px-2 py-1.5 text-xs ${danger ? "border-red-300/20 bg-red-400/10 text-red-100" : "border-white/10 bg-white/[0.04] text-slate-200 hover:border-cyan-300/40"}`}
    >
      <Icon size={13} /> {label}
    </button>
  );
}

function Panel({ title, action, children }) {
  return <section className="rounded-lg border border-white/10 bg-slate-950/70 p-4 shadow-xl shadow-black/10"><div className="mb-4 flex items-center justify-between gap-3"><h2 className="font-semibold text-white">{title}</h2>{action}</div>{children}</section>;
}

function Notice({ tone = "amber", title, detail }) {
  const tones = {
    amber: "border-amber-300/25 bg-amber-300/10 text-amber-100",
    green: "border-emerald-300/25 bg-emerald-300/10 text-emerald-100",
    red: "border-red-300/25 bg-red-300/10 text-red-100"
  };
  return <div className={`rounded-lg border px-4 py-3 ${tones[tone]}`}><p className="text-sm font-semibold">{title}</p><p className="mt-1 text-xs opacity-80">{detail}</p></div>;
}

function Status({ value }) {
  const online = value === "ONLINE" || value === "BUSY";
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${online ? "bg-emerald-400/10 text-emerald-200" : "bg-slate-700 text-slate-300"}`}>{online ? <Wifi size={12} /> : <WifiOff size={12} />}{value}</span>;
}

function SessionPill({ session }) {
  const active = session.status === "ACTIVE";
  return <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${active ? "bg-emerald-400/10 text-emerald-200" : "bg-amber-400/10 text-amber-200"}`}>{active ? <CheckCircle2 size={14} /> : <RefreshCw size={14} />}{session.status} · {session.permission}</span>;
}

function ControlButton({ icon: Icon, label, disabled, onClick }) {
  return <button disabled={disabled} onClick={onClick} title={label} className="rounded-md border border-white/10 bg-slate-950/85 p-2 text-slate-200 disabled:opacity-40"><Icon size={16} /></button>;
}

function DesktopPlaceholder({ session }) {
  return <div className="grid h-full place-items-center p-8 text-center"><div><Monitor className="mx-auto text-slate-600" size={48} /><p className="mt-3 font-semibold text-white">{session ? "Waiting for remote frames" : "No active remote desktop"}</p><p className="mt-1 text-sm text-slate-500">{session ? "The agent begins streaming after target approval." : "Select a device and request a secure session."}</p></div></div>;
}

function Empty({ title, detail }) {
  return <div className="rounded-lg border border-dashed border-white/10 bg-white/[0.02] p-5 text-center"><p className="font-medium text-slate-200">{title}</p><p className="mt-1 text-xs text-slate-500">{detail}</p></div>;
}

function formatBytes(bytes = 0) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function formatDuration(seconds = 0) {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0s";
  if (seconds < 60) return `${Math.ceil(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.ceil(seconds % 60);
  return `${minutes}m ${remaining}s`;
}

function fileIcon(item) {
  const type = item.type || "";
  const name = item.name || "";
  if (type.startsWith("image/")) return Image;
  if (type.includes("zip") || /\.(zip|rar|7z|tar|gz)$/i.test(name)) return FileArchive;
  if (type.startsWith("text/") || /\.(txt|md|json|csv|log)$/i.test(name)) return FileText;
  return File;
}
