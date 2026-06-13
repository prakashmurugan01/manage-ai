import { AnimatePresence } from "framer-motion";
import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import ProtectedRoute from "./components/rbac/ProtectedRoute.jsx";
import { ROLES } from "./utils/rbac.js";

const AppShell = lazy(() => import("./components/layout/AppShell.jsx"));
const Dashboard = lazy(() => import("./pages/Dashboard.jsx"));
const Home = lazy(() => import("./pages/Home.jsx"));
const Collaboration = lazy(() => import("./pages/Collaboration.jsx"));
const Enterprise = lazy(() => import("./pages/Enterprise.jsx"));
const FileTracking = lazy(() => import("./pages/FileTracking"));
const Files = lazy(() => import("./pages/Files.jsx"));
const Logs = lazy(() => import("./pages/Logs.jsx"));
const Login = lazy(() => import("./pages/Login.jsx"));
const Monitoring = lazy(() => import("./pages/Monitoring.jsx"));
const NotFound = lazy(() => import("./pages/NotFound.jsx"));
const Notifications = lazy(() => import("./pages/Notifications.jsx"));
const ServerMonitor = lazy(() => import("./pages/ServerMonitor.jsx"));
const RemoteAccess = lazy(() => import("./pages/RemoteAccess.jsx"));
const HostingManager = lazy(() => import("./pages/HostingManager.jsx"));
const HostingDeployment = lazy(() => import("./pages/HostingDeployment.jsx"));
const ApiKeyManager = lazy(() => import("./pages/ApiKeyManager.jsx"));
const ApiMonitor = lazy(() => import("./pages/ApiMonitor.jsx"));
const DiskMonitor = lazy(() => import("./pages/DiskMonitor.jsx"));
const ProjectIntelligence = lazy(() => import("./pages/ProjectIntelligence.jsx"));
const ProjectDetail = lazy(() => import("./pages/ProjectDetail.jsx"));
const Projects = lazy(() => import("./pages/Projects.jsx"));
const Register = lazy(() => import("./pages/Register.jsx"));
const Settings = lazy(() => import("./pages/Settings.jsx"));
const Tasks = lazy(() => import("./pages/Tasks.jsx"));
const Tickets = lazy(() => import("./pages/Tickets.jsx"));
const UCEQuery = lazy(() => import("./pages/UCEQuery"));
const Users = lazy(() => import("./pages/Users.jsx"));

function RouteFallback() {
  return (
    <div className="grid min-h-[55vh] place-items-center text-[color:var(--text)]">
      <div className="rounded-lg border border-[color:var(--border)] bg-[color:var(--surface)] p-5 text-center shadow-[var(--shadow-soft)]">
        <span className="mx-auto block h-8 w-8 animate-spin rounded-full border-2 border-[color:var(--primary)] border-t-transparent" />
        <p className="mt-3 text-sm font-semibold text-[color:var(--text-strong)]">Loading workspace</p>
      </div>
    </div>
  );
}

export default function App() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <Suspense fallback={<RouteFallback />}>
        <Routes location={location} key={location.pathname}>
          <Route path="/login" element={<Login />} />
          <Route path="/signin" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<Home />} />
          <Route
            element={
              <ProtectedRoute>
                <AppShell />
              </ProtectedRoute>
            }
          >
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="query" element={<UCEQuery />} />
            <Route path="projects" element={<Projects />} />
            <Route path="project-intelligence" element={<ProjectIntelligence />} />
            <Route path="projects/:id" element={<ProjectDetail />} />
            <Route path="tasks" element={<Tasks />} />
            <Route path="collaboration" element={<Collaboration />} />
            <Route path="tickets" element={<Tickets />} />
            <Route path="file-tracking" element={<FileTracking />} />
            <Route path="files" element={<Files />} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="server-monitor" element={<ServerMonitor />} />
            <Route path="remote-access" element={<RemoteAccess />} />
            <Route path="hosting" element={<HostingManager />} />
            <Route path="hosting/deploy" element={<HostingDeployment />} />
            <Route path="hosting/:provider" element={<HostingManager />} />
            <Route path="api-keys" element={<ApiKeyManager />} />
            <Route path="api-keys/:center" element={<ApiKeyManager />} />
            <Route path="api-monitor" element={<ApiMonitor />} />
            <Route path="disk-monitor" element={<DiskMonitor />} />
            <Route path="enterprise" element={<Enterprise />} />
            <Route
              path="users"
              element={
                <ProtectedRoute roles={[ROLES.SUPER_ADMIN, ROLES.ADMIN]}>
                  <Users />
                </ProtectedRoute>
              }
            />
            <Route
              path="logs"
              element={
                <ProtectedRoute roles={[ROLES.SUPER_ADMIN]}>
                  <Logs />
                </ProtectedRoute>
              }
            />
            <Route
              path="monitoring"
              element={
                <ProtectedRoute roles={[ROLES.SUPER_ADMIN]}>
                  <Monitoring />
                </ProtectedRoute>
              }
            />
            <Route
              path="settings"
              element={
                <ProtectedRoute roles={[ROLES.SUPER_ADMIN, ROLES.ADMIN]}>
                  <Settings />
                </ProtectedRoute>
              }
            />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </AnimatePresence>
  );
}
