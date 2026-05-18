import { AnimatePresence } from "framer-motion";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import AppShell from "./components/layout/AppShell.jsx";
import ProtectedRoute from "./components/rbac/ProtectedRoute.jsx";
import { ROLES } from "./utils/rbac.js";
import Dashboard from "./pages/Dashboard.jsx";
import Home from "./pages/Home.jsx";
import Collaboration from "./pages/Collaboration.jsx";
import Enterprise from "./pages/Enterprise.jsx";
import FileTracking from "./pages/FileTracking";
import Files from "./pages/Files.jsx";
import Logs from "./pages/Logs.jsx";
import Login from "./pages/Login.jsx";
import Monitoring from "./pages/Monitoring.jsx";
import NotFound from "./pages/NotFound.jsx";
import Notifications from "./pages/Notifications.jsx";
import ServerMonitor from "./pages/ServerMonitor.jsx";
import RemoteAccess from "./pages/RemoteAccess.jsx";
import HostingManager from "./pages/HostingManager.jsx";
import HostingDeployment from "./pages/HostingDeployment.jsx";
import ApiKeyManager from "./pages/ApiKeyManager.jsx";
import ApiMonitor from "./pages/ApiMonitor.jsx";
import DiskMonitor from "./pages/DiskMonitor.jsx";
import ProjectDetail from "./pages/ProjectDetail.jsx";
import Projects from "./pages/Projects.jsx";
import Register from "./pages/Register.jsx";
import Settings from "./pages/Settings.jsx";
import Tasks from "./pages/Tasks.jsx";
import Tickets from "./pages/Tickets.jsx";
import UCEQuery from "./pages/UCEQuery";
import Users from "./pages/Users.jsx";

export default function App() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/login" element={<Login />} />
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
    </AnimatePresence>
  );
}
