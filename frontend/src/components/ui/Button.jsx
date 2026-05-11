export default function Button({ children, variant = "primary", className = "", ...props }) {
  const variants = {
    primary: "bg-[color:var(--accent)] text-white shadow-sm hover:brightness-110",
    secondary: "border border-white/10 bg-white/10 text-slate-100 hover:bg-white/15",
    danger: "bg-rose-500 text-white hover:bg-rose-400",
    ghost: "bg-transparent text-slate-300 hover:bg-white/10"
  };

  return (
    <button
      type="button"
      className={`btn-${variant} inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
