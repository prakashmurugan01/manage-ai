import { Cpu, Gauge, LockKeyhole, RadioTower, RefreshCw, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { useState } from "react";

import { api } from "../../api/client.js";

const FEATURE_ICONS = {
  ai_copilot: Sparkles,
  zero_trust_access: LockKeyhole,
  realtime_ops: RadioTower,
  smart_audit: ShieldCheck,
  auto_backup_policy: RefreshCw,
  developer_power_tools: Zap,
};

function Stat({ label, value }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
      <p className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export default function AdvancedTechSettings({ features = [], health, serverControl, onRefresh, onNotify }) {
  const [savingId, setSavingId] = useState(null);
  const [scaling, setScaling] = useState(false);

  async function toggleFeature(feature) {
    setSavingId(feature.id);
    try {
      await api.patch(`/feature-flags/${feature.id}/`, { is_enabled: !feature.is_enabled });
      onNotify?.(`${feature.label} ${feature.is_enabled ? "disabled" : "enabled"}`);
      onRefresh?.();
    } catch (err) {
      onNotify?.("Failed to update advanced feature", "error");
    } finally {
      setSavingId(null);
    }
  }

  async function scalePlatform(delta) {
    if (!serverControl?.id) return;
    const nextScale = Math.max(1, Math.min(12, Number(serverControl.scale_units || 1) + delta));
    setScaling(true);
    try {
      await api.post(`/server-control/${serverControl.id}/control/`, { scale_units: nextScale, is_enabled: true });
      onNotify?.(`Platform scale set to ${nextScale} unit${nextScale === 1 ? "" : "s"}`);
      onRefresh?.();
    } catch (err) {
      onNotify?.("Failed to update platform scale", "error");
    } finally {
      setScaling(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-4">
        <Stat label="Modules Online" value={`${health?.enabled_modules || 0}/${health?.total_modules || 0}`} />
        <Stat label="Power Features" value={health?.advanced_features || 0} />
        <Stat label="Connectors" value={`${health?.active_connectors || 0}/${health?.connectors || 0}`} />
        <Stat label="Storage Used" value={`${Number(health?.storage_usage_percent || 0).toFixed(1)}%`} />
      </div>

      <div className="rounded-lg border border-cyan-300/20 bg-cyan-300/10 p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3">
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-cyan-400/20 text-cyan-200">
              <Cpu size={22} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">Platform Power Mode</h2>
              <p className="mt-1 text-sm text-slate-400">
                Scale the control center for heavier realtime traffic, automation jobs, and admin operations.
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
                <span className="rounded-full bg-white/10 px-2 py-1">Health: {serverControl?.health || "STABLE"}</span>
                <span className="rounded-full bg-white/10 px-2 py-1">Active users: {serverControl?.active_users || 0}</span>
                <span className="rounded-full bg-white/10 px-2 py-1">Requests: {serverControl?.incoming_requests || 0}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => scalePlatform(-1)}
              disabled={scaling || Number(serverControl?.scale_units || 1) <= 1}
              className="rounded-lg border border-white/10 bg-white/10 px-3 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              -
            </button>
            <div className="min-w-24 rounded-lg border border-white/10 bg-slate-950/50 px-4 py-2 text-center text-sm text-white">
              {serverControl?.scale_units || 1} units
            </div>
            <button
              onClick={() => scalePlatform(1)}
              disabled={scaling || Number(serverControl?.scale_units || 1) >= 12}
              className="rounded-lg border border-white/10 bg-white/10 px-3 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              +
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {features.map((feature) => {
          const Icon = FEATURE_ICONS[feature.key] || Gauge;
          const description = feature.config?.description || "Enterprise-grade control for advanced platform behavior.";
          return (
            <div key={feature.id} className="rounded-lg border border-slate-700 bg-slate-800/80 p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-purple-500/15 text-purple-200">
                    <Icon size={20} />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white">{feature.label}</h3>
                    <p className="mt-1 text-sm leading-6 text-slate-400">{description}</p>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs">
                      <span className="rounded-full bg-white/10 px-2 py-1 text-slate-300">{feature.dashboard}</span>
                      <span className="rounded-full bg-white/10 px-2 py-1 text-slate-300">{feature.config?.tier || "advanced"}</span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => toggleFeature(feature)}
                  disabled={savingId === feature.id}
                  className={`min-w-20 rounded-lg px-3 py-2 text-sm font-medium transition disabled:opacity-50 ${
                    feature.is_enabled ? "bg-emerald-500/20 text-emerald-300" : "bg-slate-700 text-slate-400"
                  }`}
                >
                  {feature.is_enabled ? "ON" : "OFF"}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <div className="rounded-lg border border-blue-500/20 bg-blue-500/10 p-4 text-sm text-blue-300">
        Advanced Tech controls combine AI automation, zero-trust governance, realtime operations, audit intelligence, backup policy, and developer power tools.
      </div>
    </div>
  );
}
