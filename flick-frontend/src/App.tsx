import { useEffect } from "react";
import { ThemeProvider } from "./context/ThemeContext";
import AppRouter from "./app/router";
import AuthRecoveryPrompt from "./components/AuthRecoveryPrompt";
import { initAuthSyncListener } from "./lib/auth";

export default function App() {
  useEffect(() => {
    const cleanup = initAuthSyncListener();
    return () => cleanup();
  }, []);

  return (
    <ThemeProvider>
      <div className="min-h-screen bg-background text-foreground">
        <AppRouter />
        <AuthRecoveryPrompt />
      </div>
    </ThemeProvider>
  );
}
