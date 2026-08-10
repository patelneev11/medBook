"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { DocumentStatusPoll, DocumentStatusValue } from "@/types/document";

const POLL_INTERVAL_MS = 3000;
const MAX_BACKOFF_MS = 30000;

interface UseDocumentStatusOptions {
  /** Fires once, the first time a poll observes status flip to "ready". */
  onReady?: (poll: DocumentStatusPoll) => void;
  /** Fires once, the first time a poll observes status flip to "error". */
  onError?: (poll: DocumentStatusPoll) => void;
  /** Fires on every successful poll, so callers can keep other state in sync. */
  onUpdate?: (poll: DocumentStatusPoll) => void;
}

/**
 * Polls GET /documents/{id}/status every 3s while the document is
 * "pending" or "processing". Stops automatically once status reaches a
 * terminal state (ready/error), on unmount (navigating away), or if never
 * started because the document was already terminal. Poll failures back
 * off exponentially (3s, 6s, 12s, capped at 30s) and reset to 3s on the
 * next successful poll.
 */
export function useDocumentStatus(
  documentId: string,
  initialStatus: DocumentStatusValue,
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
    let prevStatus = initialStatus;

    const isActiveStatus = (s: DocumentStatusValue) => s === "pending" || s === "processing";

    const runPoll = async () => {
      if (!active) return;
      try {
        const result = await api.get<DocumentStatusPoll>(`/documents/${documentId}/status`);
        if (!active) return;

        failureCount = 0;
        setPoll(result);
        optionsRef.current.onUpdate?.(result);

        const wasActive = isActiveStatus(prevStatus);
        if (wasActive && result.status === "ready") {
          optionsRef.current.onReady?.(result);
        } else if (wasActive && result.status === "error") {
          optionsRef.current.onError?.(result);
        }
        prevStatus = result.status;

        if (isActiveStatus(result.status)) {
          timeoutId = setTimeout(runPoll, POLL_INTERVAL_MS);
        }
      } catch {
        if (!active) return;
        failureCount += 1;
        const backoff = Math.min(POLL_INTERVAL_MS * 2 ** failureCount, MAX_BACKOFF_MS);
        timeoutId = setTimeout(runPoll, backoff);
      }
    };

    if (isActiveStatus(initialStatus)) {
      timeoutId = setTimeout(runPoll, POLL_INTERVAL_MS);
    }

    return () => {
      active = false;
      if (timeoutId) clearTimeout(timeoutId);
    };
    // documentId/initialStatus are the only inputs that should restart
    // polling — callbacks are read via optionsRef instead.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId, initialStatus]);

  return poll;
}