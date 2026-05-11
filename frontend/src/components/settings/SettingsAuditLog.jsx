import { Shield, User, Calendar } from "lucide-react";

const ACTION_COLORS = {
  "CREATE": "bg-green-500/20 text-green-300",
  "UPDATE": "bg-blue-500/20 text-blue-300",
  "DELETE": "bg-red-500/20 text-red-300",
  "ENABLE": "bg-green-500/20 text-green-300",
  "DISABLE": "bg-red-500/20 text-red-300",
};

const ENTITY_ICONS = {
  "MODULE_CONTROL": "🎛️",
  "ACCESS_CONTROL": "👥",
  "AUTH_SETTINGS": "🔐",
  "STORAGE_SETTINGS": "☁️",
  "API_KEY": "🔑",
  "FEATURE_FLAG": "🚩",
};

export default function SettingsAuditLog({ logs = [] }) {
  if (!logs || logs.length === 0) {
    return (
      <div className="text-center py-8 text-slate-500">
        No audit logs available yet
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="text-sm text-slate-300">
        Comprehensive audit trail of all settings changes made by administrators.
      </div>

      {/* Timeline */}
      <div className="space-y-3">
        {logs.map((log, index) => (
          <div
            key={log.id || index}
            className="p-4 rounded-lg bg-slate-800 border border-slate-700 hover:border-slate-600 transition"
          >
            <div className="flex items-start gap-4">
              {/* Icon */}
              <div className="flex-shrink-0 text-2xl">
                {ENTITY_ICONS[log.entity_type] || "📝"}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${ACTION_COLORS[log.action] || 'bg-slate-700 text-slate-400'}`}>
                    {log.action}
                  </span>
                  <span className="text-xs text-slate-400">
                    {log.entity_type.replace(/_/g, " ")}
                  </span>
                </div>

                <div className="text-white font-medium mb-2">
                  {log.change_summary}
                </div>

                {/* Change Details */}
                {(log.old_values || log.new_values) && (
                  <div className="text-xs text-slate-400 space-y-1 mb-2">
                    {log.old_values && Object.keys(log.old_values).length > 0 && (
                      <div>
                        <span className="text-slate-500">Before:</span> {JSON.stringify(log.old_values).substring(0, 100)}...
                      </div>
                    )}
                    {log.new_values && Object.keys(log.new_values).length > 0 && (
                      <div>
                        <span className="text-slate-500">After:</span> {JSON.stringify(log.new_values).substring(0, 100)}...
                      </div>
                    )}
                  </div>
                )}

                {/* Metadata */}
                <div className="flex items-center gap-4 text-xs text-slate-500 flex-wrap">
                  <div className="flex items-center gap-1">
                    <User size={14} />
                    {log.changed_by_detail?.email || "Unknown"}
                  </div>
                  <div className="flex items-center gap-1">
                    <Calendar size={14} />
                    {new Date(log.created_at).toLocaleString()}
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20 text-sm text-blue-300">
        📋 All administrative actions on settings are logged here for compliance and audit purposes. This log cannot be edited.
      </div>
    </div>
  );
}
