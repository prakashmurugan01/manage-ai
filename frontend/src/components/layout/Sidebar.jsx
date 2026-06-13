import {
  Activity,
  BarChart3,
  Bell,
  ChevronDown,
  ChevronsLeft,
  CircleGauge,
  Database,
  FileText,
  Folder,
  Globe2,
  HardDrive,
  Home,
  KeyRound,
  Layers3,
  LifeBuoy,
  LockKeyhole,
  LogOut,
  Menu,
  MessageSquareWarning,
  MonitorUp,
  Network,
  Radio,
  Rocket,
  Search,
  Server,
  Settings,
  EllipsisVertical,
  Users,
  Webhook,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../../context/AuthContext.jsx";
import useNotifications from "../../hooks/useNotifications.js";
import { hasAnyRole, ROLE_LABELS, ROLES } from "../../utils/rbac.js";

import "./Sidebar.css";

/* ─────────────────────────────────────────────
   Navigation config
───────────────────────────────────────────── */
const miniRail = [
  { label: "Dashboard",     to: "/dashboard",      icon: Home },
  { label: "Hosting",       to: "/hosting",        icon: Globe2 },
  { label: "Projects",      to: "/projects",       icon: Folder },
  { label: "Tickets",       to: "/tickets",        icon: LifeBuoy },
  { label: "Deploy",        to: "/hosting/deploy", icon: Rocket },
  { label: "Intelligence",  to: "/project-intelligence", icon: Network },
  { label: "Monitoring",    to: "/server-monitor", icon: Activity },
  { label: "API",           to: "/api-keys",       icon: Network },
  { label: "Users",         to: "/users",          icon: Users,    roles: [ROLES.SUPER_ADMIN, ROLES.ADMIN] },
  { label: "Settings",      to: "/settings",       icon: Settings, roles: [ROLES.SUPER_ADMIN, ROLES.ADMIN] },
];

const navSections = [
  {
    title: "Main",
    items: [
      { label: "Dashboard", to: "/dashboard", icon: BarChart3 },
      {
        label: "Hosting Manager",
        to: "/hosting",
        icon: Globe2,
        children: [
          { label: "Shared Hosting", to: "/hosting" },
          { label: "VPS Hosting",    to: "/hosting" },
          { label: "Cloud Hosting",  to: "/hosting" },
          { label: "Domain Manager", to: "/hosting" },
        ],
      },
      {
        label: "Projects",
        to: "/projects",
        icon: Layers3,
        children: [
          { label: "Active Projects",   to: "/projects", count: 18 },
          { label: "Pending Projects",  to: "/projects", count: 6  },
          { label: "Archived Projects", to: "/projects", count: 42 },
        ],
      },
      {
        label: "Deploy Center",
        to: "/hosting/deploy",
        icon: Rocket,
        badge: "Live",
        badgeTone: "green",
      },
      {
        label: "Project Intelligence",
        to: "/project-intelligence",
        icon: Network,
        badge: "Live",
        badgeTone: "green",
      },
      {
        label: "Tickets",
        to: "/tickets",
        icon: LifeBuoy,
        badge: "AI",
        badgeTone: "neutral",
      },
    ],
  },
  {
    title: "Server",
    items: [
      {
        label: "Server Monitor",
        to: "/server-monitor",
        icon: Activity,
        badge: "99%",
        badgeTone: "neutral",
        children: [
          { label: "CPU Usage",       to: "/server-monitor" },
          { label: "RAM Usage",       to: "/server-monitor" },
          { label: "Disk Usage",      to: "/disk-monitor"   },
          { label: "Network Traffic", to: "/server-monitor" },
        ],
      },
      { label: "Remote Access",    to: "/remote-access",  icon: MonitorUp  },
      { label: "Disk Transfer",    to: "/file-tracking",  icon: HardDrive  },
      { label: "Resource Manager", to: "/monitoring",     icon: CircleGauge, roles: [ROLES.SUPER_ADMIN] },
      { label: "SSL Manager",      to: "/hosting",        icon: LockKeyhole, badge: "12d", badgeTone: "warn" },
    ],
  },
  {
    title: "API",
    items: [
      { label: "API Integration", to: "/api-keys",    icon: KeyRound },
      { label: "Chatbot Integration", to: "/api-keys/chatbot", icon: MessageSquareWarning },
      { label: "ERP Integration", to: "/api-keys/erp", icon: Database },
      { label: "API Monitor",     to: "/api-monitor", icon: Radio,    roles: [ROLES.SUPER_ADMIN], badge: "OK", badgeTone: "neutral" },
      { label: "Webhooks",        to: "/api-keys/webhooks",    icon: Webhook  },
      { label: "API Analytics",   to: "/api-monitor", icon: BarChart3, roles: [ROLES.SUPER_ADMIN] },
    ],
  },
  {
    title: "Management",
    items: [
      { label: "User Management", to: "/users",          icon: Users,    roles: [ROLES.SUPER_ADMIN, ROLES.ADMIN] },
      { label: "Notifications",   to: "/notifications",  icon: Bell,     notification: true },
      { label: "Logs",            to: "/logs",           icon: FileText, roles: [ROLES.SUPER_ADMIN] },
      { label: "Settings",        to: "/settings",       icon: Settings, roles: [ROLES.SUPER_ADMIN, ROLES.ADMIN] },
    ],
  },
];

/* ─────────────────────────────────────────────
   Root component
───────────────────────────────────────────── */
export default function Sidebar() {
  const { user, logout } = useAuth();
  const { unreadCount }  = useNotifications();
  const navigate         = useNavigate();
  const location         = useLocation();

  const [expanded,  setExpanded]  = useState(true);
  const [openItems, setOpenItems] = useState({
    "Hosting Manager": false,
    Projects:         false,
    "Server Monitor": false,
  });

  useEffect(() => {
    document.documentElement.dataset.sidebar = expanded ? "expanded" : "compact";
  }, [expanded]);

  const visibleRail = miniRail.filter((item) => hasAnyRole(user, item.roles));

  const visibleSections = useMemo(
    () =>
      navSections
        .map((section) => ({
          ...section,
          items: section.items
            .filter((item) => hasAnyRole(user, item.roles))
            .map((item) => ({
              ...item,
              children: item.children?.filter((child) => hasAnyRole(user, child.roles)),
            })),
        }))
        .filter((section) => section.items.length),
    [user],
  );

  function toggleItem(label) {
    setOpenItems((prev) => ({ ...prev, [label]: !prev[label] }));
  }

  return (
    <>
      {/* ── Desktop ── */}
      <aside className="sb-root">
        <MiniRail
          items={visibleRail}
          unreadCount={unreadCount}
          currentPath={location.pathname}
        />

        <AnimatePresence initial={false}>
          {expanded && (
            <motion.div
              key="panel"
              className="sb-panel"
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 288, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="sb-panel-inner">
                <ProfileCard
                  user={user}
                  onCollapse={() => setExpanded(false)}
                />

                <nav className="sb-nav" aria-label="Main navigation">
                  {visibleSections.map((section) => (
                    <section key={section.title} className="sb-section">
                      <p className="sb-section-label">{section.title}</p>
                      <ul className="sb-section-list" role="list">
                        {section.items.map((item) => (
                          <NavItem
                            key={`${section.title}-${item.label}`}
                            item={item}
                            open={Boolean(openItems[item.label])}
                            onToggle={toggleItem}
                            unreadCount={unreadCount}
                            currentPath={location.pathname}
                          />
                        ))}
                      </ul>
                    </section>
                  ))}
                </nav>

                <SidebarFooter logout={logout} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Collapse tab */}
        <button
          type="button"
          className="sb-collapse-tab"
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"}
          aria-expanded={expanded}
        >
          <ChevronsLeft
            size={15}
            className={`sb-collapse-icon ${expanded ? "" : "sb-collapse-icon--flipped"}`}
          />
        </button>
      </aside>

      {/* ── Mobile bottom bar ── */}
      <MobileBar items={visibleRail} unreadCount={unreadCount} />
    </>
  );
}

/* ─────────────────────────────────────────────
   Mini Rail
───────────────────────────────────────────── */
function MiniRail({ items, unreadCount, currentPath }) {
  return (
    <div className="sb-rail" role="navigation" aria-label="Quick navigation">
      {/* Avatar */}
      <div className="sb-rail-avatar" aria-hidden="true">
        <span className="sb-rail-avatar-inner">N</span>
        <span className="sb-rail-avatar-dot" />
      </div>

      <div className="sb-rail-links">
        {items.map((item) => {
          const Icon   = item.icon;
          const active =
            currentPath === item.to ||
            (item.to !== "/dashboard" && currentPath.startsWith(item.to));

          return (
            <NavLink
              key={item.label}
              to={item.to}
              className={`sb-rail-link ${active ? "sb-rail-link--active" : ""}`}
              aria-label={item.label}
            >
              <Icon size={18} aria-hidden="true" />
              <span className="sb-rail-tooltip">{item.label}</span>
              {item.notification && unreadCount > 0 && (
                <span className="sb-rail-notif-dot" aria-label={`${unreadCount} unread`} />
              )}
            </NavLink>
          );
        })}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Profile card
───────────────────────────────────────────── */
function ProfileCard({ user, onCollapse }) {
  const initials = (user?.full_name || user?.email || "A").charAt(0).toUpperCase();
  const name     = user?.full_name || user?.email || "Admin";
  const role     = ROLE_LABELS[user?.role] || "Online";

  return (
    <div className="sb-profile">
      <div className="sb-profile-avatar">
        <span className="sb-profile-initials">{initials}</span>
        <span className="sb-profile-status" aria-hidden="true" />
      </div>

      <div className="sb-profile-info">
        <p className="sb-profile-name">{name}</p>
        <p className="sb-profile-role">
          <span className="sb-profile-role-dot" aria-hidden="true" />
          {role}
        </p>
      </div>

      <div className="sb-profile-actions">
        <button className="sb-icon-btn" type="button" aria-label="Search">
          <Search size={14} aria-hidden="true" />
        </button>
        <button className="sb-icon-btn" type="button" aria-label="More options">
          <EllipsisVertical size={14} aria-hidden="true" />
        </button>
        <button className="sb-icon-btn" type="button" onClick={onCollapse} aria-label="Collapse sidebar">
          <Menu size={14} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Nav item (with optional sub-menu)
───────────────────────────────────────────── */
function NavItem({ item, open, onToggle, unreadCount, currentPath }) {
  const Icon        = item.icon;
  const hasChildren = Boolean(item.children?.length);
  const active      =
    currentPath === item.to ||
    (item.to !== "/dashboard" && currentPath.startsWith(item.to));

  return (
    <li role="listitem">
      <NavLink
        to={item.to}
        className={`sb-nav-item ${active ? "sb-nav-item--active" : ""}`}
      >
        {/* Active left bar */}
        {active && (
          <motion.span
            layoutId="sb-active-bar"
            className="sb-nav-bar"
            transition={{ type: "spring", stiffness: 420, damping: 32 }}
          />
        )}

        <span className="sb-nav-icon">
          <Icon size={16} aria-hidden="true" />
        </span>

        <span className="sb-nav-label">{item.label}</span>

        {/* Notification badge */}
        {item.notification && unreadCount > 0 && (
          <NotifBadge count={unreadCount} />
        )}

        {/* Status badge */}
        {item.badge && !item.notification && (
          <span className={`sb-badge sb-badge--${item.badgeTone ?? "neutral"}`}>
            {item.badge}
          </span>
        )}

        {/* Expand toggle */}
        {hasChildren && (
          <button
            type="button"
            className="sb-expand-btn"
            onClick={(e) => { e.preventDefault(); onToggle(item.label); }}
            aria-label={`${open ? "Collapse" : "Expand"} ${item.label}`}
            aria-expanded={open}
          >
            <ChevronDown
              size={13}
              className={`sb-expand-icon ${open ? "sb-expand-icon--open" : ""}`}
              aria-hidden="true"
            />
          </button>
        )}
      </NavLink>

      {/* Sub-menu */}
      <AnimatePresence initial={false}>
        {hasChildren && open && (
          <motion.ul
            role="list"
            className="sb-submenu"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
          >
            {item.children.map((child) => (
              <li key={child.label} role="listitem">
                <NavLink to={child.to} className="sb-submenu-link">
                  <span className="sb-submenu-label">{child.label}</span>
                  {child.count != null && (
                    <span className="sb-submenu-count">{child.count}</span>
                  )}
                </NavLink>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </li>
  );
}

/* ─────────────────────────────────────────────
   Footer
───────────────────────────────────────────── */
function SidebarFooter({ logout }) {
  return (
    <div className="sb-footer">
      <button
        type="button"
        className="sb-signout"
        onClick={logout}
        aria-label="Sign out"
      >
        <LogOut size={15} aria-hidden="true" />
        Sign out
      </button>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Notification badge
───────────────────────────────────────────── */
function NotifBadge({ count }) {
  return (
    <motion.span
      className="sb-notif-badge"
      animate={{ scale: [1, 1.12, 1] }}
      transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
      aria-label={`${Math.min(count, 99)} unread notifications`}
    >
      {Math.min(count, 99)}
    </motion.span>
  );
}

/* ─────────────────────────────────────────────
   Mobile bottom bar
───────────────────────────────────────────── */
function MobileBar({ items, unreadCount }) {
  return (
    <nav
      className="sb-mobile-bar"
      aria-label="Mobile navigation"
      role="navigation"
    >
      {items.slice(0, 5).map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.label}
            to={item.to}
            className={({ isActive }) =>
              `sb-mobile-link ${isActive ? "sb-mobile-link--active" : ""}`
            }
            aria-label={item.label}
          >
            <Icon size={20} aria-hidden="true" />
            {item.notification && unreadCount > 0 && (
              <span className="sb-mobile-notif-dot" aria-label={`${unreadCount} unread`} />
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}
