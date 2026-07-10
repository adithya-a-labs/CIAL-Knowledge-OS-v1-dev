import type { ReactNode } from 'react';
import { Link } from 'wouter';
import { ShieldCheck } from 'lucide-react';
import { THEME } from '@/config/themeConfig';

interface AuthScreenProps {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}

export default function AuthScreen({
  title,
  subtitle,
  children,
  footer,
}: AuthScreenProps) {
  return (
    <div className="min-h-screen bg-[#f5f8f3] text-slate-900">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[minmax(0,1.08fr)_minmax(28rem,0.92fr)]">
        <section className="relative hidden overflow-hidden border-r border-[#e1e8dc] bg-[#f7faf5] lg:flex">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(47,109,37,0.08),transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.82),rgba(245,248,243,0.98))]" />
          <div className="relative flex w-full flex-col justify-between px-10 py-12 xl:px-14">
            <div className="flex items-center gap-4">
              <img src={THEME.logoPath} alt="CIAL Logo" className="h-12 w-auto object-contain" />
              <div>
                <p className="text-2xl font-semibold tracking-tight text-[#25611f]">CIAL Knowledge OS</p>
                <p className="mt-1 text-sm text-slate-500">Enterprise knowledge, grounded in source documents.</p>
              </div>
            </div>

            <div className="max-w-xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-[#d8e3d2] bg-white/80 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-[#2f6d25]">
                <ShieldCheck size={14} />
                Secure access
              </div>
              <h1 className="mt-6 text-[clamp(2.8rem,4vw,4.6rem)] font-semibold leading-[1.02] tracking-tight text-slate-950">
                Calm, controlled access to CIAL’s working knowledge.
              </h1>
              <p className="mt-5 max-w-lg text-base leading-7 text-slate-600">
                Authenticate before entering the workspace. The shell, assistant, and document views stay hidden until access is established.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-[#e0e8db] bg-white/88 p-5 shadow-sm">
                <p className="text-sm font-semibold text-slate-950">Password access today</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Email and password entry is available now, with room reserved for future enterprise SSO.
                </p>
              </div>
              <div className="rounded-2xl border border-[#e0e8db] bg-white/88 p-5 shadow-sm">
                <p className="text-sm font-semibold text-slate-950">Role-aware workspace</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Authentication feeds the existing RBAC and document access model instead of bypassing it.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="flex min-h-screen items-center justify-center px-4 py-8 sm:px-6 lg:px-10">
          <div className="w-full max-w-[30rem]">
            <div className="mb-8 flex items-center gap-3 lg:hidden">
              <img src={THEME.logoPath} alt="CIAL Logo" className="h-11 w-auto object-contain" />
              <div>
                <p className="text-xl font-semibold text-[#25611f]">CIAL Knowledge OS</p>
                <p className="text-sm text-slate-500">Secure enterprise workspace</p>
              </div>
            </div>

            <div className="rounded-[1.75rem] border border-[#e2e9dd] bg-white px-5 py-6 shadow-[0_20px_70px_-42px_rgba(15,23,42,0.45)] sm:px-7 sm:py-8">
              <div>
                <p className="text-sm font-medium uppercase tracking-[0.14em] text-[#5e7a55]">Authentication</p>
                <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">{title}</h2>
                <p className="mt-3 text-sm leading-6 text-slate-600">{subtitle}</p>
              </div>

              <div className="mt-8">{children}</div>

              <div className="mt-7 border-t border-[#edf1ea] pt-5 text-sm text-slate-600">
                {footer}
              </div>
            </div>

            <p className="mt-5 text-center text-xs text-slate-500">
              Need SSO later? This entry flow intentionally leaves room for enterprise providers without changing the shell structure.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
