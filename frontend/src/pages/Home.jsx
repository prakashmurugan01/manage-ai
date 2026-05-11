import {
  ArrowRight,
  BarChart3,
  BellRing,
  BrainCircuit,
  CheckCircle2,
  Code2,
  LockKeyhole,
  ScanFace,
  ServerCog,
  ShieldCheck,
  Users
} from "lucide-react";
import { Link } from "react-router-dom";

const products = [
  { title: "Identity and access management", detail: "Pending approvals, RBAC, face login, MFA policy.", icon: LockKeyhole },
  { title: "AI face verification", detail: "Front, left, and right face captures with match scoring.", icon: ScanFace },
  { title: "Developer operations", detail: "API access, logs, debugging tools, and test console.", icon: Code2 },
  { title: "Admin command center", detail: "Approvals, analytics, alerts, and user management.", icon: BarChart3 },
  { title: "Security intelligence", detail: "Suspicious login alerts, liveness hints, and audit logs.", icon: ShieldCheck },
  { title: "System integrations", detail: "Projects, notifications, deployment controls, and APIs.", icon: ServerCog }
];

const industries = ["Government", "Education", "Healthcare", "Manufacturing", "Finance", "Retail", "Logistics"];

export default function Home() {
  return (
    <main className="min-h-screen bg-white text-slate-950">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link to="/" className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-blue-600 text-sm font-black text-white">MA</span>
            <span className="text-sm font-semibold">ManageAI</span>
          </Link>
          <nav className="hidden items-center gap-6 text-sm text-slate-600 md:flex">
            <a href="#solutions" className="hover:text-blue-600">Solutions</a>
            <a href="#industries" className="hover:text-blue-600">Industries</a>
            <a href="#security" className="hover:text-blue-600">Security</a>
          </nav>
          <Link to="/login" className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-700">
            Take control
            <ArrowRight size={16} />
          </Link>
        </div>
      </header>

      <section className="relative overflow-hidden bg-[#062b82] text-white">
        <div className="absolute inset-0 bg-[linear-gradient(135deg,#062b82_0%,#0b55dc_56%,#06337f_100%)]" />
        <div className="relative mx-auto grid min-h-[520px] max-w-7xl gap-8 px-4 py-14 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:px-8">
          <div className="flex flex-col justify-center">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-100">Advanced AI access platform</p>
            <h1 className="mt-4 max-w-xl text-4xl font-bold leading-tight sm:text-5xl">Total visibility. Complete control. Powered by AI.</h1>
            <p className="mt-5 max-w-lg text-sm leading-6 text-sky-100">Secure every login with multi-angle face recognition, admin approvals, RBAC, realtime alerts, and role-specific dashboards.</p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/login" className="inline-flex items-center gap-2 rounded-full bg-rose-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-rose-700">
                Login now
                <ArrowRight size={16} />
              </Link>
              <Link to="/register" className="inline-flex items-center gap-2 rounded-full border border-white/40 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10">
                Register access
              </Link>
            </div>
            <div className="mt-10 grid max-w-lg grid-cols-3 gap-3 text-sm">
              <div><strong className="block text-2xl">3x</strong><span className="text-sky-100">Face angles</span></div>
              <div><strong className="block text-2xl">4</strong><span className="text-sky-100">RBAC roles</span></div>
              <div><strong className="block text-2xl">24/7</strong><span className="text-sky-100">Audit watch</span></div>
            </div>
          </div>
          <div className="flex items-center justify-center">
            <div className="relative w-full max-w-xl">
              <div className="rounded-lg border border-white/20 bg-white/10 p-5 shadow-2xl backdrop-blur">
                <div className="grid gap-3 sm:grid-cols-3">
                  {["Front", "Left", "Right"].map((angle) => (
                    <div key={angle} className="rounded-lg bg-cyan-300/15 p-4 text-center">
                      <ScanFace className="mx-auto text-cyan-100" size={40} />
                      <p className="mt-3 text-sm font-semibold">{angle}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-5 rounded-lg bg-slate-950/35 p-4">
                  <div className="flex items-center justify-between text-sm">
                    <span>Face match score</span>
                    <span className="font-semibold text-emerald-200">92%</span>
                  </div>
                  <div className="mt-3 h-2 rounded-full bg-white/15"><div className="h-2 w-[92%] rounded-full bg-emerald-300" /></div>
                  <div className="mt-4 grid grid-cols-2 gap-3 text-xs text-sky-100">
                    <span className="inline-flex items-center gap-2"><CheckCircle2 size={14} /> Liveness hint</span>
                    <span className="inline-flex items-center gap-2"><CheckCircle2 size={14} /> Admin approved</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="solutions" className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-2xl font-bold">AI-powered secure management solutions</h2>
          <p className="mt-2 text-sm text-slate-600">Built for users, developers, admins, and super admins.</p>
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {products.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.title} to="/login" className="group rounded-lg border border-blue-200 bg-blue-50 p-5 transition hover:-translate-y-1 hover:border-blue-500 hover:bg-white hover:shadow-xl">
                <Icon className="text-blue-600" size={24} />
                <h3 className="mt-4 text-sm font-bold">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{item.detail}</p>
              </Link>
            );
          })}
        </div>
      </section>

      <section id="industries" className="bg-slate-950 py-14 text-white">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <h2 className="text-center text-2xl font-bold">IT management that fits every industry</h2>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            {industries.map((industry) => <Link key={industry} to="/login" className="rounded-lg bg-blue-600 px-4 py-2 text-sm">{industry}</Link>)}
          </div>
          <div className="mt-8 grid gap-6 lg:grid-cols-[0.75fr_1fr] lg:items-center">
            <div className="rounded-lg bg-blue-700 p-8">
              <Users size={56} className="text-cyan-100" />
              <p className="mt-6 text-lg font-semibold">Build a controlled access platform with approvals, alerts, and real-time operational visibility.</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {["Pending users", "Active sessions", "Face verification logs", "Security alerts"].map((label) => (
                <div key={label} className="rounded-lg border border-white/10 bg-white/[0.06] p-4">
                  <BellRing className="text-cyan-200" size={20} />
                  <p className="mt-3 text-sm font-semibold">{label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="security" className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="rounded-lg bg-blue-600 p-6 text-white sm:p-8">
          <div className="grid gap-5 lg:grid-cols-[1fr_auto] lg:items-center">
            <div>
              <BrainCircuit size={34} className="text-cyan-100" />
              <h2 className="mt-4 text-2xl font-bold">Advanced dashboard features are ready after login.</h2>
              <p className="mt-2 text-sm text-blue-50">Developer test console, admin approval workflows, Super Admin controls, project dashboards, audit logs, and notifications.</p>
            </div>
            <Link to="/login" className="inline-flex items-center justify-center gap-2 rounded-full bg-rose-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-rose-700">
              Open secure login
              <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
