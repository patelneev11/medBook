"use client";

import { useRef, useState, useCallback } from "react";
import {
  Upload,
  X,
  RotateCcw,
  FileText,
  FileSpreadsheet,
  FileJson,
  Image as ImageIcon,
  File as FileIcon,
} from "lucide-react";
import { useFileUpload, type UploadItem } from "@/hooks/useFileUpload";
import type { Document } from "@/types/document";

// All MIME types accepted by the backend
const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "text/csv",
  "text/plain",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel",
  "image/jpeg",
  "image/png",
  "image/tiff",
  "application/json",
  "text/markdown",
].join(",");

interface FileUploadProps {
  projectId?: string;
  onSuccess?: (document: Document) => void;
  onError?: (filename: string, message: string) => void;
  maxFiles?: number;
  className?: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileTypeIcon({
  mime,
  filename,
}: {
  mime: string | undefined;
  filename: string;
}) {
  const m = mime ?? "";
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  const props = { size: 15, style: { color: "var(--text-secondary)" } } as const;
  if (m === "application/pdf" || ext === "pdf") return <FileText {...props} />;
  if (
    m.includes("spreadsheet") ||
    m.includes("excel") ||
    ext === "csv" ||
    ext === "xlsx" ||
    ext === "xls"
  )
    return <FileSpreadsheet {...props} />;
  if (m.startsWith("image/")) return <ImageIcon {...props} />;
  if (m === "application/json" || ext === "json") return <FileJson {...props} />;
  return <FileIcon {...props} />;
}

const STATUS_LABEL: Record<UploadItem["status"], string> = {
  uploading: "Uploading…",
  processing: "Processing…",
  ready: "Ready",
  failed: "Failed",
};

const STATUS_COLOR: Record<UploadItem["status"], string> = {
  uploading: "var(--text-secondary)",
  processing: "var(--brand-primary)",
  ready: "var(--success)",
  failed: "var(--error)",
};

// ── File row ──────────────────────────────────────────────────────────────────

function FileRow({
  item,
  onRemove,
  onRetry,
}: {
  item: UploadItem;
  onRemove: () => void;
  onRetry: () => void;
}) {
  const showProgress = item.status === "uploading";
  const showRetry = item.status === "failed";

  return (
    <div
      className="flex items-start gap-3 rounded-lg p-3 transition-colors"
      style={{ backgroundColor: "var(--bg-secondary)" }}
    >
      {/* File type icon */}
      <div
        className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
        style={{ backgroundColor: "var(--bg-tertiary)" }}
      >
        <FileTypeIcon mime={item.file.type} filename={item.file.name} />
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1 space-y-1.5">
        {/* Filename + remove button */}
        <div className="flex items-start justify-between gap-2">
          <span
            className="truncate text-sm font-medium leading-tight"
            style={{ color: "var(--text-primary)" }}
            title={item.file.name}
          >
            {item.file.name}
          </span>
          <button
            onClick={onRemove}
            aria-label={
              item.status === "uploading" ? "Cancel upload" : "Remove"
            }
            className="mt-0.5 shrink-0 rounded p-0.5 transition-colors hover:opacity-70"
            style={{ color: "var(--text-tertiary)" }}
          >
            <X size={14} />
          </button>
        </div>

        {/* File size */}
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          {formatBytes(item.file.size)}
        </p>

        {/* Progress bar */}
        {showProgress && (
          <div
            className="h-1 overflow-hidden rounded-full"
            style={{ backgroundColor: "var(--bg-tertiary)" }}
          >
            <div
              className="h-full rounded-full transition-all duration-200 ease-out"
              style={{
                width: `${item.progress}%`,
                backgroundColor: "var(--brand-primary)",
              }}
            />
          </div>
        )}

        {/* Status line */}
        <div className="flex items-center gap-3">
          <p
            className="text-xs"
            style={{ color: STATUS_COLOR[item.status] }}
          >
            {STATUS_LABEL[item.status]}
          </p>

          {showRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium transition-colors hover:opacity-80"
              style={{
                color: "var(--brand-primary)",
                backgroundColor: "var(--brand-secondary)",
              }}
            >
              <RotateCcw size={11} />
              Retry
            </button>
          )}
        </div>

        {/* Error message */}
        {item.status === "failed" && item.error && (
          <p className="text-xs" style={{ color: "var(--error)" }}>
            {item.error}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Drop zone ─────────────────────────────────────────────────────────────────

export function FileUpload({
  projectId,
  onSuccess,
  onError,
  maxFiles = 10,
  className = "",
}: FileUploadProps) {
  const [isActive, setIsActive] = useState(false); // hover or drag-over
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { items, uploadFiles, removeItem, retryItem } = useFileUpload({
    projectId,
    onSuccess,
    onError,
    maxFiles,
  });

  const atLimit = items.length >= maxFiles;

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
    setIsActive(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    // Only leave if the cursor actually left the zone (not into a child)
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragOver(false);
      setIsActive(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      setIsActive(false);
      if (atLimit) return;
      const files = Array.from(e.dataTransfer.files);
      if (files.length) uploadFiles(files);
    },
    [atLimit, uploadFiles]
  );

  const handleClick = useCallback(() => {
    if (!atLimit) inputRef.current?.click();
  }, [atLimit]);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? []);
      if (files.length) uploadFiles(files);
      e.target.value = "";
    },
    [uploadFiles]
  );

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Hidden file input */}
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED_MIME_TYPES}
        onChange={handleChange}
        className="hidden"
        aria-hidden="true"
      />

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload files — click or drag and drop"
        onClick={handleClick}
        onKeyDown={(e) => e.key === "Enter" && handleClick()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onMouseEnter={() => setIsActive(true)}
        onMouseLeave={() => !isDragOver && setIsActive(false)}
        className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-8 py-12 text-center transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-primary focus:ring-offset-2"
        style={{
          borderColor: isActive
            ? "var(--brand-primary)"
            : "var(--border-default)",
          backgroundColor: isActive
            ? "var(--brand-secondary)"
            : "transparent",
          opacity: atLimit ? 0.5 : 1,
          cursor: atLimit ? "not-allowed" : "pointer",
        }}
      >
        <div
          className="flex h-12 w-12 items-center justify-center rounded-full"
          style={{ backgroundColor: "var(--bg-tertiary)" }}
        >
          <Upload
            size={22}
            style={{
              color: isActive ? "var(--brand-primary)" : "var(--text-tertiary)",
            }}
          />
        </div>

        <div className="space-y-1">
          <p
            className="text-base font-medium"
            style={{ color: "var(--text-primary)" }}
          >
            {atLimit ? `Maximum ${maxFiles} files reached` : "Drag files here"}
          </p>
          {!atLimit && (
            <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              or click to browse
            </p>
          )}
        </div>

        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          Supported: PDF, CSV, Excel, TXT, Images, JSON, Markdown · Max 50 MB per file
        </p>
      </div>

      {/* File list */}
      {items.length > 0 && (
        <div className="space-y-2">
          {items.map((item) => (
            <FileRow
              key={item.id}
              item={item}
              onRemove={() => removeItem(item.id)}
              onRetry={() => retryItem(item.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
