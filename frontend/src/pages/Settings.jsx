import { Settings as SettingsIcon, AlertCircle, CheckCircle, Loader, User } from "lucide-react";
import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";

import { api } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import AvatarUpload from "../components/settings/AvatarUpload.jsx";
import ModuleControl from "../components/settings/ModuleControl.jsx";
import UserAccessManagement from "../components/settings/UserAccessManagement.jsx";
import AuthenticationSettings from "../components/settings/AuthenticationSettings.jsx";
import APIKeyManagement from "../components/settings/APIKeyManagement.jsx";
import CloudStorageSettings from "../components/settings/CloudStorageSettings.jsx";
import ServerFileAccess from "../components/settings/ServerFileAccess.jsx";
import SettingsAuditLog from "../components/settings/SettingsAuditLog.jsx";
import AdvancedTechSettings from "../components/settings/AdvancedTechSettings.jsx";

const TABS = [
  { id: "profile", label: "Profile", icon: "👤" },
  { id: "modules", label: "Module Control", icon: "🎛️" },
  { id: "access", label: "User Access", icon: "👥" },
  { id: "auth", label: "Authentication", icon: "🔐" },
  { id: "api", label: "API Keys", icon: "🔑" },
  { id: "storage", label: "Cloud Storage", icon: "☁️" },
  { id: "files", label: "File Access", icon: "📁" },
  { id: "audit", label: "Audit Logs", icon: "📋" },
  { id: "advanced", label: "Advanced Tech", icon: "⚡" },
];

export default function Settings() {
  const { user } = useAuth();
  useOutletContext();
  const [activeTab, setActiveTab] = useState("modules");
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notification, setNotification] = useState(null);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const response = await api.get("/settings/dashboard/");
      setDashboardData(response.data);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  const showNotification = (message, type = "success") => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 3000);
  };

  const handleModuleToggle = async (module) => {
    try {
      const existingModule = dashboardData.modules.find(m => m.module === module.module);
      const response = await api.patch(`/settings/modules/${existingModule.id}/`, {
        is_enabled: !module.is_enabled,
      });
      setDashboardData(prev => ({
        ...prev,
        modules: prev.modules.map(m => m.id === response.data.id ? response.data : m)
      }));
      showNotification(`${module.module} ${response.data.is_enabled ? "enabled" : "disabled"}`);
    } catch (err) {
      showNotification("Failed to update module", "error");
    }
  };

  const renderContent = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center py-12">
          <Loader className="animate-spin" size={32} />
        </div>
      );
    }

    switch (activeTab) {
      case "profile":
        return <AvatarUpload onUploadComplete={fetchDashboardData} />;
      case "modules":
        return <ModuleControl data={dashboardData?.modules} onToggle={handleModuleToggle} />;
      case "access":
        return <UserAccessManagement data={dashboardData?.access_controls} onRefresh={fetchDashboardData} />;
      case "auth":
        return <AuthenticationSettings data={dashboardData?.auth_settings} onRefresh={fetchDashboardData} />;
      case "api":
        return <APIKeyManagement onRefresh={fetchDashboardData} />;
      case "storage":
        return <CloudStorageSettings data={dashboardData?.storage_settings} onRefresh={fetchDashboardData} />;
      case "files":
        return <ServerFileAccess />;
      case "audit":
        return <SettingsAuditLog logs={dashboardData?.recent_audit_logs} />;
      case "advanced":
        return (
          <AdvancedTechSettings
            features={dashboardData?.advanced_features}
            health={dashboardData?.settings_health}
            serverControl={dashboardData?.server_control}
            onRefresh={fetchDashboardData}
            onNotify={showNotification}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-lg bg-gradient-to-br from-purple-400 to-pink-500">
            <SettingsIcon size={24} className="text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white">System Settings</h1>
            <p className="text-sm text-slate-400">Centralized control panel for your entire platform</p>
          </div>
        </div>
      </div>

      {/* Notification */}
      {notification && (
        <div className={`rounded-lg p-4 flex items-center gap-3 ${
          notification.type === "success" 
            ? "bg-green-500/20 text-green-300 border border-green-500/30"
            : "bg-red-500/20 text-red-300 border border-red-500/30"
        }`}>
          {notification.type === "success" ? 
            <CheckCircle size={20} /> : 
            <AlertCircle size={20} />
          }
          {notification.message}
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="rounded-lg p-4 flex items-center gap-3 bg-red-500/20 text-red-300 border border-red-500/30">
          <AlertCircle size={20} />
          {error}
        </div>
      )}

      {/* Tabs Navigation */}
      <div className="flex flex-wrap gap-2 border-b border-slate-700 pb-3">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg whitespace-nowrap transition font-medium ${
              activeTab === tab.id
                ? "bg-purple-600 text-white"
                : "text-slate-400 hover:text-white hover:bg-slate-800"
            }`}
          >
            <span className="mr-2">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content Area */}
      <div className="rounded-lg bg-slate-900 border border-slate-800 p-6">
        {renderContent()}
      </div>

      {/* Footer Info */}
      <div className="text-xs text-slate-500 text-center">
        All changes are logged for audit purposes. Last update: {dashboardData?.modules?.[0]?.changed_at && new Date(dashboardData.modules[0].changed_at).toLocaleString()}
      </div>
    </div>
  );
}
