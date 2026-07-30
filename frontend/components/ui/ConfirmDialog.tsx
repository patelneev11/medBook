"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "./Button";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirm",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.5)" }}
      onClick={onCancel}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-sm rounded-2xl p-6 shadow-xl"
        style={{ backgroundColor: "var(--bg-primary)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-4">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
            style={{ backgroundColor: "#FEF2F2" }}
          >
            <AlertTriangle size={18} style={{ color: "var(--error)" }} />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              {title}
            </p>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              {message}
            </p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-3">
          <Button label="Cancel" variant="secondary" onClick={onCancel} />
          <Button label={confirmLabel} variant="danger" onClick={onConfirm} />
        </div>
      </div>
    </div>
  );
}
