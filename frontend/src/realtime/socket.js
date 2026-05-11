const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/events/";

export function connectRealtime({ onMessage, onOpen, onClose } = {}) {
  const token = localStorage.getItem("accessToken");
  if (!token) return null;

  const socket = new WebSocket(`${WS_URL}?token=${encodeURIComponent(token)}`);
  socket.onopen = () => onOpen?.();
  socket.onclose = () => onClose?.();
  socket.onmessage = (event) => {
    try {
      onMessage?.(JSON.parse(event.data));
    } catch {
      onMessage?.({ type: "raw", payload: event.data });
    }
  };
  return socket;
}
