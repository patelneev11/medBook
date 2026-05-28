"use client";

import { useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/Button";

const selectClass = [
  "rounded-lg border px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2",
  "focus:ring-brand-primary/15 focus:border-brand-primary",
].join(" ");

export default function DocumentsPage() {
  const [search, setSearch] = useState("");

  return (
    <div className="space-y-6">

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search documents…"
          className="rounded-lg border px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand-primary/15 focus:border-brand-primary w-full sm:w-64"
          style={{
            backgroundColor: "var(--bg-secondary)",
            borderColor: "var(--border-default)",
            color: "var(--text-primary)",
          }}
        />
        <select
          className={selectClass}
          style={{
            backgroundColor: "var(--bg-secondary)",
            borderColor: "var(--border-default)",
            color: "var(--text-primary)",
          }}
        >
          <option value="">All types</option>
          <option value="pdf">PDF</option>
          <option value="csv">CSV</option>
          <option value="image">Image</option>
          <option value="text">Text</option>
        </select>
        <select
          className={selectClass}
          style={{
            backgroundColor: "var(--bg-secondary)",
            borderColor: "var(--border-default)",
            color: "var(--text-primary)",
          }}
        >
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="name">Name</option>
        </select>
      </div>

      {/* Empty state */}
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div
          className="flex h-16 w-16 items-center justify-center rounded-full"
          style={{ backgroundColor: "var(--bg-tertiary)" }}
        >
          <Upload size={26} style={{ color: "var(--text-tertiary)" }} />
        </div>
        <p className="mt-4 text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          No documents uploaded yet
        </p>
        <p className="mt-2 max-w-md text-sm" style={{ color: "var(--text-tertiary)" }}>
          Upload PDFs, CSVs, research papers, lab notes — anything your team needs to reference.
        </p>
        <div className="mt-6">
          <Button label="Upload document" variant="primary" />
        </div>
      </div>

    </div>
  );
}
