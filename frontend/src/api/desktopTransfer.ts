import { api } from "./client.js";

type AnyRecord = Record<string, unknown>;

function unwrap<T>(response: { data: { data?: T } } | { data: T }): T {
  const payload = response.data as { data?: T };
  return payload && Object.prototype.hasOwnProperty.call(payload, "data") ? (payload.data as T) : (response.data as T);
}

export interface DesktopDevice {
  id: string;
  device_id: string;
  name: string;
  device_type: string;
  ip_address?: string;
  mac_address?: string;
  os_name?: string;
  status: string;
  storage_path: string;
  total_storage_bytes: number;
  used_storage_bytes: number;
  cpu_percent: number;
  ram_percent: number;
  disk_percent: number;
  transfer_status?: string;
  last_seen_at?: string;
  owner?: string;
  owner_name?: string;
}

export interface DeviceConnection {
  id: string;
  source_device: string;
  destination_device: string;
  source_device_name?: string;
  destination_device_name?: string;
  status: string;
  transport: string;
  encryption: string;
  connected_at?: string;
  disconnected_at?: string;
}

export interface ProjectFile {
  id: string;
  original_name: string;
  relative_path?: string;
  size_bytes: number;
  extension?: string;
  status: string;
  uploaded_by?: string;
  uploaded_by_name?: string;
  approved_by_name?: string;
  source_device?: string;
  destination_device?: string;
  source_device_name?: string;
  destination_device_name?: string;
  security_scan_status?: string;
  risk_score: number;
  created_at: string;
  deployed_path?: string;
}

export interface TransferJob {
  id: string;
  file_name: string;
  source_device?: string;
  destination_device?: string;
  source_device_name?: string;
  destination_device_name?: string;
  source_path: string;
  destination_path: string;
  size_bytes: number;
  bytes_transferred: number;
  progress_percent: number;
  speed_bytes_per_sec: number;
  status: string;
  created_at: string;
  completed_at?: string;
  uploaded_by_name?: string;
  approved_by_name?: string;
  last_error?: string;
}

export interface StorageFile {
  id: string;
  device?: string;
  device_name?: string;
  name: string;
  path: string;
  extension?: string;
  size_bytes: number;
  owner_name?: string;
  uploaded_at?: string;
  checksum?: string;
}

export interface AuditLog {
  id: string;
  action: string;
  message: string;
  actor_name?: string;
  created_at: string;
}

export async function getTransferSummary() {
  return unwrap<AnyRecord>(await api.get("/v1/file-transfer/summary/"));
}

export async function listDevices() {
  const data = unwrap<{ results?: DesktopDevice[] } | DesktopDevice[]>(await api.get("/v1/file-transfer/devices/?page_size=200"));
  return Array.isArray(data) ? data : data.results || [];
}

export async function registerDevice(payload: AnyRecord) {
  return unwrap<DesktopDevice>(await api.post("/v1/file-transfer/devices/", payload));
}

export async function heartbeatDevice(id: string, payload: AnyRecord) {
  return unwrap<DesktopDevice>(await api.post(`/v1/file-transfer/devices/${id}/heartbeat/`, payload));
}

export async function listConnections() {
  const data = unwrap<{ results?: DeviceConnection[] } | DeviceConnection[]>(await api.get("/v1/file-transfer/connections/?page_size=200"));
  return Array.isArray(data) ? data : data.results || [];
}

export async function connectDevices(sourceDevice: string, destinationDevice: string) {
  return unwrap<DeviceConnection>(
    await api.post("/v1/file-transfer/connections/", {
      source_device: sourceDevice,
      destination_device: destinationDevice,
      transport: "webrtc-websocket",
      encryption: "TLS 1.3 + device token",
    }),
  );
}

export async function disconnectConnection(id: string) {
  return unwrap<DeviceConnection>(await api.post(`/v1/file-transfer/connections/${id}/disconnect/`));
}

export async function listProjectFiles() {
  const data = unwrap<{ results?: ProjectFile[] } | ProjectFile[]>(await api.get("/v1/file-transfer/files/?page_size=200"));
  return Array.isArray(data) ? data : data.results || [];
}

export async function approveProjectFile(id: string, payload: AnyRecord) {
  return unwrap<AnyRecord>(await api.post(`/v1/file-transfer/files/${id}/approve/`, payload));
}

export async function rejectProjectFile(id: string, reason: string) {
  return unwrap<ProjectFile>(await api.post(`/v1/file-transfer/files/${id}/reject/`, { reason }));
}

export async function deployProjectFile(id: string, payload: AnyRecord) {
  return unwrap<TransferJob>(await api.post(`/v1/file-transfer/files/${id}/deploy/`, payload));
}

export async function listTransferJobs() {
  const data = unwrap<{ results?: TransferJob[] } | TransferJob[]>(await api.get("/v1/file-transfer/jobs/?page_size=200"));
  return Array.isArray(data) ? data : data.results || [];
}

export async function startTransfer(payload: AnyRecord) {
  return unwrap<TransferJob>(await api.post("/v1/file-transfer/jobs/", payload));
}

export async function listStorageFiles() {
  const data = unwrap<{ results?: StorageFile[] } | StorageFile[]>(await api.get("/v1/file-transfer/storage/?page_size=200"));
  return Array.isArray(data) ? data : data.results || [];
}

export async function deleteStorageFile(id: string) {
  return unwrap<AnyRecord>(await api.delete(`/v1/file-transfer/storage/${id}/delete_file/`));
}

export async function renameStorageFile(id: string, name: string) {
  return unwrap<StorageFile>(await api.post(`/v1/file-transfer/storage/${id}/rename/`, { name }));
}

export async function moveStorageFile(id: string, folder: string) {
  return unwrap<StorageFile>(await api.post(`/v1/file-transfer/storage/${id}/move/`, { folder }));
}

export async function listAuditLogs() {
  const data = unwrap<{ results?: AuditLog[] } | AuditLog[]>(await api.get("/v1/file-transfer/audit-logs/?page_size=200"));
  return Array.isArray(data) ? data : data.results || [];
}

export async function uploadChunk(formData: FormData, onProgress?: (loaded: number, total?: number) => void) {
  return unwrap<AnyRecord>(
    await api.post("/v1/file-transfer/chunk-upload/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 0,
      onUploadProgress: (event) => onProgress?.(event.loaded, event.total),
    }),
  );
}

export async function downloadBlob(path: string, filename: string, preview = false) {
  const response = await api.get(path, { responseType: "blob", timeout: 0 });
  const url = URL.createObjectURL(response.data);
  if (preview) {
    window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 30000);
    return;
  }
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
