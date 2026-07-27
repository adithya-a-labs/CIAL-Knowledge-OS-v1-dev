import { useEffect, useMemo } from 'react';
import { AlertTriangle, ArrowRight } from 'lucide-react';
import { THEME } from '@/config/themeConfig';
import { useAuth } from '@/auth/AuthContext';

export default function WelcomeTransition() {
  const {
    showWelcome,
    dismissWelcome,
    aiNoticeAcknowledged,
    acknowledgeAiNotice,
    user,
  } = useAuth();
  const prefersReducedMotion = useMemo(
    () =>
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    [],
  );

  useEffect(() => {
    if (!showWelcome || !aiNoticeAcknowledged) return;
    const timeout = window.setTimeout(
      dismissWelcome,
      prefersReducedMotion ? 300 : 1250,
    );
    return () => window.clearTimeout(timeout);
  }, [aiNoticeAcknowledged, dismissWelcome, prefersReducedMotion, showWelcome]);

  if (!showWelcome || !user) return null;

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-background/88 px-4 backdrop-blur-sm">
      <div
        className={`w-full max-w-xl rounded-[1.9rem] border border-border bg-card px-6 py-7 text-center shadow-xl sm:px-8 sm:py-8 ${
          prefersReducedMotion ? '' : 'animate-in fade-in zoom-in-95 duration-500'
        }`}
      >
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-border bg-muted">
          <img src={THEME.logoPath} alt="CIAL Logo" className="h-10 w-auto object-contain" />
        </div>
        <p className="mt-5 text-xs font-semibold uppercase tracking-[0.22em] text-primary">Welcome</p>
        <h2 className="mt-3 text-[clamp(1.8rem,3vw,2.55rem)] font-semibold tracking-tight text-foreground">
          Entering CIAL Knowledge OS
        </h2>
        <p className="mt-3 text-sm leading-7 text-muted-foreground">
          Signed in as <span className="font-semibold text-foreground">{user.display_name}</span>. The workspace is loading with your access scope and document permissions.
        </p>

        <div className="mt-6 rounded-2xl border border-warning/30 bg-warning/10 px-4 py-4 text-left">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-warning" />
            <p className="text-sm leading-6 text-warning-foreground">
              CIAL Knowledge OS uses AI to assist with enterprise knowledge. Responses may contain mistakes. Verify critical information against the cited source documents.
            </p>
          </div>
        </div>

        <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
          {!aiNoticeAcknowledged ? (
            <button
              type="button"
              onClick={() => {
                acknowledgeAiNotice();
                dismissWelcome();
              }}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:bg-primary/85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              I Understand
              <ArrowRight size={15} />
            </button>
          ) : (
            <button
              type="button"
              onClick={dismissWelcome}
              className="inline-flex min-h-11 items-center justify-center rounded-xl border border-border bg-card px-4 text-sm font-semibold text-foreground transition hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              Continue
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
