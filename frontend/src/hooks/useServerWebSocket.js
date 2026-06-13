import { useEffect, useMemo, useRef, useState } from "react";

const WS_BASE = import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000/ws";

export default function useServerWebSocket() {
  const [serversById, setServersById] = useState({});
  const [isConnected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const retry = useRef(0);
  const timer = useRef(null);

  useEffect(() => {
    let socket;
    let closed = false;
    const connect = () => {
      const token = localStorage.getItem("accessToken") || "";
      socket = new WebSocket(`${WS_BASE}/server-monitor/?token=${encodeURIComponent(token)}`);
      socket.onopen = () => {
        retry.current = 0;
        setConnected(true);
      };
      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        const serverRows = payload.servers || (payload.server ? [payload.server] : []);
        const rows = payload.metrics || payload.initial_metrics || [];
        setServersById((prev) => {
          const next = { ...prev };
          serverRows.forEach((server) => {
            next[server.id] = { ...(next[server.id] || {}), ...server };
          });
          rows.forEach((metric) => {
            const id = metric.server;
            next[id] = { ...(next[id] || { id }), latest_metrics: metric };
          });
          return next;
        });
        setLastUpdate(new Date());
      };
      socket.onclose = () => {
        setConnected(false);
        if (!closed) {
          retry.current += 1;
          timer.current = setTimeout(connect, Math.min(30000, 1000 * 2 ** retry.current));
        }
      };
    };
    connect();
    return () => {
      closed = true;
      clearTimeout(timer.current);
      socket?.close();
    };
  }, []);

  return { servers: useMemo(() => Object.values(serversById), [serversById]), isConnected, lastUpdate };
}
