import { Link } from 'wouter';
import { ShieldX } from 'lucide-react';

export default function AdminAccessDeniedPage() {
  return (
    <section
      className="mx-auto flex min-h-[70vh] max-w-xl items-center justify-center"
      role="alert"
      data-status-code="403"
    >
      <div className="w-full rounded-2xl border border-destructive/30 bg-card p-8 text-center shadow-sm">
        <ShieldX className="mx-auto h-10 w-10 text-destructive" aria-hidden="true" />
        <p className="mt-5 text-xs font-bold uppercase tracking-[0.18em] text-destructive">
          403 · Restricted
        </p>
        <h1 className="mt-2 text-2xl font-semibold text-foreground">Access denied</h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          This operations console is available only to administrators with system
          monitoring permission.
        </p>
        <Link
          href="/"
          className="mt-6 inline-flex rounded-lg bg-[#2f6d25] px-4 py-2 text-sm font-semibold text-white"
        >
          Return to Knowledge OS
        </Link>
      </div>
    </section>
  );
}
