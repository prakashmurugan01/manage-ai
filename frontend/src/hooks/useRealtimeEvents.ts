import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useUCEStore } from "../stores/uceStore";
import type { UCEEvent } from "../types/uce";

export function useRealtimeEvents() {
  const queryClient = useQueryClient();
  const addEvent = useUCEStore((state) => state.addEvent);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let closed = false;
    let retry = 500;

    const connect = () => {
      const wsBase = import.meta.env.VITE_WS_URL || "ws://localhost:8000";
      socket = new WebSocket(`${wsBase}/ws/events/`);

      socket.onmessage = (message) => {
        const data = JSON.parse(message.data);
        if (data.type === "uce.event") {
          const event = data.event as UCEEvent;
          addEvent(event);
          queryClient.invalidateQueries({ queryKey: ["uce", event.source_module] });
        }
      };

      socket.onopen = () => {
        retry = 500;
      };

      socket.onclose = () => {
        if (!closed) {
          window.setTimeout(connect, retry);
          retry = Math.min(retry * 2, 8000);
        }
      };
    };

    connect();

    return () => {
      closed = true;
      socket?.close();
    };
  }, [addEvent, queryClient]);
}

