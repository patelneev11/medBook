"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

export default function SignUpPage() {
  const router = useRouter();
  const [agreed, setAgreed] = useState(false);

  function handleCreateAccount(e: React.FormEvent) {
    e.preventDefault();
    router.push("/dashboard");
  }

  return (
    <div
      className="relative flex min-h-screen items-center justify-center px-4"
      style={{ backgroundColor: "var(--bg-secondary)" }}
    >
      {/* Theme toggle — top right */}
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>

      <div className="w-full max-w-sm">
        {/* Wordmark */}
        <div className="mb-7 text-center">
          <span className="text-2xl font-bold text-brand-primary">MedNotebook</span>
          <p className="mt-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
            Create your research workspace
          </p>
        </div>

        <Card>
          <form onSubmit={handleCreateAccount} className="space-y-4">
            <Input label="Full name" type="text" name="name" placeholder="Dr. Jane Smith" />
            <Input label="Work email" type="email" name="email" placeholder="you@institution.edu" />
            <Input label="Password" type="password" name="password" placeholder="••••••••" />

            <label className="flex cursor-pointer items-start gap-2.5">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded"
                style={{ accentColor: "var(--brand-primary)" }}
              />
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                I agree to the{" "}
                <Link href="#" className="font-medium text-brand-primary hover:text-brand-hover">
                  Terms of Service
                </Link>
              </span>
            </label>

            <Button
              label="Create account"
              type="submit"
              variant="primary"
              className="w-full"
              disabled={!agreed}
            />
          </form>

          <p className="mt-5 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-brand-primary hover:text-brand-hover">
              Sign in
            </Link>
          </p>
        </Card>

        <p className="mt-6 text-center text-xs tracking-wide" style={{ color: "var(--text-tertiary)" }}>
          HIPAA-aware · Secure · For research teams
        </p>
      </div>
    </div>
  );
}
