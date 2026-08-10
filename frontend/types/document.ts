export type DocumentStatusValue = "pending" | "processing" | "ready" | "error";

export type ChunkType = "paragraph" | "table" | "list" | "header+content";

export interface Document {
  id: string;
  filename: string;
  display_name: string | null;
  mime_type: string | null;
  project_id: string | null;
  file_key: string;
  file_size_bytes: number | null;
  status: DocumentStatusValue;
  page_count: number | null;
  word_count: number | null;
  chunk_count: number | null;
  extraction_method: string | null;
  summary: string | null;
  error_message: string | null;
  processing_started_at: string | null;
  processing_completed_at: string | null;
  created_at: string;
  updated_at: string;
  uploaded_by: string;
  file_type_label: string;
}

export interface DocumentDetail extends Document {
  uploaded_by_name: string | null;
  extracted_text_preview: string | null;
}

export interface DocumentStatusPoll {
  id: string;
  status: DocumentStatusValue;
  progress_percent: number;
  error_message: string | null;
  word_count: number | null;
  page_count: number | null;
  chunk_count: number | null;
}

export interface Chunk {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  chunk_type: ChunkType | null;
  page_number: number | null;
  token_count: number | null;
  created_at: string;
}