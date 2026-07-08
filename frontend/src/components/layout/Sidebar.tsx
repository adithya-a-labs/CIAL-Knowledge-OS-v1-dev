import { Link, useLocation } from 'wouter';
import { ChevronLeft, HelpCircle, MessageSquare, Settings, Sparkles, Sun } from 'lucide-react';
import { THEME } from '@/config/themeConfig';
import { homeNavItems } from '@/data/homePageData';

export default function Sidebar() {
  const [location] = useLocation();

  const isActive = (label: string, path: string) => {
    if (label === 'Conversations') return false;
    if (path === '/') return location === '/';
    if (path === '/knowledge-center') {
      return location.startsWith('/knowledge-center') || location === '/documents' || location === '/knowledge' || location === '/policies';
    }
    if (path === '/workspace') return location === '/workspace';
    return location.startsWith(path);
  };

  return (
    <aside
      className="fixed left-0 top-0 z-30 hidden h-dvh w-60 flex-col border-r border-[#e3e9e1] bg-white/95 shadow-[8px_0_40px_-36px_rgba(15,23,42,0.55)] backdrop-blur lg:flex"
      data-testid="sidebar"
    >
      <div className="flex min-h-20 items-center gap-3 px-5 py-4">
        <img
          src={THEME.logoPath}
          alt="CIAL Logo"
          className="h-10 w-auto object-contain"
          data-testid="sidebar-logo"
        />
        <div>
          <div className="text-xl font-semibold leading-tight text-[#25611f]">CIAL</div>
          <div className="text-xs leading-tight text-slate-500">Knowledge OS</div>
        </div>
      </div>

      <nav className="scrollbar-soft flex-1 space-y-1 overflow-y-auto px-3 py-3" data-testid="sidebar-nav">
        {homeNavItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.label, item.path);

          return (
            <Link
              key={item.label}
              href={item.path}
              className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
                active
                  ? 'bg-[#edf6e9] text-[#244f1d] shadow-[inset_0_0_0_1px_rgba(47,109,37,0.06)]'
                  : 'text-slate-700 hover:bg-[#f6f8f5] hover:text-slate-950'
              }`}
              data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <Icon size={18} className={active ? 'text-[#2f6d25]' : 'text-slate-500'} />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="space-y-4 p-4">
        <div className="rounded-2xl border border-[#e3e9e1] bg-white p-4 shadow-[0_14px_34px_-28px_rgba(15,23,42,0.45)]">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-950">
            <Sparkles size={16} className="text-[#2f6d25]" />
            Ask CIAL Anything
          </div>
          <p className="text-xs leading-5 text-slate-500">Your AI knowledge assistant that knows everything.</p>
          <Link
            href="/assistant"
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-[#edf6e9] px-3 py-2.5 text-sm font-semibold text-[#24551f] transition hover:bg-[#dcefd6] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          >
            <MessageSquare size={16} />
            New Conversation
          </Link>
        </div>

        <div className="flex items-center justify-between px-1 text-slate-500">
          <button className="ce-icon-button" aria-label="Theme">
            <Sun size={17} />
          </button>
          <button className="ce-icon-button" aria-label="Help">
            <HelpCircle size={17} />
          </button>
          <button className="ce-icon-button" aria-label="Settings">
            <Settings size={17} />
          </button>
          <button className="ce-icon-button" aria-label="Collapse sidebar">
            <ChevronLeft size={17} />
          </button>
        </div>
      </div>
    </aside>
  );
}
