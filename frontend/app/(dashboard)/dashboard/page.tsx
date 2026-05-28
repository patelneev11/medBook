import { FileText, Folder, Sparkles, HardDrive, Clock } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

const stats = [
  { label: "Total documents", value: "0",    icon: FileText },
  { label: "Projects",        value: "0",    icon: Folder },
  { label: "AI queries",      value: "0",    icon: Sparkles, note: "this month" },
  { label: "Storage used",    value: "0 MB", icon: HardDrive },
];

export default function DashboardPage() {
  return (
    <div className="space-y-8">

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map(({ label, value, icon: Icon, note }) => (
          <Card key={label} className="flex items-start gap-4 !p-5">
            <div
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
              style={{ backgroundColor: "var(--brand-secondary)" }}
            >
              <Icon size={17} style={{ color: "var(--brand-primary)" }} />
            </div>
            <div>
              <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                {label}{note && <span className="ml-1">({note})</span>}
              </p>
              <p className="mt-0.5 text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>
                {value}
              </p>
            </div>
          </Card>
        ))}
      </div>

      {/* Recent documents + Recent activity */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">

        {/* Recent documents */}
        <div className="space-y-3 lg:col-span-2">
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Recent documents
          </h2>
          <Card className="flex flex-col items-center justify-center py-16 text-center">
            <div
              className="flex h-12 w-12 items-center justify-center rounded-full"
              style={{ backgroundColor: "var(--bg-secondary)" }}
            >
              <FileText size={22} style={{ color: "var(--text-tertiary)" }} />
            </div>
            <p className="mt-3 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              No documents yet
            </p>
            <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
              Upload a PDF, CSV, or text file to get started
            </p>
            <div className="mt-5">
              <Button label="Upload your first document" variant="primary" />
            </div>
          </Card>
        </div>

        {/* Recent activity */}
        <div className="space-y-3">
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Recent activity
          </h2>
          <Card className="flex flex-col items-center justify-center py-16 text-center">
            <div
              className="flex h-12 w-12 items-center justify-center rounded-full"
              style={{ backgroundColor: "var(--bg-secondary)" }}
            >
              <Clock size={22} style={{ color: "var(--text-tertiary)" }} />
            </div>
            <p className="mt-3 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              No activity yet
            </p>
            <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>
              Upload a document to get started
            </p>
          </Card>
        </div>

      </div>

      {/* Quick actions */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Quick actions
        </h2>
        <div className="flex flex-wrap gap-3">
          <Button label="Upload document" variant="primary" />
          <Button label="New project"     variant="secondary" />
          <Button label="Ask AI"          variant="secondary" />
        </div>
      </div>

    </div>
  );
}
