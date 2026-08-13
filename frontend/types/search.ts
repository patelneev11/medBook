export type SearchType = "semantic" | "keyword" | "hybrid";
export type FileTypeFilter = "pdf" | "csv" | "excel" | "image" | "text";
export type DateFilter = "week" | "month" | "3months";

export interface SearchRequestBody {
  query: string;
  project_id?: string | null;
  document_ids?: string[] | null;
  limit?: number;
  search_type: SearchType;
  file_types?: FileTypeFilter[] | null;
  date_filter?: DateFilter | null;
}

export interface SearchResultItem {
  chunk_id: string;
  document_id: string;
  document_name: string;
  project_id: string | null;
  mime_type: string | null;
  content: string;
  context_before: string | null;
  context_after: string | null;
  page_number: number | null;
  similarity_score: number;
  chunk_type: string | null;
}

export interface SearchResponse {
  query: string;
  results: SearchResultItem[];
  total_results: number;
  search_type: SearchType;
  search_time_ms: number;
}

export type SuggestionType = "recent_query" | "document" | "project";

export interface SuggestionItem {
  type: SuggestionType;
  text: string;
}

export interface SuggestResponse {
  suggestions: SuggestionItem[];
}

export interface SearchHistoryEntry {
  id: string;
  query: string;
  result_count: number;
  search_type: SearchType;
  project_name: string | null;
  created_at: string;
}

export interface SimilarDocumentItem {
  document_id: string;
  document_name: string;
  mime_type: string | null;
  similarity_score: number;
}

export interface SimilarDocumentsResponse {
  documents: SimilarDocumentItem[];
}