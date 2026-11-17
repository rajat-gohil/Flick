import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public override state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public override componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("[ErrorBoundary] Caught screening session error:", error, errorInfo);
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  public override render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div
          data-testid="screening-error-boundary-fallback"
          className="bg-background font-sans text-foreground min-h-screen flex flex-col items-center justify-center px-6"
        >
          <div className="w-full max-w-sm flex flex-col items-center gap-6 text-center p-8 rounded-2xl border border-border bg-surface shadow-sm">
            <div className="size-20 rounded-full bg-surface-secondary border border-border flex items-center justify-center text-primary">
              <span className="material-symbols-outlined text-[36px]">sync_problem</span>
            </div>
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-widest text-primary mb-1 block">
                Screening Recovery
              </span>
              <h2 className="font-editorial text-2xl font-semibold tracking-tight text-foreground mb-1.5">
                Session Display Notice
              </h2>
              <p className="text-foreground-secondary text-xs leading-relaxed max-w-xs mx-auto">
                An unexpected display issue occurred. Tap below to reload your screening session cleanly.
              </p>
            </div>
            <button
              onClick={() => {
                this.handleReset();
                window.location.reload();
              }}
              data-testid="error-boundary-reload-btn"
              className="w-full h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2 shadow-sm"
            >
              <span className="material-symbols-outlined text-[16px]">refresh</span>
              Reload Screening
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
