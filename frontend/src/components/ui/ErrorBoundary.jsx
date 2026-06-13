import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("UI render error", error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;

    const message = this.state.error?.message || "Something went wrong while rendering this page.";

    return (
      <div className="grid min-h-screen place-items-center bg-[color:var(--page-bg)] px-4 text-[color:var(--text)]">
        <div className="panel w-full max-w-xl p-6 text-center">
          <div className="mx-auto grid size-14 place-items-center rounded-2xl border border-amber-300/25 bg-amber-300/10 text-amber-200">
            <AlertTriangle size={26} />
          </div>
          <h1 className="mt-5 text-2xl font-semibold text-[color:var(--text-strong)]">Page could not load</h1>
          <p className="mt-2 text-sm leading-6 text-[color:var(--text-muted)]">{message}</p>
          <button
            type="button"
            className="btn-primary mt-6"
            onClick={() => window.location.reload()}
          >
            <RefreshCw size={16} /> Reload page
          </button>
        </div>
      </div>
    );
  }
}
