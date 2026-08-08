import { Component, type ErrorInfo, type ReactNode } from 'react';

interface AppErrorBoundaryProps {
  children: ReactNode;
}

interface AppErrorBoundaryState {
  hasError: boolean;
}

export default class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('cial_app_runtime_error', error, info);
  }

  private reload = () => window.location.reload();

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-6 text-foreground">
        <section className="w-full max-w-lg rounded-2xl border border-border bg-card p-8 text-center shadow-sm" role="alert">
          <img src="/favicon.svg" alt="CIAL" className="mx-auto h-12 w-12" />
          <h1 className="mt-5 text-xl font-semibold">CIAL couldn’t display this page</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Your session is still protected. Reload the application to recover from this unexpected error.
          </p>
          <button
            type="button"
            onClick={this.reload}
            className="mt-6 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            Reload application
          </button>
        </section>
      </main>
    );
  }
}
