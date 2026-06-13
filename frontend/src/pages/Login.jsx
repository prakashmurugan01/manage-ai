import { motion } from "framer-motion";
import {
  Activity,
  ArrowLeft,
  Eye,
  EyeOff,
  Fingerprint,
  KeyRound,
  LockKeyhole,
  Mail,
  Moon,
  RadioTower,
  ScanFace,
  ShieldCheck,
  Sparkles,
  SunMedium,
  UserRoundPlus,
  Zap
} from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import FaceCapture from "../components/auth/FaceCapture.jsx";
import { apiErrorMessage } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { THEMES, useTheme } from "../context/ThemeContext.jsx";

const themeItems = [
  { value: THEMES.DARK, label: "Dark", icon: Moon },
  { value: THEMES.LIGHT, label: "Light", icon: SunMedium },
  { value: THEMES.CYBER, label: "System", icon: Sparkles }
];

const features = [
  { title: "RBAC", label: "Role Based Security", icon: ShieldCheck },
  { title: "Face Unlock", label: "Biometric Authentication", icon: ScanFace },
  { title: "Audit Logs", label: "Real-Time Monitoring", icon: Activity }
];

const stats = [
  ["99.99%", "Uptime"],
  ["50K+", "Deployments"],
  ["256-bit", "Encryption"]
];

function AuthBackground() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden bg-[#050816]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_18%,rgba(249,115,22,0.34),transparent_30%),radial-gradient(circle_at_82%_18%,rgba(168,85,247,0.26),transparent_32%),radial-gradient(circle_at_70%_78%,rgba(244,63,94,0.22),transparent_34%),linear-gradient(135deg,#050816_0%,#090a14_52%,#180610_100%)]" />
      <div className="absolute inset-0 animated-grid opacity-20" />
      <div className="cyber-particles absolute inset-0 opacity-35" />
      <motion.div
        className="absolute -left-24 top-10 h-80 w-80 rounded-full bg-orange-500/20 blur-3xl"
        animate={{ x: [0, 42, 0], y: [0, 28, 0], scale: [1, 1.08, 1] }}
        transition={{ duration: 11, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute -right-24 top-28 h-96 w-96 rounded-full bg-fuchsia-500/18 blur-3xl"
        animate={{ x: [0, -34, 0], y: [0, 32, 0], scale: [1, 1.12, 1] }}
        transition={{ duration: 13, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="absolute inset-x-0 top-0 h-56 bg-[linear-gradient(115deg,transparent,rgba(251,146,60,0.14),rgba(217,70,239,0.13),transparent)] blur-2xl" />
    </div>
  );
}

export default function Login() {
  const { login, faceLogin } = useAuth();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState(() => ({ email: localStorage.getItem("manageaiFaceEmail") || "super@manageai.local", password: "ManageAI@12345" }));
  const [error, setError] = useState("");
  const [faceOpen, setFaceOpen] = useState(() => localStorage.getItem("manageaiFaceLoginReady") === "true");
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(form.email, form.password);
      navigate(location.state?.from?.pathname || "/dashboard", { replace: true });
    } catch (caught) {
      setError(apiErrorMessage(caught, "Invalid email or password."));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitFace(formData) {
    const signedIn = await faceLogin(formData);
    localStorage.setItem("manageaiFaceLoginReady", "true");
    localStorage.setItem("manageaiFaceEmail", signedIn?.email || form.email);
    navigate(location.state?.from?.pathname || "/dashboard", { replace: true });
  }

  return (
    <main className="relative min-h-screen overflow-hidden px-4 py-6 text-white sm:px-6 lg:px-8">
      <AuthBackground />

      <div className="relative z-10 mx-auto grid min-h-[calc(100vh-3rem)] w-full max-w-7xl items-center gap-8 lg:grid-cols-[1.08fr_0.92fr]">
        <motion.section initial={{ opacity: 0, x: -18 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.55 }} className="hidden lg:block">
          <Link to="/" className="mb-10 inline-flex items-center gap-2 text-sm text-white/68 transition hover:text-orange-200 focus:outline-none focus:ring-2 focus:ring-orange-300/50">
            <ArrowLeft size={17} />
            Back to engine
          </Link>
          <div className="max-w-3xl">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-orange-300/30 bg-orange-300/10 px-4 py-2 text-xs font-bold uppercase text-orange-100 shadow-[0_0_34px_rgba(249,115,22,0.22)]">
              <span className="h-2 w-2 animate-pulse rounded-full bg-orange-300" />
              AI operations center
            </div>
            <h1 className="text-5xl font-black leading-[1.02] text-white md:text-6xl lg:text-[72px]">
              Welcome Back to the{" "}
              <span className="bg-gradient-to-r from-orange-300 via-rose-400 to-pink-500 bg-clip-text text-transparent">
                Control Deck
              </span>
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-white/72">
              Access dashboards, hosting infrastructure, AI systems, deployment pipelines, API management, and enterprise operations from one unified platform.
            </p>
            <div className="mt-9 grid max-w-3xl grid-cols-3 gap-4">
              {features.map((item) => {
                const Icon = item.icon;
                return (
                  <motion.div
                    key={item.title}
                    whileHover={{ y: -6 }}
                    className="rounded-lg border border-white/12 bg-white/[0.055] p-5 shadow-[0_0_0_1px_rgba(251,146,60,0.05),0_20px_70px_rgba(0,0,0,0.22)] backdrop-blur-2xl transition hover:border-orange-300/45 hover:shadow-[0_0_34px_rgba(249,115,22,0.22)]"
                  >
                    <Icon className="mb-4 text-orange-200" size={23} aria-hidden="true" />
                    <div className="text-2xl font-black text-white">{item.title}</div>
                    <div className="mt-2 text-xs font-semibold text-white/58">{item.label}</div>
                  </motion.div>
                );
              })}
            </div>
            <div className="mt-8 grid max-w-2xl grid-cols-3 gap-3">
              {stats.map(([value, label]) => (
                <div key={label} className="rounded-lg border border-white/10 bg-black/18 px-5 py-4 backdrop-blur-xl">
                  <div className="text-2xl font-black text-orange-100">{value}</div>
                  <div className="mt-1 text-xs text-white/54">{label}</div>
                </div>
              ))}
            </div>
          </div>
        </motion.section>

        <motion.form
          initial={{ opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          onSubmit={submit}
          className="relative mx-auto w-full max-w-[520px] overflow-hidden rounded-lg border border-white/14 bg-white/[0.075] p-6 shadow-[0_30px_120px_rgba(244,63,94,0.22)] backdrop-blur-[30px] sm:p-8"
        >
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-orange-300 to-pink-400" />
          <div className="absolute -right-12 -top-12 h-32 w-32 rounded-full bg-pink-500/20 blur-3xl" />

          <div className="relative mb-8 flex items-start justify-between gap-4">
            <div>
              <Link to="/" className="grid h-14 w-14 place-items-center rounded-lg bg-gradient-to-br from-orange-500 to-pink-600 text-lg font-black text-white shadow-[0_0_38px_rgba(249,115,22,0.45)] focus:outline-none focus:ring-2 focus:ring-orange-300/60">
                AI
              </Link>
              <p className="mt-3 text-sm font-semibold text-white/72">ManageAI Command</p>
            </div>
            <div className="rounded-lg border border-white/10 bg-black/30 p-1 backdrop-blur-xl" role="group" aria-label="Theme">
              {themeItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setTheme(item.value)}
                    className={`h-10 w-10 rounded-md transition focus:outline-none focus:ring-2 focus:ring-orange-300/50 ${
                      theme === item.value ? "bg-gradient-to-r from-orange-500/35 to-pink-500/30 text-orange-100" : "text-white/62 hover:bg-white/10 hover:text-white"
                    }`}
                    aria-label={`Use ${item.label} theme`}
                    title={item.label}
                  >
                    <Icon size={17} className="mx-auto" />
                  </button>
                );
              })}
            </div>
          </div>

          <div className="relative mb-7">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-orange-300/30 bg-orange-300/10 px-3 py-1 text-[11px] font-bold uppercase text-orange-100">
              <Zap size={13} />
              Secure Enterprise Authentication
            </div>
            <h2 className="text-4xl font-black text-white">Engage Engine</h2>
            <p className="mt-3 text-sm leading-6 text-white/64">Protected by AI Shield with approval-gated access and biometric fallback.</p>
          </div>

          <div className="space-y-4">
            <label className="group relative block">
              <Mail className="pointer-events-none absolute left-4 top-1/2 z-10 -translate-y-1/2 text-white/45 transition group-focus-within:text-orange-200" size={18} />
              <input
                className="peer h-14 w-full rounded-2xl border border-white/12 bg-slate-950/55 px-12 pb-2 pt-5 text-sm text-white outline-none transition placeholder:text-transparent focus:border-orange-300/60 focus:ring-4 focus:ring-orange-400/15"
                id="login-email"
                type="email"
                value={form.email}
                onChange={(event) => setForm({ ...form, email: event.target.value })}
                autoComplete="email"
                placeholder="Email"
                required
              />
              <span className="pointer-events-none absolute left-12 top-2 text-[11px] font-semibold uppercase text-white/46 transition peer-placeholder-shown:top-4 peer-placeholder-shown:text-sm peer-placeholder-shown:normal-case peer-focus:top-2 peer-focus:text-[11px] peer-focus:font-semibold peer-focus:uppercase peer-focus:text-orange-100">
                Email
              </span>
            </label>

            <label className="group relative block">
              <LockKeyhole className="pointer-events-none absolute left-4 top-1/2 z-10 -translate-y-1/2 text-white/45 transition group-focus-within:text-orange-200" size={18} />
              <input
                className="peer h-14 w-full rounded-2xl border border-white/12 bg-slate-950/55 px-12 pb-2 pt-5 text-sm text-white outline-none transition placeholder:text-transparent focus:border-orange-300/60 focus:ring-4 focus:ring-orange-400/15"
                id="login-password"
                type={showPassword ? "text" : "password"}
                value={form.password}
                onChange={(event) => setForm({ ...form, password: event.target.value })}
                autoComplete="current-password"
                placeholder="Password"
                required
              />
              <span className="pointer-events-none absolute left-12 top-2 text-[11px] font-semibold uppercase text-white/46 transition peer-placeholder-shown:top-4 peer-placeholder-shown:text-sm peer-placeholder-shown:normal-case peer-focus:top-2 peer-focus:text-[11px] peer-focus:font-semibold peer-focus:uppercase peer-focus:text-orange-100">
                Password
              </span>
              <button
                type="button"
                onClick={() => setShowPassword((value) => !value)}
                className="absolute right-3 top-1/2 grid h-9 w-9 -translate-y-1/2 place-items-center rounded-md text-white/56 transition hover:bg-white/10 hover:text-white focus:outline-none focus:ring-2 focus:ring-orange-300/50"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </label>
          </div>

          {error && (
            <div className="mt-4 rounded-lg border border-rose-300/35 bg-rose-500/12 px-4 py-3 text-sm text-rose-100" role="alert">
              {error}
            </div>
          )}

          <motion.button
            whileTap={{ scale: 0.98 }}
            type="submit"
            disabled={submitting}
            className="mt-6 inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-orange-500 to-pink-600 text-sm font-black text-white shadow-[0_18px_46px_rgba(244,63,94,0.32)] transition hover:scale-[1.01] hover:shadow-[0_24px_70px_rgba(244,63,94,0.42)] focus:outline-none focus:ring-2 focus:ring-orange-200 disabled:cursor-not-allowed disabled:opacity-65"
          >
            {submitting ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/70 border-t-transparent" /> : <KeyRound size={17} />}
            {submitting ? "Engaging..." : "Engage Engine"}
          </motion.button>

          <button
            type="button"
            onClick={() => setFaceOpen((open) => !open)}
            className="mt-3 inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl border border-white/12 bg-white/[0.08] text-sm font-bold text-white transition hover:border-pink-300/45 hover:bg-white/[0.12] focus:outline-none focus:ring-2 focus:ring-pink-300/50"
          >
            <Fingerprint size={17} />
            Face Unlock
          </button>

          {faceOpen && (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-4 rounded-lg border border-white/10 bg-black/22 p-3">
              <FaceCapture email={form.email} mode="login" onSubmit={submitFace} autoStart />
              <p className="mt-3 text-xs leading-5 text-white/54">If face login fails, use password login as fallback.</p>
            </motion.div>
          )}

          <div className="mt-5 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-sm">
            <Link className="text-white/58 transition hover:text-orange-100 focus:outline-none focus:ring-2 focus:ring-orange-300/40" to="/login">
              Forgot Password
            </Link>
            <Link className="inline-flex items-center gap-1 font-bold text-orange-100 transition hover:text-pink-100 focus:outline-none focus:ring-2 focus:ring-orange-300/40" to="/register">
              <UserRoundPlus size={15} />
              Request Access
            </Link>
            <a className="text-white/58 transition hover:text-orange-100 focus:outline-none focus:ring-2 focus:ring-orange-300/40" href="mailto:admin@manageai.local">
              Contact Administrator
            </a>
          </div>

          <div className="mt-7 flex items-center justify-center gap-2 border-t border-white/10 pt-5 text-xs text-white/50">
            <RadioTower size={14} className="text-orange-200" />
            Secure Enterprise Authentication
          </div>
        </motion.form>
      </div>
    </main>
  );
}
