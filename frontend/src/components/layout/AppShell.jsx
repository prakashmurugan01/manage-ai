import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";

import { useAuth } from "../../context/AuthContext.jsx";
import { connectRealtime } from "../../realtime/socket.js";
import { ROLES } from "../../utils/rbac.js";
import Sidebar from "./Sidebar.jsx";
import Topbar from "./Topbar.jsx";

function playAlertTone() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const context = new AudioContext();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(660, context.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(920, context.currentTime + 0.08);
    gain.gain.setValueAtTime(0.001, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.12, context.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.18);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + 0.2);
    setTimeout(() => context.close(), 320);
  } catch {
    // Browsers can block audio until the first user gesture.
  }
}

export default function AppShell() {
  const { user } = useAuth();
  const [events, setEvents] = useState([]);

  useEffect(() => {
    const socket = connectRealtime({
      onMessage: (message) => {
        setEvents((items) => [message, ...items].slice(0, 8));
        if ([ROLES.SUPER_ADMIN, ROLES.ADMIN].includes(user?.role) && message.type !== "connected") {
          playAlertTone();
        }
      }
    });
    return () => socket?.close();
  }, [user?.role]);

  return (
    <div className="relative min-h-screen overflow-hidden bg-[color:var(--page-bg)] text-[color:var(--text)] transition-colors duration-300">
      <div className="pointer-events-none fixed inset-0 animated-grid opacity-35" />
      <div className="pointer-events-none fixed inset-x-0 top-0 h-56 bg-gradient-to-b from-white/8 to-transparent" />
      <Sidebar />
      <div className="relative min-h-screen lg:pl-72">
        <Topbar events={events} />
        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <Outlet context={{ events }} />
        </main>
      </div>
    </div>
  );
}
