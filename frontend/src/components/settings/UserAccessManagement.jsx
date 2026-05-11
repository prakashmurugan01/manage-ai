import { Plus, Trash2, Lock } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../../api/client.js";

const MODULES = [
  "TASKS",
  "COLLABORATION",
  "TICKETS",
  "NOTIFICATIONS",
  "AI_CHATBOT",
  "MONITORING",
  "CONNECTION_ENGINE",
  "PROJECT_FILES",
  "ANALYTICS",
  "AUDIT",
];

const ACTIONS = ["VIEW", "CREATE", "EDIT", "DELETE", "ADMIN", "EXPORT"];

export default function UserAccessManagement({ data, onRefresh }) {
  const [controls, setControls] = useState(data || []);
  const [users, setUsers] = useState([]);
  const [isAdding, setIsAdding] = useState(false);
  const [formData, setFormData] = useState({
    user: "",
    module: MODULES[0],
    actions: ["VIEW"],
  });

  useEffect(() => {
    setControls(data || []);
  }, [data]);

  useEffect(() => {
    api.get("/users/")
      .then((response) => setUsers(response.data.results || response.data || []))
      .catch(() => setUsers([]));
  }, []);

  const handleAddAccess = async () => {
    if (!formData.user) {
      alert("Please select a user");
      return;
    }

    try {
      const response = await api.post("/settings/access-controls/", formData);
      setControls([...controls, response.data]);
      setFormData({ user: "", module: MODULES[0], actions: ["VIEW"] });
      setIsAdding(false);
      onRefresh?.();
    } catch (err) {
      alert("Failed to add access control");
    }
  };

  const handleRemove = async (id) => {
    if (!confirm("Remove this access control?")) return;

    try {
      await api.delete(`/settings/access-controls/${id}/`);
      setControls(controls.filter(c => c.id !== id));
      onRefresh?.();
    } catch (err) {
      alert("Failed to remove access control");
    }
  };

  const handleToggleAction = async (controlId, action) => {
    const control = controls.find(c => c.id === controlId);
    if (!control) return;

    const newActions = control.actions.includes(action)
      ? control.actions.filter(a => a !== action)
      : [...control.actions, action];

    try {
      const response = await api.patch(`/settings/access-controls/${controlId}/`, {
        actions: newActions,
      });
      setControls(controls.map(c => c.id === controlId ? response.data : c));
      onRefresh?.();
    } catch (err) {
      alert("Failed to update actions");
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-sm text-slate-300">
        Define granular access control for each user across different modules.
      </div>

      {/* Add New Access */}
      {isAdding && (
        <div className="p-4 rounded-lg bg-slate-800 border border-slate-700">
          <div className="space-y-4">
            <div>
              <label className="text-sm text-slate-300">User</label>
              <select
                value={formData.user}
                onChange={(e) => setFormData({ ...formData, user: e.target.value })}
                className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white placeholder-slate-500"
              >
                <option value="">Select a user</option>
                {users.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.full_name || item.email} · {item.role}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm text-slate-300">Module</label>
              <select
                value={formData.module}
                onChange={(e) => setFormData({ ...formData, module: e.target.value })}
                className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white"
              >
                {MODULES.map(m => (
                  <option key={m} value={m}>{m.replace(/_/g, " ")}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm text-slate-300">Actions</label>
              <div className="mt-2 flex flex-wrap gap-2">
                {ACTIONS.map(action => (
                  <button
                    key={action}
                    onClick={() => setFormData({
                      ...formData,
                      actions: formData.actions.includes(action)
                        ? formData.actions.filter(a => a !== action)
                        : [...formData.actions, action]
                    })}
                    className={`px-3 py-1 rounded text-sm transition ${
                      formData.actions.includes(action)
                        ? "bg-purple-600 text-white"
                        : "bg-slate-700 text-slate-400 hover:bg-slate-600"
                    }`}
                  >
                    {action}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleAddAccess}
                className="px-4 py-2 rounded-lg bg-purple-600 text-white hover:bg-purple-700 transition"
              >
                Add Access
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

      {/* Access Controls List */}
      <div className="space-y-3">
        {controls.length === 0 ? (
          <div className="text-center py-8 text-slate-500">No access controls configured</div>
        ) : (
          controls.map(control => (
            <div
              key={control.id}
              className="p-4 rounded-lg bg-slate-800 border border-slate-700 space-y-3"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-white">{control.user_detail?.email}</div>
                  <div className="text-sm text-slate-400">{control.module.replace(/_/g, " ")}</div>
                </div>
                {!control.is_valid && (
                  <div className="text-xs px-2 py-1 rounded bg-red-500/20 text-red-300">
                    Expired
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                {ACTIONS.map(action => (
                  <button
                    key={action}
                    onClick={() => handleToggleAction(control.id, action)}
                    className={`px-3 py-1 rounded text-xs transition ${
                      control.actions?.includes(action)
                        ? "bg-green-500/20 text-green-300 border border-green-500/30"
                        : "bg-slate-700 text-slate-400 border border-slate-600"
                    }`}
                  >
                    {action}
                  </button>
                ))}
              </div>

              <div className="flex items-center justify-between">
                <div className="text-xs text-slate-500">
                  {control.expires_at ? `Expires: ${new Date(control.expires_at).toLocaleDateString()}` : "No expiry"}
                </div>
                <button
                  onClick={() => handleRemove(control.id)}
                  className="text-red-400 hover:text-red-300 transition"
                >
                  <Trash2 size={18} />
                </button>
              </div>
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
          Add User Access
        </button>
      )}

      <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20 text-sm text-blue-300">
        🔒 Use this to grant specific permissions to users. Each action (View, Create, Edit, Delete, Admin, Export) can be controlled independently.
      </div>
    </div>
  );
}
