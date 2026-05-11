import { motion } from "framer-motion";

export default function Page({ title, subtitle, actions, children }) {
  const hasHeader = Boolean(title || subtitle || actions);

  return (
    <motion.section initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>
      {hasHeader && (
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            {title && <h1 className="text-2xl font-semibold text-white">{title}</h1>}
            {subtitle && <p className="mt-1 max-w-3xl text-sm text-slate-400">{subtitle}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </motion.section>
  );
}
