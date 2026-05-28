"use client";

import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  // Read saved preference after hydration — must not run on the server or the
  // initial client render, otherwise the icon/aria-label won't match SSR output.
  useEffect(() => {
    if (localStorage.getItem("mednotebook-theme") === "dark") setDark(true);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  function toggle() {
    const next = !dark;
    setDark(next);
    localStorage.setItem("mednotebook-theme", next ? "dark" : "light");
  }

  return (
    <button
      onClick={toggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      className="rounded-md p-1.5 transition-colors hover:bg-[var(--bg-tertiary)]"
      style={{ color: "var(--text-secondary)" }}
    >
      {dark ? <Sun size={17} /> : <Moon size={17} />}
    </button>
  );
}
