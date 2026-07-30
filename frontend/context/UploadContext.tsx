"use client";

import { createContext, useContext, useState, useCallback } from "react";
import type { ReactNode } from "react";

interface UploadContextValue {
  isOpen: boolean;
  initialProjectId: string | undefined;
  openUpload: (projectId?: string) => void;
  closeUpload: () => void;
  /** Increments each time a document finishes uploading successfully. */
  uploadedCount: number;
  notifyDocumentUploaded: () => void;
}

const UploadContext = createContext<UploadContextValue | null>(null);

export function UploadProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [initialProjectId, setInitialProjectId] = useState<string | undefined>();
  const [uploadedCount, setUploadedCount] = useState(0);

  const openUpload = useCallback((projectId?: string) => {
    setInitialProjectId(projectId);
    setIsOpen(true);
  }, []);

  const closeUpload = useCallback(() => {
    setIsOpen(false);
    setInitialProjectId(undefined);
  }, []);

  const notifyDocumentUploaded = useCallback(() => {
    setUploadedCount((c) => c + 1);
  }, []);

  return (
    <UploadContext.Provider
      value={{ isOpen, initialProjectId, openUpload, closeUpload, uploadedCount, notifyDocumentUploaded }}
    >
      {children}
    </UploadContext.Provider>
  );
}

export function useUpload(): UploadContextValue {
  const ctx = useContext(UploadContext);
  if (!ctx) throw new Error("useUpload must be used inside <UploadProvider>");
  return ctx;
}
