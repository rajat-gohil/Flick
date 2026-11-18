import React from "react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "../context/ThemeContext";
import type { NavTab } from "./BottomNav";

interface CinemaHeaderProps {
  current?: NavTab;
  title?: string;
  subtitle?: string;
  onBack?: () => void;
  rightAction?: React.ReactNode;
}

export default function CinemaHeader({
  current,
  title,
  subtitle,
  onBack,
  rightAction,
}: CinemaHeaderProps) {
  const navigate = useNavigate();
  const { theme, toggleTheme, logoIcon } = useTheme();

  const navLinks: { id: NavTab; label: string; path: string }[] = [
    { id: "home",      label: "Home",       path: "/home"      },
    { id: "sessions",  label: "Screenings", path: "/sessions"  },
    { id: "discover",  label: "Archive",    path: "/discover"  },
    { id: "watchlist", label: "Watchlist",  path: "/watchlist" },
  ];

  return (
    <header className="sticky top-0 z-30 w-full border-b border-border/60 bg-background/95 backdrop-blur-md transition-colors">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        
        {/* ── Left: Brand or Mobile Back ── */}
        <div className="flex items-center gap-3">
          {onBack && (
            <button
              onClick={onBack}
              aria-label="Back"
              className="flex size-9 shrink-0 items-center justify-center rounded-full border border-border bg-surface text-foreground-secondary hover:text-foreground hover:bg-surface-secondary transition-colors"
            >
              <span className="material-symbols-outlined text-[18px]">arrow_back</span>
            </button>
          )}

          <div
            onClick={() => navigate("/home")}
            className={`flex items-center gap-2.5 cursor-pointer select-none group ${onBack ? "hidden md:flex" : "flex"}`}
          >
            <img src={logoIcon} alt="Flick" className="h-7 w-auto transition-transform group-hover:scale-105" />
            <span className="font-editorial text-xl font-bold tracking-tight text-foreground">
              Flick
            </span>
            <span className="hidden xl:inline text-[10px] uppercase tracking-widest text-foreground-secondary/70 border-l border-border pl-2.5 ml-0.5">
              Cinema Journal
            </span>
          </div>

          {/* Mobile Title (when onBack is present or custom title provided) */}
          {title && (
            <div className="flex flex-col min-w-0 md:hidden">
              <h1 className="font-editorial text-base sm:text-lg font-bold text-foreground leading-tight truncate">
                {title}
              </h1>
              {subtitle && (
                <p className="text-[10px] text-foreground-secondary leading-none truncate mt-0.5">
                  {subtitle}
                </p>
              )}
            </div>
          )}
        </div>

        {/* ── Center: Desktop Editorial Nav Links ── */}
        <nav
          aria-label="Desktop Navigation"
          data-tour="nav-desktop"
          className="hidden md:flex items-center gap-1 lg:gap-2"
        >
          {navLinks.map((link) => {
            const isActive = current === link.id;
            return (
              <button
                key={link.id}
                onClick={() => !isActive && navigate(link.path)}
                className={`relative px-3.5 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors ${
                  isActive
                    ? "text-primary bg-primary/10 font-bold"
                    : "text-foreground-secondary hover:text-foreground hover:bg-surface-secondary/60"
                }`}
              >
                {link.label}
                {isActive && (
                  <span className="absolute inset-x-2 -bottom-2 h-0.5 rounded-full bg-primary" />
                )}
              </button>
            );
          })}
        </nav>

        {/* ── Right: Custom Actions & Profile / Theme ── */}
        <div className="flex items-center gap-2">
          {rightAction}

          {/* Theme switcher */}
          <button
            onClick={toggleTheme}
            className="flex size-9 items-center justify-center rounded-full border border-border bg-surface text-foreground-secondary hover:text-foreground active:scale-95 transition-all shadow-xs"
            title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            aria-label="Toggle theme"
          >
            <span className="material-symbols-outlined text-[18px]">
              {theme === "dark" ? "light_mode" : "dark_mode"}
            </span>
          </button>

          {/* Profile Shortcut */}
          <button
            onClick={() => navigate("/profile")}
            className={`flex size-9 items-center justify-center rounded-full border transition-all active:scale-95 shadow-xs ${
              current === "profile"
                ? "border-primary text-primary bg-primary/10"
                : "border-border bg-surface text-foreground-secondary hover:text-foreground"
            }`}
            aria-label="Profile"
          >
            <span className="material-symbols-outlined text-[18px]">person</span>
          </button>
        </div>
      </div>
    </header>
  );
}
