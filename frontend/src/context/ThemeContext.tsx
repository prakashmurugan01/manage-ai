import { createContext } from "react";

export const THEMES = {
  DARK: "dark",
  LIGHT: "light",
  CYBER: "cyber",
  MOON: "moon",
  WHITE: "white",
} as const;

export type ThemeName = (typeof THEMES)[keyof typeof THEMES];

export type ThemeContextValue = {
  theme: ThemeName;
  setTheme: (theme: ThemeName) => void;
  toggleTheme: () => void;
  isLight: boolean;
};

export const ThemeContext = createContext<ThemeContextValue | null>(null);

export function isThemeName(value: unknown): value is ThemeName {
  return typeof value === "string" && Object.values(THEMES).includes(value as ThemeName);
}
