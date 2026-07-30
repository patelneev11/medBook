"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { X, ChevronDown } from "lucide-react";
import { FileUpload } from "./FileUpload";
import { useUpload } from "@/context/UploadContext";
import { useToast } from "@/context/ToastContext";
import type { Document } from "@/types/document";

// Placeholder project list — replace with a real API call in Session 5
interface Project {
  id: string;
  name: string;
}
const MOCK_PROJECTS: Project[] = [];

// ─── Shell ────────────────────────────────────────────────────────────────────
// Always in the DOM tree — owns scroll-lock and Escape-key global effects.
// Conditionally renders UploadModalContent so that the content's state is
// genuinely reset on every open (real unmount → remount, no setState-in-effect).

export function UploadModal() {
  const { isOpen, closeUpload } = useUpload();

  // Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeUpload();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, closeUpload]);

  // Body scroll lock
  useEffect(() => {
    document.body.style.overflow = isOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return <UploadModalContent />;
}

// ─── Content ──────────────────────────────────────────────────────────────────
// Mounts fresh every time the modal opens — local state initialises from
// props once on mount, so no state-in-effect sync is needed.

function UploadModalContent() {
  const { initialProjectId, closeUpload, notifyDocumentUploaded } = useUpload();
  const { toast } = useToast();
  const router = useRouter();

  const [projectId, setProjectId] = useState<string | undefined>(initialProjectId);
  const [hasCompleted, setHasCompleted] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);

  const handleSuccess = useCallback(
    (doc: Document) => {
      setHasCompleted(true);
      notifyDocumentUploaded();
      const name = doc.display_name ?? doc.filename;
      toast.success("Document uploaded", `${name} is being processed`);
    },
    [notifyDocumentUploaded, toast]
  );

  const handleError = useCallback(
    (_filename: string, message: string) => {
      toast.error("Upload failed", message);
    },
    [toast]
  );

  const handleOverlayClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.target === overlayRef.current) closeUpload();
    },
    [closeUpload]
  );

  const handleViewDocuments = useCallback(() => {
    closeUpload();
    router.push("/dashboard/documents");
  }, [closeUpload, router]);

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.5)" }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
    >
      <div
        className="flex w-full max-w-[560px] flex-col rounded-2xl shadow-xl"
        style={{ backgroundColor: "var(--bg-primary)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between border-b px-6 py-4"
          style={{ borderColor: "var(--border-default)" }}
        >
          <h2
            id="upload-modal-title"
            className="text-base font-semibold"
            style={{ color: "var(--text-primary)" }}
          >
            Upload documents
          </h2>
          <button
            onClick={closeUpload}
            aria-label="Close"
            className="rounded-lg p-1.5 transition-colors hover:bg-[var(--bg-tertiary)]"
            style={{ color: "var(--text-secondary)" }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto px-6 py-5 space-y-5" style={{ maxHeight: "70vh" }}>
          {/* Project selector */}
          {MOCK_PROJECTS.length > 0 && (
            <div className="space-y-1.5">
              <label
                className="text-xs font-medium"
                style={{ color: "var(--text-secondary)" }}
              >
                Add to project
              </label>
              <div className="relative">
                <select
                  value={projectId ?? ""}
                  onChange={(e) => setProjectId(e.target.value || undefined)}
                  className="w-full appearance-none rounded-lg border px-3 py-2 pr-8 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand-primary"
                  style={{
                    backgroundColor: "var(--bg-secondary)",
                    borderColor: "var(--border-default)",
                    color: "var(--text-primary)",
                  }}
                >
                  <option value="">No project</option>
                  {MOCK_PROJECTS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <ChevronDown
                  size={14}
                  className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2"
                  style={{ color: "var(--text-tertiary)" }}
                />
              </div>
            </div>
          )}

          <FileUpload projectId={projectId} onSuccess={handleSuccess} onError={handleError} />
        </div>

        {/* Footer */}
        {hasCompleted && (
          <div
            className="flex items-center justify-end border-t px-6 py-4"
            style={{ borderColor: "var(--border-default)" }}
          >
            <button
              onClick={handleViewDocuments}
              className="rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors hover:opacity-90"
              style={{ backgroundColor: "var(--brand-primary)" }}
            >
              View documents
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
