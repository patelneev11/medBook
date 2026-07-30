"use client";

import { useEffect, useLayoutEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);

  // useLayoutEffect is skipped on the server (no SSR mismatch) and runs
  // synchronously before paint on the client (no theme flicker).
  useLayoutEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
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
