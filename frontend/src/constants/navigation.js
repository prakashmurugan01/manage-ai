import {
    Activity,
    Bell,
    Boxes,
    ClipboardList,
    MessageSquare,
    LifeBuoy,
    FileText,
    Gauge,
    Settings2,
    LayoutDashboard,
    Shield,
    Users,
    Sliders
} from "lucide-react";

import { ROLES } from "../utils/rbac.js";

export const navigation = [
    { label: "Dashboard", to: "/dashboard", icon: LayoutDashboard },
    { label: "Projects", to: "/projects", icon: Boxes },
    { label: "Tasks", to: "/tasks", icon: ClipboardList },
    { label: "Collaboration", to: "/collaboration", icon: MessageSquare },
    { label: "Tickets", to: "/tickets", icon: LifeBuoy },
    { label: "Project Files", to: "/files", icon: FileText },
    { label: "Notifications", to: "/notifications", icon: Bell },
    { label: "Connection Engine", to: "/enterprise", icon: Settings2 },
    { label: "User Management", to: "/users", icon: Users, roles: [ROLES.SUPER_ADMIN, ROLES.ADMIN] },
    { label: "Settings", to: "/settings", icon: Sliders, roles: [ROLES.SUPER_ADMIN, ROLES.ADMIN] },
    { label: "Logs", to: "/logs", icon: Shield, roles: [ROLES.SUPER_ADMIN] },
    { label: "Monitoring", to: "/monitoring", icon: Gauge, roles: [ROLES.SUPER_ADMIN] },
    { label: "Activity", to: "/dashboard", icon: Activity }
];