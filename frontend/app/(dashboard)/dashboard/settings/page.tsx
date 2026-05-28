"use client";

import { useState } from "react";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

const sections = ["Profile", "Team", "Storage", "Billing", "Security"] as const;
type Section = (typeof sections)[number];

function ProfileSection() {
  const [name, setName] = useState("John Doe");
  return (
    <div className="max-w-md space-y-5">
      <div>
        <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>Profile</h3>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Update your personal information.
        </p>
      </div>
      <Input label="Full name" value={name} onChange={(e) => setName(e.target.value)} name="name" />
      <Input label="Email" type="email" value="john@mednotebook.com" disabled name="email" />
      <Button label="Save changes" variant="primary" />
    </div>
  );
}

function ComingSoon({ section }: { section: Section }) {
  return (
    <div className="max-w-md">
      <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>{section}</h3>
      <p className="mt-3 text-sm" style={{ color: "var(--text-tertiary)" }}>
        {section} settings — coming soon.
      </p>
    </div>
  );
}

export default function SettingsPage() {
  const [active, setActive] = useState<Section>("Profile");

  return (
    <div className="flex gap-10">

      {/* Left nav */}
      <nav className="w-40 shrink-0 space-y-0.5">
        {sections.map((section) => (
          <button
            key={section}
            onClick={() => setActive(section)}
            className="w-full rounded-lg px-3 py-2 text-left text-sm transition-colors"
            style={
              active === section
                ? { backgroundColor: "var(--brand-secondary)", color: "var(--brand-primary)", fontWeight: 500 }
                : { color: "var(--text-secondary)" }
            }
            onMouseEnter={(e) => {
              if (active !== section) (e.currentTarget as HTMLElement).style.backgroundColor = "var(--bg-tertiary)";
            }}
            onMouseLeave={(e) => {
              if (active !== section) (e.currentTarget as HTMLElement).style.backgroundColor = "";
            }}
          >
            {section}
          </button>
        ))}
      </nav>

      {/* Content */}
      <div className="flex-1 border-l pl-10" style={{ borderColor: "var(--border-default)" }}>
        {active === "Profile" ? <ProfileSection /> : <ComingSoon section={active} />}
      </div>

    </div>
  );
}
