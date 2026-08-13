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
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { DocumentViewer } from "@/components/documents/DocumentViewer";
import { DocumentCard } from "@/components/documents/DocumentCard";
import { DocumentDetailPanel } from "@/components/documents/DocumentDetailPanel";
import { useUpload } from "@/context/UploadContext";
import { useToast } from "@/context/ToastContext";
import { api } from "@/lib/api";
import { classifyMime, matchesType } from "@/lib/documentDisplay";
import type { Document } from "@/types/document";

// ─── Constants ────────────────────────────────────────────────────────────────

const PER_PAGE = 20;

// ─── Helpers ──────────────────────────────────────────────────────────────────

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

// ─── Failed documents banner ────────────────────────────────────────────────

function FailedDocsBanner({
  count,
  retrying,
  onRetryAll,
}: {
  count: number;
  retrying: boolean;
  onRetryAll: () => void;
}) {
  return (
    <div
      className="flex items-center justify-between gap-3 rounded-lg border px-4 py-3"
      style={{ backgroundColor: "#FEF2F2", borderColor: "var(--error)" }}
    >
      <div className="flex items-center gap-2.5">
        <AlertTriangle size={16} style={{ color: "var(--error)" }} />
        <span className="text-sm font-medium" style={{ color: "var(--error)" }}>
          {count} documents failed to process
        </span>
      </div>
      <Button
        label={retrying ? "Retrying…" : "Retry all"}
        variant="secondary"
        loading={retrying}
        onClick={onRetryAll}
      />
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
  const [detailDoc, setDetailDoc]         = useState<Document | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Document | null>(null);
  const [retryingAll, setRetryingAll]     = useState(false);

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

  // Per-card status polling (see DocumentCard/useDocumentStatus) reports
  // updates back here so search/sort/the detail panel stay in sync.
  const handleDocumentUpdate = useCallback((id: string, patch: Partial<Document>) => {
    setDocs((prev) => prev.map((d) => (d.id === id ? { ...d, ...patch } : d)));
  }, []);

  // A document can fail two different ways: parsing itself failed
  // (status "error"), or parsing succeeded but embedding permanently
  // failed after retries (status stays "ready", embedding_status "error").
  // Both are surfaced/retried together here.
  const isFailedDoc = useCallback(
    (d: Document) => d.status === "error" || (d.status === "ready" && d.embedding_status === "error"),
    []
  );

  const errorCount = useMemo(() => docs.filter(isFailedDoc).length, [docs, isFailedDoc]);

  const handleRetryAll = useCallback(async () => {
    const failedDocs = docs.filter(isFailedDoc);
    if (failedDocs.length === 0) return;

    setRetryingAll(true);
    let succeeded = 0;
    let failed = 0;

    for (let i = 0; i < failedDocs.length; i++) {
      const doc = failedDocs[i];
      try {
        await api.post(`/documents/${doc.id}/retry`, {});
        toast.info(`Reprocessing ${doc.display_name ?? doc.filename}...`);
        if (doc.status === "ready") {
          handleDocumentUpdate(doc.id, { embedding_status: "pending" });
        } else {
          handleDocumentUpdate(doc.id, { status: "pending", embedding_status: "pending", error_message: null, chunk_count: 0 });
        }
        succeeded += 1;
      } catch {
        failed += 1;
      }
      // Stagger requests so we don't hammer the server retrying a bunch at once.
      if (i < failedDocs.length - 1) {
        await new Promise((resolve) => setTimeout(resolve, 500));
      }
    }

    setRetryingAll(false);
    if (failed === 0) {
      toast.success(`Retrying ${succeeded} document${succeeded === 1 ? "" : "s"}`);
    } else {
      toast.error(`Retried ${succeeded} of ${failedDocs.length} documents`, `${failed} could not be retried.`);
    }
  }, [docs, toast, handleDocumentUpdate, isFailedDoc]);

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

        {/* Failed documents banner */}
        {!loading && !error && errorCount > 1 && (
          <FailedDocsBanner count={errorCount} retrying={retryingAll} onRetryAll={handleRetryAll} />
        )}

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
                onOpenDetail={setDetailDoc}
                onDocumentUpdate={handleDocumentUpdate}
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

      {/* Document detail panel */}
      {detailDoc && (
        <DocumentDetailPanel
          doc={detailDoc}
          onClose={() => setDetailDoc(null)}
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