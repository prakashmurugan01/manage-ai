import { Save, Loader } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../../api/client.js";

export default function AuthenticationSettings({ data, onRefresh }) {
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
      const response = await api.get("/settings/auth/");
      if (response.data.results?.length > 0) {
        setSettings(response.data.results[0]);
      } else if (response.data.id) {
        setSettings(response.data);
      }
    } catch (err) {
      console.error("Failed to fetch auth settings");
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
      const response = await api.patch(`/settings/auth/${settings.id}/`, settings);
      setSettings(response.data);
      setChanged(false);
      onRefresh?.();
      alert("Settings saved successfully");
    } catch (err) {
      alert("Failed to save settings");
    } finally {
      setLoading(false);
    }
  };

  if (!settings) {
    return <div className="text-slate-400">Loading settings...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="text-sm text-slate-300">
        Control authentication behavior and login options for your organization.
      </div>

      {/* Password Settings */}
      <div className="p-4 rounded-lg bg-slate-800 border border-slate-700 space-y-4">
        <div className="font-medium text-white mb-4">Password Management</div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={settings.allow_password_change}
            onChange={() => handleToggle("allow_password_change")}
            className="w-4 h-4 rounded"
          />
          <span className="text-slate-300">Allow users to change password</span>
        </label>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={settings.allow_forgot_password}
            onChange={() => handleToggle("allow_forgot_password")}
            className="w-4 h-4 rounded"
          />
          <span className="text-slate-300">Show &quot;Forgot Password&quot; on login</span>
        </label>

        <div className="mt-4 pt-4 border-t border-slate-700">
          <label className="text-sm text-slate-300 mb-2 block">Password expiry (days)</label>
          <input
            type="number"
            value={settings.password_expiry_days}
            onChange={(e) => handleChange("password_expiry_days", parseInt(e.target.value) || 0)}
            min="0"
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white"
          />
          <p className="text-xs text-slate-500 mt-1">0 = no expiry</p>
        </div>

        <div className="mt-4 pt-4 border-t border-slate-700">
          <label className="text-sm text-slate-300 mb-2 block">Minimum password length</label>
          <input
            type="number"
            value={settings.min_password_length}
            onChange={(e) => handleChange("min_password_length", parseInt(e.target.value) || 8)}
            min="6"
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white"
          />
        </div>
      </div>

      {/* Authentication Methods */}
      <div className="p-4 rounded-lg bg-slate-800 border border-slate-700 space-y-4">
        <div className="font-medium text-white mb-4">Login Methods</div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={settings.allow_face_login}
            onChange={() => handleToggle("allow_face_login")}
            className="w-4 h-4 rounded"
          />
          <span className="text-slate-300">Enable face recognition login</span>
        </label>

        <div className="mt-4 pt-4 border-t border-slate-700">
          <label className="text-sm text-slate-300 mb-2 block">Default login method</label>
          <select
            value={settings.default_login_method}
            onChange={(e) => handleChange("default_login_method", e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white"
          >
            <option value="EMAIL">Email</option>
            <option value="FACE">Face Recognition</option>
            <option value="BOTH">Both</option>
          </select>
        </div>
      </div>

      {/* Session & Security */}
      <div className="p-4 rounded-lg bg-slate-800 border border-slate-700 space-y-4">
        <div className="font-medium text-white mb-4">Session & Security</div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={settings.require_2fa}
            onChange={() => handleToggle("require_2fa")}
            className="w-4 h-4 rounded"
          />
          <span className="text-slate-300">Require 2FA for all users</span>
        </label>

        <div className="mt-4 pt-4 border-t border-slate-700">
          <label className="text-sm text-slate-300 mb-2 block">Session timeout (minutes)</label>
          <input
            type="number"
            value={settings.session_timeout_minutes}
            onChange={(e) => handleChange("session_timeout_minutes", parseInt(e.target.value) || 60)}
            min="5"
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
        🔐 These settings control login behavior and security policies across your organization. Changes take effect immediately for new sessions.
      </div>
    </div>
  );
}
