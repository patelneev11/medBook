"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

export default function LoginPage() {
  const router = useRouter();

  function handleSignIn(e: React.FormEvent) {
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
            Sign in to your workspace
          </p>
        </div>

        <Card>
          <form onSubmit={handleSignIn} className="space-y-4">
            <Input label="Email" type="email" name="email" placeholder="you@institution.edu" />
            <Input label="Password" type="password" name="password" placeholder="••••••••" />
            <Button label="Sign in" type="submit" variant="primary" className="w-full" />
          </form>

          <p className="mt-5 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="font-medium text-brand-primary hover:text-brand-hover">
              Sign up
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
