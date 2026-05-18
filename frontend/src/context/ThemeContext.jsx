import { createContext, useContext, useEffect, useMemo, useState } from "react";

export const THEMES = {
  DARK: "dark",
  LIGHT: "light",
  MOON: "moon",
  WHITE: "moon"
};

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem("theme");
    return saved === "white" ? THEMES.MOON : saved || THEMES.DARK;
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  const value = useMemo(() => ({ theme, setTheme }), [theme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
