import { Camera, CheckCircle2, ScanFace, UserPlus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import Button from "../components/ui/Button.jsx";
import FaceCapture from "../components/auth/FaceCapture.jsx";
import { useAuth } from "../context/AuthContext.jsx";

export default function Register() {
  const { register } = useAuth();
  const [form, setForm] = useState({ email: "", username: "", first_name: "", last_name: "", password: "", phone: "", role: "CLIENT", avatar: null });
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [faceImages, setFaceImages] = useState([]);

  async function submit(event) {
    event.preventDefault();
    setError("");
    try {
      const payload = new FormData();
      Object.entries(form).forEach(([key, value]) => {
        if (value) payload.append(key, value);
      });
      faceImages.forEach((image, index) => payload.append("face_images", image, `registration-face-${index + 1}.jpg`));
      await register(payload);
      setDone(true);
    } catch {
      setError("Registration failed. Check required fields and password strength.");
    }
  }

  async function captureRegistrationFace(formData) {
    setFaceImages(formData.getAll("face_images"));
  }

  return (
    <main className="grid min-h-screen place-items-center bg-ink-950 px-4 py-8">
      <form onSubmit={submit} className="panel w-full max-w-3xl p-6">
        {done && (
          <div className="mb-5 rounded-lg border border-emerald-300/20 bg-emerald-300/10 p-4 text-sm text-emerald-100">
            <div className="flex items-start gap-3">
              <CheckCircle2 size={18} className="mt-0.5" />
              <div>
                <p className="font-medium text-white">Account submitted for admin approval.</p>
                <p className="mt-1 text-emerald-100/80">You can sign in to view your review status. Dashboard features unlock after approval.</p>
              </div>
            </div>
          </div>
        )}
        <h1 className="text-2xl font-semibold text-white">Create ManageAI account</h1>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          {[
            ["first_name", "First name"],
            ["last_name", "Last name"],
            ["username", "Username"],
            ["email", "Email"],
            ["phone", "Phone"]
          ].map(([key, label]) => (
            <div key={key}>
              <label className="label">{label}</label>
              <input className="field" required={key !== "last_name"} type={key === "email" ? "email" : "text"} value={form[key]} onChange={(event) => setForm({ ...form, [key]: event.target.value })} />
            </div>
          ))}
          <div>
            <label className="label">Role</label>
            <select className="field" value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
              <option value="CLIENT">Client</option>
              <option value="DEVELOPER">Developer</option>
            </select>
          </div>
          <div>
            <label className="label">Password</label>
            <input className="field" required type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Profile Photo</label>
            <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-300">
              <span className="inline-flex items-center gap-2"><Camera size={16} />{form.avatar?.name || "Upload optional photo"}</span>
              <input className="hidden" type="file" accept="image/*" onChange={(event) => setForm({ ...form, avatar: event.target.files?.[0] || null })} />
            </label>
          </div>
        </div>
        {error && <p className="mt-4 rounded-lg border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-sm text-rose-200">{error}</p>}
        <div className="mt-6 flex items-center justify-between gap-3">
          <Link className="text-sm text-slate-400 hover:text-white" to="/login">Back to login</Link>
          <Button type="submit">
            <UserPlus size={16} />
            Submit for approval
          </Button>
        </div>
        <div className="mt-6 rounded-lg border border-white/10 bg-white/[0.035] p-4">
          <div className="mb-3 flex items-center gap-2">
            <ScanFace size={17} className="text-teal-200" />
            <p className="text-sm font-semibold text-white">Optional face enrollment after approval</p>
          </div>
          <p className="mb-3 text-xs text-slate-400">Capture front, left, and right angles now. The account still stays pending until an admin approves it.</p>
          <FaceCapture email={form.email} mode="enroll" onSubmit={captureRegistrationFace} />
          {faceImages.length === 3 && <p className="mt-3 text-xs font-medium text-emerald-200">Three face angles are ready for registration.</p>}
        </div>
      </form>
    </main>
  );
}
