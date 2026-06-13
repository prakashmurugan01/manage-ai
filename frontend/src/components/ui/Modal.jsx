import { X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

import Button from "./Button.jsx";

export default function Modal({ open, title, children, onClose, size = "default" }) {
  const sizes = {
    compact: "max-w-2xl",
    default: "max-w-4xl",
    wide: "max-w-[min(1440px,calc(100vw-2rem))]"
  };
  const wideChrome = size === "wide" ? "theme-modal" : "";

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2, ease: "easeInOut" }}
          className="theme-modal-backdrop fixed inset-0 z-50 grid place-items-center px-4"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 10 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className={`panel flex max-h-[88vh] w-full ${sizes[size] || sizes.default} ${wideChrome} flex-col overflow-hidden p-0`}
          >
            <div className="flex items-center justify-between gap-4 border-b border-[color:var(--border-color)] p-5">
              <h2 className="text-lg font-semibold text-[color:var(--text-primary)]">{title}</h2>
              <Button variant="ghost" onClick={onClose} aria-label="Close">
                <X size={18} />
              </Button>
            </div>
            <div className="min-h-0 overflow-y-auto p-5">
              {children}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
