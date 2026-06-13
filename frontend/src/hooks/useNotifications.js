import { useCallback, useEffect, useRef, useState } from "react";
import { api, listFrom } from "../api/client.js";
import { notificationsApi } from "../api/services.js";

const WS_BASE = import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000/ws";

export default function useNotifications() {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const socketRef = useRef(null);

  const refresh = useCallback(async () => {
    const response = await notificationsApi.list();
    const items = listFrom(response);
    setNotifications(items);
    setUnreadCount(items.filter((item) => !item.is_read).length);
    return items;
  }, []);

  useEffect(() => {
    refresh().catch(() => {});
    const token = localStorage.getItem("accessToken") || "";
    const socket = new WebSocket(`${WS_BASE}/notifications/?token=${encodeURIComponent(token)}`);
    socketRef.current = socket;
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === "notifications_initial") {
        setNotifications(payload.notifications || []);
        setUnreadCount(payload.unread_count || 0);
      }
      if ((payload.type === "new_notification" || payload.type === "notification_created") && payload.notification) {
        setNotifications((items) => [payload.notification, ...items]);
        setUnreadCount((count) => payload.unread_count ?? count + 1);
      }
      if (payload.type === "notifications_updated") {
        setUnreadCount(payload.unread_count || 0);
      }
    };
    return () => socket.close();
  }, [refresh]);

  const markRead = useCallback(async (id) => {
    await api.post(`/notifications/${id}/mark_read/`);
    setNotifications((items) => items.map((item) => (item.id === id ? { ...item, is_read: true } : item)));
    setUnreadCount((count) => Math.max(0, count - 1));
  }, []);

  const markAllRead = useCallback(async () => {
    await api.post("/notifications/mark_all_read/");
    setNotifications((items) => items.map((item) => ({ ...item, is_read: true })));
    setUnreadCount(0);
  }, []);

  return { notifications, unreadCount, markRead, markAllRead, refresh };
}
