"use client";

import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "danger";

interface ButtonProps {
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: Variant;
  type?: "button" | "submit" | "reset";
  className?: string;
}

const variantStyles: Record<Variant, string> = {
  primary:
    "bg-brand-primary text-white border border-transparent hover:bg-brand-hover",
  secondary:
    "bg-transparent border border-[var(--border-default)] text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] hover:border-[var(--border-hover)]",
  danger:
    "bg-error text-white border border-transparent hover:opacity-90",
};

export function Button({
  label,
  onClick,
  disabled = false,
  loading = false,
  variant = "primary",
  type = "button",
  className = "",
}: ButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all focus:outline-none focus:ring-2 focus:ring-brand-primary focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40 ${variantStyles[variant]} ${className}`}
    >
      {loading && <Spinner size="sm" />}
      {label}
    </button>
  );
}
