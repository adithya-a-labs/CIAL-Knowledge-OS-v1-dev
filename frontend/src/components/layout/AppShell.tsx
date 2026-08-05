import { useEffect, useRef, useState } from 'react';
import { Menu } from 'lucide-react';
import { useLocation } from 'wouter';
import Sidebar from './Sidebar';
import MobileSidebarDrawer from './MobileSidebarDrawer';

const GLOBAL_NAV_COLLAPSED_STORAGE_KEY = 'cial-global-nav-collapsed';
const MOBILE_NAVIGATION_QUERY = '(max-width: 1023px)';

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobileViewport, setMobileViewport] = useState(
    () => window.matchMedia(MOBILE_NAVIGATION_QUERY).matches,
  );
  const [location] = useLocation();
  const mobileNavigationTriggerRef = useRef<HTMLButtonElement>(null);
  const isAssistantWorkspace = location.startsWith('/assistant');
  const isDocumentWorkspace = location.startsWith('/knowledge/document/');
  const isNotebookWorkspace = location.startsWith('/notebooks/') && location !== '/notebooks';
  const wasDocumentWorkspace = useRef(isDocumentWorkspace);
  const hasGlobalNavPreference = useRef(
    window.localStorage.getItem(GLOBAL_NAV_COLLAPSED_STORAGE_KEY) !== null,
  );
  const [globalNavCollapsed, setGlobalNavCollapsed] = useState(() => {
    const saved = window.localStorage.getItem(GLOBAL_NAV_COLLAPSED_STORAGE_KEY);
    return saved === null ? isDocumentWorkspace : saved === 'true';
  });

  useEffect(() => {
    if (
      isDocumentWorkspace
      && !wasDocumentWorkspace.current
      && !hasGlobalNavPreference.current
    ) {
      setGlobalNavCollapsed(true);
    }
    wasDocumentWorkspace.current = isDocumentWorkspace;
  }, [isDocumentWorkspace]);

  useEffect(() => {
    setMobileOpen(false);
  }, [location]);

  useEffect(() => {
    const mediaQuery = window.matchMedia(MOBILE_NAVIGATION_QUERY);
    const handleBreakpointChange = (event: MediaQueryListEvent) => {
      setMobileViewport(event.matches);
      if (!event.matches) setMobileOpen(false);
    };
    setMobileViewport(mediaQuery.matches);
    if (!mediaQuery.matches) setMobileOpen(false);
    mediaQuery.addEventListener('change', handleBreakpointChange);
    return () => mediaQuery.removeEventListener('change', handleBreakpointChange);
  }, []);

  const handleGlobalNavCollapsedChange = (collapsed: boolean) => {
    hasGlobalNavPreference.current = true;
    window.localStorage.setItem(GLOBAL_NAV_COLLAPSED_STORAGE_KEY, String(collapsed));
    setGlobalNavCollapsed(collapsed);
  };

  return (
    <div className="app-shell h-screen overflow-hidden">
      <Sidebar collapsed={globalNavCollapsed} onCollapsedChange={handleGlobalNavCollapsedChange} />
      <MobileSidebarDrawer
        open={mobileViewport && mobileOpen}
        onClose={() => setMobileOpen(false)}
        returnFocusRef={mobileNavigationTriggerRef}
      />
      <button
        ref={mobileNavigationTriggerRef}
        onClick={() => setMobileOpen(true)}
        className="fixed left-3 top-3 z-40 inline-flex min-h-8 min-w-8 items-center justify-center rounded-lg border border-border bg-popover/92 text-muted-foreground shadow-sm backdrop-blur transition hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring lg:hidden"
        data-testid="button-hamburger"
        aria-label="Open global navigation"
      >
        <Menu size={18} />
      </button>

      <div className={`flex h-screen min-w-0 flex-col overflow-hidden transition-[padding] duration-[var(--motion-duration-standard)] ease-[var(--motion-ease-move)] ${globalNavCollapsed ? 'lg:pl-16' : 'lg:pl-60'}`}>
        <main
          className={`flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-y-auto ${
            isAssistantWorkspace || isDocumentWorkspace || isNotebookWorkspace
              ? 'px-0 py-0'
              : 'app-content px-3 py-5 sm:px-5 md:px-7 lg:px-8 2xl:px-10'
          }`}
          data-testid="main-content"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
