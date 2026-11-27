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

function getSavedTheme(): Theme | null {
  try {
    const saved = localStorage.getItem("flick_theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // Ignore storage access errors
  }
  return null;
}

function getSystemTheme(): Theme {
  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  return "dark";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [hasExplicitPref, setHasExplicitPref] = useState<boolean>(() => getSavedTheme() !== null);
  const [theme, setTheme] = useState<Theme>(() => getSavedTheme() ?? getSystemTheme());

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    root.classList.toggle("dark", theme === "dark");
    root.style.colorScheme = theme;

    // Clean up any obsolete style override tag if left in DOM
    const oldStyle = document.getElementById("flick-theme-override");
    if (oldStyle) oldStyle.remove();

    if (hasExplicitPref) {
      try {
        localStorage.setItem("flick_theme", theme);
      } catch {
        // Ignore storage access errors
      }
    }
  }, [theme, hasExplicitPref]);

  useEffect(() => {
    if (hasExplicitPref) return;
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;

    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const handleChange = (e: MediaQueryListEvent) => {
      setTheme(e.matches ? "light" : "dark");
    };

    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", handleChange);
      return () => mq.removeEventListener("change", handleChange);
    }
    return undefined;
  }, [hasExplicitPref]);

  const toggleTheme = () => {
    setHasExplicitPref(true);
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };
  const isDark = theme === "dark";
  const logoIcon = isDark ? FLICK_LOGOS.icon.dark : FLICK_LOGOS.icon.light;
  const logoFull = isDark ? FLICK_LOGOS.full.dark : FLICK_LOGOS.full.light;

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, isDark, logoIcon, logoFull }}>
      {children}
    </ThemeContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  return useContext(ThemeContext);
}
