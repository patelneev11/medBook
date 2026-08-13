"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, X, Clock, FileText, Folder } from "lucide-react";
import { getSearchHistory, getSuggestions, clearSearchHistory } from "@/lib/search";
import type { SearchHistoryEntry, SuggestionItem } from "@/types/search";

const MIN_SUGGEST_CHARS = 3;
const DEBOUNCE_MS = 250;
const RECENT_COUNT = 5;

const SUGGESTION_ICON: Record<SuggestionItem["type"], typeof Clock> = {
  recent_query: Clock,
  document: FileText,
  project: Folder,
};

export function TopBarSearch() {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [recent, setRecent] = useState<SearchHistoryEntry[]>([]);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const collapse = useCallback(() => {
    setExpanded(false);
    setDropdownOpen(false);
    setQuery("");
    setSuggestions([]);
  }, []);

  const expand = useCallback(() => {
    setExpanded(true);
    setDropdownOpen(true);
    // Wait for the width transition to start before focusing so the
    // cursor doesn't jump into a not-yet-visible input.
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  // Load recent searches once, when the bar opens with nothing typed yet.
  useEffect(() => {
    if (expanded && query.length === 0) {
      getSearchHistory()
        .then((history) => setRecent(history.slice(0, RECENT_COUNT)))
        .catch(() => setRecent([]));
    }
  }, [expanded, query.length]);

  // Debounced autocomplete once the user has typed enough to search on.
  useEffect(() => {
    if (query.trim().length < MIN_SUGGEST_CHARS) {
      setSuggestions([]);
      return;
    }
    const handle = setTimeout(() => {
      getSuggestions(query.trim())
        .then((res) => setSuggestions(res.suggestions))
        .catch(() => setSuggestions([]));
    }, DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [query]);

  // Click outside collapses the bar, same as Escape.
  useEffect(() => {
    if (!expanded) return;
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        collapse();
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [expanded, collapse]);

  const runSearch = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    collapse();
    router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      runSearch(query);
    } else if (e.key === "Escape") {
      collapse();
    }
  };

  const handleClearHistory = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await clearSearchHistory();
      setRecent([]);
    } catch {
      // Non-critical — leave the stale list visible rather than surface an error toast for this.
    }
  };

  const showRecent = dropdownOpen && query.length === 0 && recent.length > 0;
  const showSuggestions = dropdownOpen && query.trim().length >= MIN_SUGGEST_CHARS && suggestions.length > 0;

  return (
    <div ref={containerRef} className="relative flex items-center" style={{ width: expanded ? "100%" : "32px" }}>
      {!expanded ? (
        <button
          onClick={expand}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors hover:bg-[var(--bg-tertiary)]"
          style={{ color: "var(--text-secondary)" }}
          aria-label="Search"
        >
          <Search size={16} />
        </button>
      ) : (
        <div
          className="flex w-full items-center gap-2 overflow-hidden rounded-lg border px-3 py-1.5 transition-[width] duration-200 ease-out"
          style={{ backgroundColor: "var(--bg-secondary)", borderColor: "var(--border-default)" }}
        >
          <Search size={14} style={{ color: "var(--text-tertiary)", flexShrink: 0 }} />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setDropdownOpen(true); }}
            onFocus={() => setDropdownOpen(true)}
            onKeyDown={handleKeyDown}
            placeholder="Search your documents…"
            className="flex-1 bg-transparent text-sm focus:outline-none"
            style={{ color: "var(--text-primary)" }}
          />
          <button
            onClick={collapse}
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded transition-colors hover:bg-[var(--bg-tertiary)]"
            style={{ color: "var(--text-tertiary)" }}
            aria-label="Close search"
          >
            <X size={13} />
          </button>
        </div>
      )}

      {(showRecent || showSuggestions) && (
        <div
          className="absolute left-0 top-full z-30 mt-1.5 w-full overflow-hidden rounded-lg border py-2 shadow-lg"
          style={{ backgroundColor: "var(--bg-primary)", borderColor: "var(--border-default)" }}
        >
          {showRecent && (
            <div className="px-3">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-tertiary)" }}>
                  Recent searches
                </span>
                <button
                  onClick={handleClearHistory}
                  className="text-xs font-medium transition-colors hover:opacity-80"
                  style={{ color: "var(--brand-primary)" }}
                >
                  Clear history
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5 pb-1">
                {recent.map((entry) => (
                  <button
                    key={entry.id}
                    onClick={() => runSearch(entry.query)}
                    className="rounded-full px-2.5 py-1 text-xs transition-colors hover:opacity-80"
                    style={{ backgroundColor: "var(--bg-tertiary)", color: "var(--text-secondary)" }}
                  >
                    {entry.query}
                  </button>
                ))}
              </div>
            </div>
          )}

          {showSuggestions && (
            <div className="flex flex-col">
              {suggestions.map((s, i) => {
                const Icon = SUGGESTION_ICON[s.type];
                return (
                  <button
                    key={`${s.type}-${i}`}
                    onClick={() => runSearch(s.text)}
                    className="flex items-center gap-2.5 px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--bg-secondary)]"
                    style={{ color: "var(--text-primary)" }}
                  >
                    <Icon size={14} style={{ color: "var(--text-tertiary)", flexShrink: 0 }} />
                    <span className="truncate">{s.text}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}