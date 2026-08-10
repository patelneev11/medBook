import {
  FileText,
  FileSpreadsheet,
  FileJson,
  Image as ImageIcon,
  File as FileIcon,
} from "lucide-react";
import type { Document } from "@/types/document";

export type FileClass = "pdf" | "spreadsheet" | "image" | "json" | "text" | "other";

export function classifyMime(mime: string | null): FileClass {
  if (!mime) return "other";
  if (mime === "application/pdf") return "pdf";
  if (mime.includes("spreadsheet") || mime.includes("excel") || mime === "text/csv")
    return "spreadsheet";
  if (mime.startsWith("image/")) return "image";
  if (mime === "application/json") return "json";
  if (mime === "text/plain" || mime === "text/markdown") return "text";
  return "other";
}

export const FILE_STYLES: Record<FileClass, { icon: React.ElementType; bg: string; color: string }> = {
  pdf:         { icon: FileText,        bg: "#FEF2F2",                color: "#DC2626" },
  spreadsheet: { icon: FileSpreadsheet, bg: "var(--brand-secondary)", color: "var(--brand-primary)" },
  image:       { icon: ImageIcon,       bg: "#EFF6FF",                color: "#2563EB" },
  json:        { icon: FileJson,        bg: "#FFFBEB",                color: "#D97706" },
  text:        { icon: FileText,        bg: "var(--bg-tertiary)",      color: "var(--text-secondary)" },
  other:       { icon: FileIcon,        bg: "var(--bg-tertiary)",      color: "var(--text-secondary)" },
};

export function matchesType(doc: Document, filter: string): boolean {
  if (!filter) return true;
  return classifyMime(doc.mime_type) === filter;
}

export function formatBytes(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso: string): string {
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

export function formatNumber(n: number | null): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US");
}