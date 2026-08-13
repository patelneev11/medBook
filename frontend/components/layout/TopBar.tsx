"use client";

import { usePathname } from "next/navigation";
import { Bell, Menu, Upload } from "lucide-react";
import { ApiStatus } from "@/components/ui/ApiStatus";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { TopBarSearch } from "@/components/layout/TopBarSearch";
import { useUpload } from "@/context/UploadContext";

const pageTitles: Record<string, string> = {
  "/dashboard":           "Dashboard",
  "/dashboard/documents": "Documents",
  "/dashboard/projects":  "Projects",
  "/dashboard/ask":       "Ask AI",
  "/dashboard/settings":  "Settings",
  "/search":              "Search",
};

interface TopBarProps {
  onMenuClick: () => void;
}

export function TopBar({ onMenuClick }: TopBarProps) {
  const pathname = usePathname();
  const title = pageTitles[pathname] ?? "MedNotebook";
  const { openUpload } = useUpload();

  return (
    <header
      className="flex h-14 shrink-0 items-center gap-3 border-b px-4 md:px-6"
      style={{ backgroundColor: "var(--bg-primary)", borderColor: "var(--border-default)" }}
    >
      {/* Hamburger — mobile only */}
      <button
        onClick={onMenuClick}
        className="rounded-md p-1.5 transition-colors hover:bg-[var(--bg-tertiary)] md:hidden"
        style={{ color: "var(--text-secondary)" }}
        aria-label="Open menu"
      >
        <Menu size={20} />
      </button>

      {/* Page title */}
      <h1 className="w-40 shrink-0 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
        {title}
      </h1>

      {/* Search */}
      <div className="flex flex-1 items-center">
        <TopBarSearch />
      </div>

      {/* Right actions */}
      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={() => openUpload()}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-white transition-colors hover:opacity-90"
          style={{ backgroundColor: "var(--brand-primary)" }}
          aria-label="Upload document"
        >
          <Upload size={13} />
          <span className="hidden sm:inline">Upload</span>
        </button>
        <ApiStatus />
        <ThemeToggle />
        <button
          className="rounded-md p-1.5 transition-colors hover:bg-[var(--bg-tertiary)]"
          style={{ color: "var(--text-secondary)" }}
          aria-label="Notifications"
        >
          <Bell size={17} />
        </button>
        <div
          className="ml-1 flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold"
          style={{ backgroundColor: "var(--brand-secondary)", color: "var(--brand-primary)" }}
        >
          JD
        </div>
      </div>
    </header>
  );
}
