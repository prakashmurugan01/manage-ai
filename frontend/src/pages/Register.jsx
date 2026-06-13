import { motion } from "framer-motion";
import {
  ArrowLeft,
  BellRing,
  Camera,
  CheckCircle2,
  ChevronRight,
  IdCard,
  LockKeyhole,
  Mail,
  Phone,
  ScanFace,
  ShieldCheck,
  Sparkles,
  Upload,
  User,
  UserRound,
  UserRoundPlus,
  UsersRound,
  Zap
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import Button from "../components/ui/Button.jsx";
import FaceCapture from "../components/auth/FaceCapture.jsx";
import { apiErrorMessage } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

const workflow = [
  "User Registers",
  "Status = Pending Approval",
  "Admin Notification",
  "Super Admin Notification",
  "Approval Required",
  "User Access Granted"
];

const fieldIcon = {
  first_name: User,
  last_name: UserRound,
  username: IdCard,
  email: Mail,
  phone: Phone,
  password: LockKeyhole
};

function AuthBackground() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden bg-[#050816]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_16%_12%,rgba(249,115,22,0.32),transparent_30%),radial-gradient(circle_at_84%_24%,rgba(217,70,239,0.24),transparent_34%),radial-gradient(circle_at_58%_88%,rgba(244,63,94,0.18),transparent_34%),linear-gradient(135deg,#050816_0%,#090a14_54%,#190612_100%)]" />
      <div className="absolute inset-0 animated-grid opacity-20" />
      <div className="cyber-particles absolute inset-0 opacity-30" />
      <motion.div
        className="absolute left-[-8rem] top-16 h-96 w-96 rounded-full bg-orange-500/20 blur-3xl"
        animate={{ x: [0, 38, 0], y: [0, 22, 0], scale: [1, 1.1, 1] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute right-[-10rem] bottom-12 h-[28rem] w-[28rem] rounded-full bg-pink-500/18 blur-3xl"
        animate={{ x: [0, -44, 0], y: [0, -24, 0], scale: [1, 1.12, 1] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}

function FloatingField({ name, label, type = "text", value, onChange, required = true }) {
  const Icon = fieldIcon[name] || User;
  return (
    <label className="group relative block">
      <Icon className="pointer-events-none absolute left-4 top-1/2 z-10 -translate-y-1/2 text-white/42 transition group-focus-within:text-orange-200" size={18} />
      <input
        className="peer h-14 w-full rounded-2xl border border-white/12 bg-slate-950/55 px-12 pb-2 pt-5 text-sm text-white outline-none transition placeholder:text-transparent focus:border-orange-300/60 focus:ring-4 focus:ring-orange-400/15"
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={name === "password" ? "new-password" : name}
        placeholder={label}
        required={required}
      />
      <span className="pointer-events-none absolute left-12 top-2 text-[11px] font-semibold uppercase text-white/46 transition peer-placeholder-shown:top-4 peer-placeholder-shown:text-sm peer-placeholder-shown:normal-case peer-focus:top-2 peer-focus:text-[11px] peer-focus:font-semibold peer-focus:uppercase peer-focus:text-orange-100">
        {label}
      </span>
    </label>
  );
}

export default function Register() {
  const { register } = useAuth();
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    username: "",
    email: "",
    phone: "",
    password: "",
    role: "CLIENT",
    avatar: null
  });
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [faceImages, setFaceImages] = useState([]);

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const payload = new FormData();
      Object.entries(form).forEach(([key, value]) => {
        if (value) payload.append(key, value);
      });
      faceImages.forEach((image, index) => payload.append("face_images", image, `registration-face-${index + 1}.jpg`));
      await register(payload);
      setDone(true);
    } catch (caught) {
      setError(apiErrorMessage(caught, "Registration failed. Check required fields and password strength."));
    } finally {
      setSubmitting(false);
    }
  }

  async function saveRegistrationFace(formData) {
    setFaceImages(formData.getAll("face_images"));
  }

  return (
    <main className="relative min-h-screen overflow-hidden px-4 py-6 text-white sm:px-6 lg:px-8">
      <AuthBackground />
      <div className="relative z-10 mx-auto grid min-h-[calc(100vh-3rem)] max-w-7xl items-center gap-8 lg:grid-cols-[0.9fr_1.1fr]">
        <motion.section initial={{ opacity: 0, x: -18 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.55 }} className="hidden lg:block">
          <Link to="/login" className="mb-10 inline-flex items-center gap-2 text-sm text-white/68 transition hover:text-orange-200 focus:outline-none focus:ring-2 focus:ring-orange-300/50">
            <ArrowLeft size={17} />
            Back to login
          </Link>
          <div className="max-w-2xl">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-orange-300/30 bg-orange-300/10 px-4 py-2 text-xs font-bold uppercase text-orange-100 shadow-[0_0_34px_rgba(249,115,22,0.22)]">
              <BellRing size={14} />
              Approval Required
            </div>
            <h1 className="text-5xl font-black leading-[1.04] text-white md:text-6xl">
              Request access to the{" "}
              <span className="bg-gradient-to-r from-orange-300 via-rose-400 to-pink-500 bg-clip-text text-transparent">
                Control Deck
              </span>
            </h1>
            <p className="mt-6 text-lg leading-8 text-white/70">
              Enterprise accounts stay locked until an Admin or Super Admin approves the request. Until approval, users cannot login and see: &quot;Your account is pending approval.&quot;
            </p>
            <div className="mt-8 rounded-lg border border-white/12 bg-white/[0.055] p-5 backdrop-blur-2xl">
              <div className="mb-4 flex items-center gap-2 text-sm font-bold text-orange-100">
                <ShieldCheck size={18} />
                Registration workflow
              </div>
              <div className="grid gap-3">
                {workflow.map((step, index) => (
                  <div key={step} className="flex items-center gap-3 rounded-lg border border-white/10 bg-black/18 px-4 py-3">
                    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-gradient-to-br from-orange-500 to-pink-600 text-xs font-black text-white">
                      {index + 1}
                    </span>
                    <span className="text-sm text-white/78">{step}</span>
                    {index < workflow.length - 1 && <ChevronRight className="ml-auto text-white/30" size={16} />}
                  </div>
                ))}
              </div>
            </div>
            <div className="mt-5 grid grid-cols-3 gap-3">
              {[
                ["Face Optional", ScanFace],
                ["RBAC Ready", UsersRound],
                ["AI Shield", Sparkles]
              ].map(([label, Icon]) => (
                <div key={label} className="rounded-lg border border-white/10 bg-black/20 p-4 backdrop-blur-xl">
                  <Icon className="mb-3 text-orange-200" size={20} />
                  <div className="text-sm font-bold text-white">{label}</div>
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
          className="relative mx-auto w-full max-w-3xl overflow-hidden rounded-lg border border-white/14 bg-white/[0.075] p-5 shadow-[0_30px_120px_rgba(244,63,94,0.22)] backdrop-blur-[30px] sm:p-7"
        >
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-orange-300 to-pink-400" />
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
              <div className="grid h-14 w-14 place-items-center rounded-lg bg-gradient-to-br from-orange-500 to-pink-600 text-lg font-black text-white shadow-[0_0_38px_rgba(249,115,22,0.45)]">
                AI
              </div>
              <p className="mt-3 text-sm font-semibold text-white/72">ManageAI Command</p>
            </div>
            <div className="rounded-lg border border-emerald-300/20 bg-emerald-300/10 px-3 py-2 text-xs font-semibold text-emerald-100">
              Pending Approval
            </div>
          </div>

          {done ? (
            <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="rounded-lg border border-emerald-300/25 bg-emerald-300/10 p-6">
              <CheckCircle2 className="text-emerald-200" size={38} />
              <h2 className="mt-4 text-3xl font-black text-white">Access request submitted</h2>
              <p className="mt-3 text-sm leading-6 text-emerald-50/82">
                Your account is pending approval. Admin and Super Admin users have been notified. You cannot login until approval is granted.
              </p>
              <div className="mt-5 rounded-lg border border-white/10 bg-black/20 p-4">
                <div className="flex items-center gap-2 text-sm font-bold text-white">
                  <ScanFace size={17} className="text-orange-200" />
                  Face recognition is optional
                </div>
                <p className="mt-2 text-sm leading-6 text-white/62">
                  After approval, you may enroll Front, Left, and Right face captures for Face Unlock. Password login remains available as fallback.
                </p>
              </div>
              <div className="mt-6 flex flex-wrap items-center gap-3">
                <Link className="btn-secondary" to="/login">Return to login</Link>
                <a className="btn-secondary" href="mailto:admin@manageai.local">Contact Administrator</a>
              </div>
            </motion.div>
          ) : (
            <>
              <div className="mb-6">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-orange-300/30 bg-orange-300/10 px-3 py-1 text-[11px] font-bold uppercase text-orange-100">
                  <Zap size={13} />
                  Enterprise Registration
                </div>
                <h2 className="text-4xl font-black text-white">Create access request</h2>
                <p className="mt-3 text-sm leading-6 text-white/64">Submit your profile for approval. Biometric enrollment is available after access is granted.</p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <FloatingField name="first_name" label="First Name" value={form.first_name} onChange={(value) => update("first_name", value)} />
                <FloatingField name="last_name" label="Last Name" value={form.last_name} onChange={(value) => update("last_name", value)} required={false} />
                <FloatingField name="username" label="Username" value={form.username} onChange={(value) => update("username", value)} />
                <FloatingField name="email" label="Email" type="email" value={form.email} onChange={(value) => update("email", value)} />
                <FloatingField name="phone" label="Phone" value={form.phone} onChange={(value) => update("phone", value)} />
                <FloatingField name="password" label="Password" type="password" value={form.password} onChange={(value) => update("password", value)} />
                <label className="relative block">
                  <UsersRound className="pointer-events-none absolute left-4 top-1/2 z-10 -translate-y-1/2 text-white/42" size={18} />
                  <select
                    className="h-14 w-full rounded-2xl border border-white/12 bg-slate-950/55 px-12 text-sm font-semibold text-white outline-none transition focus:border-orange-300/60 focus:ring-4 focus:ring-orange-400/15"
                    value={form.role}
                    onChange={(event) => update("role", event.target.value)}
                    aria-label="Role"
                  >
                    <option value="CLIENT">Client</option>
                    <option value="DEVELOPER">Developer</option>
                  </select>
                </label>
                <label className="flex h-14 cursor-pointer items-center justify-between gap-3 rounded-2xl border border-white/12 bg-slate-950/55 px-4 text-sm text-white/72 transition hover:border-orange-300/45 focus-within:ring-4 focus-within:ring-orange-400/15">
                  <span className="inline-flex min-w-0 items-center gap-3">
                    <Camera size={18} className="shrink-0 text-white/42" />
                    <span className="truncate">{form.avatar?.name || "Profile Photo"}</span>
                  </span>
                  <Upload size={17} className="shrink-0 text-orange-200" />
                  <input className="sr-only" type="file" accept="image/*" onChange={(event) => update("avatar", event.target.files?.[0] || null)} />
                </label>
              </div>

              <div className="mt-5 rounded-lg border border-white/10 bg-black/18 p-4">
                <div className="flex items-start gap-3">
                  <ScanFace className="mt-0.5 text-orange-200" size={19} />
                  <div>
                    <p className="text-sm font-bold text-white">Face recognition is optional</p>
                    <p className="mt-1 text-xs leading-5 text-white/58">
                      Register without face now, or save Front, Left, and Right live camera captures with this request. Face login stays disabled until approval.
                    </p>
                  </div>
                </div>
                <div className="mt-4">
                  <FaceCapture
                    email={form.email}
                    mode="enroll"
                    onSubmit={saveRegistrationFace}
                    startLabel="Live camera"
                    submitLabel="Save face captures"
                  />
                  {faceImages.length === 3 && (
                    <p className="mt-3 rounded-lg border border-emerald-300/20 bg-emerald-300/10 px-3 py-2 text-xs font-semibold text-emerald-100">
                      Front, Left, and Right face captures are saved with this registration request.
                    </p>
                  )}
                </div>
              </div>

              {error && (
                <div className="mt-4 rounded-lg border border-rose-300/35 bg-rose-500/12 px-4 py-3 text-sm text-rose-100" role="alert">
                  {error}
                </div>
              )}

              <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
                <Link className="text-sm text-white/58 transition hover:text-orange-100 focus:outline-none focus:ring-2 focus:ring-orange-300/40" to="/login">
                  Back to login
                </Link>
                <Button type="submit" disabled={submitting} className="!rounded-2xl !bg-gradient-to-r !from-orange-500 !to-pink-600 !px-6 !text-white">
                  {submitting ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/70 border-t-transparent" /> : <UserRoundPlus size={16} />}
                  {submitting ? "Submitting..." : "Submit for approval"}
                </Button>
              </div>
            </>
          )}
        </motion.form>
      </div>
    </main>
  );
}
