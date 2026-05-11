import { Power } from "lucide-react";
import { useState } from "react";

import { deploymentsApi } from "../../api/services.js";
import Button from "../ui/Button.jsx";

export default function DeploymentToggle({ deployment, onChange }) {
  const [busy, setBusy] = useState(false);
  if (!deployment) return null;

  async function toggle() {
    setBusy(true);
    try {
      const { data } = await deploymentsApi.toggle(deployment.id, {
        is_enabled: !deployment.is_enabled,
        version: deployment.version || "manual-toggle",
        notes: "Updated from ManageAI console"
      });
      onChange?.(data);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button variant={deployment.is_enabled ? "danger" : "primary"} onClick={toggle} disabled={busy}>
      <Power size={16} />
      {deployment.is_enabled ? "Turn Off" : "Turn On"}
    </Button>
  );
}
