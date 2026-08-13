"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { DocumentStatusPoll, DocumentStatusValue, EmbeddingStatusValue } from "@/types/document";

const POLL_INTERVAL_MS = 3000;
const MAX_BACKOFF_MS = 30000;

interface UseDocumentStatusOptions {
  /** Fires once, the first time a poll observes status flip to "indexed". */
  onReady?: (poll: DocumentStatusPoll) => void;
  /**
   * Fires once, the first time a poll observes a terminal failure — either
   * status "error" (parsing failed), or status "ready" with embedding_status
   * "error" (parsed fine, but embedding permanently failed after retries).
   */
  onError?: (poll: DocumentStatusPoll) => void;
  /** Fires on every successful poll, so callers can keep other state in sync. */
  onUpdate?: (poll: DocumentStatusPoll) => void;
}

const isActive = (status: DocumentStatusValue, embeddingStatus: EmbeddingStatusValue) => {
  if (status === "pending" || status === "processing") return true;
  // "ready" means parsed but not yet searchable — keep polling until
  // embedding finishes ("indexed") or permanently fails.
  if (status === "ready") return embeddingStatus === "pending" || embeddingStatus === "generating";
  return false;
};

const isFailed = (poll: Pick<DocumentStatusPoll, "status" | "embedding_status">) =>
  poll.status === "error" || (poll.status === "ready" && poll.embedding_status === "error");

/**
 * Polls GET /documents/{id}/status every 3s while the document is still
 * being worked on: "pending"/"processing" (parsing), or "ready" with
 * embeddings still pending/generating. Stops on a terminal state —
 * "indexed" (success), "error" (parse failed), or "ready" + embedding_status
 * "error" (embedding permanently failed) — on unmount, or if never started
 * because the document was already terminal. Poll failures back off
 * exponentially (3s, 6s, 12s, capped at 30s) and reset to 3s on the next
 * successful poll.
 */
export function useDocumentStatus(
  documentId: string,
  initialStatus: DocumentStatusValue,
  initialEmbeddingStatus: EmbeddingStatusValue,
  options: UseDocumentStatusOptions = {}
): DocumentStatusPoll | null {
  const [poll, setPoll] = useState<DocumentStatusPoll | null>(null);

  // Options change every render (inline arrow functions) — keep the latest
  // in a ref rather than resubscribing the polling effect on every render.
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    let active = true;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    let failureCount = 0;
    let prevActive = isActive(initialStatus, initialEmbeddingStatus);

    const runPoll = async () => {
      if (!active) return;
      try {
        const result = await api.get<DocumentStatusPoll>(`/documents/${documentId}/status`);
        if (!active) return;

        failureCount = 0;
        setPoll(result);
        optionsRef.current.onUpdate?.(result);

        if (prevActive && result.status === "indexed") {
          optionsRef.current.onReady?.(result);
        } else if (prevActive && isFailed(result)) {
          optionsRef.current.onError?.(result);
        }
        prevActive = isActive(result.status, result.embedding_status);

        if (prevActive) {
          timeoutId = setTimeout(runPoll, POLL_INTERVAL_MS);
        }
      } catch {
        if (!active) return;
        failureCount += 1;
        const backoff = Math.min(POLL_INTERVAL_MS * 2 ** failureCount, MAX_BACKOFF_MS);
        timeoutId = setTimeout(runPoll, backoff);
      }
    };

    if (isActive(initialStatus, initialEmbeddingStatus)) {
      timeoutId = setTimeout(runPoll, POLL_INTERVAL_MS);
    }

    return () => {
      active = false;
      if (timeoutId) clearTimeout(timeoutId);
    };
    // documentId/initialStatus/initialEmbeddingStatus are the only inputs
    // that should restart polling — callbacks are read via optionsRef instead.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId, initialStatus, initialEmbeddingStatus]);

  return poll;
}