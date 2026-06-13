import { Canvas, useFrame } from "@react-three/fiber";
import { Environment, Float, MeshDistortMaterial, OrbitControls, Sparkles } from "@react-three/drei";
import { ArrowRight, Box, Gauge, LockKeyhole, Network, Power, ShieldCheck, Zap } from "lucide-react";
import { Suspense, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const modules = [
  { label: "Observability", icon: Gauge },
  { label: "Identity", icon: LockKeyhole },
  { label: "Network", icon: Network },
  { label: "Security", icon: ShieldCheck }
];

function EngineCore({ powered, onToggle }) {
  const group = useRef(null);
  const core = useRef(null);
  const ringA = useRef(null);
  const ringB = useRef(null);
  const ringC = useRef(null);
  const [hovered, setHovered] = useState(false);

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const speed = powered ? 1 : 0.18;

    if (group.current) {
      group.current.rotation.y += delta * 0.35 * speed;
      group.current.rotation.x = Math.sin(t * 0.35) * 0.12;
    }

    if (core.current) {
      core.current.rotation.y -= delta * 1.25 * speed;
      core.current.scale.setScalar(1 + (powered ? Math.sin(t * 4) * 0.045 : 0) + (hovered ? 0.06 : 0));
    }

    if (ringA.current) ringA.current.rotation.z += delta * 0.9 * speed;
    if (ringB.current) ringB.current.rotation.x += delta * 0.65 * speed;
    if (ringC.current) ringC.current.rotation.y += delta * 1.15 * speed;
  });

  const accent = powered ? "#ff6a2c" : "#394155";
  const hot = powered ? "#ff3010" : "#000000";

  return (
    <group
      ref={group}
      onClick={(event) => {
        event.stopPropagation();
        onToggle();
      }}
      onPointerOver={(event) => {
        event.stopPropagation();
        setHovered(true);
      }}
      onPointerOut={() => setHovered(false)}
    >
      <mesh>
        <sphereGeometry args={[2.45, 64, 64]} />
        <meshBasicMaterial color={accent} transparent opacity={powered ? 0.055 : 0.025} />
      </mesh>

      <Float speed={2} rotationIntensity={0.28} floatIntensity={0.42}>
        <mesh ref={core}>
          <icosahedronGeometry args={[1, 4]} />
          <MeshDistortMaterial
            color={accent}
            emissive={hot}
            emissiveIntensity={powered ? 1.7 : 0.05}
            roughness={0.16}
            metalness={0.88}
            distort={powered ? 0.42 : 0.12}
            speed={powered ? 3 : 0.6}
          />
        </mesh>
      </Float>

      <mesh ref={ringA}>
        <torusGeometry args={[1.55, 0.04, 18, 120]} />
        <meshStandardMaterial color={accent} emissive={hot} emissiveIntensity={powered ? 1.8 : 0.08} metalness={1} roughness={0.2} />
      </mesh>
      <mesh ref={ringB} rotation={[Math.PI / 2.7, 0, 0]}>
        <torusGeometry args={[1.88, 0.03, 18, 120]} />
        <meshStandardMaterial color={powered ? "#ffb070" : "#293044"} emissive={powered ? "#ff8030" : "#000000"} emissiveIntensity={powered ? 1.3 : 0} metalness={1} roughness={0.3} />
      </mesh>
      <mesh ref={ringC} rotation={[0, Math.PI / 3, 0]}>
        <torusGeometry args={[2.18, 0.025, 18, 120]} />
        <meshStandardMaterial color={powered ? "#ff4060" : "#22283a"} emissive={powered ? "#ff2050" : "#000000"} emissiveIntensity={powered ? 1.1 : 0} metalness={1} roughness={0.36} />
      </mesh>

      <pointLight color={powered ? "#ff5a22" : "#0b1020"} intensity={powered ? 18 : 0.8} distance={10} decay={2} />
      {powered && <Sparkles count={90} scale={5.5} size={3} speed={1.35} color="#ff8a40" />}
    </group>
  );
}

function EngineScene({ powered, onToggle }) {
  return (
    <>
      <color attach="background" args={["#05070d"]} />
      <fog attach="fog" args={["#05070d", 6, 18]} />
      <ambientLight intensity={0.35} />
      <directionalLight position={[5, 5, 5]} intensity={0.85} />
      <Suspense fallback={null}>
        <EngineCore powered={powered} onToggle={onToggle} />
        <Environment preset="night" />
      </Suspense>
      <OrbitControls enableZoom={false} enablePan={false} autoRotate={!powered} autoRotateSpeed={0.55} />
    </>
  );
}

export default function Home() {
  const [powered, setPowered] = useState(false);
  const [transitioning, setTransitioning] = useState(false);
  const navigate = useNavigate();

  function handleToggle() {
    if (transitioning) return;

    const next = !powered;
    setPowered(next);

    if (next) {
      setTransitioning(true);
      window.setTimeout(() => {
        navigate("/signin");
      }, 1350);
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#05070d] text-white">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_10%,rgba(249,115,22,0.22),transparent_30%),radial-gradient(circle_at_84%_22%,rgba(244,63,94,0.16),transparent_32%),linear-gradient(135deg,#05070d,#080b14_58%,#12070b)]" />
      <div
        className="pointer-events-none absolute inset-0 opacity-20"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,120,60,0.28) 1px, transparent 1px), linear-gradient(90deg, rgba(255,120,60,0.28) 1px, transparent 1px)",
          backgroundSize: "80px 80px",
          maskImage: "radial-gradient(ellipse at center, black, transparent 76%)"
        }}
      />

      <header className="relative z-20 flex items-center justify-between px-5 py-5 sm:px-8 lg:px-14">
        <Link to="/" className="flex items-center gap-3">
          <span className={`h-3 w-3 rounded-full transition ${powered ? "bg-orange-300 shadow-[0_0_22px_#ff6a2c]" : "bg-white/25"}`} />
          <span className="text-sm font-black uppercase tracking-[0.3em]">ManageAI</span>
        </Link>
        <nav className="hidden items-center gap-8 text-sm text-white/55 md:flex">
          <a href="#platform" className="transition hover:text-orange-200">Platform</a>
          <a href="#modules" className="transition hover:text-orange-200">Modules</a>
          <a href="#security" className="transition hover:text-orange-200">Security</a>
        </nav>
        <Link
          to="/signin"
          className="inline-flex items-center gap-2 rounded-full border border-white/20 px-5 py-2 text-sm font-semibold transition hover:border-orange-300/70 hover:text-orange-200"
        >
          Sign in
          <ArrowRight size={16} />
        </Link>
      </header>

      <section className="relative z-10 grid min-h-[calc(100vh-84px)] grid-cols-1 items-center gap-10 px-5 pb-12 sm:px-8 lg:grid-cols-[0.92fr_1.08fr] lg:px-14">
        <div className="max-w-2xl">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-orange-300/30 bg-orange-300/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.22em] text-orange-200">
            <span className={`h-1.5 w-1.5 rounded-full ${powered ? "animate-pulse bg-orange-300" : "bg-white/35"}`} />
            {powered ? "Engine engaged" : "Standby mode"}
          </div>
          <h1 className="text-5xl font-black leading-[1.02] tracking-tight sm:text-6xl lg:text-7xl">
            The{" "}
            <span className="bg-gradient-to-r from-orange-300 via-rose-400 to-amber-200 bg-clip-text text-transparent">
              engine
            </span>
            <br />
            of your infra.
          </h1>
          <p className="mt-6 max-w-xl text-base leading-7 text-white/60 sm:text-lg">
            Tap the 3D core. Power on the ManageAI engine. Step into a secure control deck for identity,
            operations, automation, projects, hosting, monitoring, and AI assistance.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-5">
            <button
              type="button"
              onClick={handleToggle}
              disabled={transitioning}
              className={`group relative h-16 w-32 rounded-full border-2 transition-all duration-500 ${
                powered
                  ? "border-orange-300 bg-gradient-to-r from-orange-500 to-rose-600 shadow-[0_0_44px_rgba(255,90,34,0.62)]"
                  : "border-white/20 bg-white/[0.055]"
              }`}
              aria-label="Power engine"
            >
              <span
                className={`absolute top-1/2 grid h-12 w-12 -translate-y-1/2 place-items-center rounded-full bg-white text-lg shadow-xl transition-all duration-500 ${
                  powered ? "left-[calc(100%-3.25rem)] text-orange-600" : "left-1 text-slate-500"
                }`}
              >
                <Power size={22} />
              </span>
            </button>
            <div>
              <p className="text-sm font-black uppercase tracking-[0.22em]">{powered ? "Powering up" : "Engine off"}</p>
              <p className="mt-1 text-xs text-white/45">{transitioning ? "Routing to sign-in deck" : "Use the toggle or click the 3D core"}</p>
            </div>
          </div>

          <div className="mt-11 grid max-w-xl grid-cols-3 gap-3">
            {[
              { value: "99.99%", label: "Uptime" },
              { value: "2.4M", label: "Events/s" },
              { value: "180+", label: "Modules" }
            ].map((metric) => (
              <div key={metric.label} className="rounded-lg border border-white/10 bg-white/[0.045] p-4 backdrop-blur">
                <p className="bg-gradient-to-r from-orange-200 to-rose-300 bg-clip-text text-2xl font-black text-transparent">{metric.value}</p>
                <p className="mt-1 text-[10px] uppercase tracking-[0.2em] text-white/40">{metric.label}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="relative h-[460px] w-full sm:h-[560px] lg:h-[660px]">
          <div className={`absolute inset-0 transition duration-1000 ${transitioning ? "scale-150 opacity-0" : "scale-100 opacity-100"}`}>
            <Canvas camera={{ position: [0, 0, 6], fov: 50 }} dpr={[1, 2]}>
              <EngineScene powered={powered} onToggle={handleToggle} />
            </Canvas>
          </div>

          <div className="pointer-events-none absolute inset-0">
            <div className="absolute left-4 top-4 rounded-lg border border-white/10 bg-slate-950/45 px-3 py-2 text-[10px] uppercase tracking-[0.22em] text-orange-200/80 backdrop-blur">
              Core // ME-9
            </div>
            <div className="absolute right-4 top-4 rounded-lg border border-white/10 bg-slate-950/45 px-3 py-2 text-right text-[10px] uppercase tracking-[0.22em] text-orange-200/80 backdrop-blur">
              {powered ? "Online" : "Standby"}
            </div>
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full border border-white/10 bg-slate-950/45 px-4 py-2 text-[10px] uppercase tracking-[0.22em] text-white/42 backdrop-blur">
              drag to rotate / click core
            </div>
          </div>

          {transitioning && (
            <div className="absolute inset-0 grid place-items-center">
              <div className="text-center">
                <div className="mx-auto mb-4 h-16 w-16 animate-spin rounded-full border-4 border-orange-300 border-t-transparent" />
                <p className="text-sm font-bold uppercase tracking-[0.35em] text-orange-200">Entering deck</p>
              </div>
            </div>
          )}
        </div>
      </section>

      <section id="modules" className="relative z-10 border-y border-white/10 bg-white/[0.035] px-5 py-5 sm:px-8 lg:px-14">
        <div className="mx-auto grid max-w-7xl gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {modules.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.label} to="/signin" className="group flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.045] p-4 transition hover:border-orange-300/40 hover:bg-white/[0.075]">
                <span className="flex items-center gap-3 text-sm font-semibold text-white/72">
                  <Icon size={18} className="text-orange-200" />
                  {item.label}
                </span>
                <ArrowRight size={16} className="text-white/28 transition group-hover:translate-x-1 group-hover:text-orange-200" />
              </Link>
            );
          })}
        </div>
      </section>

      <section id="platform" className="relative z-10 px-5 py-16 sm:px-8 lg:px-14">
        <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.28em] text-orange-200">Control deck</p>
            <h2 className="mt-4 text-3xl font-black tracking-tight sm:text-5xl">One entry point for the whole operation.</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {["Face verification", "Admin approvals", "AI operations"].map((label) => (
              <div key={label} className="rounded-lg border border-white/10 bg-slate-950/45 p-5">
                <Box size={20} className="text-orange-200" />
                <p className="mt-4 text-sm font-bold">{label}</p>
                <p className="mt-2 text-xs leading-5 text-white/46">Ready after secure sign-in.</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <style>{`
        canvas {
          cursor: grab;
        }

        canvas:active {
          cursor: grabbing;
        }
      `}</style>
    </main>
  );
}
