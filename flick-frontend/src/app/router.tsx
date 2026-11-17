import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { pageVariants, pageVariantsReduced, usePrefersReducedMotion } from "../lib/motion";
import CinematicLoader from "../components/CinematicLoader";

// Auth + public (code-split)
const EntryPage          = lazy(() => import("../pages/EntryPage"));
const LoginPage          = lazy(() => import("../pages/LoginPage"));
const RegisterPage       = lazy(() => import("../pages/RegisterPage"));
const UsernamePage       = lazy(() => import("../pages/UsernamePage"));
const ForgotPasswordPage = lazy(() => import("../pages/ForgotPasswordPage"));
const ResetPasswordPage  = lazy(() => import("../pages/ResetPasswordPage"));
const GuestRecoveryPage  = lazy(() => import("../pages/GuestRecoveryPage"));
const GuestConvertPage   = lazy(() => import("../pages/GuestConvertPage"));

// Protected (code-split)
const HomePage           = lazy(() => import("../pages/HomePage"));
const CreateSessionPage  = lazy(() => import("../pages/CreateSessionPage"));
const SessionPage        = lazy(() => import("../pages/SessionPage"));
const PreferencesPage    = lazy(() => import("../pages/PreferencesPage"));
const ProfilePage        = lazy(() => import("../pages/ProfilePage"));
const SessionsListPage   = lazy(() => import("../pages/SessionsListPage"));
const WatchlistPage      = lazy(() => import("../pages/WatchlistPage"));
const DiscoverPage              = lazy(() => import("../pages/DiscoverPage"));
const AccountSettingsPage       = lazy(() => import("../pages/AccountSettingsPage"));
const NotificationsSettingsPage = lazy(() => import("../pages/NotificationsSettingsPage"));
const AutoJoin                  = lazy(() => import("../pages/AutoJoin"));

// Legal + auth extras (code-split)
const TermsPage          = lazy(() => import("../pages/TermsPage"));
const PrivacyPage        = lazy(() => import("../pages/PrivacyPage"));
const VerifyEmailPage    = lazy(() => import("../pages/VerifyEmailPage"));

// Utilities
const JoinViaLink        = lazy(() => import("../pages/JoinViaLink"));
import RequireAuth        from "../components/RequireAuth";

// Register service worker for PWA + push notifications (production only)
if ("serviceWorker" in navigator) {
  if (import.meta.env.PROD) {
    window.addEventListener("load", () => {
      navigator.serviceWorker
        .register("/sw.js")
        .then((reg) => console.log("[SW] Registered:", reg.scope))
        .catch((err) => console.warn("[SW] Registration failed:", err));
    });
  } else {
    // In development, unregister any existing service worker to prevent intercepting Vite dev assets
    navigator.serviceWorker.getRegistrations().then((registrations) => {
      for (const reg of registrations) {
        reg.unregister();
      }
    });
  }
}

function RouteLoadingFallback() {
  return (
    <CinematicLoader
      message="Loading Film Archive"
      submessage="Preparing curated cinematic experience..."
      fullScreen={true}
    />
  );
}

function AnimatedRoutes() {
  const location = useLocation();
  const shouldReduceMotion = usePrefersReducedMotion();
  const variants = shouldReduceMotion ? pageVariantsReduced : pageVariants;

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        variants={variants}
        initial="initial"
        animate="animate"
        exit="exit"
        className="min-h-screen"
      >
        <Routes location={location} key={location.pathname}>

          {/* ── Splash / Landing ── */}
          <Route path="/" element={<EntryPage />} />

          {/* ── Auth (public) ── */}
          <Route path="/login"    element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/username" element={<UsernamePage />} />
          <Route path="/recover"  element={<GuestRecoveryPage />} />

          {/* ── Password reset (public) ── */}
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password"  element={<ResetPasswordPage />} />

          {/* ── Deep-link join (public → saves code → redirects to auto-join) ── */}
          <Route path="/join/:sessionCode" element={<JoinViaLink />} />

          {/* ── Protected: auto-join after login ── */}
          <Route path="/auto-join" element={<RequireAuth><AutoJoin /></RequireAuth>} />

          {/* ── Protected: home dashboard ── */}
          <Route path="/home" element={<RequireAuth><HomePage /></RequireAuth>} />

          {/* ── Protected: profile ── */}
          <Route path="/profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />

          {/* ── Protected: sessions list ── */}
          <Route path="/sessions" element={<RequireAuth><SessionsListPage /></RequireAuth>} />

          {/* ── Protected: session history (consolidated to sessions archive) ── */}
          <Route path="/history" element={<Navigate to="/sessions?tab=history" replace />} />

          {/* ── Protected: watchlist ── */}
          <Route path="/watchlist" element={<RequireAuth><WatchlistPage /></RequireAuth>} />

          {/* ── Protected: discover ── */}
          <Route path="/discover" element={<RequireAuth><DiscoverPage /></RequireAuth>} />
          <Route path="/account-settings" element={<RequireAuth><AccountSettingsPage /></RequireAuth>} />
          <Route path="/convert" element={<RequireAuth><GuestConvertPage /></RequireAuth>} />
          <Route path="/notifications-settings" element={<RequireAuth><NotificationsSettingsPage /></RequireAuth>} />

          {/* ── Protected: session flow ── */}
          <Route path="/session/create"          element={<RequireAuth><CreateSessionPage /></RequireAuth>} />
          <Route path="/session/:id/preferences" element={<RequireAuth><PreferencesPage /></RequireAuth>} />
          <Route path="/session/:id"             element={<RequireAuth><SessionPage /></RequireAuth>} />

          {/* ── Legal (public) ── */}
          <Route path="/terms"   element={<TermsPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />

          {/* ── Email verification ── */}
          <Route path="/verify-email" element={<VerifyEmailPage />} />

          {/* ── Catch-all: unknown paths → home ── */}
          <Route path="*" element={<Navigate to="/" replace />} />

        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

export default function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteLoadingFallback />}>
        <AnimatedRoutes />
      </Suspense>
    </BrowserRouter>
  );
}
