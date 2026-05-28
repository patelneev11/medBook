"use client";

import { useState } from "react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Spinner } from "@/components/ui/Spinner";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-xs font-semibold uppercase tracking-widest" style={{ color: "var(--text-tertiary)" }}>
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function PreviewPage() {
  const [loading, setLoading] = useState(false);

  function simulateLoad() {
    setLoading(true);
    setTimeout(() => setLoading(false), 2000);
  }

  return (
    <div className="min-h-screen p-10" style={{ backgroundColor: "var(--bg-secondary)" }}>
      <div className="mx-auto max-w-2xl space-y-10">

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>Design System</h1>
            <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>MedNotebook component preview</p>
          </div>
          <ThemeToggle />
        </div>

        <Section title="Buttons">
          <div className="flex flex-wrap items-center gap-3">
            <Button label="Primary"    variant="primary" />
            <Button label="Secondary"  variant="secondary" />
            <Button label="Danger"     variant="danger" />
            <Button label="Disabled"   variant="primary" disabled />
            <Button
              label={loading ? "Loading…" : "Click to load"}
              variant="primary"
              loading={loading}
              onClick={simulateLoad}
            />
          </div>
        </Section>

        <Section title="Inputs">
          <div className="space-y-4">
            <Input label="Email"     type="email"    placeholder="you@example.com" />
            <Input label="Password"  type="password" placeholder="••••••••" />
            <Input label="Disabled"  value="john@mednotebook.com" disabled />
            <Input label="With error" placeholder="Enter a value" error="This field is required" />
          </div>
        </Section>

        <Section title="Card">
          <Card>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              Card with warm border, subtle shadow, and bg-primary background. Sits on bg-secondary.
            </p>
          </Card>
        </Section>

        <Section title="Badges">
          <div className="flex flex-wrap gap-2">
            <Badge label="Active"   variant="green" />
            <Badge label="Inactive" variant="gray" />
            <Badge label="Info"     variant="blue" />
            <Badge label="Error"    variant="red" />
          </div>
        </Section>

        <Section title="Spinners">
          <div className="flex items-center gap-4 text-brand-primary">
            <Spinner size="sm" />
            <Spinner size="md" />
            <Spinner size="lg" />
          </div>
        </Section>

        <Section title="Typography">
          <Card>
            <div className="space-y-2">
              {(["3xl","2xl","xl","lg","md","base","sm","xs"] as const).map((size) => (
                <p key={size} className={`text-${size}`} style={{ color: "var(--text-primary)" }}>
                  text-{size} — The quick brown fox
                </p>
              ))}
            </div>
          </Card>
        </Section>

        <Section title="Colour tokens">
          <Card>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {[
                ["bg-primary",   "var(--bg-primary)"],
                ["bg-secondary", "var(--bg-secondary)"],
                ["bg-tertiary",  "var(--bg-tertiary)"],
                ["text-primary", "var(--text-primary)"],
                ["brand-primary","var(--brand-primary)"],
                ["brand-secondary","var(--brand-secondary)"],
                ["accent",       "var(--accent)"],
                ["error",        "var(--error)"],
                ["success",      "var(--success)"],
              ].map(([name, val]) => (
                <div key={name} className="flex items-center gap-2">
                  <div
                    className="h-5 w-5 flex-shrink-0 rounded border"
                    style={{ backgroundColor: val, borderColor: "var(--border-default)" }}
                  />
                  <span className="text-xs" style={{ color: "var(--text-secondary)" }}>{name}</span>
                </div>
              ))}
            </div>
          </Card>
        </Section>

      </div>
    </div>
  );
}
