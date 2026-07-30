"use client";

import {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from "react";
import {
  Upload,
  FileText,
  FileSpreadsheet,
  FileJson,
  Image as ImageIcon,
  File as FileIcon,
  MoreHorizontal,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  RefreshCw,
  Trash2,
  Download,
  Eye,
  Sparkles,
  FolderInput,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { DocumentViewer } from "@/components/documents/DocumentViewer";
import { useUpload } from "@/context/UploadContext";
import { useToast } from "@/context/ToastContext";
import { api } from "@/lib/api";
import type { Document } from "@/types/document";

// ─── Constants ────────────────────────────────────────────────────────────────

const PER_PAGE = 20;
const POLL_INTERVAL_MS = 3000;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatBytes(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  const diffMs = Date.now() - date.getTime();
  const diffH = diffMs / 3_600_000;
  const diffD = diffMs / 86_400_000;
  if (diffH < 1) return "Just now";
  if (diffH < 24) return `${Math.floor(diffH)}h ago`;
  if (diffD < 2) return "Yesterday";
  if (diffD < 7) return `${Math.floor(diffD)} days ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

type FileClass = "pdf" | "spreadsheet" | "image" | "json" | "text" | "other";

function classifyMime(mime: string | null): FileClass {
  if (!mime) return "other";
  if (mime === "application/pdf") return "pdf";
  if (mime.includes("spreadsheet") || mime.includes("excel") || mime === "text/csv")
    return "spreadsheet";
  if (mime.startsWith("image/")) return "image";
  if (mime === "application/json") return "json";
  if (mime === "text/plain" || mime === "text/markdown") return "text";
  return "other";
}

const FILE_STYLES: Record<FileClass, { icon: React.ElementType; bg: string; color: string }> = {
  pdf:         { icon: FileText,        bg: "#FEF2F2",                color: "#DC2626" },
  spreadsheet: { icon: FileSpreadsheet, bg: "var(--brand-secondary)", color: "var(--brand-primary)" },
  image:       { icon: ImageIcon,       bg: "#EFF6FF",                color: "#2563EB" },
  json:        { icon: FileJson,        bg: "#FFFBEB",                color: "#D97706" },
  text:        { icon: FileText,        bg: "var(--bg-tertiary)",      color: "var(--text-secondary)" },
  other:       { icon: FileIcon,        bg: "var(--bg-tertiary)",      color: "var(--text-secondary)" },
};

function matchesType(doc: Document, filter: string): boolean {
  if (!filter) return true;
  return classifyMime(doc.mime_type) === filter;
}

function applySort(docs: Document[], sort: string): Document[] {
  const copy = [...docs];
  if (sort === "oldest")
    return copy.sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    );
  if (sort === "name")
    return copy.sort((a, b) =>
      (a.display_name ?? a.filename).localeCompare(b.display_name ?? b.filename)
    );
  return copy.sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div
      className="animate-pulse space-y-3 rounded-xl border p-5"
      style={{ backgroundColor: "var(--bg-primary)", borderColor: "var(--border-default)" }}
    >
      <div className="h-10 w-10 rounded-lg" style={{ backgroundColor: "var(--bg-tertiary)" }} />
      <div className="space-y-2">
        <div className="h-3.5 w-full rounded" style={{ backgroundColor: "var(--bg-tertiary)" }} />
        <div className="h-3.5 w-3/4 rounded" style={{ backgroundColor: "var(--bg-tertiary)" }} />
      </div>
      <div className="h-3 w-1/2 rounded" style={{ backgroundColor: "var(--bg-tertiary)" }} />
      <div className="h-5 w-16 rounded-full" style={{ backgroundColor: "var(--bg-tertiary)" }} />
    </div>
  );
}

// ─── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: Document["status"] }) {
  if (status === "ready") return <Badge label="Ready" variant="green" />;
  if (status === "error") return <Badge label="Failed" variant="red" />;
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{ backgroundColor: "#EFF6FF", color: "#2563EB" }}
    >
      <Spinner size="sm" className="h-3 w-3" />
      Processing
    </span>
  );
}

// ─── Document card ────────────────────────────────────────────────────────────

interface DocumentCardProps {
  doc: Document;
  menuOpenId: string | null;
  onMenuToggle: (id: string) => void;
  onView: (doc: Document) => void;
  onDownload: (doc: Document) => void;
  onDeleteRequest: (doc: Document) => void;
}

function DocumentCard({
  doc,
  menuOpenId,
  onMenuToggle,
  onView,
  onDownload,
  onDeleteRequest,
}: DocumentCardProps) {
  const cls = classifyMime(doc.mime_type);
  const { icon: Icon, bg, color } = FILE_STYLES[cls];
  const name = doc.display_name ?? doc.filename;
  const menuOpen = menuOpenId === doc.id;
  const isViewable = cls === "pdf" || cls === "image";

  return (
    <div
      className="group relative flex flex-col gap-3 rounded-xl border p-5 transition-shadow hover:shadow-md"
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
      <div className="mt-auto flex items-center justify-between gap-2">
        <StatusBadge status={doc.status} />
        {doc.project_id && (
          <span className="truncate text-xs" style={{ color: "var(--text-tertiary)" }}>
            {doc.project_id}
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyState({ onUpload }: { onUpload: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div
        className="flex h-16 w-16 items-center justify-center rounded-full"
        style={{ backgroundColor: "var(--bg-tertiary)" }}
      >
        <Upload size={26} style={{ color: "var(--text-tertiary)" }} />
      </div>
      <p className="mt-4 text-base font-semibold" style={{ color: "var(--text-primary)" }}>
        No documents uploaded yet
      </p>
      <p className="mt-2 max-w-md text-sm" style={{ color: "var(--text-tertiary)" }}>
        Upload PDFs, CSVs, research papers, lab notes — anything your team needs to reference.
      </p>
      <div className="mt-6">
        <Button label="Upload document" variant="primary" onClick={onUpload} />
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const SELECT_CLASS =
  "rounded-lg border px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand-primary/15 focus:border-brand-primary";

export default function DocumentsPage() {
  const { openUpload, uploadedCount } = useUpload();
  const { toast } = useToast();

  // ── Fetch state ───────────────────────────────────────────────────────────
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  // ── Filter / sort ─────────────────────────────────────────────────────────
  const [search, setSearch]   = useState("");
  const [typeFilter, setType] = useState("");
  const [sort, setSort]       = useState("newest");

  // ── UI state ──────────────────────────────────────────────────────────────
  const [menuOpenId, setMenuOpenId]       = useState<string | null>(null);
  const [viewDoc, setViewDoc]             = useState<Document | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Document | null>(null);

  // ── Fetch ─────────────────────────────────────────────────────────────────
  const fetchDocs = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<Document[]>(`/documents?page=${p}&per_page=${PER_PAGE}`);
      setDocs(data);
      setHasMore(data.length === PER_PAGE);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { fetchDocs(page); }, [page, fetchDocs]);

  // Re-fetch after new uploads — guarded by a ref so there is no cascading loop
  const prevUploadedCount = useRef(0);
  useEffect(() => {
    if (uploadedCount > prevUploadedCount.current) {
      prevUploadedCount.current = uploadedCount;
      setPage(1);
      fetchDocs(1);
    }
  }, [uploadedCount, fetchDocs]);

  // ── Polling for processing docs ───────────────────────────────────────────
  const docsRef = useRef<Document[]>([]);
  useEffect(() => { docsRef.current = docs; }, [docs]);

  useEffect(() => {
    const timer = setInterval(async () => {
      const processing = docsRef.current.filter(
        (d) => d.status === "pending" || d.status === "processing"
      );
      if (processing.length === 0) return;

      const results = await Promise.all(
        processing.map((d) => api.get<Document>(`/documents/${d.id}`).catch(() => null))
      );

      setDocs((prev) =>
        prev.map((d) => {
          const updated = results.find((r) => r?.id === d.id);
          return updated ?? d;
        })
      );
    }, POLL_INTERVAL_MS);

    return () => clearInterval(timer);
  }, []);

  // ── Close menu on outside click ───────────────────────────────────────────
  useEffect(() => {
    if (!menuOpenId) return;
    const handler = () => setMenuOpenId(null);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [menuOpenId]);

  // ── Actions ───────────────────────────────────────────────────────────────
  const handleDownload = useCallback(async (doc: Document) => {
    try {
      const { url } = await api.get<{ url: string; expires_in: number }>(
        `/documents/${doc.id}/download`
      );
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      if (err instanceof TypeError) {
        toast.error("Connection lost", "Check your internet connection");
      } else {
        toast.error("Could not generate download link.");
      }
    }
  }, [toast]);

  const handleView = useCallback((doc: Document) => {
    const cls = classifyMime(doc.mime_type);
    if (cls === "pdf" || cls === "image") {
      setViewDoc(doc);
    } else {
      handleDownload(doc);
    }
  }, [handleDownload]);

  const handleDeleteConfirmed = useCallback(async () => {
    if (!confirmDelete) return;
    const { id } = confirmDelete;
    setConfirmDelete(null);

    // Optimistic remove
    setDocs((prev) => prev.filter((d) => d.id !== id));

    try {
      await api.del(`/documents/${id}`);
      toast.success("Document deleted");
    } catch {
      toast.error("Could not delete document.", "Please try again.");
      fetchDocs(page); // restore on failure
    }
  }, [confirmDelete, toast, fetchDocs, page]);

  // ── Client-side filter + sort ─────────────────────────────────────────────
  const filtered = useMemo(() => {
    let result = docs;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (d) =>
          (d.display_name ?? d.filename).toLowerCase().includes(q) ||
          d.filename.toLowerCase().includes(q)
      );
    }
    if (typeFilter) result = result.filter((d) => matchesType(d, typeFilter));
    return applySort(result, sort);
  }, [docs, search, typeFilter, sort]);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <>
      <div className="space-y-6">

        {/* Filter bar */}
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search documents…"
            className="w-full rounded-lg border px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand-primary/15 focus:border-brand-primary sm:w-64"
            style={{
              backgroundColor: "var(--bg-secondary)",
              borderColor: "var(--border-default)",
              color: "var(--text-primary)",
            }}
          />
          <select
            value={typeFilter}
            onChange={(e) => setType(e.target.value)}
            className={SELECT_CLASS}
            style={{
              backgroundColor: "var(--bg-secondary)",
              borderColor: "var(--border-default)",
              color: "var(--text-primary)",
            }}
          >
            <option value="">All types</option>
            <option value="pdf">PDF</option>
            <option value="spreadsheet">CSV / Excel</option>
            <option value="image">Image</option>
            <option value="text">Text / Markdown</option>
            <option value="json">JSON</option>
          </select>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className={SELECT_CLASS}
            style={{
              backgroundColor: "var(--bg-secondary)",
              borderColor: "var(--border-default)",
              color: "var(--text-primary)",
            }}
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="name">Name</option>
          </select>
          <div className="ml-auto">
            <Button label="Upload" variant="primary" onClick={() => openUpload()} />
          </div>
        </div>

        {/* Loading */}
        {loading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div
              className="flex h-14 w-14 items-center justify-center rounded-full"
              style={{ backgroundColor: "#FEF2F2" }}
            >
              <AlertCircle size={24} style={{ color: "var(--error)" }} />
            </div>
            <p className="mt-4 text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              Failed to load documents
            </p>
            <p className="mt-1 text-sm" style={{ color: "var(--text-tertiary)" }}>{error}</p>
            <div className="mt-5">
              <Button label="Try again" variant="secondary" onClick={() => fetchDocs(page)} />
            </div>
          </div>
        )}

        {/* Empty */}
        {!loading && !error && docs.length === 0 && (
          <EmptyState onUpload={() => openUpload()} />
        )}

        {/* No filter results */}
        {!loading && !error && docs.length > 0 && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <RefreshCw size={28} style={{ color: "var(--text-tertiary)" }} />
            <p className="mt-3 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              No documents match your filters
            </p>
            <button
              onClick={() => { setSearch(""); setType(""); }}
              className="mt-2 text-sm underline"
              style={{ color: "var(--brand-primary)" }}
            >
              Clear filters
            </button>
          </div>
        )}

        {/* Grid */}
        {!loading && !error && filtered.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((doc) => (
              <DocumentCard
                key={doc.id}
                doc={doc}
                menuOpenId={menuOpenId}
                onMenuToggle={(id) => setMenuOpenId((prev) => (prev === id ? null : id))}
                onView={handleView}
                onDownload={handleDownload}
                onDeleteRequest={(doc) => { setMenuOpenId(null); setConfirmDelete(doc); }}
              />
            ))}
          </div>
        )}

        {/* Pagination */}
        {!loading && !error && (hasMore || page > 1) && (
          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="flex items-center gap-1 rounded-lg border px-3 py-2 text-sm transition-colors hover:bg-[var(--bg-tertiary)] disabled:cursor-not-allowed disabled:opacity-40"
              style={{ borderColor: "var(--border-default)", color: "var(--text-primary)" }}
            >
              <ChevronLeft size={15} /> Previous
            </button>
            <span className="text-sm" style={{ color: "var(--text-tertiary)" }}>
              Page {page}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasMore}
              className="flex items-center gap-1 rounded-lg border px-3 py-2 text-sm transition-colors hover:bg-[var(--bg-tertiary)] disabled:cursor-not-allowed disabled:opacity-40"
              style={{ borderColor: "var(--border-default)", color: "var(--text-primary)" }}
            >
              Next <ChevronRight size={15} />
            </button>
          </div>
        )}

      </div>

      {/* Document viewer modal */}
      {viewDoc && (
        <DocumentViewer
          doc={viewDoc}
          onClose={() => setViewDoc(null)}
          onDownload={handleDownload}
        />
      )}

      {/* Delete confirmation */}
      {confirmDelete && (
        <ConfirmDialog
          title={`Delete "${confirmDelete.display_name ?? confirmDelete.filename}"?`}
          message="This will permanently remove the file, all its extracted text, and cannot be undone."
          confirmLabel="Delete"
          onConfirm={handleDeleteConfirmed}
          onCancel={() => setConfirmDelete(null)}
        />
      )}

    </>
  );
}
