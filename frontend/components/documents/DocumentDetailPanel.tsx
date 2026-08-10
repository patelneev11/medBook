"use client";

import { useEffect, useState } from "react";
import type { ElementType, KeyboardEvent } from "react";
import { useRouter } from "next/navigation";
import {
  X,
  Calendar,
  HardDrive,
  User,
  Send,
  Clock,
  Loader2,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { api } from "@/lib/api";
import { classifyMime, FILE_STYLES, formatBytes, formatDate, formatNumber } from "@/lib/documentDisplay";
import { Spinner } from "@/components/ui/Spinner";
import type { Chunk, Document, DocumentDetail } from "@/types/document";

type Tab = "overview" | "chunks" | "ask";

// Matches _TEXT_PREVIEW_CHARS in backend/mednotebook_backend/routers/documents.py
const TEXT_PREVIEW_CHARS = 500;

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "chunks", label: "Chunks" },
  { key: "ask", label: "Ask AI" },
];

interface DocumentDetailPanelProps {
  doc: Document;
  onClose: () => void;
}

export function DocumentDetailPanel({ doc, onClose }: DocumentDetailPanelProps) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("overview");

  // No animation plugin in this project's Tailwind setup — slide the panel
  // in manually: mount off-screen, then flip to translate-x-0 next frame so
  // the transition actually has a "from" state to animate away from.
  const [slidIn, setSlidIn] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setSlidIn(true));
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setDetail(null);
    setTab("overview");
    api
      .get<DocumentDetail>(`/documents/${doc.id}`)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [doc.id]);

  useEffect(() => {
    const handler = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const name = doc.display_name ?? doc.filename;
  const cls = classifyMime(doc.mime_type);
  const { icon: Icon, bg, color } = FILE_STYLES[cls];

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="document-detail-title"
    >
      <div
        className={`flex h-full w-full max-w-md flex-col shadow-xl transition-transform duration-200 ease-out ${
          slidIn ? "translate-x-0" : "translate-x-full"
        }`}
        style={{ backgroundColor: "var(--bg-primary)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex shrink-0 items-center justify-between gap-3 border-b px-5 py-4"
          style={{ borderColor: "var(--border-default)" }}
        >
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" style={{ backgroundColor: bg }}>
              <Icon size={18} style={{ color }} />
            </div>
            <p
              id="document-detail-title"
              className="truncate text-sm font-semibold"
              style={{ color: "var(--text-primary)" }}
              title={name}
            >
              {name}
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

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading && (
            <div className="flex items-center justify-center py-16">
              <Spinner size="md" />
            </div>
          )}
          {!loading && !detail && (
            <p className="py-16 text-center text-sm" style={{ color: "var(--text-tertiary)" }}>
              Could not load document details.
            </p>
          )}
          {!loading && detail && tab === "overview" && <OverviewTab doc={detail} />}
          {!loading && detail && tab === "chunks" && <ChunksTab documentId={detail.id} />}
          {!loading && detail && tab === "ask" && <AskTab doc={detail} />}
        </div>

        {/* Tabs */}
        <div className="flex shrink-0 border-t" style={{ borderColor: "var(--border-default)" }}>
          {TABS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className="flex-1 py-3 text-sm font-medium transition-colors"
              style={{
                color: tab === key ? "var(--brand-primary)" : "var(--text-secondary)",
                borderTop: tab === key ? "2px solid var(--brand-primary)" : "2px solid transparent",
                marginTop: "-1px",
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Overview ───────────────────────────────────────────────────────────────

function OverviewTab({ doc }: { doc: DocumentDetail }) {
  return (
    <div className="space-y-5">
      <div className="space-y-2.5 text-sm">
        <MetaRow icon={Calendar} label="Uploaded" value={new Date(doc.created_at).toLocaleString()} />
        <MetaRow icon={HardDrive} label="File size" value={formatBytes(doc.file_size_bytes)} />
        <MetaRow icon={User} label="Uploaded by" value={doc.uploaded_by_name ?? "Unknown"} />
      </div>

      <div className="rounded-lg border p-3" style={{ borderColor: "var(--border-default)", backgroundColor: "var(--bg-secondary)" }}>
        <StatusDetail doc={doc} />
      </div>

      {doc.status === "ready" && (
        <div className="grid grid-cols-2 gap-3">
          <Stat label="Words" value={formatNumber(doc.word_count)} />
          <Stat label="Pages" value={formatNumber(doc.page_count)} />
          <Stat label="Chunks" value={formatNumber(doc.chunk_count)} />
          <Stat label="Extraction" value={doc.extraction_method ?? "—"} />
        </div>
      )}

      {doc.status === "ready" && doc.extracted_text_preview && (
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
            Preview
          </p>
          <div className="relative max-h-40 overflow-hidden rounded-lg border p-3" style={{ borderColor: "var(--border-default)" }}>
            <p className="whitespace-pre-wrap text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              {doc.extracted_text_preview}
              {/* The backend truncates at exactly this many chars — only imply
                  "there's more" when the preview actually hit that limit. */}
              {doc.extracted_text_preview.length >= TEXT_PREVIEW_CHARS && "…"}
            </p>
            <div
              className="pointer-events-none absolute inset-x-0 bottom-0 h-10"
              style={{ background: "linear-gradient(to bottom, transparent, var(--bg-primary))" }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function StatusDetail({ doc }: { doc: DocumentDetail }) {
  if (doc.status === "pending") {
    return <DetailRow icon={Clock} color="var(--text-secondary)" title="Waiting to process" subtitle="Queued for extraction" />;
  }
  if (doc.status === "processing") {
    return (
      <DetailRow
        icon={Loader2}
        spin
        color="#2563EB"
        title="Extracting text…"
        subtitle={doc.processing_started_at ? `Started ${formatDate(doc.processing_started_at)}` : undefined}
      />
    );
  }
  if (doc.status === "ready") {
    return (
      <DetailRow
        icon={CheckCircle2}
        color="var(--brand-primary)"
        title="Ready"
        subtitle={doc.processing_completed_at ? `Completed ${formatDate(doc.processing_completed_at)}` : undefined}
      />
    );
  }
  return (
    <div className="flex items-start gap-2.5">
      <AlertTriangle size={16} style={{ color: "var(--error)" }} className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        <p className="text-sm font-medium" style={{ color: "var(--error)" }}>Failed to process</p>
        {doc.error_message && (
          <p className="mt-0.5 text-xs" style={{ color: "var(--text-tertiary)" }}>{doc.error_message}</p>
        )}
      </div>
    </div>
  );
}

function MetaRow({ icon: Icon, label, value }: { icon: ElementType; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <Icon size={14} style={{ color: "var(--text-tertiary)" }} />
      <span style={{ color: "var(--text-tertiary)" }}>{label}</span>
      <span className="ml-auto truncate text-right" style={{ color: "var(--text-primary)" }}>{value}</span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-2.5" style={{ borderColor: "var(--border-default)" }}>
      <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{label}</p>
      <p className="truncate text-sm font-semibold" style={{ color: "var(--text-primary)" }} title={value}>{value}</p>
    </div>
  );
}

function DetailRow({
  icon: Icon,
  color,
  title,
  subtitle,
  spin,
}: {
  icon: ElementType;
  color: string;
  title: string;
  subtitle?: string;
  spin?: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <Icon size={16} style={{ color }} className={spin ? "animate-spin" : ""} />
      <div>
        <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{title}</p>
        {subtitle && <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{subtitle}</p>}
      </div>
    </div>
  );
}

// ─── Chunks ─────────────────────────────────────────────────────────────────

function ChunksTab({ documentId }: { documentId: string }) {
  const [chunks, setChunks] = useState<Chunk[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setChunks(null);
    setError(null);
    api
      .get<Chunk[]>(`/documents/${documentId}/chunks?limit=10`)
      .then((data) => { if (!cancelled) setChunks(data); })
      .catch(() => { if (!cancelled) setError("Could not load chunks."); });
    return () => { cancelled = true; };
  }, [documentId]);

  if (error) return <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>{error}</p>;
  if (!chunks) return <div className="flex justify-center py-10"><Spinner size="md" /></div>;
  if (chunks.length === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
        No chunks yet — this document may still be processing.
      </p>
    );
  }

  return (
    <div className="space-y-2.5">
      {chunks.map((chunk) => (
        <div key={chunk.id} className="rounded-lg border p-3" style={{ borderColor: "var(--border-default)" }}>
          <div className="mb-1.5 flex items-center justify-between text-xs" style={{ color: "var(--text-tertiary)" }}>
            <span>Chunk {chunk.chunk_index}</span>
            <span>
              {chunk.token_count ?? "—"} tokens{chunk.page_number ? ` · p.${chunk.page_number}` : ""}
            </span>
          </div>
          <p
            className="text-xs leading-relaxed"
            style={{
              color: "var(--text-secondary)",
              display: "-webkit-box",
              WebkitLineClamp: 3,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {chunk.content}
          </p>
        </div>
      ))}
    </div>
  );
}

// ─── Ask AI ─────────────────────────────────────────────────────────────────

function AskTab({ doc }: { doc: DocumentDetail }) {
  const router = useRouter();
  const [input, setInput] = useState("");
  const name = doc.display_name ?? doc.filename;

  const handleGo = () => {
    const params = new URLSearchParams({ document_id: doc.id, document_name: name });
    if (input.trim()) params.set("q", input.trim());
    router.push(`/dashboard/ask?${params.toString()}`);
  };

  return (
    <div className="space-y-3">
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
        Ask a question with <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{name}</span> in context.
      </p>
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => { if (e.key === "Enter") handleGo(); }}
          placeholder="Ask about this document…"
          className="flex-1 rounded-lg border px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand-primary/15 focus:border-brand-primary"
          style={{ backgroundColor: "var(--bg-secondary)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
        />
        <button
          onClick={handleGo}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-primary text-white transition-colors hover:bg-brand-hover"
          aria-label="Go to Ask AI"
        >
          <Send size={14} />
        </button>
      </div>
      <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
        Opens the Ask AI page with this document pre-selected.
      </p>
    </div>
  );
}