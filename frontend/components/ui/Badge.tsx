type BadgeVariant = "green" | "gray" | "blue" | "red";

interface BadgeProps {
  label: string;
  variant?: BadgeVariant;
}

export function Badge({ label, variant = "gray" }: BadgeProps) {
  const styles: Record<BadgeVariant, { background: string; color: string }> = {
    green: { background: "var(--brand-secondary)", color: "var(--brand-primary)" },
    gray:  { background: "var(--bg-tertiary)",     color: "var(--text-secondary)" },
    blue:  { background: "#EFF6FF",                color: "#2563EB" },
    red:   { background: "#FEF2F2",                color: "var(--error)" },
  };

  const s = styles[variant];
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{ backgroundColor: s.background, color: s.color }}
    >
      {label}
    </span>
  );
}
