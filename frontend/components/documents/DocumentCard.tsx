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
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
} from "lucide-react";
import { useToast } from "@/context/ToastContext";
import { api } from "@/lib/api";
import { classifyMime, FILE_STYLES, formatBytes, formatDate, formatNumber } from "@/lib/documentDisplay";
import { useDocumentStatus } from "@/hooks/useDocumentStatus";
import type { Document, DocumentStatusValue } from "@/types/document";

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

  const cls = classifyMime(doc.mime_type);
  const { icon: Icon, bg, color } = FILE_STYLES[cls];
  const name = doc.display_name ?? doc.filename;
  const menuOpen = menuOpenId === doc.id;
  const isViewable = cls === "pdf" || cls === "image";

  const poll = useDocumentStatus(doc.id, doc.status, {
    onUpdate: (p) => {
      onDocumentUpdate(doc.id, {
        status: p.status,
        word_count: p.word_count,
        page_count: p.page_count,
        chunk_count: p.chunk_count,
        error_message: p.error_message,
      });
    },
    onReady: () => {
      toast.success(`${name} is ready`, "You can now ask AI questions about it");
    },
    onError: (p) => {
      toast.error(`${name} failed to process`, p.error_message ?? undefined);
    },
  });

  const liveStatus: DocumentStatusValue = poll?.status ?? doc.status;
  const wordCount = poll?.word_count ?? doc.word_count;
  const chunkCount = poll?.chunk_count ?? doc.chunk_count;
  const errorMessage = poll?.error_message ?? doc.error_message;

  const handleRetry = async (e: MouseEvent) => {
    e.stopPropagation();
    setRetrying(true);
    try {
      await api.post(`/documents/${doc.id}/retry`, {});
      toast.info(`Reprocessing ${name}...`);
      // status -> "pending" both updates the badge immediately and, via the
      // initialStatus prop into useDocumentStatus, restarts polling.
      onDocumentUpdate(doc.id, { status: "pending", error_message: null, chunk_count: 0 });
    } catch {
      toast.error("Could not retry processing", "Please try again.");
    } finally {
      setRetrying(false);
    }
  };

  return (
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
          wordCount={wordCount}
          chunkCount={chunkCount}
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
  );
}

// ─── Status row ─────────────────────────────────────────────────────────────

function StatusRow({
  status,
  wordCount,
  chunkCount,
  errorMessage,
  retrying,
  onRetry,
}: {
  status: DocumentStatusValue;
  wordCount: number | null;
  chunkCount: number | null;
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
    const parts = ["Ready"];
    if (wordCount != null) parts.push(`${formatNumber(wordCount)} word${wordCount === 1 ? "" : "s"}`);
    if (chunkCount != null) parts.push(`${formatNumber(chunkCount)} chunk${chunkCount === 1 ? "" : "s"}`);
    return (
      <span
        className="inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
        style={{ backgroundColor: "var(--brand-secondary)", color: "var(--brand-primary)" }}
      >
        <CheckCircle2 size={12} />
        {parts.join(" · ")}
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