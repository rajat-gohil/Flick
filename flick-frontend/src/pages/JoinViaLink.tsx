import { useParams, Navigate } from "react-router-dom";
import { useEffect } from "react";

export default function JoinViaLink() {
  const { sessionCode } = useParams<{ sessionCode: string }>();

  useEffect(() => {
    if (sessionCode) {
      localStorage.setItem(
        "pendingSessionCode",
        sessionCode.toUpperCase()
      );
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