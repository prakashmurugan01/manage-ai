import { Navigate, useLocation } from "react-router-dom";
import { motion } from "framer-motion";

import { useAuth } from "../../context/AuthContext.jsx";
import { hasAnyRole } from "../../utils/rbac.js";
import Button from "../ui/Button.jsx";
import Badge from "../ui/Badge.jsx";

function AccountReviewState({ user, onSignOut }) {
  const rejected = user?.approval_status === "REJECTED";
  return (
    <div className="grid min-h-screen place-items-center bg-ink-950 px-4 text-slate-200">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="panel w-full max-w-lg p-6">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">Account Access</p>
            <h1 className="mt-2 text-2xl font-semibold text-white">{rejected ? "Registration rejected" : "Pending admin approval"}</h1>
          </div>
          <Badge value={user?.approval_status || "PENDING"} />
        </div>
        <p className="text-sm leading-6 text-slate-300">
          {rejected
            ? "Your account cannot access dashboard features. Contact an Admin or Super Admin for the next step."
            : "Your account is under review. Please wait for an Admin or Super Admin to approve your access."}
        </p>
        {user?.rejection_reason && (
          <div className="mt-4 rounded-lg border border-rose-300/20 bg-rose-300/10 p-3 text-sm text-rose-100">
            {user.rejection_reason}
          </div>
        )}
        <div className="mt-6 flex justify-end">
          <Button variant="secondary" onClick={onSignOut}>Sign out</Button>
        </div>
      </motion.div>
    </div>
  );
}

export default function ProtectedRoute({ children, roles = [] }) {
  const { user, loading, logout } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center bg-ink-950 text-slate-200">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="panel w-full max-w-sm p-6 text-center">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-lg border border-teal-300/20 bg-teal-300/10">
            <motion.span animate={{ rotate: 360 }} transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }} className="h-7 w-7 rounded-full border-2 border-teal-200 border-t-transparent" />
          </div>
          <p className="mt-4 text-sm font-medium text-white">Loading secure workspace</p>
          <p className="mt-2 text-xs text-slate-500">Syncing dashboard modules and realtime controls.</p>
        </motion.div>
      </div>
    );
  }

  if (!user || user.is_active === false) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (user.approval_status && user.approval_status !== "APPROVED") {
    return <AccountReviewState user={user} onSignOut={logout} />;
  }

  if (!hasAnyRole(user, roles)) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}
