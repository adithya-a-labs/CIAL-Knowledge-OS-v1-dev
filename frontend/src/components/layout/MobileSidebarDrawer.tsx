import { useEffect } from 'react';
import { Link, useLocation } from 'wouter';
import { Bell, HelpCircle, MessageSquare, Settings, Sparkles, X } from 'lucide-react';
import { THEME } from '@/config/themeConfig';
import { CURRENT_USER } from '@/config/userConfig';
import { homeNavItems } from '@/data/homePageData';

interface MobileSidebarDrawerProps {
  open: boolean;
  onClose: () => void;
}

const ASSISTANT_CONTEXT_STORAGE_KEY = 'cial-assistant-selected-context';
const NEW_CONVERSATION_EVENT = 'cial-new-conversation';

export default function MobileSidebarDrawer({ open, onClose }: MobileSidebarDrawerProps) {
  const [location] = useLocation();

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
      return location.startsWith('/knowledge-center') || location === '/documents' || location === '/knowledge' || location === '/policies';
    }
    if (path === '/workspace') return location === '/workspace';
    return location.startsWith(path);
  };

  const startNewConversation = () => {
    window.localStorage.removeItem(ASSISTANT_CONTEXT_STORAGE_KEY);
    window.dispatchEvent(new Event(NEW_CONVERSATION_EVENT));
  };

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
          {homeNavItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.label, item.path);

            return (
              <Link
                key={item.label}
                href={item.path}
                className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
                  active ? 'bg-[#edf6e9] text-[#244f1d]' : 'text-slate-700 hover:bg-[#f6f8f5] hover:text-slate-950'
                }`}
              >
                <Icon size={18} className={active ? 'text-[#2f6d25]' : 'text-slate-500'} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-4">
          <div className="rounded-2xl border border-[#e3e9e1] bg-white p-4 shadow-sm">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-950">
              <Sparkles size={16} className="text-[#2f6d25]" />
              Ask CIAL Anything
            </div>
            <p className="text-xs leading-5 text-slate-500">Your AI knowledge assistant that knows everything.</p>
            <Link
              href="/assistant"
              onClick={startNewConversation}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-[#edf6e9] px-3 py-2.5 text-sm font-semibold text-[#24551f]"
              aria-label="Start a new conversation"
            >
              <MessageSquare size={16} />
              New Conversation
            </Link>
          </div>
          <div className="mt-3 rounded-2xl border border-[#e3e9e1] bg-white p-3 shadow-sm">
            <div className="flex min-w-0 items-center gap-3 rounded-xl p-2">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#25611f] text-sm font-bold text-white">{CURRENT_USER.initials}</div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-slate-950">{CURRENT_USER.name}</div>
                <div className="truncate text-xs text-slate-500">{CURRENT_USER.department}</div>
              </div>
            </div>
            <div className="mt-2 flex items-center justify-between px-1 text-slate-500">
              <button className="ce-icon-button" aria-label="Notifications" title="Notifications"><Bell size={17} /></button>
              <button className="ce-icon-button" aria-label="Help" title="Help"><HelpCircle size={17} /></button>
              <button className="ce-icon-button" aria-label="Settings" title="Settings"><Settings size={17} /></button>
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}
