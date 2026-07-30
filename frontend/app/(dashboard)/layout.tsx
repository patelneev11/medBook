"use client";

import type { ReactNode } from "react";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { UploadProvider } from "@/context/UploadContext";
import { UploadModal } from "@/components/upload/UploadModal";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <UploadProvider>
      <DashboardShell>{children}</DashboardShell>
      <UploadModal />
    </UploadProvider>
  );
}
