import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent, DragEvent, FormEvent, ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  CheckCircle2,
  Download,
  Eye,
  FileUp,
  Folder,
  HardDrive,
  History,
  Laptop,
  Link2,
  LogIn,
  Monitor,
  RefreshCw,
  Rocket,
  Search,
  Shield,
  Trash2,
  Upload,
  Wifi,
  WifiOff,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import {
  approveProjectFile,
  connectDevices,
  deleteStorageFile,
  deployProjectFile,
  disconnectConnection,
  downloadBlob,
  getTransferSummary,
  heartbeatDevice,
  listAuditLogs,
  listConnections,
  listDevices,
  listProjectFiles,
  listStorageFiles,
  listTransferJobs,
  moveStorageFile,
  registerDevice,
  rejectProjectFile,
  renameStorageFile,
  uploadChunk,
} from "../api/desktopTransfer";
import type { DesktopDevice, DeviceConnection, ProjectFile, StorageFile, TransferJob } from "../api/desktopTransfer";
import { useAuth } from "../context/AuthContext.jsx";

const CHUNK_SIZE = 2 * 1024 * 1024;

type Tone = "cyan" | "emerald" | "amber" | "rose" | "violet" | "blue" | "slate";
type TabId = "super" | "admin" | "developer" | "devices" | "transfer" | "upload" | "approval" | "storage" | "history";

const toneText: Record<Tone, string> = {
  cyan: "text-cyan-200",
  emerald: "text-emerald-200",
  amber: "text-amber-200",
  rose: "text-rose-200",
  violet: "text-violet-200",
  blue: "text-blue-200",
  slate: "text-slate-300",
};

const toneBorder: Record<Tone, string> = {
  cyan: "border-cyan-300/25",
  emerald: "border-emerald-300/25",
  amber: "border-amber-300/25",
  rose: "border-rose-300/25",
  violet: "border-violet-300/25",
  blue: "border-blue-300/25",
  slate: "border-slate-300/20",
};

const toneBg: Record<Tone, string> = {
  cyan: "bg-cyan-400/10",
  emerald: "bg-emerald-400/10",
  amber: "bg-amber-400/10",
  rose: "bg-rose-400/10",
  violet: "bg-violet-400/10",
  blue: "bg-blue-400/10",
  slate: "bg-slate-400/10",
};

function makeId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `WEB-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getStoredDeviceId() {
  const key = "desktopTransferDeviceId";
  let id = localStorage.getItem(key);
  if (!id) {
    id = `WEB-${makeId().slice(0, 12).toUpperCase()}`;
    localStorage.setItem(key, id);
  }
  return id;
}

function getDefaultDeviceName() {
  const platform = navigator.platform || "Web Device";
  return `${platform} Browser`;
}

function formatBytes(value: unknown) {
  const bytes = Number(value || 0);
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function formatSpeed(value: unknown) {
  const speed = Number(value || 0);
  return speed ? `${formatBytes(speed)}/s` : "0 B/s";
}

function statusTone(status = ""): Tone {
  if (["online", "connected", "completed", "approved", "deployed", "clean"].includes(status)) return "emerald";
  if (["pending", "uploading", "in_progress", "queued", "connecting"].includes(status)) return "cyan";
  if (["maintenance", "deploying"].includes(status)) return "amber";
  if (["offline", "failed", "rejected", "quarantined", "disconnected"].includes(status)) return "rose";
  return "slate";
}

function isAdmin(user: { role?: string; is_staff?: boolean; is_superuser?: boolean } | null) {
  return Boolean(user?.is_superuser || user?.is_staff || user?.role === "SUPER_ADMIN" || user?.role === "ADMIN");
}

function useDesktopTransferSocket(enabled: boolean) {
  const queryClient = useQueryClient();
  const [lastEvent, setLastEvent] = useState<string>("waiting");

  useEffect(() => {
    if (!enabled) return undefined;
    const token = localStorage.getItem("accessToken");
    if (!token) return undefined;
    let socket: WebSocket | null = null;
    let closed = false;
    let retry = 500;

    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${protocol}://${window.location.host}/ws/file-transfer/?token=${encodeURIComponent(token)}`);
      socket.onopen = () => {
        retry = 500;
        setLastEvent("connected");
      };
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data);
          setLastEvent(event.type || "event");
          queryClient.invalidateQueries({ queryKey: ["desktop-transfer"] });
        } catch {
          setLastEvent("event");
        }
      };
      socket.onclose = () => {
        setLastEvent("reconnecting");
        if (!closed) {
          window.setTimeout(connect, retry);
          retry = Math.min(retry * 2, 8000);
        }
      };
    };

    connect();
    return () => {
      closed = true;
      socket?.close();
    };
  }, [enabled, queryClient]);

  return lastEvent;
}

export default function FileTracking() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const queryClient = useQueryClient();
  const socketEvent = useDesktopTransferSocket(Boolean(user));
  const [activeTab, setActiveTab] = useState<TabId>(admin ? "admin" : "developer");
  const [search, setSearch] = useState("");
  const [dragging, setDragging] = useState(false);
  const [selectedSource, setSelectedSource] = useState("");
  const [selectedDestination, setSelectedDestination] = useState("");
  const [uploadDestination, setUploadDestination] = useState("");
  const [approvalDestination, setApprovalDestination] = useState("");
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [uploadMessage, setUploadMessage] = useState("");
  const [registerForm, setRegisterForm] = useState(() => ({
    device_id: getStoredDeviceId(),
    name: getDefaultDeviceName(),
    device_type: "desktop",
    ip_address: "",
    mac_address: "",
    os_name: navigator.userAgent,
    storage_path: "/server_storage/projects/",
  }));

  const summaryQuery = useQuery({ queryKey: ["desktop-transfer", "summary"], queryFn: getTransferSummary, refetchInterval: 10000 });
  const devicesQuery = useQuery({ queryKey: ["desktop-transfer", "devices"], queryFn: listDevices, refetchInterval: 10000 });
  const connectionsQuery = useQuery({ queryKey: ["desktop-transfer", "connections"], queryFn: listConnections, refetchInterval: 10000 });
  const filesQuery = useQuery({ queryKey: ["desktop-transfer", "files"], queryFn: listProjectFiles, refetchInterval: 10000 });
  const jobsQuery = useQuery({ queryKey: ["desktop-transfer", "jobs"], queryFn: listTransferJobs, refetchInterval: 5000 });
  const storageQuery = useQuery({ queryKey: ["desktop-transfer", "storage"], queryFn: listStorageFiles, refetchInterval: 10000 });
  const auditQuery = useQuery({ queryKey: ["desktop-transfer", "audit"], queryFn: listAuditLogs, enabled: admin, refetchInterval: 10000 });

  const devices = devicesQuery.data || [];
  const connections = connectionsQuery.data || [];
  const files = filesQuery.data || [];
  const jobs = jobsQuery.data || [];
  const storage = storageQuery.data || [];
  const audits = auditQuery.data || [];
  const onlineDevices = devices.filter((device) => device.status === "online");
  const serverDevices = devices.filter((device) => ["server", "nas", "storage"].includes(device.device_type));
  const pendingFiles = files.filter((file) => file.status === "pending");
  const filteredFiles = useMemo(() => {
    const term = search.toLowerCase().trim();
    if (!term) return files;
    return files.filter((file) => `${file.original_name} ${file.status} ${file.uploaded_by_name || ""} ${file.source_device_name || ""} ${file.destination_device_name || ""}`.toLowerCase().includes(term));
  }, [files, search]);

  useEffect(() => {
    if (!selectedSource && devices[0]) setSelectedSource(devices[0].id);
    if (!selectedDestination && devices[1]) setSelectedDestination(devices[1].id);
    if (!uploadDestination && serverDevices[0]) setUploadDestination(serverDevices[0].id);
    if (!approvalDestination && serverDevices[0]) setApprovalDestination(serverDevices[0].id);
  }, [approvalDestination, devices, selectedDestination, selectedSource, serverDevices, uploadDestination]);

  const invalidateAll = () => queryClient.invalidateQueries({ queryKey: ["desktop-transfer"] });

  const registerMutation = useMutation({ mutationFn: registerDevice, onSuccess: invalidateAll });
  const heartbeatMutation = useMutation({ mutationFn: ({ id }: { id: string }) => heartbeatDevice(id, { transfer_status: "ready" }), onSuccess: invalidateAll });
  const connectMutation = useMutation({ mutationFn: () => connectDevices(selectedSource, selectedDestination), onSuccess: invalidateAll });
  const disconnectMutation = useMutation({ mutationFn: disconnectConnection, onSuccess: invalidateAll });
  const approveMutation = useMutation({ mutationFn: ({ id, destination }: { id: string; destination: string }) => approveProjectFile(id, { destination_device: destination }), onSuccess: invalidateAll });
  const rejectMutation = useMutation({ mutationFn: ({ id, reason }: { id: string; reason: string }) => rejectProjectFile(id, reason), onSuccess: invalidateAll });
  const deployMutation = useMutation({ mutationFn: ({ id, destination }: { id: string; destination: string }) => deployProjectFile(id, { destination_device: destination }), onSuccess: invalidateAll });
  const deleteStorageMutation = useMutation({ mutationFn: deleteStorageFile, onSuccess: invalidateAll });
  const renameStorageMutation = useMutation({ mutationFn: ({ id, name }: { id: string; name: string }) => renameStorageFile(id, name), onSuccess: invalidateAll });
  const moveStorageMutation = useMutation({ mutationFn: ({ id, folder }: { id: string; folder: string }) => moveStorageFile(id, folder), onSuccess: invalidateAll });

  const uploadSingleFile = async (file: File, options: { destination?: string; autoTransfer?: boolean; source?: string } = {}) => {
    const uploadId = makeId();
    const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    const totalChunks = Math.max(1, Math.ceil(file.size / CHUNK_SIZE));
    setUploadProgress((current) => ({ ...current, [uploadId]: 0 }));
    for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex += 1) {
      const start = chunkIndex * CHUNK_SIZE;
      const chunk = file.slice(start, Math.min(file.size, start + CHUNK_SIZE));
      const form = new FormData();
      form.append("upload_id", uploadId);
      form.append("file_name", file.name);
      form.append("relative_path", relativePath);
      form.append("total_size", String(file.size));
      form.append("total_chunks", String(totalChunks));
      form.append("chunk_index", String(chunkIndex));
      form.append("source_device", options.source || selectedSource || "");
      form.append("destination_device", options.destination || uploadDestination || selectedDestination || "");
      form.append("auto_transfer", options.autoTransfer ? "true" : "false");
      form.append("chunk", chunk, file.name);
      await uploadChunk(form, () => {
        const progress = Math.round(((chunkIndex + 1) / totalChunks) * 100);
        setUploadProgress((current) => ({ ...current, [uploadId]: progress }));
      });
    }
    setUploadProgress((current) => ({ ...current, [uploadId]: 100 }));
  };

  const uploadFiles = async (fileList: FileList | File[], options: { destination?: string; autoTransfer?: boolean; source?: string } = {}) => {
    const items = Array.from(fileList);
    if (!items.length) return;
    setUploadMessage(`Uploading ${items.length} file${items.length === 1 ? "" : "s"}...`);
    for (const file of items) {
      await uploadSingleFile(file, options);
    }
    setUploadMessage(admin && options.autoTransfer ? "Upload and transfer completed." : "Upload completed. Waiting for admin review.");
    invalidateAll();
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>, autoTransfer = false) => {
    event.preventDefault();
    setDragging(false);
    uploadFiles(event.dataTransfer.files, { destination: uploadDestination, source: selectedSource, autoTransfer });
  };

  const registerSubmit = (event: FormEvent) => {
    event.preventDefault();
    localStorage.setItem("desktopTransferDeviceId", registerForm.device_id);
    registerMutation.mutate(registerForm);
  };

  const transferSubmit = async (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files;
    if (!selected?.length) return;
    await uploadFiles(selected, { destination: selectedDestination, source: selectedSource, autoTransfer: admin });
    event.target.value = "";
  };

  const tabs: Array<{ id: TabId; label: string; icon: LucideIcon; adminOnly?: boolean }> = [
    { id: "super", label: "Super Admin Dashboard", icon: Shield, adminOnly: true },
    { id: "admin", label: "Admin Dashboard", icon: Monitor, adminOnly: true },
    { id: "developer", label: "Developer Dashboard", icon: Laptop },
    { id: "devices", label: "Device Connection", icon: Link2 },
    { id: "transfer", label: "Desktop Transfer", icon: Upload },
    { id: "upload", label: "File Upload", icon: FileUp },
    { id: "approval", label: "Admin Approval", icon: CheckCircle2, adminOnly: true },
    { id: "storage", label: "Server Storage", icon: HardDrive },
    { id: "history", label: "Transfer History", icon: History },
  ].filter((tab) => !tab.adminOnly || admin);

  return (
    <div className="min-h-screen space-y-5 p-4 text-slate-200 lg:p-6">
      <section className="rounded-lg border border-white/10 bg-slate-950/85 p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge label={`Socket ${socketEvent}`} tone={socketEvent === "connected" ? "emerald" : "amber"} icon={Wifi} />
              <StatusBadge label={user?.role || "Authenticated"} tone={admin ? "violet" : "cyan"} icon={Shield} />
              <StatusBadge label="JWT secured APIs" tone="emerald" icon={LogIn} />
            </div>
            <p className="mt-5 text-xs font-semibold uppercase text-cyan-200">Real-Time Desktop-to-Desktop File Transfer</p>
            <h1 className="mt-2 text-3xl font-semibold text-white">Working Transfer, Approval, Deployment and Physical Storage Platform</h1>
            <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-400">
              Register devices, connect peers, upload in chunks, approve or reject developer files, deploy approved files to server storage, and manage history in real time.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <button className="btn-primary" type="button" onClick={() => invalidateAll()}>
              <RefreshCw size={16} />
              Refresh Live Data
            </button>
            <button className="btn-secondary" type="button" onClick={() => setActiveTab("devices")}>
              <Monitor size={16} />
              Register Device
            </button>
          </div>
        </div>
      </section>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        <Metric icon={Monitor} label="Devices" value={Number((summaryQuery.data?.devices as { total?: number })?.total ?? devices.length)} detail={`${onlineDevices.length} online`} tone="cyan" />
        <Metric icon={Upload} label="Active Transfers" value={Number((summaryQuery.data?.transfers as { active?: number })?.active ?? 0)} detail="real transfer jobs" tone="emerald" />
        <Metric icon={CheckCircle2} label="Pending Approval" value={Number((summaryQuery.data?.files as { pending?: number })?.pending ?? pendingFiles.length)} detail="admin review queue" tone="amber" />
        <Metric icon={Rocket} label="Deployed" value={Number((summaryQuery.data?.files as { deployed?: number })?.deployed ?? 0)} detail="server storage copies" tone="violet" />
        <Metric icon={HardDrive} label="Storage Files" value={Number((summaryQuery.data?.storage as { files?: number })?.files ?? storage.length)} detail={formatBytes((summaryQuery.data?.storage as { bytes?: number })?.bytes ?? 0)} tone="blue" />
        <Metric icon={History} label="History" value={jobs.length} detail="stored transfer records" tone="slate" />
      </div>

      <div className="flex gap-2 overflow-x-auto rounded-lg border border-white/10 bg-white/[0.035] p-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`inline-flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition ${
              activeTab === tab.id ? "bg-cyan-400 text-slate-950" : "bg-slate-950/60 text-slate-300 hover:bg-white/10"
            }`}
            type="button"
            onClick={() => setActiveTab(tab.id)}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {(activeTab === "super" || activeTab === "admin" || activeTab === "developer") && (
        <DashboardSection admin={admin} files={filteredFiles} jobs={jobs} devices={devices} pendingFiles={pendingFiles} setTab={setActiveTab} />
      )}

      {activeTab === "devices" && (
        <div className="grid gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
          <Panel title="Device Registration" eyebrow="Unique Device ID and storage path" icon={Monitor}>
            <form className="grid gap-3" onSubmit={registerSubmit}>
              <Field label="Device ID" value={registerForm.device_id} onChange={(value) => setRegisterForm((current) => ({ ...current, device_id: value }))} />
              <Field label="Device Name" value={registerForm.name} onChange={(value) => setRegisterForm((current) => ({ ...current, name: value }))} />
              <SelectField label="Device Type" value={registerForm.device_type} options={["desktop", "laptop", "mobile", "tablet", "server", "nas", "storage"]} onChange={(value) => setRegisterForm((current) => ({ ...current, device_type: value }))} />
              <Field label="IP Address" value={registerForm.ip_address} onChange={(value) => setRegisterForm((current) => ({ ...current, ip_address: value }))} required={false} />
              <Field label="MAC Address" value={registerForm.mac_address} onChange={(value) => setRegisterForm((current) => ({ ...current, mac_address: value }))} required={false} />
              <Field label="OS" value={registerForm.os_name} onChange={(value) => setRegisterForm((current) => ({ ...current, os_name: value }))} />
              <Field label="Storage Path" value={registerForm.storage_path} onChange={(value) => setRegisterForm((current) => ({ ...current, storage_path: value }))} />
              <button className="btn-primary" type="submit" disabled={registerMutation.isPending}>
                <Wifi size={16} />
                {registerMutation.isPending ? "Registering" : "Register / Heartbeat"}
              </button>
            </form>
          </Panel>

          <Panel title="Live Devices" eyebrow="Online/offline status from database and WebSocket events" icon={Laptop}>
            <div className="grid gap-3 lg:grid-cols-2">
              {devices.map((device) => (
                <DeviceCard key={device.id} device={device} onHeartbeat={() => heartbeatMutation.mutate({ id: device.id })} />
              ))}
              {!devices.length && <EmptyState text="No devices registered yet. Register this browser or a server storage device to begin." />}
            </div>
          </Panel>
        </div>
      )}

      {activeTab === "transfer" && (
        <div className="grid gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
          <Panel title="Connect Devices" eyebrow="Connect and disconnect updates database and socket events" icon={Link2}>
            <div className="grid gap-3">
              <SelectField label="Source Device" value={selectedSource} options={devices.map((device) => device.id)} labels={Object.fromEntries(devices.map((device) => [device.id, device.name]))} onChange={setSelectedSource} />
              <SelectField label="Destination Device" value={selectedDestination} options={devices.map((device) => device.id)} labels={Object.fromEntries(devices.map((device) => [device.id, device.name]))} onChange={setSelectedDestination} />
              <button className="btn-primary" type="button" disabled={!selectedSource || !selectedDestination || selectedSource === selectedDestination || connectMutation.isPending} onClick={() => connectMutation.mutate()}>
                <Wifi size={16} />
                Connect
              </button>
              <label className="btn-secondary cursor-pointer">
                <Upload size={16} />
                Choose File and Transfer
                <input className="hidden" type="file" multiple onChange={transferSubmit} />
              </label>
              <p className="text-xs text-slate-500">{admin ? "Admin transfers deploy directly to the selected destination." : "Developer transfers upload for Admin approval."}</p>
            </div>
          </Panel>

          <Panel title="Active Connections and Transfer Jobs" eyebrow="Connection and job status is persisted" icon={Activity}>
            <div className="grid gap-3 lg:grid-cols-2">
              {connections.map((connection) => (
                <ConnectionCard key={connection.id} connection={connection} onDisconnect={() => disconnectMutation.mutate(connection.id)} />
              ))}
              {!connections.length && <EmptyState text="No active connections. Select two registered devices and click Connect." />}
            </div>
            <div className="mt-5 space-y-3">
              {jobs.slice(0, 8).map((job) => (
                <TransferJobRow key={job.id} job={job} />
              ))}
            </div>
          </Panel>
        </div>
      )}

      {activeTab === "upload" && (
        <Panel title="Drag and Drop Upload" eyebrow="Chunk upload starts immediately and stores details in the database" icon={FileUp}>
          <div className="mb-4 grid gap-3 md:grid-cols-2">
            <SelectField label="Source Device" value={selectedSource} options={devices.map((device) => device.id)} labels={Object.fromEntries(devices.map((device) => [device.id, device.name]))} onChange={setSelectedSource} />
            <SelectField label="Target Server / Device" value={uploadDestination} options={devices.map((device) => device.id)} labels={Object.fromEntries(devices.map((device) => [device.id, device.name]))} onChange={setUploadDestination} />
          </div>
          <div
            className={`rounded-lg border border-dashed p-8 text-center transition ${dragging ? "border-cyan-300 bg-cyan-400/10" : "border-white/15 bg-slate-950/55"}`}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => handleDrop(event, false)}
          >
            <Upload className="mx-auto text-cyan-200" size={38} />
            <h2 className="mt-4 text-xl font-semibold text-white">Drop project files or folders</h2>
            <p className="mt-2 text-sm text-slate-400">Developer uploads become Pending Review. Admin users can approve from mobile, tablet, laptop, or desktop.</p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <label className="btn-primary cursor-pointer">
                <FileUp size={16} />
                Select Files
                <input className="hidden" type="file" multiple onChange={(event) => event.target.files && uploadFiles(event.target.files, { destination: uploadDestination, source: selectedSource, autoTransfer: false })} />
              </label>
              <label className="btn-secondary cursor-pointer">
                <Folder size={16} />
                Select Folder
                <input
                  className="hidden"
                  type="file"
                  multiple
                  onChange={(event) => event.target.files && uploadFiles(event.target.files, { destination: uploadDestination, source: selectedSource, autoTransfer: false })}
                  {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
                />
              </label>
            </div>
          </div>
          {uploadMessage && <p className="mt-3 rounded-lg border border-white/10 bg-white/[0.035] p-3 text-sm text-slate-300">{uploadMessage}</p>}
          <ProgressList progress={uploadProgress} />
        </Panel>
      )}

      {activeTab === "approval" && admin && (
        <Panel title="Admin Approval" eyebrow="Download, preview, approve, reject and deploy to physical server storage" icon={CheckCircle2}>
          <div className="mb-4 grid gap-3 md:grid-cols-[1fr_260px]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
              <input className="form-control w-full pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search uploaded files" />
            </div>
            <SelectField label="Deploy Target" value={approvalDestination} options={devices.map((device) => device.id)} labels={Object.fromEntries(devices.map((device) => [device.id, device.name]))} onChange={setApprovalDestination} />
          </div>
          <div className="space-y-3">
            {filteredFiles.map((file) => (
              <ProjectFileRow
                key={file.id}
                file={file}
                admin={admin}
                onDownload={() => downloadBlob(`/v1/file-transfer/files/${file.id}/download/`, file.original_name)}
                onPreview={() => downloadBlob(`/v1/file-transfer/files/${file.id}/preview/`, file.original_name, true)}
                onApprove={() => approveMutation.mutate({ id: file.id, destination: approvalDestination || file.destination_device || "" })}
                onReject={() => rejectMutation.mutate({ id: file.id, reason: window.prompt("Reject reason") || "" })}
                onDeploy={() => deployMutation.mutate({ id: file.id, destination: approvalDestination || file.destination_device || "" })}
              />
            ))}
            {!filteredFiles.length && <EmptyState text="No uploaded files found." />}
          </div>
        </Panel>
      )}

      {activeTab === "storage" && (
        <Panel title="Physical Server Storage" eyebrow="Files are read from the configured physical storage folder" icon={HardDrive}>
          <div className="space-y-3">
            {storage.map((file) => (
              <StorageRow
                key={file.id}
                file={file}
                admin={admin}
                onDownload={() => downloadBlob(`/v1/file-transfer/storage/${file.id}/download/`, file.name)}
                onDelete={() => deleteStorageMutation.mutate(file.id)}
                onRename={() => {
                  const name = window.prompt("New file name", file.name);
                  if (name) renameStorageMutation.mutate({ id: file.id, name });
                }}
                onMove={() => {
                  const folder = window.prompt("Move to folder under storage root", "");
                  if (folder !== null) moveStorageMutation.mutate({ id: file.id, folder });
                }}
              />
            ))}
            {!storage.length && <EmptyState text="No files are stored in physical server storage yet. Approve a file to deploy it." />}
          </div>
        </Panel>
      )}

      {activeTab === "history" && (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
          <Panel title="Transfer History" eyebrow="Source, destination, file, status, time and approver" icon={History}>
            <div className="space-y-3">
              {jobs.map((job) => (
                <TransferJobRow key={job.id} job={job} />
              ))}
              {!jobs.length && <EmptyState text="No transfers have been recorded yet." />}
            </div>
          </Panel>
          <Panel title="Audit Logs" eyebrow="Security and action trail" icon={Shield}>
            {admin ? (
              <div className="space-y-3">
                {audits.slice(0, 20).map((log) => (
                  <div key={log.id} className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
                    <p className="font-semibold text-white">{log.action}</p>
                    <p className="mt-1 text-sm text-slate-400">{log.message}</p>
                    <p className="mt-2 text-xs text-slate-500">
                      {log.actor_name || "system"} - {new Date(log.created_at).toLocaleString()}
                    </p>
                  </div>
                ))}
                {!audits.length && <EmptyState text="No audit logs yet." />}
              </div>
            ) : (
              <EmptyState text="Audit logs are available to Admin and Super Admin roles." />
            )}
          </Panel>
        </div>
      )}
    </div>
  );
}

function DashboardSection({
  admin,
  files,
  jobs,
  devices,
  pendingFiles,
  setTab,
}: {
  admin: boolean;
  files: ProjectFile[];
  jobs: TransferJob[];
  devices: DesktopDevice[];
  pendingFiles: ProjectFile[];
  setTab: (tab: TabId) => void;
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      <Panel title={admin ? "Operations Dashboard" : "Developer Dashboard"} eyebrow="Role-based workspace" icon={Activity}>
        <div className="grid gap-3 md:grid-cols-3">
          <QuickAction icon={Monitor} label="Register Device" detail="Create or heartbeat a unique device ID." onClick={() => setTab("devices")} />
          <QuickAction icon={FileUp} label="Upload Project" detail="Chunk upload files or folders." onClick={() => setTab("upload")} />
          <QuickAction icon={History} label="Transfer History" detail="Review completed and failed jobs." onClick={() => setTab("history")} />
          {admin && <QuickAction icon={CheckCircle2} label="Approve Files" detail={`${pendingFiles.length} pending review.`} onClick={() => setTab("approval")} />}
          {admin && <QuickAction icon={HardDrive} label="Server Storage" detail="Download, rename, move, delete." onClick={() => setTab("storage")} />}
          {admin && <QuickAction icon={Rocket} label="Deploy" detail="Deploy approved files to a server." onClick={() => setTab("approval")} />}
        </div>
      </Panel>
      <Panel title="Live Snapshot" eyebrow="Database-backed state" icon={Wifi}>
        <div className="space-y-3">
          <Info label="Registered devices" value={devices.length} />
          <Info label="Online devices" value={devices.filter((device) => device.status === "online").length} />
          <Info label="Visible files" value={files.length} />
          <Info label="Transfer jobs" value={jobs.length} />
          <Info label="Failed transfers" value={jobs.filter((job) => job.status === "failed").length} />
        </div>
      </Panel>
    </div>
  );
}

function Panel({ title, eyebrow, icon: Icon, children }: { title: string; eyebrow: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-white/10 bg-white/[0.035] p-4 shadow-[0_18px_60px_rgba(2,6,23,0.26)] backdrop-blur">
      <div className="mb-4 flex items-start gap-3">
        <span className="grid size-10 place-items-center rounded-lg border border-cyan-300/20 bg-cyan-400/10 text-cyan-200">
          <Icon size={19} />
        </span>
        <div>
          <p className="text-xs font-semibold text-cyan-200">{eyebrow}</p>
          <h2 className="mt-1 text-lg font-semibold text-white">{title}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}

function Metric({ icon: Icon, label, value, detail, tone }: { icon: LucideIcon; label: string; value: string | number; detail: string; tone: Tone }) {
  return (
    <div className={`rounded-lg border ${toneBorder[tone]} bg-white/[0.04] p-4`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-slate-400">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
          <p className="mt-1 text-xs text-slate-500">{detail}</p>
        </div>
        <span className={`grid size-10 place-items-center rounded-lg ${toneBg[tone]} ${toneText[tone]}`}>
          <Icon size={19} />
        </span>
      </div>
    </div>
  );
}

function DeviceCard({ device, onHeartbeat }: { device: DesktopDevice; onHeartbeat: () => void }) {
  const tone = statusTone(device.status);
  return (
    <div className={`rounded-lg border ${toneBorder[tone]} bg-slate-950/60 p-4`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-white">{device.name}</h3>
          <p className="mt-1 text-xs text-slate-500">
            {device.device_id} - {device.device_type} - {device.os_name || "OS pending"}
          </p>
        </div>
        <StatusBadge label={device.status} tone={tone} icon={device.status === "online" ? Wifi : WifiOff} />
      </div>
      <div className="mt-4 grid gap-2 text-xs md:grid-cols-2">
        <Info label="IP" value={device.ip_address || "not set"} compact />
        <Info label="MAC" value={device.mac_address || "not set"} compact />
        <Info label="CPU" value={`${Math.round(device.cpu_percent || 0)}%`} compact />
        <Info label="RAM" value={`${Math.round(device.ram_percent || 0)}%`} compact />
        <Info label="Disk" value={`${Math.round(device.disk_percent || 0)}%`} compact />
        <Info label="Storage" value={device.storage_path} compact />
      </div>
      <button className="btn-secondary mt-4" type="button" onClick={onHeartbeat}>
        <RefreshCw size={16} />
        Heartbeat
      </button>
    </div>
  );
}

function ConnectionCard({ connection, onDisconnect }: { connection: DeviceConnection; onDisconnect: () => void }) {
  const tone = statusTone(connection.status);
  return (
    <div className={`rounded-lg border ${toneBorder[tone]} bg-slate-950/60 p-4`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-white">
            {connection.source_device_name} to {connection.destination_device_name}
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            {connection.transport} - {connection.encryption}
          </p>
        </div>
        <StatusBadge label={connection.status} tone={tone} />
      </div>
      <button className="btn-secondary mt-4" type="button" onClick={onDisconnect}>
        <WifiOff size={16} />
        Disconnect
      </button>
    </div>
  );
}

function ProjectFileRow({
  file,
  admin,
  onDownload,
  onPreview,
  onApprove,
  onReject,
  onDeploy,
}: {
  file: ProjectFile;
  admin: boolean;
  onDownload: () => void;
  onPreview: () => void;
  onApprove: () => void;
  onReject: () => void;
  onDeploy: () => void;
}) {
  const tone = statusTone(file.status);
  return (
    <div className={`rounded-lg border ${toneBorder[tone]} bg-slate-950/60 p-4`}>
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate font-semibold text-white">{file.original_name}</h3>
            <StatusBadge label={file.status} tone={tone} />
            <Risk value={file.risk_score} />
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {formatBytes(file.size_bytes)} - {file.uploaded_by_name || "unknown"} - {new Date(file.created_at).toLocaleString()}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            {file.source_device_name || "source pending"} to {file.destination_device_name || "target pending"} - scan {file.security_scan_status || "pending"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary" type="button" onClick={onPreview}>
            <Eye size={16} />
            Preview
          </button>
          <button className="btn-secondary" type="button" onClick={onDownload}>
            <Download size={16} />
            Download
          </button>
          {admin && file.status === "pending" && (
            <>
              <button className="btn-primary" type="button" onClick={onApprove}>
                <CheckCircle2 size={16} />
                Approve
              </button>
              <button className="btn-secondary" type="button" onClick={onReject}>
                <XCircle size={16} />
                Reject
              </button>
            </>
          )}
          {admin && ["approved", "failed"].includes(file.status) && (
            <button className="btn-primary" type="button" onClick={onDeploy}>
              <Rocket size={16} />
              Deploy
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function TransferJobRow({ job }: { job: TransferJob }) {
  const tone = statusTone(job.status);
  return (
    <div className={`rounded-lg border ${toneBorder[tone]} bg-slate-950/60 p-4`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-white">{job.file_name}</h3>
          <p className="mt-1 text-xs text-slate-500">
            {job.source_device_name || "upload"} to {job.destination_device_name || "destination"} - {formatBytes(job.size_bytes)}
          </p>
          {job.last_error && <p className="mt-1 text-xs text-rose-200">{job.last_error}</p>}
        </div>
        <StatusBadge label={job.status} tone={tone} />
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
        <div className={`h-full rounded-full ${tone === "rose" ? "bg-rose-300" : tone === "emerald" ? "bg-emerald-300" : "bg-cyan-300"}`} style={{ width: `${Math.min(100, Math.max(0, job.progress_percent || 0))}%` }} />
      </div>
      <div className="mt-2 flex flex-wrap justify-between gap-2 text-xs text-slate-400">
        <span>{Math.round(job.progress_percent || 0)}%</span>
        <span>{formatBytes(job.bytes_transferred)} transferred</span>
        <span>{formatSpeed(job.speed_bytes_per_sec)}</span>
      </div>
    </div>
  );
}

function StorageRow({ file, admin, onDownload, onDelete, onRename, onMove }: { file: StorageFile; admin: boolean; onDownload: () => void; onDelete: () => void; onRename: () => void; onMove: () => void }) {
  return (
    <div className="rounded-lg border border-white/10 bg-slate-950/60 p-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-white">{file.name}</h3>
          <p className="mt-1 truncate text-xs text-slate-500">{file.path}</p>
          <p className="mt-1 text-xs text-slate-400">
            {formatBytes(file.size_bytes)} - {file.extension || "file"} - {file.owner_name || "system"} - {file.device_name || "storage"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary" type="button" onClick={onDownload}>
            <Download size={16} />
            Download
          </button>
          {admin && (
            <>
              <button className="btn-secondary" type="button" onClick={onRename}>
                Rename
              </button>
              <button className="btn-secondary" type="button" onClick={onMove}>
                Move
              </button>
              <button className="btn-secondary" type="button" onClick={onDelete}>
                <Trash2 size={16} />
                Delete
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ProgressList({ progress }: { progress: Record<string, number> }) {
  const entries = Object.entries(progress);
  if (!entries.length) return null;
  return (
    <div className="mt-4 space-y-3">
      {entries.map(([id, value]) => (
        <div key={id} className="rounded-lg border border-white/10 bg-slate-950/60 p-3">
          <div className="flex justify-between gap-3 text-sm">
            <span className="truncate text-slate-300">{id}</span>
            <span className="font-semibold text-white">{value}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full bg-cyan-300" style={{ width: `${value}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function QuickAction({ icon: Icon, label, detail, onClick }: { icon: LucideIcon; label: string; detail: string; onClick: () => void }) {
  return (
    <button className="rounded-lg border border-white/10 bg-slate-950/60 p-4 text-left transition hover:border-cyan-300/30 hover:bg-cyan-400/10" type="button" onClick={onClick}>
      <Icon className="text-cyan-200" size={20} />
      <h3 className="mt-3 font-semibold text-white">{label}</h3>
      <p className="mt-1 text-sm text-slate-400">{detail}</p>
    </button>
  );
}

function Field({ label, value, onChange, type = "text", required = true }: { label: string; value: string | number; onChange: (value: string) => void; type?: "text" | "number"; required?: boolean }) {
  return (
    <label className="grid gap-2 text-xs font-semibold text-slate-400">
      {label}
      <input className="form-control normal-case" type={type} value={value} onChange={(event) => onChange(event.target.value)} required={required} />
    </label>
  );
}

function SelectField({ label, value, options, labels, onChange }: { label: string; value: string; options: string[]; labels?: Record<string, string>; onChange: (value: string) => void }) {
  return (
    <label className="grid gap-2 text-xs font-semibold text-slate-400">
      {label}
      <select className="form-control normal-case" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Select</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {labels?.[option] || option}
          </option>
        ))}
      </select>
    </label>
  );
}

function StatusBadge({ label, tone, icon: Icon }: { label: string; tone: Tone; icon?: LucideIcon }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-semibold ${toneBorder[tone]} ${toneBg[tone]} ${toneText[tone]}`}>
      {Icon && <Icon size={13} />}
      <span>{label}</span>
    </span>
  );
}

function Risk({ value }: { value: number }) {
  const tone: Tone = value >= 70 ? "rose" : value >= 40 ? "amber" : "emerald";
  return <StatusBadge label={`Risk ${Math.round(value || 0)}`} tone={tone} />;
}

function Info({ label, value, compact = false }: { label: string; value: ReactNode; compact?: boolean }) {
  return (
    <div className={compact ? "min-w-0 rounded-md bg-white/[0.04] p-2" : "flex items-center justify-between gap-3 border-b border-white/10 pb-2 last:border-b-0"}>
      <span className="text-slate-500">{label}</span>
      <span className="truncate font-semibold text-white">{value}</span>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-lg border border-dashed border-white/15 bg-slate-950/45 p-6 text-center text-sm text-slate-400">{text}</div>;
}
