"use client";

import { useState } from "react";
import type { MouseEvent } from "react";
import {
  MoreHorizontal,
  Eye,
  Download,
  Sparkles,
  FolderInput,
  Trash2,
  Clock,
  Loader2,
  AlertTriangle,
  RotateCcw,
  Layers,
} from "lucide-react";
import { useToast } from "@/context/ToastContext";
import { api } from "@/lib/api";
import { classifyMime, FILE_STYLES, formatBytes, formatDate, formatNumber } from "@/lib/documentDisplay";
import { useDocumentStatus } from "@/hooks/useDocumentStatus";
import { SimilarDocumentsPanel } from "@/components/documents/SimilarDocumentsPanel";
import type { Document, DocumentStatusValue, EmbeddingStatusValue } from "@/types/document";

const ERROR_MESSAGE_MAX_LEN = 70;

interface DocumentCardProps {
  doc: Document;
  menuOpenId: string | null;
  onMenuToggle: (id: string) => void;
  onView: (doc: Document) => void;
  onDownload: (doc: Document) => void;
  onDeleteRequest: (doc: Document) => void;
  onOpenDetail: (doc: Document) => void;
  onDocumentUpdate: (id: string, patch: Partial<Document>) => void;
}

export function DocumentCard({
  doc,
  menuOpenId,
  onMenuToggle,
  onView,
  onDownload,
  onDeleteRequest,
  onOpenDetail,
  onDocumentUpdate,
}: DocumentCardProps) {
  const { toast } = useToast();
  const [retrying, setRetrying] = useState(false);
  const [showSimilar, setShowSimilar] = useState(false);

  const cls = classifyMime(doc.mime_type);
  const { icon: Icon, bg, color } = FILE_STYLES[cls];
  const name = doc.display_name ?? doc.filename;
  const menuOpen = menuOpenId === doc.id;
  const isViewable = cls === "pdf" || cls === "image";

  const poll = useDocumentStatus(doc.id, doc.status, doc.embedding_status, {
    onUpdate: (p) => {
      onDocumentUpdate(doc.id, {
        status: p.status,
        embedding_status: p.embedding_status,
        word_count: p.word_count,
        page_count: p.page_count,
        chunk_count: p.chunk_count,
        error_message: p.error_message,
      });
    },
    onReady: () => {
      toast.success(`${name} is fully indexed`, "Ask AI anything about it");
    },
    onError: (p) => {
      if (p.status === "ready") {
        toast.error(`${name} couldn't be indexed`, "Text was extracted, but embedding failed. You can retry.");
      } else {
        toast.error(`${name} failed to process`, p.error_message ?? undefined);
      }
    },
  });

  const liveStatus: DocumentStatusValue = poll?.status ?? doc.status;
  const liveEmbeddingStatus: EmbeddingStatusValue = poll?.embedding_status ?? doc.embedding_status;
  const wordCount = poll?.word_count ?? doc.word_count;
  const errorMessage = poll?.error_message ?? doc.error_message;

  const handleRetry = async (e: MouseEvent) => {
    e.stopPropagation();
    setRetrying(true);
    try {
      await api.post(`/documents/${doc.id}/retry`, {});
      // Two different retry paths on the backend depending on where things
      // failed: a full reprocess (status -> pending) if parsing itself
      // failed, or just the embedding step (status stays "ready",
      // embedding_status -> pending) if only embedding failed. Either way
      // the patch below both updates the badge immediately and, via the
      // initialStatus/initialEmbeddingStatus props into useDocumentStatus,
      // restarts polling.
      if (liveStatus === "ready") {
        toast.info(`Retrying embeddings for ${name}...`);
        onDocumentUpdate(doc.id, { embedding_status: "pending" });
      } else {
        toast.info(`Reprocessing ${name}...`);
        onDocumentUpdate(doc.id, { status: "pending", embedding_status: "pending", error_message: null, chunk_count: 0 });
      }
    } catch {
      toast.error("Could not retry processing", "Please try again.");
    } finally {
      setRetrying(false);
    }
  };

  return (
    <>
    <div
      onClick={() => onOpenDetail(doc)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter") onOpenDetail(doc); }}
      className="group relative flex cursor-pointer flex-col gap-3 rounded-xl border p-5 transition-shadow hover:shadow-md"
      style={{ backgroundColor: "var(--bg-primary)", borderColor: "var(--border-default)" }}
    >
      {/* File type icon */}
      <div
        className="flex h-10 w-10 items-center justify-center rounded-lg"
        style={{ backgroundColor: bg }}
      >
        <Icon size={20} style={{ color }} />
      </div>

      {/* Three-dot button — appears on hover */}
      <div className="absolute right-3 top-3">
        <button
          onClick={(e) => { e.stopPropagation(); onMenuToggle(doc.id); }}
          className="flex h-7 w-7 items-center justify-center rounded-md opacity-0 transition-opacity group-hover:opacity-100"
          style={{ color: "var(--text-secondary)" }}
          aria-label="Document options"
          aria-expanded={menuOpen}
        >
          <MoreHorizontal size={15} />
        </button>

        {/* Dropdown */}
        {menuOpen && (
          <div
            className="absolute right-0 top-8 z-20 w-44 overflow-hidden rounded-lg border py-1 shadow-lg"
            style={{ backgroundColor: "var(--bg-primary)", borderColor: "var(--border-default)" }}
          >
            {isViewable && (
              <button
                onClick={(e) => { e.stopPropagation(); onMenuToggle(doc.id); onView(doc); }}
                className="flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-[var(--bg-secondary)]"
                style={{ color: "var(--text-primary)" }}
              >
                <Eye size={14} style={{ color: "var(--text-tertiary)" }} />
                View
              </button>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); onMenuToggle(doc.id); onDownload(doc); }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-[var(--bg-secondary)]"
              style={{ color: "var(--text-primary)" }}
            >
              <Download size={14} style={{ color: "var(--text-tertiary)" }} />
              Download
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onMenuToggle(doc.id); }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-[var(--bg-secondary)]"
              style={{ color: "var(--text-primary)" }}
            >
              <Sparkles size={14} style={{ color: "var(--text-tertiary)" }} />
              Summarize
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onMenuToggle(doc.id); setShowSimilar(true); }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-[var(--bg-secondary)]"
              style={{ color: "var(--text-primary)" }}
            >
              <Layers size={14} style={{ color: "var(--text-tertiary)" }} />
              Find similar
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onMenuToggle(doc.id); }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-[var(--bg-secondary)]"
              style={{ color: "var(--text-primary)" }}
            >
              <FolderInput size={14} style={{ color: "var(--text-tertiary)" }} />
              Move to project
            </button>
            <div className="my-1 border-t" style={{ borderColor: "var(--border-default)" }} />
            <button
              onClick={(e) => { e.stopPropagation(); onMenuToggle(doc.id); onDeleteRequest(doc); }}
              className="flex w-full items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-[#FEF2F2]"
              style={{ color: "var(--error)" }}
            >
              <Trash2 size={14} />
              Delete
            </button>
          </div>
        )}
      </div>

      {/* Filename */}
      <p
        className="text-sm font-semibold leading-snug"
        style={{
          color: "var(--text-primary)",
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
        }}
        title={name}
      >
        {name}
      </p>

      {/* Meta */}
      <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
        {formatBytes(doc.file_size_bytes)} · {formatDate(doc.created_at)}
      </p>

      {/* Status + project */}
      <div className="mt-auto flex flex-col gap-2">
        <StatusRow
          status={liveStatus}
          embeddingStatus={liveEmbeddingStatus}
          wordCount={wordCount}
          errorMessage={errorMessage}
          retrying={retrying}
          onRetry={handleRetry}
        />
        {doc.project_id && (
          <span className="truncate text-xs" style={{ color: "var(--text-tertiary)" }}>
            {doc.project_id}
          </span>
        )}
      </div>
    </div>

    {/* Rendered as a sibling, not nested inside the card's clickable div —
        otherwise a click on the modal backdrop would bubble up and also
        trigger onOpenDetail underneath it. */}
    {showSimilar && (
      <SimilarDocumentsPanel
        documentId={doc.id}
        documentName={name}
        onClose={() => setShowSimilar(false)}
      />
    )}
    </>
  );
}

// ─── Status row ─────────────────────────────────────────────────────────────

function StatusRow({
  status,
  embeddingStatus,
  wordCount,
  errorMessage,
  retrying,
  onRetry,
}: {
  status: DocumentStatusValue;
  embeddingStatus: EmbeddingStatusValue;
  wordCount: number | null;
  errorMessage: string | null;
  retrying: boolean;
  onRetry: (e: MouseEvent) => void;
}) {
  if (status === "pending") {
    return (
      <span
        className="inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
        style={{ backgroundColor: "var(--bg-tertiary)", color: "var(--text-secondary)" }}
      >
        <Clock size={12} />
        Waiting to process
      </span>
    );
  }

  if (status === "processing") {
    return (
      <span
        className="inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
        style={{ backgroundColor: "#EFF6FF", color: "#2563EB" }}
      >
        <Loader2 size={12} className="animate-spin" />
        Extracting text...
      </span>
    );
  }

  if (status === "ready") {
    // Parsed successfully — embedding is either still running or
    // permanently failed after retries (parsing content stays usable
    // either way, it just isn't searchable yet).
    if (embeddingStatus === "error") {
      return (
        <div className="flex flex-col items-start gap-1.5">
          <span
            className="inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
            style={{ backgroundColor: "#FEF2F2", color: "var(--error)" }}
          >
            <AlertTriangle size={12} />
            Indexing failed
          </span>
          <button
            onClick={onRetry}
            disabled={retrying}
            className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium transition-colors hover:opacity-80 disabled:opacity-40"
            style={{ color: "var(--brand-primary)" }}
          >
            <RotateCcw size={11} className={retrying ? "animate-spin" : ""} />
            {retrying ? "Retrying…" : "Retry"}
          </button>
        </div>
      );
    }
    return (
      <span
        className="inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
        style={{ backgroundColor: "#F5F3FF", color: "#7C3AED" }}
      >
        <Loader2 size={12} className="animate-spin" />
        Building search index...
      </span>
    );
  }

  if (status === "indexed") {
    const label = wordCount != null
      ? `Ready for AI · ${formatNumber(wordCount)} word${wordCount === 1 ? "" : "s"}`
      : "Ready for AI";
    return (
      <span
        className="inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
        style={{ backgroundColor: "var(--brand-secondary)", color: "var(--brand-primary)" }}
      >
        <Sparkles size={12} />
        {label}
      </span>
    );
  }

  // error
  const truncated =
    errorMessage && errorMessage.length > ERROR_MESSAGE_MAX_LEN
      ? `${errorMessage.slice(0, ERROR_MESSAGE_MAX_LEN)}…`
      : errorMessage;

  return (
    <div className="flex flex-col items-start gap-1.5">
      <span
        className="inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
        style={{ backgroundColor: "#FEF2F2", color: "var(--error)" }}
        title={errorMessage ?? undefined}
      >
        <AlertTriangle size={12} />
        {truncated ?? "Failed to process"}
      </span>
      <button
        onClick={onRetry}
        disabled={retrying}
        className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium transition-colors hover:opacity-80 disabled:opacity-40"
        style={{ color: "var(--brand-primary)" }}
      >
        <RotateCcw size={11} className={retrying ? "animate-spin" : ""} />
        {retrying ? "Retrying…" : "Retry"}
      </button>
    </div>
  );
}