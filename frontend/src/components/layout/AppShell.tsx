import { useState } from 'react';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import MobileSidebarDrawer from './MobileSidebarDrawer';

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="app-shell h-screen overflow-hidden">
      <Sidebar />
      <MobileSidebarDrawer open={mobileOpen} onClose={() => setMobileOpen(false)} />

      <div className="flex h-screen min-w-0 flex-col overflow-hidden transition-[padding] duration-200 ease-out lg:pl-60">
        <TopBar onMenuClick={() => setMobileOpen(true)} />
        <main className="app-content flex min-h-0 w-full min-w-0 flex-1 flex-col overflow-y-auto px-3 py-5 sm:px-5 md:px-7 lg:px-8 2xl:px-10" data-testid="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}
