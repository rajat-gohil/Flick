import { useNavigate } from "react-router-dom";

export type NavTab = "home" | "sessions" | "discover" | "watchlist" | "profile";

interface BottomNavProps {
  current: NavTab;
}

export default function BottomNav({ current }: BottomNavProps) {
  const navigate = useNavigate();

  const tabs: { id: NavTab; label: string; icon: string; path: string }[] = [
    { id: "home",      label: "Home",       icon: "home",      path: "/home"      },
    { id: "sessions",  label: "Screenings", icon: "movie",     path: "/sessions"  },
    { id: "discover",  label: "Archive",    icon: "explore",   path: "/discover"  },
    { id: "watchlist", label: "Watchlist",  icon: "bookmark",  path: "/watchlist" },
    { id: "profile",   label: "Profile",    icon: "person",    path: "/profile"   },
  ];

  return (
    <nav
      aria-label="Mobile Navigation"
      data-tour="nav-mobile"
      className="md:hidden fixed bottom-0 left-0 right-0 z-40 flex items-center justify-around border-t border-border/60 bg-background/95 backdrop-blur-md px-3 pt-2 pb-[max(1.25rem,calc(0.5rem+env(safe-area-inset-bottom)))] transition-colors"
    >
      {tabs.map((tab) => {
        const isActive = current === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => !isActive && navigate(tab.path)}
            aria-current={isActive ? "page" : undefined}
            className={`flex flex-1 flex-col items-center justify-center gap-1 py-1 transition-colors ${
              isActive ? "text-primary" : "text-foreground-secondary hover:text-foreground active:scale-95"
            }`}
          >
            <span
              className="material-symbols-outlined text-[22px]"
              style={{ fontVariationSettings: isActive ? "'FILL' 1" : "'FILL' 0" }}
            >
              {tab.icon}
            </span>
            <span
              className={`text-[10px] leading-none uppercase tracking-wider ${
                isActive ? "font-semibold text-primary" : "font-medium"
              }`}
            >
              {tab.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
