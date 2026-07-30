export interface Document {
  id: string;
  filename: string;
  display_name: string | null;
  mime_type: string | null;
  project_id: string | null;
  file_key: string;
  file_size_bytes: number | null;
  status: "pending" | "processing" | "ready" | "error";
  page_count: number | null;
  word_count: number | null;
  summary: string | null;
  created_at: string;
  updated_at: string;
  uploaded_by: string;
  file_type_label: string;
}
