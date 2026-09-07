import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  fallbackMessage?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an unhandled error:", error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: "20px",
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            borderRadius: "var(--radius, 8px)",
            color: "var(--text-main, #f8fafc)",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
            margin: "12px 0",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "var(--danger, #ef4444)", fontWeight: 700 }}>
            <AlertTriangle size={20} />
            <span>{this.props.fallbackTitle || "Component Error Encountered"}</span>
          </div>
          <p style={{ fontSize: "0.85rem", color: "var(--text-muted, #94a3b8)", margin: 0 }}>
            {this.props.fallbackMessage ||
              "An unexpected error occurred while rendering this component. The rest of the application remains fully functional."}
          </p>
          {this.state.error && (
            <div
              style={{
                fontFamily: "monospace",
                fontSize: "0.75rem",
                background: "var(--bg-dark, #0b0f17)",
                padding: "8px 12px",
                borderRadius: "6px",
                border: "1px solid var(--border, rgba(255,255,255,0.1))",
                color: "#fca5a5",
                maxHeight: "100px",
                overflowY: "auto",
              }}
            >
              {this.state.error.message || String(this.state.error)}
            </div>
          )}
          <div>
            <button
              type="button"
              onClick={this.handleReset}
              className="btn-secondary"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "0.8rem",
                padding: "6px 12px",
              }}
            >
              <RefreshCw size={14} /> Retry Component
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
