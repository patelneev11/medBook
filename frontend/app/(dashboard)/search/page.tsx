"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Search as SearchIcon,
  FileSearch,
  Sparkles,
  ChevronRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { runSearch } from "@/lib/search";
import { classifyMime, FILE_STYLES } from "@/lib/documentDisplay";
import { Spinner } from "@/components/ui/Spinner";
import { Badge } from "@/components/ui/Badge";
import type { DateFilter, FileTypeFilter, SearchResultItem, SearchType } from "@/types/search";

interface ProjectOption {
  id: string;
  name: string;
}

const SEARCH_TYPES: { value: SearchType; label: string }[] = [
  { value: "semantic", label: "Semantic" },
  { value: "keyword", label: "Keyword" },
  { value: "hybrid", label: "Hybrid" },
];

const FILE_TYPE_OPTIONS: { value: FileTypeFilter; label: string }[] = [
  { value: "pdf", label: "PDF" },
  { value: "csv", label: "CSV" },
  { value: "excel", label: "Excel" },
  { value: "image", label: "Image" },
  { value: "text", label: "Text" },
];

const DATE_OPTIONS: { value: DateFilter | "all"; label: string }[] = [
  { value: "week", label: "Last week" },
  { value: "month", label: "Last month" },
  { value: "3months", label: "Last 3 months" },
  { value: "all", label: "All time" },
];

// ─── Sentence highlighting ──────────────────────────────────────────────────
// The backend returns a chunk of text, not a specific "best sentence" — this
// picks the sentence with the most query-term overlap to bold, client-side.

function splitSentences(text: string): string[] {
  // Paragraph breaks are sentence boundaries too — a header line followed by
  // a blank line and then prose has no terminal punctuation between them,
  // so without this the punctuation-only regex below treats "Header\n\nFirst
  // sentence of the body." as one giant unsplit unit.
  return text
    .split(/\n\s*\n/)
    .flatMap((para) => para.split(/(?<=[.!?])\s+(?=[A-Z])/))
    .map((s) => s.trim())
    .filter(Boolean);
}

function highlightContent(content: string, query: string) {
  const queryWords = query.toLowerCase().split(/\s+/).filter((w) => w.length > 2);
  if (queryWords.length === 0) return content;

  const sentences = splitSentences(content);
  if (sentences.length <= 1) return content;

  let bestIndex = -1;
  let bestScore = 0;
  sentences.forEach((sentence, i) => {
    const lower = sentence.toLowerCase();
    const score = queryWords.reduce((acc, w) => acc + (lower.includes(w) ? 1 : 0), 0);
    if (score > bestScore) {
      bestScore = score;
      bestIndex = i;
    }
  });

  if (bestIndex === -1) return content;

  return (
    <>
      {sentences.slice(0, bestIndex).join(" ")}
      {bestIndex > 0 && " "}
      <strong style={{ color: "var(--brand-primary)" }}>{sentences[bestIndex]}</strong>
      {bestIndex < sentences.length - 1 && " "}
      {sentences.slice(bestIndex + 1).join(" ")}
    </>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={null}>
      <SearchPageContent />
    </Suspense>
  );
}

function SearchPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [searchType, setSearchType] = useState<SearchType>("hybrid");
  const [projectIds, setProjectIds] = useState<Set<string>>(new Set());
  const [fileTypes, setFileTypes] = useState<Set<FileTypeFilter>>(new Set());
  const [dateFilter, setDateFilter] = useState<DateFilter | "all">("all");

  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [results, setResults] = useState<SearchResultItem[] | null>(null);
  const [totalResults, setTotalResults] = useState(0);
  const [searchTimeMs, setSearchTimeMs] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // A new search typed into the topbar while already on this page updates
  // the URL — pick that up rather than only reading it once on mount.
  useEffect(() => {
    setQuery(searchParams.get("q") ?? "");
  }, [searchParams]);

  useEffect(() => {
    api.get<ProjectOption[]>("/projects").then(setProjects).catch(() => setProjects([]));
  }, []);

  const projectNameById = useMemo(() => {
    const map = new Map<string, string>();
    projects.forEach((p) => map.set(p.id, p.name));
    return map;
  }, [projects]);

  const performSearch = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await runSearch({
        query: trimmed,
        search_type: searchType,
        // Checkboxes allow multiple, but the backend currently only
        // supports scoping to one project — send the first checked one
        // rather than silently ignore the rest. Moot in practice today
        // since GET /projects has no real data to populate checkboxes
        // with yet (the Projects feature isn't wired to the DB).
        project_id: projectIds.size > 0 ? [...projectIds][0] : undefined,
        file_types: fileTypes.size > 0 ? [...fileTypes] : undefined,
        date_filter: dateFilter === "all" ? undefined : dateFilter,
        limit: 20,
      });
      setResults(res.results);
      setTotalResults(res.total_results);
      setSearchTimeMs(res.search_time_ms);
    } catch {
      setError("Search failed. Please try again.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [query, searchType, projectIds, fileTypes, dateFilter]);

  useEffect(() => {
    performSearch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, searchType, projectIds, fileTypes, dateFilter]);

  const toggleSetValue = <T,>(set: Set<T>, value: T, setter: (s: Set<T>) => void) => {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    setter(next);
  };

  const askAboutResult = (result: SearchResultItem) => {
    const params = new URLSearchParams({
      document_id: result.document_id,
      document_name: result.document_name,
      q: query,
    });
    router.push(`/dashboard/ask?${params.toString()}`);
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Summary */}
      <div>
        <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          {query ? `Search results for "${query}"` : "Search"}
        </h2>
        {results !== null && !loading && (
          <p className="mt-1 text-sm" style={{ color: "var(--text-tertiary)" }}>
            {totalResults} result{totalResults === 1 ? "" : "s"} for &quot;{query}&quot; · {searchTimeMs}ms
          </p>
        )}
      </div>

      <div className="flex flex-col gap-5 lg:flex-row">
        {/* ── Results (65%) ── */}
        <div className="min-w-0 lg:w-[65%]">
          {loading && (
            <div className="flex items-center justify-center py-20">
              <Spinner size="md" />
            </div>
          )}

          {!loading && error && (
            <p className="rounded-lg border p-4 text-sm" style={{ borderColor: "var(--border-default)", color: "var(--error)" }}>
              {error}
            </p>
          )}

          {!loading && !error && query && results !== null && results.length === 0 && (
            <div className="rounded-xl border p-8 text-center" style={{ borderColor: "var(--border-default)" }}>
              <FileSearch size={28} className="mx-auto mb-3" style={{ color: "var(--text-tertiary)" }} />
              <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                No results found for &quot;{query}&quot;
              </p>
              <ul className="mx-auto mt-3 max-w-xs space-y-1 text-left text-xs" style={{ color: "var(--text-tertiary)" }}>
                <li>• Check spelling</li>
                <li>• Try different keywords</li>
                <li>• Upload more documents related to this topic</li>
              </ul>
            </div>
          )}

          {!loading && !error && results && results.length > 0 && (
            <div className="flex flex-col gap-3">
              {results.map((r) => {
                const cls = classifyMime(r.mime_type);
                const { icon: Icon, bg, color } = FILE_STYLES[cls];
                const projectName = r.project_id ? projectNameById.get(r.project_id) : null;
                return (
                  <div
                    key={r.chunk_id}
                    className="rounded-xl border p-4"
                    style={{ borderColor: "var(--border-default)", backgroundColor: "var(--bg-primary)" }}
                  >
                    <div className="mb-2 flex items-center gap-2">
                      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md" style={{ backgroundColor: bg }}>
                        <Icon size={14} style={{ color }} />
                      </div>
                      <span className="truncate text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                        {r.document_name}
                      </span>
                      {projectName && <Badge label={projectName} variant="blue" />}
                      {r.page_number != null && (
                        <span className="ml-auto shrink-0 text-xs" style={{ color: "var(--text-tertiary)" }}>
                          Page {r.page_number}
                        </span>
                      )}
                    </div>

                    <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                      {highlightContent(r.content, query)}
                    </p>

                    <div className="mt-3 flex items-center gap-3">
                      {/* Similarity as a subtle bar, not a number */}
                      <div className="h-1 w-24 overflow-hidden rounded-full" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.max(4, Math.min(100, Math.round(r.similarity_score * 100)))}%`,
                            backgroundColor: "var(--brand-primary)",
                          }}
                        />
                      </div>
                      <button
                        onClick={() => askAboutResult(r)}
                        className="ml-auto flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors hover:opacity-80"
                        style={{ color: "var(--brand-primary)" }}
                      >
                        <Sparkles size={12} />
                        Ask AI about this
                        <ChevronRight size={12} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {!loading && !query && (
            <div className="rounded-xl border p-8 text-center" style={{ borderColor: "var(--border-default)" }}>
              <SearchIcon size={28} className="mx-auto mb-3" style={{ color: "var(--text-tertiary)" }} />
              <p className="text-sm" style={{ color: "var(--text-tertiary)" }}>
                Use the search bar above to search your documents.
              </p>
            </div>
          )}
        </div>

        {/* ── Filters (35%) ── */}
        <div className="lg:w-[35%]">
          <div className="flex flex-col gap-5 rounded-xl border p-4" style={{ borderColor: "var(--border-default)" }}>
            {/* Search type */}
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                Search type
              </p>
              <div className="flex rounded-lg border p-0.5" style={{ borderColor: "var(--border-default)" }}>
                {SEARCH_TYPES.map((t) => (
                  <button
                    key={t.value}
                    onClick={() => setSearchType(t.value)}
                    className="flex-1 rounded-md py-1.5 text-xs font-medium transition-colors"
                    style={{
                      backgroundColor: searchType === t.value ? "var(--brand-primary)" : "transparent",
                      color: searchType === t.value ? "#fff" : "var(--text-secondary)",
                    }}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Project filter */}
            {projects.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                  Project
                </p>
                <div className="flex flex-col gap-1.5">
                  {projects.map((p) => (
                    <label key={p.id} className="flex items-center gap-2 text-sm" style={{ color: "var(--text-secondary)" }}>
                      <input
                        type="checkbox"
                        checked={projectIds.has(p.id)}
                        onChange={() => toggleSetValue(projectIds, p.id, setProjectIds)}
                      />
                      {p.name}
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* File type filter */}
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                File type
              </p>
              <div className="flex flex-col gap-1.5">
                {FILE_TYPE_OPTIONS.map((f) => (
                  <label key={f.value} className="flex items-center gap-2 text-sm" style={{ color: "var(--text-secondary)" }}>
                    <input
                      type="checkbox"
                      checked={fileTypes.has(f.value)}
                      onChange={() => toggleSetValue(fileTypes, f.value, setFileTypes)}
                    />
                    {f.label}
                  </label>
                ))}
              </div>
            </div>

            {/* Date filter */}
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                Date
              </p>
              <div className="flex flex-col gap-1.5">
                {DATE_OPTIONS.map((d) => (
                  <label key={d.value} className="flex items-center gap-2 text-sm" style={{ color: "var(--text-secondary)" }}>
                    <input
                      type="radio"
                      name="date-filter"
                      checked={dateFilter === d.value}
                      onChange={() => setDateFilter(d.value)}
                    />
                    {d.label}
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}