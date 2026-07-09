import * as React from 'react';
import { useEffect } from 'react';
import { Link, useLocation } from 'wouter';
import { Bell, HelpCircle, MessageSquarePlus, Settings2, X, Search } from 'lucide-react';
import { THEME } from '@/config/themeConfig';
import { CURRENT_USER } from '@/config/userConfig';
import { homeNavItems } from '@/data/homePageData';
import { useCommandPalette } from '@/components/common/CommandPalette';

interface MobileSidebarDrawerProps {
  open: boolean;
  onClose: () => void;
}

const ASSISTANT_CONTEXT_STORAGE_KEY = 'cial-assistant-selected-context';
const ASSISTANT_NEW_SESSION_PENDING_STORAGE_KEY = 'cial-new-conversation-pending';
const NEW_CONVERSATION_EVENT = 'cial-new-conversation';

export default function MobileSidebarDrawer({ open, onClose }: MobileSidebarDrawerProps) {
  const [location] = useLocation();
  const { setOpen } = useCommandPalette();

  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  useEffect(() => {
    onClose();
  }, [location]);

  if (!open) return null;

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
    <div className="fixed inset-0 z-50 flex lg:hidden">
      <div className="absolute inset-0 bg-black/35 backdrop-blur-sm" onClick={onClose} data-testid="sidebar-overlay" />
      <aside className="relative flex h-full w-[min(19rem,86vw)] flex-col bg-white shadow-2xl animate-in slide-in-from-left duration-200" data-testid="mobile-sidebar">
        <div className="flex items-center justify-between border-b border-[#e3e9e1] px-4 py-4">
          <div className="flex items-center gap-3">
            <img src={THEME.logoPath} alt="CIAL Logo" className="h-9 w-auto object-contain" />
            <div>
              <div className="text-lg font-semibold text-[#25611f]">CIAL</div>
              <div className="text-xs text-slate-500">Knowledge OS</div>
            </div>
          </div>
          <button onClick={onClose} className="ce-icon-button" data-testid="button-close-sidebar" aria-label="Close sidebar">
            <X size={18} />
          </button>
        </div>

        <nav className="scrollbar-soft flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {primaryNavItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.label, item.path);
            const isHome = item.label === 'Home';

            return (
              <React.Fragment key={item.label}>
                <Link
                  href={item.path}
                  className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
                    active ? 'bg-[#edf6e9] text-[#244f1d]' : 'text-slate-700 hover:bg-[#f6f8f5] hover:text-slate-950'
                  }`}
                >
                  <Icon size={18} className={active ? 'text-[#2f6d25]' : 'text-slate-500'} />
                  <span>{item.label}</span>
                </Link>

                {isHome && (
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      setOpen(true);
                    }}
                    className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-slate-700 transition hover:bg-[#f6f8f5] hover:text-slate-950 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  >
                    <Search size={18} className="text-slate-500" />
                    <span>Search</span>
                    <span className="ml-auto text-[10px] text-slate-400 font-mono">Ctrl+K</span>
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
            className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold text-slate-900"
            aria-label="Start a new conversation"
          >
            <MessageSquarePlus size={18} className="text-[#2f6d25]" />
            New Conversation
          </Link>
          <button className="relative flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-slate-700 transition hover:bg-[#f6f8f5]">
            <Bell size={18} className="text-slate-500" />
            <span>Notifications</span>
            {(CURRENT_USER.notificationsCount ?? 0) > 0 && (
              <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-[#b76a09] px-1 text-[10px] font-bold text-white">{CURRENT_USER.notificationsCount}</span>
            )}
          </button>
          <button className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-slate-700 transition hover:bg-[#f6f8f5]">
            <HelpCircle size={18} className="text-slate-500" />
            <span>Help</span>
          </button>
          <button className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-slate-700 transition hover:bg-[#f6f8f5]">
            <Settings2 size={18} className="text-slate-500" />
            <span>Theme & Settings</span>
          </button>
          <div className="flex min-w-0 items-center gap-3 rounded-xl px-3 py-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#25611f] text-sm font-bold text-white">{CURRENT_USER.initials}</div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-slate-950">{CURRENT_USER.name}</div>
              <div className="truncate text-xs text-slate-500">{CURRENT_USER.department}</div>
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}
