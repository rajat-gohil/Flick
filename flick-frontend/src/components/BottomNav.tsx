import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { usePrefersReducedMotion } from "../lib/motion";

export type NavTab = "home" | "sessions" | "discover" | "watchlist" | "profile";

interface BottomNavProps {
  current: NavTab;
}

export default function BottomNav({ current }: BottomNavProps) {
  const navigate = useNavigate();
  const shouldReduceMotion = usePrefersReducedMotion();

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
          <motion.button
            key={tab.id}
            onClick={() => !isActive && navigate(tab.path)}
            aria-current={isActive ? "page" : undefined}
            whileTap={shouldReduceMotion ? undefined : { scale: 0.94 }}
            className={`relative flex flex-1 flex-col items-center justify-center gap-1 py-1 rounded-xl transition-colors cursor-pointer select-none ${
              isActive ? "text-primary" : "text-foreground-secondary hover:text-foreground"
            }`}
          >
            {/* Sliding Active Pill */}
            {isActive && (
              <motion.div
                layoutId={shouldReduceMotion ? undefined : "bottomNavActivePill"}
                transition={{
                  type: "spring",
                  stiffness: 420,
                  damping: 34,
                  mass: 0.8,
                }}
                className="absolute inset-x-1 inset-y-0 rounded-xl bg-primary/10 border border-primary/20 pointer-events-none -z-10"
              />
            )}

            <motion.span
              animate={shouldReduceMotion ? undefined : { scale: isActive ? 1.08 : 1 }}
              transition={{ type: "spring", stiffness: 480, damping: 26 }}
              className="material-symbols-outlined text-[22px]"
              style={{ fontVariationSettings: isActive ? "'FILL' 1" : "'FILL' 0" }}
            >
              {tab.icon}
            </motion.span>
            <span
              className={`text-[10px] leading-none uppercase tracking-wider ${
                isActive ? "font-semibold text-primary" : "font-medium"
              }`}
            >
              {tab.label}
            </span>
          </motion.button>
        );
      })}
    </nav>
  );
}
