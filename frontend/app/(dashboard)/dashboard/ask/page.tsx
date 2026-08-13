"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Sparkles, Send, BookOpen, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Document } from "@/types/document";

const EXAMPLE_QUESTIONS = [
  "Summarize my most recent upload",
  "What are the key findings in Project Alpha?",
  "Compare results across my CSV files",
];

const POLL_INTERVAL_MS = 5000;
// Large enough to cover realistic usage without building full pagination
// for what's just a readiness count — see backend's per_page cap (100).
const DOCUMENT_FETCH_LIMIT = 100;

export default function AskAIPage() {
  return (
    <Suspense fallback={null}>
      <AskAIPageContent />
    </Suspense>
  );
}

function AskAIPageContent() {
  const searchParams = useSearchParams();
  // Pre-filled when arriving from a document's detail panel — the actual
  // AI wiring (using document_id as context) is Session 7; for now this
  // just carries the question text and which document prompted it.
  const [input, setInput] = useState(() => searchParams.get("q") ?? "");
  const documentName = searchParams.get("document_name");

  const [documents, setDocuments] = useState<Document[] | null>(null);

  useEffect(() => {
    let active = true;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    const fetchDocuments = async () => {
      try {
        const docs = await api.get<Document[]>(`/documents?per_page=${DOCUMENT_FETCH_LIMIT}`);
        if (!active) return;
        setDocuments(docs);

        // Keep polling while there are documents but none are indexed yet,
        // so this banner clears on its own once one finishes — same spirit
        // as the per-card status polling, just for the aggregate count.
        const indexedCount = docs.filter((d) => d.status === "indexed").length;
        if (docs.length > 0 && indexedCount === 0) {
          timeoutId = setTimeout(fetchDocuments, POLL_INTERVAL_MS);
        }
      } catch {
        if (active) setDocuments((prev) => prev ?? []);
      }
    };

    fetchDocuments();
    return () => {
      active = false;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, []);

  const totalCount = documents?.length ?? 0;
  const indexedCount = documents?.filter((d) => d.status === "indexed").length ?? 0;
  const stillIndexing = totalCount > 0 && indexedCount === 0;
  const canSend = indexedCount > 0 && input.trim().length > 0;

  const disabledReason = totalCount === 0 ? "Upload documents first" : stillIndexing ? "Documents still indexing" : null;

  return (
    <div className="flex flex-col gap-6 lg:flex-row lg:h-[calc(100dvh-56px-48px)]">

      {/* ── Left: Chat ── */}
      <div className="flex w-full min-h-0 flex-col gap-3 lg:w-[60%]">

        {/* Notice */}
        <div
          className="shrink-0 rounded-lg border px-4 py-2 text-xs"
          style={{ backgroundColor: "var(--brand-secondary)", borderColor: "var(--brand-primary)", color: "var(--brand-primary)", opacity: 0.9 }}
        >
          {documentName
            ? `Asking about "${documentName}" — answers are based on your uploaded documents only`
            : "Answers are based on your uploaded documents only"}
        </div>

        {/* Indexing status */}
        {stillIndexing && (
          <div
            className="flex shrink-0 items-center gap-2.5 rounded-lg border px-4 py-2.5"
            style={{ backgroundColor: "#F5F3FF", borderColor: "#7C3AED" }}
          >
            <Loader2 size={15} className="shrink-0 animate-spin" style={{ color: "#7C3AED" }} />
            <p className="text-xs" style={{ color: "#7C3AED" }}>
              Your documents are still being indexed. This usually takes 1-2 minutes.
            </p>
          </div>
        )}
        {totalCount > 0 && (
          <p className="shrink-0 px-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
            {indexedCount} of {totalCount} document{totalCount === 1 ? "" : "s"} ready for AI queries
          </p>
        )}

        {/* Messages */}
        <div
          className="h-80 overflow-y-auto rounded-xl border lg:flex-1"
          style={{ backgroundColor: "var(--bg-secondary)", borderColor: "var(--border-default)" }}
        >
          <div className="flex h-full flex-col items-center justify-center p-8 text-center">
            <div
              className="flex h-12 w-12 items-center justify-center rounded-full"
              style={{ backgroundColor: "var(--brand-secondary)" }}
            >
              <Sparkles size={22} style={{ color: "var(--brand-primary)" }} />
            </div>
            <p className="mt-3 text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              Ask anything about your documents
            </p>
            <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
              Your answers will include citations back to the source.
            </p>

            {/* Example pills */}
            <div className="mt-6 flex w-full max-w-sm flex-col gap-2">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => setInput(q)}
                  className="rounded-full border px-4 py-2 text-left text-sm transition-colors"
                  style={{ borderColor: "var(--border-default)", backgroundColor: "var(--bg-primary)", color: "var(--text-secondary)" }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLElement).style.backgroundColor = "var(--brand-secondary)";
                    (e.currentTarget as HTMLElement).style.color = "var(--brand-primary)";
                    (e.currentTarget as HTMLElement).style.borderColor = "var(--brand-primary)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.backgroundColor = "var(--bg-primary)";
                    (e.currentTarget as HTMLElement).style.color = "var(--text-secondary)";
                    (e.currentTarget as HTMLElement).style.borderColor = "var(--border-default)";
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Input */}
        <div className="shrink-0 space-y-1.5">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={indexedCount === 0}
              placeholder="Ask a question about your documents…"
              className="flex-1 rounded-lg border px-4 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand-primary/15 focus:border-brand-primary disabled:cursor-not-allowed disabled:opacity-60"
              style={{
                backgroundColor: "var(--bg-secondary)",
                borderColor: "var(--border-default)",
                color: "var(--text-primary)",
              }}
            />
            <div className="group relative">
              <button
                disabled={!canSend}
                className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-primary text-white transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-40"
              >
                <Send size={15} />
              </button>
              {disabledReason && (
                <div
                  className="pointer-events-none absolute bottom-full right-0 mb-2 hidden whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs text-white group-hover:block"
                  style={{ backgroundColor: "var(--text-primary)" }}
                >
                  {disabledReason}
                </div>
              )}
            </div>
          </div>
          <p className="px-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
            AI responses include source citations
          </p>
        </div>
      </div>

      {/* ── Right: Sources ── */}
      <div className="flex w-full min-h-0 flex-col gap-3 lg:w-[40%]">
        <h2 className="shrink-0 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Sources
        </h2>
        <div
          className="flex flex-1 flex-col items-center justify-center rounded-xl border p-8 text-center"
          style={{ backgroundColor: "var(--bg-secondary)", borderColor: "var(--border-default)" }}
        >
          <div
            className="flex h-12 w-12 items-center justify-center rounded-full"
            style={{ backgroundColor: "var(--bg-tertiary)" }}
          >
            <BookOpen size={22} style={{ color: "var(--text-tertiary)" }} />
          </div>
          <p className="mt-3 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            No sources yet
          </p>
          <p className="mt-1.5 max-w-xs text-xs" style={{ color: "var(--text-tertiary)" }}>
            Sources from your documents will appear here when you ask a question
          </p>
        </div>
      </div>

    </div>
  );
}