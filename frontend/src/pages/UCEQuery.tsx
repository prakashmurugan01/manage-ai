import QueryInterface from "../components/uce/QueryInterface";
import { useRealtimeEvents } from "../hooks/useRealtimeEvents";

export default function UCEQuery() {
  useRealtimeEvents();

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <QueryInterface />
    </div>
  );
}
