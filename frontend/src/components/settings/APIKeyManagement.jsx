import { Plus, Copy, Eye, EyeOff, Trash2, Lock, CheckCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../../api/client.js";

export default function APIKeyManagement() {
  const [apiKeys, setApiKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isAdding, setIsAdding] = useState(false);
  const [showKey, setShowKey] = useState(null);
  const [formData, setFormData] = useState({
    name: "",
    provider: "OPENAI",
    raw_key: "",
    notes: "",
  });

  useEffect(() => {
    fetchAPIKeys();
  }, []);

  const fetchAPIKeys = async () => {
    try {
      const response = await api.get("/api-keys/");
      setApiKeys(response.data.results || response.data);
      setLoading(false);
    } catch (err) {
      console.error("Failed to fetch API keys");
      setLoading(false);
    }
  };

  const handleAddKey = async () => {
    if (!formData.name || !formData.raw_key) {
      alert("Name and key are required");
      return;
    }

    try {
      const response = await api.post("/api-keys/", formData);
      setApiKeys([...apiKeys, response.data]);
      setFormData({ name: "", provider: "OPENAI", raw_key: "", notes: "" });
      setIsAdding(false);
      alert("API key added successfully");
    } catch (err) {
      alert("Failed to add API key");
    }
  };

  const handleDeleteKey = async (id) => {
    if (!confirm("Delete this API key?")) return;

    try {
      await api.delete(`/api-keys/${id}/`);
      setApiKeys(apiKeys.filter(k => k.id !== id));
    } catch (err) {
      alert("Failed to delete API key");
    }
  };

  const handleCopyKey = (preview) => {
    navigator.clipboard.writeText(preview);
    alert("Key preview copied");
  };

  const handleToggleActive = async (id, isActive) => {
    try {
      const response = await api.patch(`/api-keys/${id}/`, {
        is_active: !isActive
      });
      setApiKeys(apiKeys.map(k => k.id === id ? response.data : k));
    } catch (err) {
      alert("Failed to update API key status");
    }
  };

  if (loading) {
    return <div className="text-slate-400">Loading API keys...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="text-sm text-slate-300">
        Manage API keys for integrations. Only authorized developers can view and use these keys.
      </div>

      {/* Add New Key */}
      {isAdding && (
        <div className="p-4 rounded-lg bg-slate-800 border border-slate-700">
          <div className="space-y-4">
            <div>
              <label className="text-sm text-slate-300">Key Name</label>
              <input
                type="text"
                placeholder="e.g., Production OpenAI"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white placeholder-slate-500"
              />
            </div>
            <div>
              <label className="text-sm text-slate-300">Provider</label>
              <select
                value={formData.provider}
                onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white"
              >
                <option value="OPENAI">OpenAI</option>
                <option value="META">Meta</option>
                <option value="OPEN_SOURCE">Open Source</option>
                <option value="OTHER">Other</option>
              </select>
            </div>
            <div>
              <label className="text-sm text-slate-300">API Key</label>
              <textarea
                placeholder="Paste your API key here"
                value={formData.raw_key}
                onChange={(e) => setFormData({ ...formData, raw_key: e.target.value })}
                className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white placeholder-slate-500 font-mono text-xs"
                rows="3"
              />
            </div>
            <div>
              <label className="text-sm text-slate-300">Notes (Optional)</label>
              <input
                type="text"
                placeholder="e.g., Production environment, expires in 6 months"
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white placeholder-slate-500"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleAddKey}
                className="px-4 py-2 rounded-lg bg-purple-600 text-white hover:bg-purple-700 transition"
              >
                Add Key
              </button>
              <button
                onClick={() => setIsAdding(false)}
                className="px-4 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 transition"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* API Keys List */}
      <div className="space-y-3">
        {apiKeys.length === 0 ? (
          <div className="text-center py-8 text-slate-500">No API keys configured</div>
        ) : (
          apiKeys.map(key => (
            <div
              key={key.id}
              className="p-4 rounded-lg bg-slate-800 border border-slate-700"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <div className="font-medium text-white flex items-center gap-2">
                    {key.name}
                    {key.is_active && (
                      <CheckCircle size={16} className="text-green-400" />
                    )}
                  </div>
                  <div className="text-sm text-slate-400 mt-1">{key.provider}</div>
                  {key.notes && (
                    <div className="text-xs text-slate-500 mt-1">{key.notes}</div>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowKey(showKey === key.id ? null : key.id)}
                    className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition"
                  >
                    {showKey === key.id ? (
                      <EyeOff size={18} />
                    ) : (
                      <Eye size={18} />
                    )}
                  </button>
                  <button
                    onClick={() => handleCopyKey(key.key_preview)}
                    className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700 transition"
                  >
                    <Copy size={18} />
                  </button>
                  <button
                    onClick={() => handleDeleteKey(key.id)}
                    className="p-2 rounded-lg text-red-400 hover:text-red-300 hover:bg-red-500/10 transition"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>

              {/* Key Preview */}
              <div className="mt-3 pt-3 border-t border-slate-700">
                <div className="flex items-center gap-2">
                  <Lock size={14} className="text-slate-500" />
                  <code className="text-xs text-slate-400 font-mono">{key.key_preview}</code>
                </div>
              </div>

              {/* Grants */}
              {key.grants && key.grants.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-700">
                  <div className="text-xs text-slate-400 mb-2">Shared with:</div>
                  <div className="flex flex-wrap gap-2">
                    {key.grants.map(grant => (
                      <div
                        key={grant.id}
                        className="px-2 py-1 rounded-full bg-blue-500/20 text-blue-300 text-xs"
                      >
                        {grant.developer_detail?.email}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {!isAdding && (
        <button
          onClick={() => setIsAdding(true)}
          className="w-full px-4 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:text-white hover:border-slate-600 transition flex items-center justify-center gap-2"
        >
          <Plus size={18} />
          Add API Key
        </button>
      )}

      <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20 text-sm text-blue-300">
        🔑 API keys are encrypted and stored securely. Only key previews are visible. Share keys with developers through access grants to control who can view and use them.
      </div>
    </div>
  );
}
