import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

type Theme = "light" | "dark";
type ThemePref = Theme | "system";

const STORAGE_KEY = "bazzix.theme";

type ThemeCtx = {
  theme: Theme;
  preference: ThemePref;
  setPreference: (p: ThemePref) => void;
};

const ThemeContext = createContext<ThemeCtx | null>(null);

function systemTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function resolveTheme(pref: ThemePref): Theme {
  return pref === "system" ? systemTheme() : pref;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePref>("dark");
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const stored = (window.localStorage.getItem(STORAGE_KEY) as ThemePref | null) ?? "dark";
    setPreferenceState(stored);
    setTheme(resolveTheme(stored));
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    root.style.colorScheme = theme;
  }, [theme]);

  useEffect(() => {
    if (preference !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => setTheme(systemTheme());
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [preference]);

  const setPreference = (p: ThemePref) => {
    setPreferenceState(p);
    window.localStorage.setItem(STORAGE_KEY, p);
    setTheme(resolveTheme(p));
  };

  const value = useMemo(() => ({ theme, preference, setPreference }), [theme, preference]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within <ThemeProvider>");
  return ctx;
}
