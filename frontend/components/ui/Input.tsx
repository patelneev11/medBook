"use client";

import type { ChangeEvent } from "react";

interface InputProps {
  label?: string;
  placeholder?: string;
  error?: string;
  type?: string;
  value?: string;
  onChange?: (e: ChangeEvent<HTMLInputElement>) => void;
  name?: string;
  id?: string;
  disabled?: boolean;
}

export function Input({
  label,
  placeholder,
  error,
  type = "text",
  value,
  onChange,
  name,
  id,
  disabled = false,
}: InputProps) {
  const inputId = id ?? name;
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label
          htmlFor={inputId}
          className="text-sm font-medium"
          style={{ color: "var(--text-secondary)" }}
        >
          {label}
        </label>
      )}
      <input
        id={inputId}
        name={name}
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        className={`rounded-lg border px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50 ${
          error
            ? "border-error focus:border-error focus:ring-error/20"
            : "focus:border-brand-primary focus:ring-brand-primary/15"
        }`}
        style={{
          backgroundColor: "var(--bg-secondary)",
          borderColor: error ? undefined : "var(--border-default)",
          color: "var(--text-primary)",
        }}
      />
      {error && (
        <p className="text-xs text-error">{error}</p>
      )}
    </div>
  );
}
