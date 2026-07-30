"use client";

import { useEffect } from "react";
import { CheckCircle2, XCircle, Info, AlertTriangle, X } from "lucide-react";

export type ToastVariant = "success" | "error" | "info" | "warning";

export interface ToastData {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
}

// ─── Variant config ───────────────────────────────────────────────────────────

const VARIANT_CONFIG: Record<
  ToastVariant,
  { border: string; iconColor: string; Icon: React.ElementType }
> = {
  success: { border: "#16A34A", iconColor: "#16A34A", Icon: CheckCircle2 },
  error:   { border: "#DC2626", iconColor: "#DC2626", Icon: XCircle },
  info:    { border: "#2563EB", iconColor: "#2563EB", Icon: Info },
  warning: { border: "#D97706", iconColor: "#D97706", Icon: AlertTriangle },
};

// ─── Single toast ─────────────────────────────────────────────────────────────

function Toast({
  toast,
  onDismiss,
}: {
  toast: ToastData;
  onDismiss: (id: string) => void;
}) {
  const { border, iconColor, Icon } = VARIANT_CONFIG[toast.variant];

  useEffect(() => {
    const t = setTimeout(() => onDismiss(toast.id), 4000);
    return () => clearTimeout(t);
  }, [toast.id, onDismiss]);

  return (
    <div
      className="flex w-full max-w-sm items-start gap-3 rounded-lg border px-4 py-3 shadow-lg"
      style={{
        backgroundColor: "var(--bg-primary)",
        borderColor: "var(--border-default)",
        borderLeftColor: border,
        borderLeftWidth: "3px",
        color: "var(--text-primary)",
        animation: "toast-slide-in 0.22s ease-out forwards",
      }}
      role="status"
      aria-live="polite"
    >
      <Icon
        size={16}
        style={{ color: iconColor, flexShrink: 0, marginTop: "1px" }}
        aria-hidden="true"
      />

      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium leading-snug" style={{ color: "var(--text-primary)" }}>
          {toast.title}
        </p>
        {toast.description && (
          <p className="mt-0.5 text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            {toast.description}
          </p>
        )}
      </div>

      <button
        onClick={() => onDismiss(toast.id)}
        className="shrink-0 rounded p-0.5 transition-opacity hover:opacity-60"
        style={{ color: "var(--text-tertiary)" }}
        aria-label="Dismiss notification"
      >
        <X size={13} />
      </button>
    </div>
  );
}

// ─── Container ────────────────────────────────────────────────────────────────

export function ToastContainer({
  toasts,
  onDismiss,
}: {
  toasts: ToastData[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) return null;

  return (
    <>
      <style>{`
        @keyframes toast-slide-in {
          from { transform: translateX(calc(100% + 1rem)); opacity: 0; }
          to   { transform: translateX(0);                 opacity: 1; }
        }
      `}</style>
      <div
        className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2"
        aria-label="Notifications"
      >
        {toasts.map((t) => (
          <Toast key={t.id} toast={t} onDismiss={onDismiss} />
        ))}
      </div>
    </>
  );
}
