import {
    Activity,
    Bell,
    KeyRound,
    Server,
    Boxes,
    LifeBuoy,
    Gauge,
    HardDrive,
    MonitorUp,
    Settings2,
    LayoutDashboard,
    Shield,
    Users,
    Sliders,
    Rocket
} from "lucide-react";

import { ROLES } from "../utils/rbac.js";

export const navigation = [
    { label: "Dashboard", to: "/dashboard", icon: LayoutDashboard },
    { label: "Hosting Manager", to: "/hosting", icon: Gauge },
    { label: "Projects", to: "/projects", icon: Boxes },
    { label: "Tickets", to: "/tickets", icon: LifeBuoy },
    { label: "API Integration", to: "/api-keys", icon: KeyRound },
    { label: "Server Monitor", to: "/server-monitor", icon: Server },
    { label: "Remote Access", to: "/remote-access", icon: MonitorUp },
    { label: "Disk Transfer", to: "/file-tracking", icon: HardDrive },
    { label: "Deploy Project", to: "/hosting/deploy", icon: Rocket },

    { label: "Desk Connection", to: "/enterprise", icon: Settings2 },
    { label: "Notifications", to: "/notifications", icon: Bell },
    { label: "User Management", to: "/users", icon: Users, roles: [ROLES.SUPER_ADMIN, ROLES.ADMIN] },
    { label: "Settings", to: "/settings", icon: Sliders, roles: [ROLES.SUPER_ADMIN, ROLES.ADMIN] },
    { label: "Logs", to: "/logs", icon: Shield, roles: [ROLES.SUPER_ADMIN] },
    { label: "API Monitor", to: "/api-monitor", icon: Activity, roles: [ROLES.SUPER_ADMIN] }
];
