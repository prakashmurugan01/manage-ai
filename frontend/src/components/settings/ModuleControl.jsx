import { ToggleLeft, ToggleRight } from "lucide-react";

export default function ModuleControl({ data, onToggle }) {
  if (!data) return <div className="text-slate-400">No modules configured</div>;

  const moduleDescriptions = {
    TASKS: "Task management and project planning",
    COLLABORATION: "Real-time team collaboration and messaging",
    TICKETS: "Support ticket tracking system",
    NOTIFICATIONS: "Email and push notifications",
    AI_CHATBOT: "AI-powered chatbot assistance",
    MONITORING: "System monitoring and alerts",
    CONNECTION_ENGINE: "Integration and connector management",
    PROJECT_FILES: "Project file storage and sharing",
    ANALYTICS: "Analytics and reporting",
    AUDIT: "Audit logging and compliance",
  };

  return (
    <div className="space-y-4">
      <div className="text-sm text-slate-300 mb-6">
        Control which system modules are enabled or disabled for your organization.
      </div>
      
      <div className="grid gap-4">
        {data.map(module => (
          <div
            key={module.id}
            className="flex items-center justify-between p-4 rounded-lg bg-slate-800 border border-slate-700 hover:border-slate-600 transition"
          >
            <div className="flex-1">
              <div className="font-medium text-white mb-1">{module.module.replace(/_/g, " ")}</div>
              <div className="text-xs text-slate-400">{moduleDescriptions[module.module]}</div>
              {module.description && (
                <div className="text-xs text-slate-500 mt-1">{module.description}</div>
              )}
            </div>
            
            <div className="flex items-center gap-4 ml-4">
              <div className="text-xs text-slate-500 text-right">
                {module.changed_at && `Updated: ${new Date(module.changed_at).toLocaleDateString()}`}
              </div>
              <button
                onClick={() => onToggle(module)}
                className={`transition ${
                  module.is_enabled
                    ? "text-green-400 hover:text-green-300"
                    : "text-slate-600 hover:text-slate-500"
                }`}
              >
                {module.is_enabled ? (
                  <ToggleRight size={28} />
                ) : (
                  <ToggleLeft size={28} />
                )}
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20 text-sm text-blue-300">
        💡 Disabling a module will immediately prevent all users from accessing it. Changes are logged for audit purposes.
      </div>
    </div>
  );
}
