import { Link, useLocation } from 'wouter';
import type React from 'react';
import {
  Activity,
  ArrowRight,
  Clock3,
  FileText,
  MessageSquare,
  MoreHorizontal,
  Search,
  Sparkles,
} from 'lucide-react';
import {
  continueWorking,
  knowledgeUpdates,
  quickActions,
  recentDocuments,
  recommendedDocuments,
} from '@/data/homePageData';
import { CURRENT_USER } from '@/config/userConfig';

const toneClass: Record<string, string> = {
  green: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  blue: 'bg-blue-50 text-blue-700 border-blue-100',
  violet: 'bg-violet-50 text-violet-700 border-violet-100',
  amber: 'bg-amber-50 text-amber-700 border-amber-100',
  rose: 'bg-rose-50 text-rose-700 border-rose-100',
  orange: 'bg-orange-50 text-orange-700 border-orange-100',
};

function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="min-w-0">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-950">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export default function DashboardPage() {
  const [, navigate] = useLocation();

  return (
    <div className="mx-auto flex w-full max-w-[86rem] flex-col gap-7" data-testid="dashboard-page">
      <section className="pt-2">
        <p className="text-sm text-slate-500">Good morning, {CURRENT_USER.name.split(' ')[0]}</p>
        <h1 className="mt-2 text-[clamp(2rem,4vw,3.75rem)] font-semibold leading-tight text-slate-950">
          What would you like to work on today?
        </h1>
        <form
          className="mt-7 flex min-h-16 items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 shadow-[0_18px_60px_-34px_rgba(15,23,42,0.45)] transition focus-within:border-primary focus-within:ring-4 focus-within:ring-primary/10"
          onSubmit={(event) => {
            event.preventDefault();
            navigate('/assistant');
          }}
        >
          <Search size={21} className="shrink-0 text-slate-400" />
          <input
            className="min-w-0 flex-1 bg-transparent text-base text-slate-900 placeholder:text-slate-400"
            placeholder="Ask AI or search enterprise knowledge..."
            aria-label="Ask AI or search enterprise knowledge"
            type="search"
          />
          <button type="submit" className="ce-action ce-action-primary h-10 px-3">
            <Sparkles size={15} />
            Ask
          </button>
        </form>
      </section>

      <section className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {quickActions.map((action) => {
          const Icon = action.icon;
          return (
            <Link
              key={action.title}
              href={action.path}
              className="group flex min-h-20 items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-3 shadow-sm transition hover:border-slate-300 hover:bg-slate-50"
            >
              <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border ${toneClass[action.tone]}`}>
                <Icon size={18} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-slate-950">{action.title}</span>
                <span className="mt-0.5 block truncate text-xs text-slate-500">{action.subtitle}</span>
              </span>
              <ArrowRight size={15} className="text-slate-300 transition group-hover:text-slate-600" />
            </Link>
          );
        })}
      </section>

      <div className="grid gap-7 xl:grid-cols-[minmax(0,1.45fr)_minmax(22rem,0.7fr)]">
        <div className="space-y-7">
          <Section title="Continue Working">
            <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
              {continueWorking.map((item) => {
                const Icon = item.icon;
                return (
                  <button key={item.title} className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-slate-50">
                    <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border ${toneClass[item.tone]}`}>
                      <Icon size={17} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-slate-950">{item.title}</span>
                      <span className="mt-0.5 block truncate text-xs text-slate-500">{item.description}</span>
                    </span>
                    <span className="shrink-0 text-xs text-slate-500">{item.time}</span>
                  </button>
                );
              })}
            </div>
          </Section>

          <Section title="Recent Documents" action={<Link href="/knowledge-center" className="text-xs font-semibold text-primary">Browse all</Link>}>
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
              <table className="w-full min-w-[42rem] text-left text-sm">
                <thead className="border-b border-slate-100 bg-slate-50 text-xs font-semibold text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Name</th>
                    <th className="px-4 py-3">Department</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Updated</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {recentDocuments.map((document) => (
                    <tr key={document.name} className="hover:bg-slate-50">
                      <td className="max-w-[26rem] px-4 py-3">
                        <div className="flex min-w-0 items-center gap-3">
                          <FileText size={16} className="shrink-0 text-primary" />
                          <span className="truncate font-medium text-slate-900">{document.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{document.department}</td>
                      <td className="px-4 py-3"><span className="ce-badge">{document.type}</span></td>
                      <td className="px-4 py-3 text-slate-600">{document.updated}</td>
                      <td className="px-4 py-3 text-right">
                        <button className="ce-icon-button" aria-label={`Actions for ${document.name}`}><MoreHorizontal size={16} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </div>

        <div className="space-y-7">
          <Section title="Recent AI Conversations" action={<Link href="/assistant" className="text-xs font-semibold text-primary">Open assistant</Link>}>
            <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
              {continueWorking.map((item) => (
                <button key={item.title} className="flex w-full items-start gap-3 rounded-lg px-2 py-2 text-left transition hover:bg-slate-50">
                  <MessageSquare size={16} className="mt-0.5 shrink-0 text-primary" />
                  <span className="min-w-0 flex-1">
                    <span className="line-clamp-2 text-sm font-medium text-slate-900">{item.title}</span>
                    <span className="mt-1 block text-xs text-slate-500">{item.time}</span>
                  </span>
                </button>
              ))}
            </div>
          </Section>

          <Section title="Suggested Knowledge">
            <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
              {recommendedDocuments.map((item) => (
                <button key={item.title} className="flex w-full items-start gap-3 rounded-lg px-2 py-2 text-left transition hover:bg-slate-50">
                  <FileText size={16} className="mt-0.5 shrink-0 text-primary" />
                  <span className="min-w-0 flex-1">
                    <span className="line-clamp-2 text-sm font-medium text-slate-900">{item.title}</span>
                    <span className="mt-1 block text-xs text-slate-500">{item.meta}</span>
                  </span>
                  <span className="ce-badge shrink-0">{item.badge}</span>
                </button>
              ))}
            </div>
          </Section>

          <Section title="Recent Enterprise Activity">
            <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
              {knowledgeUpdates.slice(0, 3).map((item) => (
                <div key={item.title} className="flex items-start gap-3">
                  <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
                    {item.time.includes('day') ? <Clock3 size={14} /> : <Activity size={14} />}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-900">{item.title}</p>
                    <p className="mt-0.5 text-xs leading-5 text-slate-500">{item.description} / {item.time}</p>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        </div>
      </div>
    </div>
  );
}
