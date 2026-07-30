"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { ToastContainer, type ToastData, type ToastVariant } from "@/components/ui/Toast";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ToastHelpers {
  success: (title: string, description?: string) => void;
  error:   (title: string, description?: string) => void;
  info:    (title: string, description?: string) => void;
  warning: (title: string, description?: string) => void;
}

interface ToastContextValue {
  showToast: (title: string, description?: string, variant?: ToastVariant) => void;
  dismiss:   (id: string) => void;
  toast:     ToastHelpers;
}

const MAX_TOASTS = 4;

// ─── Context ──────────────────────────────────────────────────────────────────

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

// ─── Provider ─────────────────────────────────────────────────────────────────

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (title: string, description?: string, variant: ToastVariant = "info") => {
      const id = crypto.randomUUID();
      setToasts((prev) => {
        const next = [...prev, { id, title, description, variant }];
        // Drop oldest when over the cap
        return next.length > MAX_TOASTS ? next.slice(next.length - MAX_TOASTS) : next;
      });
    },
    []
  );

  // Listen for session-expired events dispatched by the API client
  useEffect(() => {
    const handler = () => {
      showToast("Session expired", "Please sign in again", "warning");
    };
    window.addEventListener("mednotebook:session-expired", handler);
    return () => window.removeEventListener("mednotebook:session-expired", handler);
  }, [showToast]);

  const toast = useMemo<ToastHelpers>(
    () => ({
      success: (title, description) => showToast(title, description, "success"),
      error:   (title, description) => showToast(title, description, "error"),
      info:    (title, description) => showToast(title, description, "info"),
      warning: (title, description) => showToast(title, description, "warning"),
    }),
    [showToast]
  );

  const value = useMemo<ToastContextValue>(
    () => ({ showToast, dismiss, toast }),
    [showToast, dismiss, toast]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}
