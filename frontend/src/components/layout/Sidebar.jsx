import { LogOut } from "lucide-react";
import { NavLink } from "react-router-dom";

import { navigation } from "../../constants/navigation.js";
import { useAuth } from "../../context/AuthContext.jsx";
import { hasAnyRole, ROLE_LABELS } from "../../utils/rbac.js";

export default function Sidebar() {
  const { user, logout } = useAuth();
  const items = navigation.filter((item) => hasAnyRole(user, item.roles));

  return (
    <aside className="app-sidebar fixed inset-y-0 left-0 z-40 hidden w-72 border-r px-4 py-5 backdrop-blur lg:block">
      <div className="mb-8 flex items-center gap-3 px-2">
        <div className="brand-mark grid h-10 w-10 place-items-center rounded-lg bg-gradient-to-br from-teal-300 to-sky-400 text-sm font-black text-white">
          MA
        </div>
        <div>
          <p className="text-sm font-semibold text-white">ManageAI</p>
          <p className="text-xs text-slate-400">Internal Control Center</p>
        </div>
      </div>

      <nav className="space-y-1">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.label}
              to={item.to}
              className={({ isActive }) =>
                [
                  "theme-nav-item flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
                  isActive ? "theme-nav-active text-white" : "text-slate-400 hover:text-white"
                ].join(" ")
              }
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="surface-soft absolute bottom-5 left-4 right-4 rounded-lg p-3">
        <p className="truncate text-sm font-medium text-white">{user?.full_name || user?.email}</p>
        <p className="text-xs text-slate-400">{ROLE_LABELS[user?.role]}</p>
        <button
          type="button"
          onClick={logout}
          className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-white/10 px-3 py-2 text-sm text-slate-200 transition hover:bg-white/15"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  );
}
