import { CheckCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { listFrom } from "../api/client.js";
import { notificationsApi } from "../api/services.js";
import Button from "../components/ui/Button.jsx";
import Page from "../components/ui/Page.jsx";

export default function Notifications() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    notificationsApi.list().then((response) => setItems(listFrom(response)));
  }, []);

  async function markRead(id) {
    const { data } = await notificationsApi.markRead(id);
    setItems((current) => current.map((item) => (item.id === id ? data : item)));
  }

  return (
    <Page title="Notifications" subtitle="Task assignment, deployment, file, and system messages.">
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.id} className={`panel flex items-start justify-between gap-4 p-4 ${item.is_read ? "opacity-70" : ""}`}>
            <div>
              <p className="font-medium text-white">{item.title}</p>
              <p className="mt-1 text-sm text-slate-400">{item.message}</p>
              <p className="mt-2 text-xs text-slate-500">{new Date(item.created_at).toLocaleString()}</p>
            </div>
            {!item.is_read && (
              <Button variant="secondary" onClick={() => markRead(item.id)}>
                <CheckCheck size={16} />
                Read
              </Button>
            )}
          </div>
        ))}
        {!items.length && <p className="panel p-6 text-sm text-slate-500">No notifications yet.</p>}
      </div>
    </Page>
  );
}
