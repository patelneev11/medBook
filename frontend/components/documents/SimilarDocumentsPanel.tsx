"use client";

import { useEffect, useState } from "react";
import { X, Sparkles } from "lucide-react";
import { classifyMime, FILE_STYLES } from "@/lib/documentDisplay";
import { findSimilarDocuments } from "@/lib/search";
import { Spinner } from "@/components/ui/Spinner";
import type { SimilarDocumentItem } from "@/types/search";

interface SimilarDocumentsPanelProps {
  documentId: string;
  documentName: string;
  onClose: () => void;
}

export function SimilarDocumentsPanel({ documentId, documentName, onClose }: SimilarDocumentsPanelProps) {
  const [items, setItems] = useState<SimilarDocumentItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [slidIn, setSlidIn] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setSlidIn(true));
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    let cancelled = false;
    findSimilarDocuments(documentId)
      .then((res) => { if (!cancelled) setItems(res.documents); })
      .catch(() => { if (!cancelled) setError("Could not load similar documents."); });
    return () => { cancelled = true; };
  }, [documentId]);

  useEffect(() => {
    const handler = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="similar-documents-title"
    >
      <div
        className={`flex h-full w-full max-w-md flex-col shadow-xl transition-transform duration-200 ease-out ${
          slidIn ? "translate-x-0" : "translate-x-full"
        }`}
        style={{ backgroundColor: "var(--bg-primary)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex shrink-0 items-center justify-between gap-3 border-b px-5 py-4"
          style={{ borderColor: "var(--border-default)" }}
        >
          <div className="min-w-0">
            <p id="similar-documents-title" className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Similar documents
            </p>
            <p className="truncate text-xs" style={{ color: "var(--text-tertiary)" }} title={documentName}>
              Based on {documentName}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="shrink-0 rounded-lg p-1.5 transition-colors hover:bg-[var(--bg-tertiary)]"
            style={{ color: "var(--text-secondary)" }}
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {items === null && !error && (
            <div className="flex items-center justify-center py-16">
              <Spinner size="md" />
            </div>
          )}

          {error && (
            <p className="py-16 text-center text-sm" style={{ color: "var(--text-tertiary)" }}>{error}</p>
          )}

          {items !== null && items.length === 0 && !error && (
            <div className="py-16 text-center">
              <Sparkles size={24} className="mx-auto mb-2" style={{ color: "var(--text-tertiary)" }} />
              <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
                No similar documents found yet — this document may not be indexed, or nothing else in your library is closely related.
              </p>
            </div>
          )}

          {items !== null && items.length > 0 && (
            <div className="flex flex-col gap-2.5">
              {items.map((item) => {
                const cls = classifyMime(item.mime_type);
                const { icon: Icon, bg, color } = FILE_STYLES[cls];
                return (
                  <div
                    key={item.document_id}
                    className="flex items-center gap-3 rounded-lg border p-3"
                    style={{ borderColor: "var(--border-default)" }}
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" style={{ backgroundColor: bg }}>
                      <Icon size={16} style={{ color }} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium" style={{ color: "var(--text-primary)" }} title={item.document_name}>
                        {item.document_name}
                      </p>
                      <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.max(4, Math.min(100, Math.round(item.similarity_score * 100)))}%`,
                            backgroundColor: "var(--brand-primary)",
                          }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}