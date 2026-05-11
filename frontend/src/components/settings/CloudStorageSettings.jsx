import { Save, Loader, HardDrive } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../../api/client.js";

export default function CloudStorageSettings({ data, onRefresh }) {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(false);
  const [changed, setChanged] = useState(false);

  useEffect(() => {
    if (data) {
      setSettings(data);
    } else {
      fetchSettings();
    }
  }, [data]);

  const fetchSettings = async () => {
    try {
      const response = await api.get("/settings/storage/");
      if (response.data.results?.length > 0) {
        setSettings(response.data.results[0]);
      } else if (response.data.id) {
        setSettings(response.data);
      }
    } catch (err) {
      console.error("Failed to fetch storage settings");
    }
  };

  const handleToggle = (field) => {
    setSettings(prev => ({
      ...prev,
      [field]: !prev[field]
    }));
    setChanged(true);
  };

  const handleChange = (field, value) => {
    setSettings(prev => ({
      ...prev,
      [field]: value
    }));
    setChanged(true);
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      const response = await api.patch(`/settings/storage/${settings.id}/`, settings);
      setSettings(response.data);
      setChanged(false);
      onRefresh?.();
      alert("Storage settings saved");
    } catch (err) {
      alert("Failed to save settings");
    } finally {
      setLoading(false);
    }
  };

  if (!settings) {
    return <div className="text-slate-400">Loading storage settings...</div>;
  }

  const storagePercent = settings.usage_percent || 0;
  const storageColor = storagePercent > 90 ? "bg-red-500" : storagePercent > 70 ? "bg-yellow-500" : "bg-green-500";
  const currentUsage = Number(settings.current_usage_gb || 0);
  const storageLimit = Number(settings.storage_limit_gb || 0);

  return (
    <div className="space-y-6">
      <div className="text-sm text-slate-300">
        Manage cloud storage settings and monitor usage.
      </div>

      {/* Storage Usage */}
      <div className="p-4 rounded-lg bg-slate-800 border border-slate-700">
        <div className="flex items-center gap-3 mb-4">
          <HardDrive size={24} className="text-purple-400" />
          <div>
            <div className="text-sm text-slate-400">Storage Usage</div>
            <div className="font-medium text-white">
              {currentUsage.toFixed(2)} GB / {storageLimit.toFixed(2)} GB
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full h-3 rounded-full bg-slate-900 border border-slate-700 overflow-hidden">
          <div
            className={`h-full ${storageColor} transition-all duration-300`}
            style={{ width: `${Math.min(storagePercent, 100)}%` }}
          />
        </div>

        <div className="mt-2 text-xs text-slate-400">
          {storagePercent.toFixed(1)}% used • {settings.file_count} files
        </div>

        {storagePercent > 90 && (
          <div className="mt-3 p-3 rounded-lg bg-red-500/10 text-red-300 text-xs border border-red-500/20">
            ⚠️ Storage usage is above 90%. Consider increasing limit or cleaning old files.
          </div>
        )}
      </div>

      {/* Provider Settings */}
      <div className="p-4 rounded-lg bg-slate-800 border border-slate-700 space-y-4">
        <div className="font-medium text-white mb-4">Storage Provider</div>

        <div>
          <label className="text-sm text-slate-300 mb-2 block">Provider</label>
          <select
            value={settings.provider}
            onChange={(e) => handleChange("provider", e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white"
          >
            <option value="LOCAL">Local Storage</option>
            <option value="AWS_S3">AWS S3</option>
            <option value="AZURE_BLOB">Azure Blob Storage</option>
            <option value="GCP_STORAGE">Google Cloud Storage</option>
          </select>
        </div>

        {settings.provider !== "LOCAL" && (
          <>
            <div>
              <label className="text-sm text-slate-300 mb-2 block">Endpoint URL</label>
              <input
                type="url"
                value={settings.endpoint_url}
                onChange={(e) => handleChange("endpoint_url", e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white"
              />
            </div>

            <div>
              <label className="text-sm text-slate-300 mb-2 block">Bucket Name</label>
              <input
                type="text"
                value={settings.bucket_name}
                onChange={(e) => handleChange("bucket_name", e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white"
              />
            </div>
          </>
        )}

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={settings.is_enabled}
            onChange={() => handleToggle("is_enabled")}
            className="w-4 h-4 rounded"
          />
          <span className="text-slate-300">Enable cloud storage</span>
        </label>
      </div>

      {/* Backup Settings */}
      <div className="p-4 rounded-lg bg-slate-800 border border-slate-700 space-y-4">
        <div className="font-medium text-white mb-4">Backup & Maintenance</div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={settings.is_backup_enabled}
            onChange={() => handleToggle("is_backup_enabled")}
            className="w-4 h-4 rounded"
          />
          <span className="text-slate-300">Enable automatic backups</span>
        </label>

        {settings.last_backup_at && (
          <div className="text-xs text-slate-400">
            Last backup: {new Date(settings.last_backup_at).toLocaleString()}
          </div>
        )}

        <div>
          <label className="text-sm text-slate-300 mb-2 block">Storage Limit (GB)</label>
          <input
            type="number"
            value={settings.storage_limit_gb}
            onChange={(e) => handleChange("storage_limit_gb", parseFloat(e.target.value) || 100)}
            min="10"
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white"
          />
        </div>
      </div>

      {/* Save Button */}
      {changed && (
        <button
          onClick={handleSave}
          disabled={loading}
          className="w-full px-4 py-3 rounded-lg bg-purple-600 text-white hover:bg-purple-700 transition disabled:opacity-50 flex items-center justify-center gap-2 font-medium"
        >
          {loading ? (
            <>
              <Loader size={18} className="animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save size={18} />
              Save Settings
            </>
          )}
        </button>
      )}

      <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20 text-sm text-blue-300">
        ☁️ Choose your storage provider and configure backup settings. Local storage keeps files on the server, while cloud providers offer scalability and redundancy.
      </div>
    </div>
  );
}
