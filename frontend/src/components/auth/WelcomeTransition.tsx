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
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-[rgba(245,248,243,0.88)] px-4 backdrop-blur-sm">
      <div
        className={`w-full max-w-xl rounded-[1.9rem] border border-[#dfe7da] bg-white px-6 py-7 text-center shadow-[0_24px_90px_-48px_rgba(15,23,42,0.55)] sm:px-8 sm:py-8 ${
          prefersReducedMotion ? '' : 'animate-in fade-in zoom-in-95 duration-500'
        }`}
      >
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-[#dce6d7] bg-[#f6faf3]">
          <img src={THEME.logoPath} alt="CIAL Logo" className="h-10 w-auto object-contain" />
        </div>
        <p className="mt-5 text-xs font-semibold uppercase tracking-[0.22em] text-[#5b7653]">Welcome</p>
        <h2 className="mt-3 text-[clamp(1.8rem,3vw,2.55rem)] font-semibold tracking-tight text-slate-950">
          Entering CIAL Knowledge OS
        </h2>
        <p className="mt-3 text-sm leading-7 text-slate-600">
          Signed in as <span className="font-semibold text-slate-900">{user.display_name}</span>. The workspace is loading with your access scope and document permissions.
        </p>

        <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-4 text-left">
          <div className="flex items-start gap-3">
            <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-700" />
            <p className="text-sm leading-6 text-amber-950">
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
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-[#25611f] px-4 text-sm font-semibold text-white transition hover:bg-[#1e5119]"
            >
              I Understand
              <ArrowRight size={15} />
            </button>
          ) : (
            <button
              type="button"
              onClick={dismissWelcome}
              className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[#dce4d8] bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-[#f6f8f5]"
            >
              Continue
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
