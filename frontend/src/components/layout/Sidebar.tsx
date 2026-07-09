import * as React from 'react';
import { Link, useLocation } from 'wouter';
import { Bell, ChevronDown, HelpCircle, History, MessageSquarePlus, Settings2, Search } from 'lucide-react';
import { THEME } from '@/config/themeConfig';
import { CURRENT_USER } from '@/config/userConfig';
import { homeNavItems } from '@/data/homePageData';
import { useCommandPalette } from '@/components/common/CommandPalette';
import { Kbd } from '@/components/ui/kbd';
import {
  ASSISTANT_HISTORY_SIDEBAR_VISIBILITY_EVENT,
  readAssistantHistorySidebarOpen,
  requestAssistantHistorySidebarOpen,
} from '@/lib/assistantHistorySidebar';

const ASSISTANT_CONTEXT_STORAGE_KEY = 'cial-assistant-selected-context';
const ASSISTANT_NEW_SESSION_PENDING_STORAGE_KEY = 'cial-new-conversation-pending';
const NEW_CONVERSATION_EVENT = 'cial-new-conversation';

export default function Sidebar() {
  const [location] = useLocation();
  const { setOpen } = useCommandPalette();
  const [assistantHistoryOpen, setAssistantHistoryOpen] = React.useState(readAssistantHistorySidebarOpen);

  React.useEffect(() => {
    const handleHistoryVisibilityChange = (event: Event) => {
      const detail = (event as CustomEvent<{ open?: boolean }>).detail;
      setAssistantHistoryOpen(typeof detail?.open === 'boolean' ? detail.open : readAssistantHistorySidebarOpen());
    };

    window.addEventListener(ASSISTANT_HISTORY_SIDEBAR_VISIBILITY_EVENT, handleHistoryVisibilityChange);
    return () => window.removeEventListener(ASSISTANT_HISTORY_SIDEBAR_VISIBILITY_EVENT, handleHistoryVisibilityChange);
  }, []);

  const isAssistantRoute = location.startsWith('/assistant');
  const showHistoryShortcut = isAssistantRoute && !assistantHistoryOpen;

  const isActive = (label: string, path: string) => {
    if (label === 'Conversations') return false;
    if (path === '/') return location === '/';
    if (path === '/knowledge-center') {
      return location.startsWith('/knowledge-center') || location.startsWith('/knowledge/document') || location === '/documents' || location === '/knowledge' || location === '/policies';
    }
    if (path === '/workspace') return location === '/workspace' || location.startsWith('/workspace/');
    if (path === '/saved-knowledge') return location === '/saved-knowledge' || location === '/workspace/bookmarks';
    return location.startsWith(path);
  };

  const startNewConversation = () => {
    window.localStorage.removeItem(ASSISTANT_CONTEXT_STORAGE_KEY);
    window.localStorage.setItem(ASSISTANT_NEW_SESSION_PENDING_STORAGE_KEY, String(Date.now()));
    window.dispatchEvent(new Event(NEW_CONVERSATION_EVENT));
  };

  const primaryNavItems = homeNavItems.filter((item) => item.label !== 'Conversations');

  return (
    <aside
      className="fixed left-0 top-0 z-30 hidden h-dvh w-60 flex-col border-r border-[#e3e9e1] bg-white/95 backdrop-blur lg:flex"
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
        {primaryNavItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.label, item.path);
          const isHome = item.label === 'Home';

          return (
            <React.Fragment key={item.label}>
              <Link
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

              {isHome && (
                <button
                  type="button"
                  onClick={() => setOpen(true)}
                  className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-slate-700 transition hover:bg-[#f6f8f5] hover:text-slate-950 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  data-testid="nav-search"
                >
                  <Search size={18} className="text-slate-500" />
                  <span className="truncate">Search</span>
                  <Kbd className="ml-auto text-[10px] text-slate-400 bg-slate-100 border border-slate-200">Ctrl+K</Kbd>
                </button>
              )}

              {showHistoryShortcut && item.label === 'AI Assistant' && (
                <button
                  type="button"
                  onClick={requestAssistantHistorySidebarOpen}
                  className="ml-11 mt-1 inline-flex h-8 items-center gap-1.5 rounded-full border border-[#dbe5d7] bg-[#f7faf4] px-2.5 text-xs font-medium text-slate-700 transition hover:border-[#cddbc7] hover:bg-[#eef5e8] hover:text-slate-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  data-testid="button-sidebar-open-history"
                  aria-label="Reopen conversation history"
                  title="History"
                >
                  <History size={13} className="text-[#2f6d25]" />
                  <span>History</span>
                </button>
              )}
            </React.Fragment>
          );
        })}
      </nav>

      <div className="space-y-1 border-t border-[#e8ece6] p-3">
        <Link
          href="/assistant"
          onClick={startNewConversation}
          className="flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold text-slate-900 transition hover:bg-[#f6f8f5] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          aria-label="Start a new conversation"
        >
          <MessageSquarePlus size={18} className="text-[#2f6d25]" />
          <span>New Conversation</span>
        </Link>
        <button className="relative flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-slate-700 transition hover:bg-[#f6f8f5] hover:text-slate-950" aria-label="Notifications" title="Notifications" data-testid="button-notifications">
          <Bell size={18} className="text-slate-500" />
          <span>Notifications</span>
          {(CURRENT_USER.notificationsCount ?? 0) > 0 && (
            <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-[#b76a09] px-1 text-[10px] font-bold text-white" data-testid="notification-badge">{CURRENT_USER.notificationsCount}</span>
          )}
        </button>
        <button className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-slate-700 transition hover:bg-[#f6f8f5] hover:text-slate-950" aria-label="Help" title="Help" data-testid="button-help">
          <HelpCircle size={18} className="text-slate-500" />
          <span>Help</span>
        </button>
        <button className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-slate-700 transition hover:bg-[#f6f8f5] hover:text-slate-950" aria-label="Theme and settings" title="Theme and settings">
          <Settings2 size={18} className="text-slate-500" />
          <span>Theme & Settings</span>
        </button>
        <button
          className="flex w-full min-w-0 items-center gap-3 rounded-xl px-3 py-3 text-left transition-colors hover:bg-[#f6f8f5] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          data-testid="button-user-profile"
          aria-label="Open user menu"
          title="User menu"
        >
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-[#25611f] text-sm font-bold text-white shadow-sm">
            {CURRENT_USER.initials}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold leading-tight text-slate-950" data-testid="text-username">{CURRENT_USER.name}</div>
            <div className="truncate text-xs leading-tight text-slate-500" data-testid="text-department">{CURRENT_USER.department}</div>
          </div>
          <ChevronDown size={14} className="text-muted-foreground" />
        </button>
      </div>
    </aside>
  );
}
