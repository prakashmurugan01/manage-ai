import { motion } from "framer-motion";
import { ScanFace, LogIn, Moon, Sun, SunMedium } from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import Button from "../components/ui/Button.jsx";
import FaceCapture from "../components/auth/FaceCapture.jsx";
import { apiErrorMessage } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { THEMES, useTheme } from "../context/ThemeContext.jsx";

const themeItems = [
  { value: THEMES.DARK, icon: Moon },
  { value: THEMES.LIGHT, icon: SunMedium },
  { value: THEMES.WHITE, icon: Sun }
];

export default function Login() {
  const { login, faceLogin } = useAuth();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "super@manageai.local", password: "ManageAI@12345" });
  const [error, setError] = useState("");
  const [faceOpen, setFaceOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(form.email, form.password);
      navigate(location.state?.from?.pathname || "/dashboard", { replace: true });
    } catch (error) {
      setError(apiErrorMessage(error, "Invalid email or password."));
    } finally {
      setSubmitting(false);
    }
  }

  async function submitFace(formData) {
    await faceLogin(formData);
    navigate(location.state?.from?.pathname || "/dashboard", { replace: true });
  }

  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden bg-ink-950 px-4">
      <div className="pointer-events-none absolute inset-0 animated-grid opacity-40" />
      <motion.form initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} onSubmit={submit} className="glass-band relative w-full max-w-md p-6">
        <div className="mb-6">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div className="brand-mark grid h-11 w-11 place-items-center rounded-lg bg-gradient-to-br from-teal-300 to-sky-400 font-black text-white">MA</div>
            <div className="rounded-lg border border-white/10 bg-white/[0.04] p-1">
              {themeItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button key={item.value} type="button" onClick={() => setTheme(item.value)} className={`h-8 w-8 rounded-md ${theme === item.value ? "bg-white/15 text-teal-200" : "text-slate-400"}`}>
                    <Icon size={15} className="mx-auto" />
                  </button>
                );
              })}
            </div>
          </div>
          <h1 className="text-2xl font-semibold text-white">Sign in to ManageAI</h1>
          <p className="mt-1 text-sm text-slate-400">Secure internal SaaS operations console.</p>
        </div>
        <label className="label">Email</label>
        <input className="field mb-4" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
        <label className="label">Password</label>
        <input className="field mb-4" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
        {error && <p className="mb-4 rounded-lg border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-sm text-rose-200">{error}</p>}
        <Button type="submit" disabled={submitting} className="w-full">
          <LogIn size={16} />
          {submitting ? "Signing in..." : "Sign in"}
        </Button>
        <Button type="button" variant="secondary" className="mt-3 w-full" onClick={() => setFaceOpen((open) => !open)}>
          <ScanFace size={16} />
          Face unlock
        </Button>
        {faceOpen && (
          <div className="mt-4">
            <FaceCapture email={form.email} mode="login" onSubmit={submitFace} />
          </div>
        )}
        <p className="mt-4 text-center text-sm text-slate-400">
          New workspace user? <Link className="text-teal-200 hover:text-teal-100" to="/register">Create account</Link>
        </p>
      </motion.form>
    </main>
  );
}
