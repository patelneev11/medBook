"use client";

import { useRef, useState, useCallback } from "react";
import type { Document } from "@/types/document";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export type UploadStatus = "uploading" | "processing" | "ready" | "failed";

export interface UploadItem {
  id: string;
  file: File;
  progress: number;
  status: UploadStatus;
  error?: string;
  document?: Document;
}

interface UseFileUploadOptions {
  projectId?: string;
  onSuccess?: (document: Document) => void;
  onError?: (filename: string, message: string) => void;
  maxFiles?: number;
}

function errorMessageForStatus(status: number, body: string): string {
  if (status === 413) return "File is too large (max 50MB)";
  if (status === 415) return "File type not supported";
  if (status === 500) return "Upload failed. Please try again.";
  try {
    const parsed = JSON.parse(body) as { error?: string };
    return parsed.error ?? "Upload failed. Please try again.";
  } catch {
    return "Upload failed. Please try again.";
  }
}

export function useFileUpload({
  projectId,
  onSuccess,
  onError,
  maxFiles = 10,
}: UseFileUploadOptions) {
  const [items, setItems] = useState<UploadItem[]>([]);
  const xhrMap = useRef<Map<string, XMLHttpRequest>>(new Map());

  const updateItem = useCallback(
    (id: string, patch: Partial<UploadItem>) => {
      setItems((prev) =>
        prev.map((item) => (item.id === id ? { ...item, ...patch } : item))
      );
    },
    []
  );

  const startUpload = useCallback(
    (file: File) => {
      const id = crypto.randomUUID();
      const newItem: UploadItem = { id, file, progress: 0, status: "uploading" };
      setItems((prev) => [...prev, newItem]);

      const xhr = new XMLHttpRequest();
      xhrMap.current.set(id, xhr);

      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          updateItem(id, { progress: Math.round((e.loaded / e.total) * 100) });
        }
      };

      xhr.onload = () => {
        xhrMap.current.delete(id);

        if (xhr.status === 401) {
          localStorage.removeItem("auth_token");
          window.location.href = "/login";
          return;
        }

        if (xhr.status === 201) {
          const doc: Document = JSON.parse(xhr.responseText);
          updateItem(id, { status: "processing", progress: 100, document: doc });
          onSuccess?.(doc);
        } else {
          const message = errorMessageForStatus(xhr.status, xhr.responseText);
          updateItem(id, { status: "failed", error: message });
          onError?.(file.name, message);
        }
      };

      xhr.onerror = () => {
        xhrMap.current.delete(id);
        const message = "Upload failed. Please try again.";
        updateItem(id, { status: "failed", error: message });
        onError?.(file.name, message);
      };

      // onabort: user cancelled — remove from list immediately
      xhr.onabort = () => {
        xhrMap.current.delete(id);
        setItems((prev) => prev.filter((item) => item.id !== id));
      };

      const formData = new FormData();
      formData.append("file", file);
      if (projectId) formData.append("project_id", projectId);

      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("auth_token")
          : null;

      xhr.open("POST", `${BASE_URL}/documents/upload`);
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.send(formData);
    },
    [projectId, onSuccess, onError, updateItem]
  );

  const uploadFiles = useCallback(
    (files: File[]) => {
      const slots = maxFiles - items.length;
      if (slots <= 0) return;
      files.slice(0, slots).forEach(startUpload);
    },
    [items.length, maxFiles, startUpload]
  );

  const removeItem = useCallback((id: string) => {
    const xhr = xhrMap.current.get(id);
    if (xhr) {
      xhr.abort(); // triggers onabort → removes from list
    } else {
      setItems((prev) => prev.filter((item) => item.id !== id));
    }
  }, []);

  const retryItem = useCallback(
    (id: string) => {
      const item = items.find((i) => i.id === id);
      if (!item) return;
      setItems((prev) => prev.filter((i) => i.id !== id));
      startUpload(item.file);
    },
    [items, startUpload]
  );

  return { items, uploadFiles, removeItem, retryItem };
}
