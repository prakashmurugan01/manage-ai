import { type ReactNode, useCallback, useLayoutEffect, useMemo, useState } from "react";

import { ThemeContext, THEMES, type ThemeName, isThemeName } from "./ThemeContext.tsx";

const STORAGE_KEY = "theme";
const LIGHT_THEMES = new Set<ThemeName>([THEMES.LIGHT, THEMES.WHITE]);

function getInitialTheme(): ThemeName {
  if (typeof window === "undefined") return THEMES.DARK;

  const saved = window.localStorage.getItem(STORAGE_KEY);
  if (isThemeName(saved)) return saved;

  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? THEMES.LIGHT : THEMES.DARK;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeName>(getInitialTheme);
  const isLight = LIGHT_THEMES.has(theme);

  const setTheme = useCallback((nextTheme: ThemeName) => {
    setThemeState(isThemeName(nextTheme) ? nextTheme : THEMES.DARK);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((current) => (LIGHT_THEMES.has(current) ? THEMES.DARK : THEMES.LIGHT));
  }, []);

  useLayoutEffect(() => {
    const root = document.documentElement;
    const scheme = isLight ? "light" : "dark";

    root.dataset.theme = theme;
    root.dataset.colorScheme = scheme;
    root.style.colorScheme = scheme;
    root.style.setProperty("--theme-color-scheme", scheme);
    root.classList.toggle("light", isLight);
    root.classList.toggle("dark", !isLight);

    if (document.body) {
      document.body.dataset.theme = theme;
      document.body.dataset.colorScheme = scheme;
    }

    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [isLight, theme]);

  const value = useMemo(
    () => ({
      theme,
      setTheme,
      toggleTheme,
      isLight,
    }),
    [isLight, setTheme, theme, toggleTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
