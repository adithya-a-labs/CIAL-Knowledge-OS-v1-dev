import * as React from 'react';
import { useEffect } from 'react';
import { Link, useLocation } from 'wouter';
import { Bell, HelpCircle, LogOut, MessageSquarePlus, Settings2, X, Search } from 'lucide-react';
import { THEME } from '@/config/themeConfig';
import { useAuth } from '@/auth/AuthContext';
import { homeNavItems } from '@/data/homePageData';
import { useCommandPalette } from '@/components/common/CommandPalette';
import { startNewConversation } from '@/lib/assistantNavigation';

interface MobileSidebarDrawerProps {
  open: boolean;
  onClose: () => void;
}

export default function MobileSidebarDrawer({ open, onClose }: MobileSidebarDrawerProps) {
  const [location, navigate] = useLocation();
  const { setOpen } = useCommandPalette();
  const { logout, userView } = useAuth();
  const drawerRef = React.useRef<HTMLElement>(null);
  const closeButtonRef = React.useRef<HTMLButtonElement>(null);
  const previousFocusRef = React.useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (open) {
      previousFocusRef.current = document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
      window.requestAnimationFrame(() => closeButtonRef.current?.focus());
    }
    document.body.style.overflow = open ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
      if (open) previousFocusRef.current?.focus();
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !drawerRef.current) return;
      const focusable = Array.from(
        drawerRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => element.getClientRects().length > 0);
      const first = focusable[0];
      const last = focusable.at(-1);
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose, open]);

  useEffect(() => {
    onClose();
  }, [location]);

  if (!open) return null;

  const isActive = (label: string, path: string) => {
    if (label === 'Conversations') return false;
    if (label === 'AI Assistant') return location.startsWith('/assistant');
    if (path === '/') return location === '/';
    if (path === '/knowledge-center') {
      return location.startsWith('/knowledge-center') || location.startsWith('/knowledge/document') || location === '/documents' || location === '/knowledge' || location === '/policies';
    }
    if (path === '/workspace') return location === '/workspace' || location.startsWith('/workspace/');
    if (path === '/saved-knowledge') return location === '/saved-knowledge' || location === '/workspace/bookmarks';
    return location.startsWith(path);
  };

  const primaryNavItems = homeNavItems.filter((item) => item.label !== 'Conversations');

  return (
    <div className="fixed inset-0 z-50 flex lg:hidden">
      <div className="absolute inset-0 bg-black/35 backdrop-blur-sm" onClick={onClose} data-testid="sidebar-overlay" />
      <aside
        ref={drawerRef}
        className="relative flex h-full w-[min(19rem,86vw)] flex-col bg-white shadow-2xl animate-in slide-in-from-left duration-200"
        data-testid="mobile-sidebar"
        role="dialog"
        aria-modal="true"
        aria-label="Global application navigation"
      >
        <div className="flex items-center justify-between border-b border-[#e3e9e1] px-4 py-4">
          <div className="flex items-center gap-3">
            <img src={THEME.logoPath} alt="CIAL Logo" className="h-9 w-auto object-contain" />
            <div>
              <div className="text-lg font-semibold text-[#25611f]">CIAL</div>
              <div className="text-xs text-slate-500">Knowledge OS</div>
            </div>
          </div>
          <button ref={closeButtonRef} onClick={onClose} className="ce-icon-button" data-testid="button-close-sidebar" aria-label="Close sidebar">
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
                  onClick={(event) => {
                    if (item.label !== 'AI Assistant') return;
                    event.preventDefault();
                    onClose();
                    startNewConversation(navigate);
                  }}
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
            href="/assistant/new"
            onClick={(event) => {
              event.preventDefault();
              onClose();
              startNewConversation(navigate);
            }}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold text-slate-900"
            aria-label="Start a new conversation"
          >
            <MessageSquarePlus size={18} className="text-[#2f6d25]" />
            New Conversation
          </Link>
          <button className="relative flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-slate-700 transition hover:bg-[#f6f8f5]">
            <Bell size={18} className="text-slate-500" />
            <span>Notifications</span>
            {(userView?.notificationsCount ?? 0) > 0 && (
              <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-[#b76a09] px-1 text-[10px] font-bold text-white">{userView?.notificationsCount}</span>
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
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#25611f] text-sm font-bold text-white">{userView?.initials ?? 'CU'}</div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-slate-950">{userView?.name ?? 'CIAL User'}</div>
              <div className="truncate text-xs text-slate-500">{userView?.department ?? 'CIAL'}</div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void logout()}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-slate-700 transition hover:bg-[#f6f8f5]"
          >
            <LogOut size={18} className="text-slate-500" />
            <span>Log Out</span>
          </button>
        </div>
      </aside>
    </div>
  );
}
