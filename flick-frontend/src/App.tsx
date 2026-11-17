import { ThemeProvider } from "./context/ThemeContext";
import AppRouter from "./app/router";

export default function App() {
  return (
    <ThemeProvider>
      <div className="min-h-screen bg-background text-foreground">
        <AppRouter />
      </div>
    </ThemeProvider>
  );
}
