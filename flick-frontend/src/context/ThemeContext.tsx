import { createContext, useContext, useEffect, useState } from "react";

export type Theme = "dark" | "light";

export const FLICK_LOGOS = {
  icon: {
    dark: "/F Dark Mode.svg",
    light: "/F Light Mode.svg",
  },
  full: {
    dark: "/Flick Dark Mode Main Logo.svg",
    light: "/Flick Light Mode Main Logo.svg",
  },
} as const;

type ThemeContextValue = {
  theme: Theme;
  toggleTheme: () => void;
  isDark: boolean;
  logoIcon: string;
  logoFull: string;
};

const ThemeContext = createContext<ThemeContextValue>({
  theme: "dark",
  toggleTheme: () => {},
  isDark: true,
  logoIcon: FLICK_LOGOS.icon.dark,
  logoFull: FLICK_LOGOS.full.dark,
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const saved = localStorage.getItem("flick_theme");
      if (saved === "light" || saved === "dark") return saved;
    } catch (_e: unknown) {}
    return "dark";
  });

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    root.classList.toggle("dark", theme === "dark");
    root.style.colorScheme = theme;

    // Clean up any obsolete style override tag if left in DOM
    const oldStyle = document.getElementById("flick-theme-override");
    if (oldStyle) oldStyle.remove();

    try {
      localStorage.setItem("flick_theme", theme);
    } catch (_e: unknown) {}
  }, [theme]);

  const toggleTheme = () => setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  const isDark = theme === "dark";
  const logoIcon = isDark ? FLICK_LOGOS.icon.dark : FLICK_LOGOS.icon.light;
  const logoFull = isDark ? FLICK_LOGOS.full.dark : FLICK_LOGOS.full.light;

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, isDark, logoIcon, logoFull }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
