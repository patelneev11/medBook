"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, FileText, Folder, Sparkles, Settings } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const navItems: { label: string; href: string; icon: LucideIcon }[] = [
  { label: "Dashboard", href: "/dashboard",           icon: Home },
  { label: "Documents", href: "/dashboard/documents", icon: FileText },
  { label: "Projects",  href: "/dashboard/projects",  icon: Folder },
  { label: "Ask AI",    href: "/dashboard/ask",        icon: Sparkles },
  { label: "Settings",  href: "/dashboard/settings",   icon: Settings },
];

interface SidebarProps {
  onClose?: () => void;
}

export function Sidebar({ onClose }: SidebarProps) {
  const pathname = usePathname();

  function isActive(href: string) {
    if (href === "/dashboard") return pathname === "/dashboard";
    return pathname === href || pathname.startsWith(href + "/");
  }

  return (
    <aside
      className="flex h-screen w-60 shrink-0 flex-col border-r"
      style={{ backgroundColor: "var(--bg-primary)", borderColor: "var(--border-default)" }}
    >
      {/* Logo */}
      <div
        className="flex h-14 items-center border-b px-5"
        style={{ borderColor: "var(--border-default)" }}
      >
        <span className="text-base font-bold text-brand-primary">MedNotebook</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        {navItems.map(({ label, href, icon: Icon }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              onClick={onClose}
              className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors"
              style={
                active
                  ? { backgroundColor: "var(--brand-secondary)", color: "var(--brand-primary)" }
                  : { color: "var(--text-secondary)" }
              }
              onMouseEnter={(e) => {
                if (!active) (e.currentTarget as HTMLElement).style.backgroundColor = "var(--bg-tertiary)";
              }}
              onMouseLeave={(e) => {
                if (!active) (e.currentTarget as HTMLElement).style.backgroundColor = "";
              }}
            >
              <Icon size={15} style={{ color: active ? "var(--brand-primary)" : "var(--text-tertiary)" }} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* User section */}
      <div
        className="border-t px-4 py-4"
        style={{ borderColor: "var(--border-default)" }}
      >
        <div className="flex items-center gap-3">
          <div
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
            style={{ backgroundColor: "var(--brand-secondary)", color: "var(--brand-primary)" }}
          >
            JD
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium" style={{ color: "var(--text-primary)" }}>John Doe</p>
            <p className="truncate text-xs" style={{ color: "var(--text-tertiary)" }}>john@mednotebook.com</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
