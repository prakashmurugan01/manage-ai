import { lazy, Suspense, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../../context/AuthContext.jsx";
import { connectRealtime } from "../../realtime/socket.js";
import { ROLES } from "../../utils/rbac.js";
import Sidebar from "./Sidebar.jsx";
import Topbar from "./Topbar.jsx";

const FloatingAIAssistant = lazy(() => import("../ai/FloatingAIAssistant.jsx"));

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
  const location = useLocation();
  const [events, setEvents] = useState([]);
  const isDeployCenter = location.pathname === "/hosting/deploy";
  const isProjectIntelligence = location.pathname.startsWith("/project-intelligence");
  const isWideWorkspace = isDeployCenter || isProjectIntelligence;
  const showAssistant = !isDeployCenter && !isProjectIntelligence;

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
      <div
        className="pointer-events-none fixed inset-x-0 top-0 h-56"
        style={{ background: "linear-gradient(to bottom, color-mix(in srgb, var(--accent-primary) 8%, transparent), transparent)" }}
      />
      <Sidebar />
      <div className="shell-content relative min-h-screen transition-[padding-left] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]">
        <Topbar events={events} />
        <main className={`mx-auto w-full px-4 py-6 sm:px-6 lg:px-8 ${isWideWorkspace ? "max-w-[1800px]" : "max-w-7xl"}`}>
          <Outlet context={{ events }} />
        </main>
        {showAssistant && (
          <Suspense fallback={null}>
            <FloatingAIAssistant />
          </Suspense>
        )}
      </div>
    </div>
  );
}
