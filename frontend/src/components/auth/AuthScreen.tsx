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
    <div className="min-h-screen bg-background text-foreground">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[minmax(0,1.08fr)_minmax(28rem,0.92fr)]">
        <section className="relative hidden overflow-hidden border-r border-border bg-background lg:flex">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,hsl(var(--primary)/0.10),transparent_34%),linear-gradient(180deg,hsl(var(--card)/0.82),hsl(var(--background)/0.98))]" />
          <div className="relative flex w-full flex-col justify-between px-10 py-12 xl:px-14">
            <div className="flex items-center gap-4">
              <img src={THEME.logoPath} alt="CIAL Logo" className="h-12 w-auto object-contain" />
              <div>
                <p className="text-2xl font-semibold tracking-tight text-primary">CIAL Knowledge OS</p>
                <p className="mt-1 text-sm text-muted-foreground">Enterprise knowledge, grounded in source documents.</p>
              </div>
            </div>

            <div className="max-w-xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card/80 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-primary">
                <ShieldCheck size={14} />
                Secure access
              </div>
              <h1 className="mt-6 text-[clamp(2.8rem,4vw,4.6rem)] font-semibold leading-[1.02] tracking-tight text-foreground">
                Calm, controlled access to CIAL’s working knowledge.
              </h1>
              <p className="mt-5 max-w-lg text-base leading-7 text-muted-foreground">
                Authenticate before entering the workspace. The shell, assistant, and document views stay hidden until access is established.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-border bg-card/88 p-5 shadow-sm">
                <p className="text-sm font-semibold text-foreground">Password access today</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Email and password entry is available now, with room reserved for future enterprise SSO.
                </p>
              </div>
              <div className="rounded-2xl border border-border bg-card/88 p-5 shadow-sm">
                <p className="text-sm font-semibold text-foreground">Role-aware workspace</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
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
                <p className="text-xl font-semibold text-primary">CIAL Knowledge OS</p>
                <p className="text-sm text-muted-foreground">Secure enterprise workspace</p>
              </div>
            </div>

            <div className="rounded-[1.75rem] border border-border bg-card px-5 py-6 shadow-xl sm:px-7 sm:py-8">
              <div>
                <p className="text-sm font-medium uppercase tracking-[0.14em] text-primary">Authentication</p>
                <h2 className="mt-3 text-3xl font-semibold tracking-tight text-foreground">{title}</h2>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{subtitle}</p>
              </div>

              <div className="mt-8">{children}</div>

              <div className="mt-7 border-t border-border pt-5 text-sm text-muted-foreground">
                {footer}
              </div>
            </div>

            <p className="mt-5 text-center text-xs text-muted-foreground">
              Need SSO later? This entry flow intentionally leaves room for enterprise providers without changing the shell structure.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
