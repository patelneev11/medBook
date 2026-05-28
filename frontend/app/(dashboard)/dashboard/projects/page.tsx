import { Folder } from "lucide-react";
import { Button } from "@/components/ui/Button";

export default function ProjectsPage() {
  return (
    <div className="space-y-6">

      <div className="flex items-center justify-end">
        <Button label="New project" variant="primary" />
      </div>

      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div
          className="flex h-16 w-16 items-center justify-center rounded-full"
          style={{ backgroundColor: "var(--bg-tertiary)" }}
        >
          <Folder size={26} style={{ color: "var(--text-tertiary)" }} />
        </div>
        <p className="mt-4 text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          No projects yet
        </p>
        <p className="mt-2 max-w-md text-sm" style={{ color: "var(--text-tertiary)" }}>
          Projects help you organize documents by study, patient group, or research topic.
        </p>
        <div className="mt-6">
          <Button label="Create your first project" variant="primary" />
        </div>
      </div>

    </div>
  );
}
