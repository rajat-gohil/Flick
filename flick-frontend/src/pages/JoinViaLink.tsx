import { useParams, Navigate } from "react-router-dom";
import { useEffect } from "react";
import { trackEvent } from "../lib/analytics";

export default function JoinViaLink() {
  const { sessionCode } = useParams<{ sessionCode: string }>();

  useEffect(() => {
    if (sessionCode) {
      localStorage.setItem(
        "pendingSessionCode",
        sessionCode.toUpperCase()
      );
      trackEvent("invite_link_opened", {
        has_auth_token: Boolean(localStorage.getItem("auth_token")),
      });
    }
  }, [sessionCode]);

  if (!sessionCode) {
    return <Navigate to="/" replace />;
  }

  const token = localStorage.getItem("auth_token");

  if (!token) {
    // Redirect to entry page (login/register lives there now)
    return <Navigate to="/" replace />;
  }

  return <Navigate to="/auto-join" replace />;
}