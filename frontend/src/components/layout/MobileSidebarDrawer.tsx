import * as React from 'react';
import { Link, useLocation } from 'wouter';
import { Bell, HelpCircle, LogOut, MessageSquarePlus, X, Search } from 'lucide-react';
import { THEME } from '@/config/themeConfig';
import { useAuth } from '@/auth/AuthContext';
import { homeNavItems } from '@/data/homePageData';
import { useCommandPalette } from '@/components/common/CommandPalette';
import { startNewConversation } from '@/lib/assistantNavigation';
import AppearanceToggle from '@/components/theme/AppearanceToggle';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from '@/components/ui/sheet';

interface MobileSidebarDrawerProps {
  open: boolean;
  onClose: () => void;
  returnFocusRef: React.RefObject<HTMLButtonElement | null>;
}

export default function MobileSidebarDrawer({ open, onClose, returnFocusRef }: MobileSidebarDrawerProps) {
  const [location, navigate] = useLocation();
  const { setOpen } = useCommandPalette();
  const { logout, userView } = useAuth();
  const searchHandoffPending = React.useRef(false);

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
    <Sheet open={open} onOpenChange={(nextOpen) => { if (!nextOpen) onClose(); }}>
      <SheetContent
        side="left"
        showCloseButton={false}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          if (searchHandoffPending.current) {
            searchHandoffPending.current = false;
            window.requestAnimationFrame(() => setOpen(true));
            return;
          }
          window.requestAnimationFrame(() => returnFocusRef.current?.focus());
        }}
        className="flex h-full w-[min(19rem,86vw)] flex-col gap-0 border-r border-sidebar-border bg-sidebar p-0 text-sidebar-foreground shadow-2xl sm:max-w-[19rem]"
        data-testid="mobile-sidebar"
        aria-label="Global application navigation"
      >
        <SheetTitle className="sr-only">Global application navigation</SheetTitle>
        <SheetDescription className="sr-only">Navigate CIAL Knowledge OS on a compact screen.</SheetDescription>
        <div className="flex items-center justify-between border-b border-sidebar-border px-4 py-4">
          <div className="flex items-center gap-3">
            <img src={THEME.logoPath} alt="CIAL Logo" className="h-9 w-auto object-contain" />
            <div>
              <div className="brand-wordmark text-lg font-semibold text-primary">CIAL</div>
              <div className="text-xs text-muted-foreground">Knowledge OS</div>
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
                  onClick={(event) => {
                    onClose();
                    if (item.label === 'AI Assistant') {
                      event.preventDefault();
                      startNewConversation(navigate);
                    }
                  }}
                  className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
                    active ? 'bg-sidebar-accent text-sidebar-accent-foreground' : 'text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
                  }`}
                  aria-current={active ? 'page' : undefined}
                >
                  <Icon size={18} className={active ? 'text-primary' : 'text-muted-foreground'} />
                  <span>{item.label}</span>
                </Link>

                {isHome && (
                  <button
                    type="button"
                    onClick={() => {
                      searchHandoffPending.current = true;
                      onClose();
                    }}
                    className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-medium text-sidebar-foreground/80 transition hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  >
                    <Search size={18} className="text-muted-foreground" />
                    <span>Search</span>
                    <span className="ml-auto font-mono text-[10px] text-muted-foreground">Ctrl+K</span>
                  </button>
                )}
              </React.Fragment>
            );
          })}
        </nav>

        <div className="space-y-1 border-t border-sidebar-border p-3">
          <Link
            href="/assistant/new"
            onClick={(event) => {
              event.preventDefault();
              onClose();
              startNewConversation(navigate);
            }}
            className="sidebar-utility-action flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold text-foreground hover:bg-sidebar-accent"
            aria-label="Start a new conversation"
          >
            <MessageSquarePlus size={18} className="sidebar-utility-icon text-primary" />
            New Conversation
          </Link>
          <button className="relative flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-sidebar-foreground/80 transition hover:bg-sidebar-accent">
            <Bell size={18} className="text-muted-foreground" />
            <span>Notifications</span>
            {(userView?.notificationsCount ?? 0) > 0 && (
              <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-warning px-1 text-[10px] font-bold text-black">{userView?.notificationsCount}</span>
            )}
          </button>
          <button className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-sidebar-foreground/80 transition hover:bg-sidebar-accent">
            <HelpCircle size={18} className="text-muted-foreground" />
            <span>Help</span>
          </button>
          <AppearanceToggle variant="mobile" />
          <div className="flex min-w-0 items-center gap-3 rounded-xl px-3 py-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">{userView?.initials ?? 'CU'}</div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-foreground">{userView?.name ?? 'CIAL User'}</div>
              <div className="truncate text-xs text-muted-foreground">{userView?.department ?? 'CIAL'}</div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              onClose();
              void logout();
            }}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-sidebar-foreground/80 transition hover:bg-sidebar-accent"
          >
            <LogOut size={18} className="text-muted-foreground" />
            <span>Log Out</span>
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
