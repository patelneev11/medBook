"use client";

import { useEffect, useState } from "react";

type Status = "checking" | "connected" | "offline";

// Inlined at build time — constant, safe to use before hooks
const IS_DEV = process.env.NEXT_PUBLIC_ENVIRONMENT === "development";

export function ApiStatus() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    if (!IS_DEV) return;

    let cancelled = false;

    async function check() {
      try {
        const base =
          process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
        const res = await fetch(`${base}/health`, { cache: "no-store" });
        if (!cancelled) setStatus(res.ok ? "connected" : "offline");
      } catch {
        if (!cancelled) setStatus("offline");
      }
    }

    check();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!IS_DEV || status === "checking") return null;

  const connected = status === "connected";

  return (
    <div
      className="flex items-center"
      title={connected ? "API connected" : "API offline"}
      aria-label={connected ? "API connected" : "API offline"}
    >
      <span
        className={[
          "block h-2 w-2 rounded-full",
          connected ? "bg-green-500" : "animate-pulse bg-red-500",
        ].join(" ")}
      />
    </div>
  );
}
