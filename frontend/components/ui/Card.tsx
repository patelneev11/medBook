import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
}

export function Card({ children, className = "" }: CardProps) {
  return (
    <div
      className={`rounded-xl border p-6 ${className}`}
      style={{
        backgroundColor: "var(--bg-primary)",
        borderColor: "var(--border-default)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {children}
    </div>
  );
}
