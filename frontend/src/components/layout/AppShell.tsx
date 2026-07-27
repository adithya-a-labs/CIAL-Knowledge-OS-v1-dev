import { useEffect, useRef, useState } from 'react';
import { Menu } from 'lucide-react';
import { useLocation } from 'wouter';
import Sidebar from './Sidebar';
import MobileSidebarDrawer from './MobileSidebarDrawer';

const GLOBAL_NAV_COLLAPSED_STORAGE_KEY = 'cial-global-nav-collapsed';

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [location] = useLocation();
  const isAssistantWorkspace = location.startsWith('/assistant');
  const isDocumentWorkspace = location.startsWith('/knowledge/document/');
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

  const handleGlobalNavCollapsedChange = (collapsed: boolean) => {
    hasGlobalNavPreference.current = true;
    window.localStorage.setItem(GLOBAL_NAV_COLLAPSED_STORAGE_KEY, String(collapsed));
    setGlobalNavCollapsed(collapsed);
  };

  return (
    <div className="app-shell h-screen overflow-hidden">
      <Sidebar collapsed={globalNavCollapsed} onCollapsedChange={handleGlobalNavCollapsedChange} />
      <MobileSidebarDrawer open={mobileOpen} onClose={() => setMobileOpen(false)} />
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed left-3 top-3 z-40 inline-flex min-h-8 min-w-8 items-center justify-center rounded-lg border border-border bg-popover/92 text-muted-foreground shadow-sm backdrop-blur transition hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring lg:hidden"
        data-testid="button-hamburger"
        aria-label="Open global navigation"
      >
        <Menu size={18} />
      </button>

      <div className={`flex h-screen min-w-0 flex-col overflow-hidden transition-[padding] duration-200 ease-out ${globalNavCollapsed ? 'lg:pl-16' : 'lg:pl-60'}`}>
        <main
          className={`flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-y-auto ${
            isAssistantWorkspace || isDocumentWorkspace
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
