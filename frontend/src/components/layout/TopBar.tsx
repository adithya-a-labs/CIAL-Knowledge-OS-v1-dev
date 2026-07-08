import { Bell, HelpCircle, ChevronDown, Menu } from 'lucide-react';
import { CURRENT_USER } from '@/config/userConfig';

interface TopBarProps {
  onMenuClick: () => void;
}

export default function TopBar({ onMenuClick }: TopBarProps) {
  return (
    <header
      className="sticky top-0 z-20 flex min-h-16 items-center justify-between border-b border-[#e3e9e1] bg-white/88 px-3 backdrop-blur-md sm:px-5"
      data-testid="topbar"
    >
      {/* Mobile hamburger */}
      <button
        onClick={onMenuClick}
        className="inline-flex min-h-8 min-w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-[#f6f8f5] hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring lg:!hidden"
        data-testid="button-hamburger"
        aria-label="Open sidebar"
      >
        <Menu size={20} />
      </button>

      {/* Desktop spacer */}
      <div className="hidden lg:block" />

      {/* Right side */}
      <div className="flex min-w-0 items-center gap-1.5 sm:gap-2">
        <button
          className="ce-icon-button relative"
          data-testid="button-notifications"
          aria-label="Notifications"
        >
          <Bell size={18} />
          {(CURRENT_USER.notificationsCount ?? 0) > 0 && (
            <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-[#b76a09] text-[9px] font-bold text-white" data-testid="notification-badge">
              {CURRENT_USER.notificationsCount}
            </span>
          )}
        </button>

        <button
          className="ce-icon-button"
          data-testid="button-help"
          aria-label="Help"
        >
          <HelpCircle size={18} />
        </button>

        {/* TODO: Replace static profile data with the authenticated user session. */}
        <button
          className="flex min-w-0 items-center gap-3 rounded-xl px-2 py-1.5 transition-colors hover:bg-[#f6f8f5] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring sm:px-3"
          data-testid="button-user-profile"
        >
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-[#25611f] text-sm font-bold text-white shadow-sm">
            {CURRENT_USER.initials}
          </div>
          <div className="hidden max-w-36 text-left sm:block md:max-w-44">
            <div className="text-sm font-semibold leading-tight text-slate-950" data-testid="text-username">{CURRENT_USER.name}</div>
            <div className="truncate text-xs leading-tight text-slate-500" data-testid="text-department">{CURRENT_USER.department}</div>
          </div>
          <ChevronDown size={14} className="hidden text-muted-foreground sm:block" />
        </button>
      </div>
    </header>
  );
}
