import { useEffect, useState } from "react";

import { listFrom } from "../api/client.js";
import { auditApi } from "../api/services.js";
import Badge from "../components/ui/Badge.jsx";
import Page from "../components/ui/Page.jsx";

export default function Logs() {
  const [auditLogs, setAuditLogs] = useState([]);
  const [apiLogs, setApiLogs] = useState([]);

  useEffect(() => {
    auditApi.auditLogs().then((response) => setAuditLogs(listFrom(response)));
    auditApi.apiLogs().then((response) => setApiLogs(listFrom(response)));
  }, []);

  return (
    <Page title="System Logs" subtitle="Audit trail and API request monitoring for Super Admin review.">
      <div className="grid gap-6 xl:grid-cols-2">
        <div className="panel overflow-hidden">
          <div className="border-b border-white/10 p-4">
            <h2 className="text-sm font-semibold text-white">Audit Trail</h2>
          </div>
          <div className="max-h-[580px] divide-y divide-white/10 overflow-auto scrollbar-thin">
            {auditLogs.map((log) => (
              <div key={log.id} className="p-4 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <p className="font-medium text-white">{log.action} {log.entity_type}</p>
                  <Badge value={log.method || "API"} />
                </div>
                <p className="mt-1 text-xs text-slate-400">{log.actor_detail?.email || "System"} · {new Date(log.created_at).toLocaleString()}</p>
                <p className="mt-2 truncate text-xs text-slate-500">{log.path}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="panel overflow-hidden">
          <div className="border-b border-white/10 p-4">
            <h2 className="text-sm font-semibold text-white">API Requests</h2>
          </div>
          <div className="max-h-[580px] divide-y divide-white/10 overflow-auto scrollbar-thin">
            {apiLogs.map((log) => (
              <div key={log.id} className="p-4 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <p className="font-medium text-white">{log.method} {log.path}</p>
                  <Badge value={String(log.status_code)} />
                </div>
                <p className="mt-1 text-xs text-slate-400">{log.duration_ms} ms · {log.user_detail?.email || "anonymous"}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Page>
  );
}
