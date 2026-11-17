import { Navigate } from "react-router-dom";

/**
 * RequireAuth — wraps protected routes.
 * If no auth_token is in localStorage, redirects to the landing page.
 * The current URL is saved so the user is returned after login (via AutoJoin etc.).
 */
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("auth_token");
  if (!token) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}