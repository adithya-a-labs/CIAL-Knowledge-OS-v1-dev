import { Link } from 'wouter';
import type React from 'react';
import {
  FileText,
  MessageSquare,
  MoreVertical,
  Plane,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import {
  aiHeroIcons,
  continueWorking,
  expertsOnCall,
  knowledgeUpdates,
  popularSearches,
  quickActions,
  recentDocuments,
  recommendedDocuments,
  suggestedPrompts,
} from '@/data/homePageData';

const typeBadgeClass: Record<string, string> = {
  Manual: 'bg-blue-50 text-blue-700 border-blue-100',
  SOP: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  Checklist: 'bg-violet-50 text-violet-700 border-violet-100',
  Policy: 'bg-orange-50 text-orange-700 border-orange-100',
};

const softToneClass: Record<string, string> = {
  green: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  blue: 'bg-blue-50 text-blue-700 border-blue-100',
  violet: 'bg-violet-50 text-violet-700 border-violet-100',
  amber: 'bg-amber-50 text-amber-700 border-amber-100',
  rose: 'bg-rose-50 text-rose-700 border-rose-100',
  orange: 'bg-orange-50 text-orange-700 border-orange-100',
};

const statusToneClass: Record<string, string> = {
  Available: 'bg-emerald-500',
  Busy: 'bg-amber-500',
};

function ViewAllLink({ label = 'View all' }: { label?: string }) {
  return (
    <button className="rounded-md text-xs font-medium text-[#2f6d25] transition hover:text-[#244f1d] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
      {label}
    </button>
  );
}

function HomeCard({
  title,
  children,
  viewLabel,
  className = '',
}: {
  title: string;
  children: React.ReactNode;
  viewLabel?: string;
  className?: string;
}) {
  return (
    <section className={`min-w-0 overflow-hidden rounded-2xl border border-[#e5eee3] bg-white/90 shadow-[0_12px_40px_-28px_rgba(15,23,42,0.35)] ${className}`}>
      <div className="flex items-center justify-between gap-3 px-4 pb-2 pt-4 sm:px-5">
        <h2 className="text-base font-semibold text-slate-950">{title}</h2>
        <ViewAllLink label={viewLabel} />
      </div>
      {children}
    </section>
  );
}

function AirportIllustration() {
  return (
    <div className="relative min-h-[15rem] overflow-hidden rounded-2xl border border-[#dcebd8] bg-[linear-gradient(145deg,#eff8ee_0%,#d8ead5_55%,#b6d2c9_100%)] shadow-[inset_0_1px_0_rgba(255,255,255,0.75)]">
      <div className="absolute left-8 top-12 h-10 w-28 rounded-full bg-white/25 blur-[1px]" />
      <div className="absolute left-14 top-8 h-16 w-16 rounded-full bg-white/20" />
      <div className="absolute right-10 top-10 flex items-center gap-2 text-[#51869b] opacity-80">
        <Plane size={46} strokeWidth={1.6} />
        <div className="h-px w-10 bg-[#51869b]/35" />
      </div>
      <div className="absolute bottom-0 left-0 right-0 h-16 bg-[#477f6f]/80" />
      <div className="absolute bottom-0 right-0 h-36 w-[68%] rounded-tl-[5rem] bg-[#2f6f73]/80" />
      <div className="absolute bottom-7 right-0 h-24 w-[63%] rounded-tl-[4rem] border-t border-white/25 bg-[#6aa0a0]/65" />
      <div className="absolute bottom-0 left-[38%] h-28 w-36 bg-[#5e928f]/85">
        <div className="mx-auto mt-4 h-4 w-24 bg-[#285f63]/65" />
        <div className="mt-7 grid grid-cols-3 gap-px px-4">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-8 bg-[#2f6870]/60" />
          ))}
        </div>
      </div>
      <div className="absolute bottom-24 left-[57%] h-32 w-20 bg-[#79aeb0]/80">
        <div className="h-full border-x border-white/20" />
      </div>
      <div className="absolute bottom-52 left-[55%] h-14 w-28 rounded-t-lg bg-[#5d9298]/90">
        <div className="grid h-full grid-cols-4 gap-px p-2">
          {Array.from({ length: 8 }).map((_, index) => (
            <div key={index} className="bg-[#2d6170]/45" />
          ))}
        </div>
      </div>
      <div className="absolute bottom-[16.5rem] left-[62%] h-9 w-px bg-[#5d9298]/70" />
      <div className="absolute bottom-0 left-4 h-12 w-12 rounded-t-full bg-[#3f765f]/80" />
      <div className="absolute bottom-0 left-14 h-8 w-8 rounded-t-full bg-[#3f765f]/80" />
      <div className="absolute bottom-0 left-24 h-5 w-24 rounded-t-full bg-[#3f765f]/70" />
      <div className="absolute bottom-0 left-0 right-0 h-4 bg-[#2d665f]/80" />
    </div>
  );
}

function AiHero() {
  const { Mic, Send, Sparkles } = aiHeroIcons;

  return (
    <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
      <div className="space-y-5">
        <div>
          <h1 className="text-[1.65rem] font-semibold leading-tight tracking-normal text-slate-950 sm:text-4xl">
            Good morning, <span className="text-[#2f6d25]">Ananya</span> 👋
          </h1>
          <p className="mt-2 text-base text-slate-500">How can I help you today?</p>
        </div>

        <form
          className="flex min-h-20 items-center gap-3 rounded-2xl border border-[#bfdcba] bg-white px-4 shadow-[0_18px_55px_-32px_rgba(47,109,37,0.45)] transition focus-within:border-[#82b377] focus-within:ring-4 focus-within:ring-[#d8ead5]"
          onSubmit={(event) => event.preventDefault()}
        >
          <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-[#eef8eb] text-[#2f6d25]">
            <Sparkles size={22} />
          </div>
          <input
            aria-label="Ask CIAL AI"
            className="min-w-0 flex-1 bg-transparent text-base text-slate-900 placeholder:text-slate-400"
            placeholder="Ask anything to CIAL AI..."
            type="search"
          />
          <button
            type="button"
            className="hidden h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring sm:flex"
            aria-label="Use microphone"
          >
            <Mic size={20} />
          </button>
          <button
            type="submit"
            className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-[#24611f] text-white shadow-[0_12px_24px_-14px_rgba(36,97,31,0.8)] transition hover:bg-[#1d5019] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            aria-label="Send question"
          >
            <Send size={21} />
          </button>
        </form>

        <div className="flex flex-wrap gap-2 pl-0 sm:pl-6">
          <span className="mr-2 self-center text-sm text-slate-500">Try asking:</span>
          {suggestedPrompts.map((prompt) => (
            <button
              key={prompt}
              className="rounded-full border border-[#e0e7dd] bg-white px-4 py-2 text-sm text-slate-700 shadow-sm transition hover:border-[#bddbb7] hover:bg-[#f6fbf5] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      <AirportIllustration />
    </section>
  );
}

function QuickActionStrip() {
  return (
    <section className="grid overflow-hidden rounded-2xl border border-[#e5eee3] bg-white/90 shadow-[0_12px_40px_-30px_rgba(15,23,42,0.4)] sm:grid-cols-2 lg:grid-cols-5">
      {quickActions.map((action, index) => {
        const Icon = action.icon;
        return (
          <Link
            key={action.title}
            href={action.path}
            className={`group flex min-h-[5.5rem] items-center gap-3 px-3 py-4 transition hover:bg-[#f8fbf7] focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ring ${
              index > 0 ? 'lg:border-l lg:border-[#e9eee7]' : ''
            }`}
          >
            <span className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl border ${softToneClass[action.tone]}`}>
              <Icon size={20} />
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-semibold leading-tight text-slate-950">{action.title}</span>
              <span className="mt-1 block text-xs leading-tight text-slate-500">{action.subtitle}</span>
            </span>
          </Link>
        );
      })}
    </section>
  );
}

function ContinueWorkingCard() {
  return (
    <HomeCard title="Continue Working">
      <div className="divide-y divide-[#eef3ec] px-4 pb-4 sm:px-5">
        {continueWorking.map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.title} className="flex w-full items-center gap-3 py-3 text-left transition hover:bg-[#fbfdfb] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
              <span className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl border ${softToneClass[item.tone]}`}>
                <Icon size={19} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-slate-950">{item.title}</span>
                <span className="mt-0.5 block truncate text-xs text-slate-500">{item.description}</span>
              </span>
              <span className="flex-shrink-0 text-xs text-slate-500">{item.time}</span>
            </button>
          );
        })}
      </div>
    </HomeCard>
  );
}

function RecommendedCard() {
  return (
    <HomeCard title="Recommended for You">
      <div className="space-y-2 px-4 pb-3 sm:px-5">
        {recommendedDocuments.map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.title} className="flex w-full items-center gap-3 rounded-xl py-2 text-left transition hover:bg-[#fbfdfb] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
              <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-emerald-100 bg-emerald-50 text-[#2f6d25]">
                <Icon size={17} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-slate-950">{item.title}</span>
                <span className="mt-0.5 block truncate text-xs text-slate-500">{item.meta}</span>
              </span>
              <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${typeBadgeClass[item.badge]}`}>
                {item.badge}
              </span>
            </button>
          );
        })}
        <p className="flex items-center gap-2 border-t border-[#eef3ec] pt-3 text-xs text-slate-500">
          <Sparkles size={14} className="text-[#2f6d25]" />
          Based on your role and recent activity
        </p>
      </div>
    </HomeCard>
  );
}

function KnowledgeUpdatesCard() {
  return (
    <HomeCard title="Knowledge Updates">
      <div className="space-y-3 px-4 pb-4 sm:px-5">
        {knowledgeUpdates.map((item) => (
          <div key={item.title} className="grid grid-cols-[auto_1fr_auto] items-center gap-3">
            <span className={`h-2 w-2 rounded-full ${item.tone === 'green' ? 'bg-emerald-500' : item.tone === 'violet' ? 'bg-violet-500' : item.tone === 'amber' ? 'bg-amber-500' : 'bg-blue-500'}`} />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-slate-950">{item.title}</p>
              <p className="truncate text-xs text-slate-500">{item.description}</p>
            </div>
            <span className={`text-xs ${item.time === 'View now' ? 'font-medium text-blue-600' : 'text-slate-500'}`}>{item.time}</span>
          </div>
        ))}
      </div>
    </HomeCard>
  );
}

function RecentDocumentsTable() {
  return (
    <HomeCard title="Recent Documents">
      <div className="overflow-x-auto px-4 pb-4 sm:px-5">
        <table className="w-full min-w-[34rem] border-collapse text-left">
          <thead>
            <tr className="border-b border-[#eef3ec] text-xs font-medium text-slate-500">
              <th className="py-3 pr-4">Name</th>
              <th className="py-3 pr-4">Department</th>
              <th className="py-3 pr-4">Type</th>
              <th className="py-3 pr-4">Updated</th>
              <th className="py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eef3ec]">
            {recentDocuments.map((document) => (
              <tr key={document.name} className="text-sm transition hover:bg-[#fbfdfb]">
                <td className="max-w-[24rem] py-3 pr-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border border-emerald-100 bg-emerald-50 text-[#2f6d25]">
                      <FileText size={15} />
                    </span>
                    <span className="truncate font-medium text-slate-800">{document.name}</span>
                  </div>
                </td>
                <td className="py-3 pr-4 text-slate-600">{document.department}</td>
                <td className="py-3 pr-4">
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${typeBadgeClass[document.type]}`}>
                    {document.type}
                  </span>
                </td>
                <td className="py-3 pr-4 text-slate-700">{document.updated}</td>
                <td className="py-3 text-right">
                  <button className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring" aria-label={`Actions for ${document.name}`}>
                    <MoreVertical size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </HomeCard>
  );
}

function PopularSearchesCard() {
  return (
    <HomeCard title="Popular Searches" viewLabel="See all">
      <div className="space-y-3 px-4 pb-4 sm:px-5">
        {popularSearches.map((search, index) => (
          <button key={search.term} className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 rounded-lg text-left transition hover:bg-[#fbfdfb] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#2f6d25] text-xs font-semibold text-white">
              {index + 1}
            </span>
            <span className="truncate text-sm text-slate-800">{search.term}</span>
            <span className="flex items-center gap-1 text-xs text-slate-500">
              <TrendingUp size={13} className="text-[#2f6d25]" />
              {search.count}
            </span>
          </button>
        ))}
      </div>
    </HomeCard>
  );
}

function ExpertsOnCallCard() {
  return (
    <HomeCard title="Experts on Call">
      <div className="divide-y divide-[#eef3ec] px-4 pb-3 sm:px-5">
        {expertsOnCall.map((expert) => (
          <div key={expert.name} className="flex items-center gap-3 py-3">
            <span className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full text-sm font-semibold ${softToneClass[expert.tone]}`}>
              {expert.initials}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-950">{expert.name}</p>
              <p className="truncate text-xs text-slate-500">{expert.role}</p>
              <p className="truncate text-xs text-slate-500">{expert.department}</p>
            </div>
            <div className="hidden items-center gap-2 sm:flex">
              <span className={`h-2 w-2 rounded-full ${statusToneClass[expert.status]}`} />
              <span className="text-xs text-slate-600">{expert.status}</span>
            </div>
            <button className="flex h-9 w-9 items-center justify-center rounded-xl border border-[#e5eee3] text-[#2f6d25] transition hover:bg-[#f6fbf5] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring" aria-label={`Contact ${expert.name}`}>
              <MessageSquare size={17} />
            </button>
          </div>
        ))}
        <p className="flex items-center gap-2 pt-3 text-xs text-slate-500">
          <Sparkles size={14} className="text-[#2f6d25]" />
          Need help? Ask AI to connect you.
        </p>
      </div>
    </HomeCard>
  );
}

function StatusFooter() {
  return (
    <p className="pb-1 text-center text-xs text-slate-500">
      CIAL Knowledge OS · Intelligent · Secure · Always Learning
    </p>
  );
}

export default function DashboardPage() {
  return (
    <div className="mx-auto flex w-full max-w-[96rem] flex-col gap-5" data-testid="dashboard-page">
      {/* TODO: Replace mock homepage arrays with user-personalized API data once backend endpoints are available. */}
      <AiHero />
      <QuickActionStrip />
      <div className="grid gap-5 lg:grid-cols-3">
        <ContinueWorkingCard />
        <RecommendedCard />
        <KnowledgeUpdatesCard />
      </div>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(19rem,0.85fr)_minmax(21rem,1.25fr)]">
        <RecentDocumentsTable />
        <PopularSearchesCard />
        <ExpertsOnCallCard />
      </div>
      <StatusFooter />
    </div>
  );
}
