import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message || "Unknown error" };
  }

  componentDidCatch(error, info) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary card" role="alert">
          <h3 style={{ color: "#c0392b", marginBottom: "0.5rem" }}>Something went wrong</h3>
          <p style={{ color: "#555", fontSize: "0.9rem", marginBottom: "1rem" }}>
            An unexpected error occurred while rendering this section.
          </p>
          <p style={{ color: "#888", fontSize: "0.8rem", fontFamily: "var(--font-mono)" }}>
            {this.state.message}
          </p>
          <button
            className="action-btn secondary"
            style={{ marginTop: "1rem" }}
            onClick={() => this.setState({ hasError: false, message: "" })}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
