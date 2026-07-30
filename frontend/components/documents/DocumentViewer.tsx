"use client";

import { useEffect, useState } from "react";
import { X, Download, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Document } from "@/types/document";

interface PresignedResponse {
  url: string;
  expires_in: number;
}

type ViewClass = "pdf" | "image" | "other";

function viewClass(mime: string | null): ViewClass {
  if (!mime) return "other";
  if (mime === "application/pdf") return "pdf";
  if (mime.startsWith("image/")) return "image";
  return "other";
}

interface DocumentViewerProps {
  doc: Document;
  onClose: () => void;
  onDownload: (doc: Document) => void;
}

export function DocumentViewer({ doc, onClose, onDownload }: DocumentViewerProps) {
  const cls = viewClass(doc.mime_type);
  const name = doc.display_name ?? doc.filename;

  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Non-viewable types: fall through to download immediately
  useEffect(() => {
    if (cls === "other") {
      onDownload(doc);
      onClose();
      return;
    }
    api
      .get<PresignedResponse>(`/documents/${doc.id}/view`)
      .then((r) => setUrl(r.url))
      .catch(() => setError("Could not load file preview."))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  if (cls === "other") return null;

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col"
      style={{ backgroundColor: "rgba(0,0,0,0.88)" }}
      onClick={onClose}
    >
      {/* Header */}
      <div
        className="flex shrink-0 items-center justify-between gap-4 border-b px-5 py-3"
        style={{
          backgroundColor: "var(--bg-primary)",
          borderColor: "var(--border-default)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <p
          className="truncate text-sm font-medium"
          style={{ color: "var(--text-primary)" }}
          title={name}
        >
          {name}
        </p>
        <div className="flex shrink-0 items-center gap-1">
          <button
            onClick={() => onDownload(doc)}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors hover:bg-[var(--bg-tertiary)]"
            style={{ color: "var(--text-secondary)" }}
          >
            <Download size={13} />
            Download
          </button>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 transition-colors hover:bg-[var(--bg-tertiary)]"
            style={{ color: "var(--text-secondary)" }}
            aria-label="Close viewer"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Content area */}
      <div
        className="flex flex-1 items-center justify-center overflow-hidden p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {loading && (
          <Loader2
            size={32}
            className="animate-spin"
            style={{ color: "rgba(255,255,255,0.5)" }}
          />
        )}

        {error && (
          <p className="text-sm" style={{ color: "rgba(255,255,255,0.6)" }}>
            {error}
          </p>
        )}

        {url && cls === "pdf" && (
          <iframe
            src={url}
            title={name}
            className="h-full w-full rounded-lg"
            style={{ border: "none", maxWidth: "960px" }}
          />
        )}

        {url && cls === "image" && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={url}
            alt={name}
            className="max-h-full max-w-full rounded-lg object-contain shadow-2xl"
          />
        )}
      </div>
    </div>
  );
}
