import { api } from "./client.js";

export interface FileTrackingDashboard {
  totals: {
    transfers: number;
    bytes_moved: number;
    open_alerts: number;
    volumes: number;
  };
  by_status: Record<string, number>;
  by_extension: Array<{ file_extension: string; total: number; bytes: number }>;
  volume_usage: Array<{
    id: string;
    label: string;
    mount_path: string;
    disk_type: string;
    used_bytes: number;
    free_bytes: number;
    total_bytes: number;
    is_online: boolean;
  }>;
  recent_transfers: Array<Record<string, unknown>>;
  recent_alerts: Array<Record<string, unknown>>;
}

export async function getFileTrackingDashboard(): Promise<FileTrackingDashboard> {
  const { data } = await api.get("/v1/file-tracking/dashboard/");
  return data.data as FileTrackingDashboard;
}

export async function createFileTransfer(payload: Record<string, unknown>) {
  const { data } = await api.post("/v1/file-tracking/transfers/", payload);
  return data.data;
}

