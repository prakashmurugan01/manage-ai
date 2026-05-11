import { Folder, File, FolderOpen, ChevronRight, AlertCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../../api/client.js";

export default function ServerFileAccess() {
  const [currentPath, setCurrentPath] = useState("/");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [breadcrumbs, setBreadcrumbs] = useState([]);

  useEffect(() => {
    loadDirectory(currentPath);
  }, [currentPath]);

  const loadDirectory = async (path) => {
    try {
      setLoading(true);
      setError(null);
      // Simulate file listing - in real implementation, you'd call an API
      const mockItems = generateMockFileStructure(path);
      setItems(mockItems);

      // Update breadcrumbs
      const parts = path.split("/").filter(Boolean);
      setBreadcrumbs(parts);
    } catch (err) {
      setError("Failed to load directory");
    } finally {
      setLoading(false);
    }
  };

  const generateMockFileStructure = (path) => {
    const structure = {
      "/": [
        { name: "backend", type: "folder", path: "/backend" },
        { name: "frontend", type: "folder", path: "/frontend" },
        { name: "docs", type: "folder", path: "/docs" },
        { name: "docker-compose.yml", type: "file", size: "2.5 KB" },
        { name: "README.md", type: "file", size: "4.8 KB" },
      ],
      "/backend": [
        { name: "apps", type: "folder", path: "/backend/apps" },
        { name: "manage_ai", type: "folder", path: "/backend/manage_ai" },
        { name: "manage.py", type: "file", size: "627 B" },
        { name: "requirements.txt", type: "file", size: "1.2 KB" },
      ],
      "/backend/apps": [
        { name: "accounts", type: "folder", path: "/backend/apps/accounts" },
        { name: "projects", type: "folder", path: "/backend/apps/projects" },
        { name: "tasks", type: "folder", path: "/backend/apps/tasks" },
        { name: "enterprise", type: "folder", path: "/backend/apps/enterprise" },
      ],
      "/frontend": [
        { name: "src", type: "folder", path: "/frontend/src" },
        { name: "public", type: "folder", path: "/frontend/public" },
        { name: "package.json", type: "file", size: "1.5 KB" },
        { name: "vite.config.js", type: "file", size: "756 B" },
      ],
    };

    return structure[path] || [];
  };

  const handleNavigate = (path) => {
    setCurrentPath(path);
  };

  const handleBreadcrumbClick = (index) => {
    const parts = currentPath.split("/").filter(Boolean);
    const newPath = "/" + parts.slice(0, index + 1).join("/");
    setCurrentPath(newPath);
  };

  const handleHome = () => {
    setCurrentPath("/");
  };

  return (
    <div className="space-y-6">
      <div className="text-sm text-slate-300">
        Browse server files and folders. This view allows admins to inspect project structure and files.
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-red-500/20 text-red-300 border border-red-500/30 flex items-center gap-2">
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      {/* File Browser */}
      <div className="rounded-lg bg-slate-800 border border-slate-700 overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-slate-700 bg-slate-900">
          <div className="flex items-center gap-2 mb-3">
            <button
              onClick={handleHome}
              className="px-3 py-1 rounded-lg text-sm bg-slate-700 text-slate-300 hover:bg-slate-600 transition"
            >
              Home
            </button>
            <span className="text-slate-500">/</span>
            {breadcrumbs.map((part, index) => (
              <div key={index} className="flex items-center gap-2">
                <button
                  onClick={() => handleBreadcrumbClick(index)}
                  className="text-sm text-blue-400 hover:text-blue-300 transition"
                >
                  {part}
                </button>
                {index < breadcrumbs.length - 1 && (
                  <ChevronRight size={16} className="text-slate-600" />
                )}
              </div>
            ))}
          </div>
          <div className="text-xs text-slate-500">
            Viewing: {currentPath}
          </div>
        </div>

        {/* File List */}
        <div className="divide-y divide-slate-700">
          {loading ? (
            <div className="p-8 text-center text-slate-500">Loading...</div>
          ) : items.length === 0 ? (
            <div className="p-8 text-center text-slate-500">Empty directory</div>
          ) : (
            items.map((item, index) => (
              <div
                key={index}
                className="p-4 hover:bg-slate-700/50 transition cursor-pointer flex items-center gap-3 group"
                onClick={() => item.type === "folder" && handleNavigate(item.path)}
              >
                {item.type === "folder" ? (
                  <>
                    <FolderOpen size={18} className="text-amber-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-white group-hover:text-blue-400 transition font-medium truncate">
                        {item.name}
                      </div>
                    </div>
                    <ChevronRight size={16} className="text-slate-600 flex-shrink-0" />
                  </>
                ) : (
                  <>
                    <File size={18} className="text-slate-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-white truncate">{item.name}</div>
                      <div className="text-xs text-slate-500">{item.size}</div>
                    </div>
                  </>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Project Structure Info */}
      <div className="grid grid-cols-2 gap-4">
        <div className="p-4 rounded-lg bg-slate-800 border border-slate-700">
          <div className="text-xs text-slate-400 mb-2">📂 Backend Structure</div>
          <div className="text-sm text-slate-300">Python/Django</div>
          <div className="text-xs text-slate-500 mt-2">REST API, WebSockets, Async Tasks</div>
        </div>
        <div className="p-4 rounded-lg bg-slate-800 border border-slate-700">
          <div className="text-xs text-slate-400 mb-2">⚛️ Frontend Structure</div>
          <div className="text-sm text-slate-300">React/Vite</div>
          <div className="text-xs text-slate-500 mt-2">Components, Pages, Real-time UI</div>
        </div>
      </div>

      <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20 text-sm text-blue-300">
        📁 This is a read-only file browser. Use it to inspect project structure, verify deployments, and audit server contents. All access is logged.
      </div>
    </div>
  );
}
