import { api } from "@/lib/api";
import type {
  SearchHistoryEntry,
  SearchRequestBody,
  SearchResponse,
  SimilarDocumentsResponse,
  SuggestResponse,
} from "@/types/search";

export function runSearch(body: SearchRequestBody): Promise<SearchResponse> {
  return api.post<SearchResponse>("/search", body);
}

export function getSuggestions(q: string, limit = 5): Promise<SuggestResponse> {
  return api.get<SuggestResponse>(`/search/suggest?q=${encodeURIComponent(q)}&limit=${limit}`);
}

export function getSearchHistory(): Promise<SearchHistoryEntry[]> {
  return api.get<SearchHistoryEntry[]>("/search/history");
}

export function clearSearchHistory(): Promise<void> {
  return api.del<void>("/search/history");
}

export function findSimilarDocuments(documentId: string, limit = 5): Promise<SimilarDocumentsResponse> {
  return api.post<SimilarDocumentsResponse>(`/documents/${documentId}/similar?limit=${limit}`, {});
}