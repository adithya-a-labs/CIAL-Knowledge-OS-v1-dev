import { useState } from 'react';
import { Menu } from 'lucide-react';
import { useLocation } from 'wouter';
import Sidebar from './Sidebar';
import MobileSidebarDrawer from './MobileSidebarDrawer';

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [location] = useLocation();
  const isAssistantWorkspace = location.startsWith('/assistant');

  return (
    <div className="app-shell h-screen overflow-hidden">
      <Sidebar />
      <MobileSidebarDrawer open={mobileOpen} onClose={() => setMobileOpen(false)} />
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed left-3 top-3 z-40 inline-flex min-h-8 min-w-8 items-center justify-center rounded-lg border border-[#dce4d8] bg-white/92 text-slate-500 shadow-sm backdrop-blur transition hover:bg-[#f6f8f5] hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring lg:hidden"
        data-testid="button-hamburger"
        aria-label="Open sidebar"
      >
        <Menu size={18} />
      </button>

      <div className="flex h-screen min-w-0 flex-col overflow-hidden transition-[padding] duration-200 ease-out lg:pl-60">
        <main
          className={`flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-y-auto ${
            isAssistantWorkspace
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
