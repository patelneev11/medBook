"use client";

import { useState } from "react";
import { Sparkles, Send, BookOpen } from "lucide-react";

const EXAMPLE_QUESTIONS = [
  "Summarize my most recent upload",
  "What are the key findings in Project Alpha?",
  "Compare results across my CSV files",
];

const HAS_DOCUMENTS = false;

export default function AskAIPage() {
  const [input, setInput] = useState("");
  const canSend = HAS_DOCUMENTS && input.trim().length > 0;

  return (
    <div className="flex flex-col gap-6 lg:flex-row lg:h-[calc(100dvh-56px-48px)]">

      {/* ── Left: Chat ── */}
      <div className="flex w-full min-h-0 flex-col gap-3 lg:w-[60%]">

        {/* Notice */}
        <div
          className="shrink-0 rounded-lg border px-4 py-2 text-xs"
          style={{ backgroundColor: "var(--brand-secondary)", borderColor: "var(--brand-primary)", color: "var(--brand-primary)", opacity: 0.9 }}
        >
          Answers are based on your uploaded documents only
        </div>

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
              placeholder="Ask a question about your documents…"
              className="flex-1 rounded-lg border px-4 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand-primary/15 focus:border-brand-primary"
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
              {!HAS_DOCUMENTS && (
                <div
                  className="pointer-events-none absolute bottom-full right-0 mb-2 hidden whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs text-white group-hover:block"
                  style={{ backgroundColor: "var(--text-primary)" }}
                >
                  Upload documents first
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
