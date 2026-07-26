import * as React from 'react';
import { Link, useLocation } from 'wouter';
import {
  Activity,
  Bell,
  ChevronDown,
  HelpCircle,
  History,
  LogOut,
  MessageSquarePlus,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings2,
} from 'lucide-react';
import { THEME } from '@/config/themeConfig';
import { useAuth } from '@/auth/AuthContext';
import { homeNavItems } from '@/data/homePageData';
import { useCommandPalette } from '@/components/common/CommandPalette';
import { Kbd } from '@/components/ui/kbd';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  ASSISTANT_HISTORY_SIDEBAR_VISIBILITY_EVENT,
  readAssistantHistorySidebarOpen,
  requestAssistantHistorySidebarOpen,
} from '@/lib/assistantHistorySidebar';
import { startNewConversation } from '@/lib/assistantNavigation';

interface SidebarProps {
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
}

function RailTooltip({
  collapsed,
  label,
  children,
}: {
  collapsed: boolean;
  label: string;
  children: React.ReactElement;
}) {
  if (!collapsed) return children;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent side="right" sideOffset={10}>{label}</TooltipContent>
    </Tooltip>
  );
}

export default function Sidebar({ collapsed, onCollapsedChange }: SidebarProps) {
  const [location, navigate] = useLocation();
  const { setOpen } = useCommandPalette();
  const { logout, userView, user } = useAuth();
  const [assistantHistoryOpen, setAssistantHistoryOpen] = React.useState(readAssistantHistorySidebarOpen);

  React.useEffect(() => {
    const handleHistoryVisibilityChange = (event: Event) => {
      const detail = (event as CustomEvent<{ open?: boolean }>).detail;
      setAssistantHistoryOpen(typeof detail?.open === 'boolean' ? detail.open : readAssistantHistorySidebarOpen());
    };
    window.addEventListener(ASSISTANT_HISTORY_SIDEBAR_VISIBILITY_EVENT, handleHistoryVisibilityChange);
    return () => window.removeEventListener(ASSISTANT_HISTORY_SIDEBAR_VISIBILITY_EVENT, handleHistoryVisibilityChange);
  }, []);

  const isActive = (label: string, path: string) => {
    if (label === 'Conversations') return false;
    if (label === 'AI Assistant') return location.startsWith('/assistant');
    if (path === '/') return location === '/';
    if (path === '/knowledge-center') {
      return location.startsWith('/knowledge-center')
        || location.startsWith('/knowledge/document')
        || location === '/documents'
        || location === '/knowledge'
        || location === '/policies';
    }
    if (path === '/workspace') return location === '/workspace' || location.startsWith('/workspace/');
    if (path === '/saved-knowledge') return location === '/saved-knowledge' || location === '/workspace/bookmarks';
    return location.startsWith(path);
  };

  const primaryNavItems = homeNavItems.filter((item) => item.label !== 'Conversations');
  const isAssistantRoute = location.startsWith('/assistant');
  const showHistoryShortcut = isAssistantRoute && !assistantHistoryOpen && !collapsed;
  const canMonitorSystem = Boolean(
    user?.permission_names.some((permission) => ['monitor_system', 'manage_settings'].includes(permission)),
  );
  const itemLayout = collapsed ? 'justify-center px-0' : 'gap-3 px-3';
  const focusRing = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2f6d25] focus-visible:ring-offset-2';

  return (
    <aside
      className={`fixed left-0 top-0 z-30 hidden h-dvh flex-col overflow-hidden border-r border-[#e3e9e1] bg-white/95 backdrop-blur transition-[width] duration-200 ease-out lg:flex ${
        collapsed ? 'w-16' : 'w-60'
      }`}
      data-testid="sidebar"
      data-collapsed={collapsed}
      aria-label="Global application navigation"
    >
      <div className={`flex h-16 shrink-0 items-center ${collapsed ? 'justify-center px-2' : 'gap-3 px-5'}`}>
        <img
          src={THEME.logoPath}
          alt="CIAL Logo"
          className={collapsed ? 'h-9 w-9 object-contain' : 'h-10 w-auto object-contain'}
          data-testid="sidebar-logo"
        />
        {!collapsed && (
          <div>
            <div className="text-xl font-semibold leading-tight text-[#25611f]">CIAL</div>
            <div className="text-xs leading-tight text-slate-500">Knowledge OS</div>
          </div>
        )}
      </div>

      <nav className={`scrollbar-soft min-h-0 flex-1 space-y-1 overflow-y-auto py-2 ${collapsed ? 'px-2' : 'px-3'}`} data-testid="sidebar-nav">
        {primaryNavItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.label, item.path);
          return (
            <React.Fragment key={item.label}>
              <RailTooltip collapsed={collapsed} label={item.label}>
                <Link
                  href={item.path}
                  onClick={(event) => {
                    if (item.label !== 'AI Assistant') return;
                    event.preventDefault();
                    startNewConversation(navigate);
                  }}
                  className={`flex h-11 items-center rounded-xl text-sm font-medium transition-colors ${focusRing} ${itemLayout} ${
                    active
                      ? 'bg-[#edf6e9] text-[#244f1d] shadow-[inset_0_0_0_1px_rgba(47,109,37,0.06)]'
                      : 'text-slate-700 hover:bg-[#f6f8f5] hover:text-slate-950'
                  }`}
                  data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, '-')}`}
                  aria-label={item.label}
                  aria-current={active ? 'page' : undefined}
                >
                  <Icon size={19} className={active ? 'text-[#2f6d25]' : 'text-slate-500'} />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </Link>
              </RailTooltip>

              {item.label === 'Home' && (
                <RailTooltip collapsed={collapsed} label="Search">
                  <button
                    type="button"
                    onClick={() => setOpen(true)}
                    className={`flex h-11 w-full items-center rounded-xl text-sm font-medium text-slate-700 transition-colors hover:bg-[#f6f8f5] hover:text-slate-950 ${focusRing} ${itemLayout}`}
                    data-testid="nav-search"
                    aria-label="Search"
                  >
                    <Search size={19} className="text-slate-500" />
                    {!collapsed && (
                      <>
                        <span className="truncate">Search</span>
                        <Kbd className="ml-auto border border-slate-200 bg-slate-100 text-[10px] text-slate-400">Ctrl+K</Kbd>
                      </>
                    )}
                  </button>
                </RailTooltip>
              )}

              {showHistoryShortcut && item.label === 'AI Assistant' && (
                <button
                  type="button"
                  onClick={requestAssistantHistorySidebarOpen}
                  className={`ml-11 mt-1 inline-flex h-8 items-center gap-1.5 rounded-full border border-[#dbe5d7] bg-[#f7faf4] px-2.5 text-xs font-medium text-slate-700 transition-colors hover:border-[#cddbc7] hover:bg-[#eef5e8] hover:text-slate-950 ${focusRing}`}
                  data-testid="button-sidebar-open-history"
                  aria-label="Reopen conversation history"
                >
                  <History size={13} className="text-[#2f6d25]" />
                  <span>History</span>
                </button>
              )}
            </React.Fragment>
          );
        })}
      </nav>

      <div className={`shrink-0 space-y-1 border-t border-[#e8ece6] py-2 ${collapsed ? 'px-2' : 'px-3'}`}>
        {canMonitorSystem ? (
          <RailTooltip collapsed={collapsed} label="System Monitor">
            <Link href="/admin/system-monitor" className={`flex h-10 items-center rounded-xl text-sm font-semibold text-[#285f28] transition-colors hover:bg-[#edf6e9] ${focusRing} ${itemLayout}`} data-testid="nav-system-monitor" aria-label="System Monitor">
              <Activity size={18} />
              {!collapsed && <span>System Monitor</span>}
            </Link>
          </RailTooltip>
        ) : null}
        <RailTooltip collapsed={collapsed} label="New Conversation">
          <Link href="/assistant/new" onClick={(event) => { event.preventDefault(); startNewConversation(navigate); }} className={`flex h-10 items-center rounded-xl text-sm font-semibold text-slate-900 transition-colors hover:bg-[#f6f8f5] ${focusRing} ${itemLayout}`} aria-label="Start a new conversation">
            <MessageSquarePlus size={18} className="text-[#2f6d25]" />
            {!collapsed && <span>New Conversation</span>}
          </Link>
        </RailTooltip>
        <RailTooltip collapsed={collapsed} label="Notifications">
          <button className={`relative flex h-10 w-full items-center rounded-xl text-sm font-medium text-slate-700 transition-colors hover:bg-[#f6f8f5] hover:text-slate-950 ${focusRing} ${itemLayout}`} aria-label="Notifications" data-testid="button-notifications">
            <Bell size={18} className="text-slate-500" />
            {!collapsed && <span>Notifications</span>}
            {(userView?.notificationsCount ?? 0) > 0 && (
              <span className={collapsed ? 'absolute right-1 top-1 h-2 w-2 rounded-full bg-[#b76a09]' : 'ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-[#b76a09] px-1 text-[10px] font-bold text-white'} data-testid="notification-badge">
                {!collapsed && userView?.notificationsCount}
              </span>
            )}
          </button>
        </RailTooltip>
        <RailTooltip collapsed={collapsed} label="Help">
          <button className={`flex h-10 w-full items-center rounded-xl text-sm font-medium text-slate-700 transition-colors hover:bg-[#f6f8f5] hover:text-slate-950 ${focusRing} ${itemLayout}`} aria-label="Help" data-testid="button-help">
            <HelpCircle size={18} className="text-slate-500" />
            {!collapsed && <span>Help</span>}
          </button>
        </RailTooltip>
        <RailTooltip collapsed={collapsed} label="Settings">
          <button className={`flex h-10 w-full items-center rounded-xl text-sm font-medium text-slate-700 transition-colors hover:bg-[#f6f8f5] hover:text-slate-950 ${focusRing} ${itemLayout}`} aria-label="Theme and settings">
            <Settings2 size={18} className="text-slate-500" />
            {!collapsed && <span>Theme & Settings</span>}
          </button>
        </RailTooltip>
        <RailTooltip collapsed={collapsed} label={userView?.name ?? 'User profile'}>
          <button className={`flex h-11 w-full min-w-0 items-center rounded-xl text-left transition-colors hover:bg-[#f6f8f5] ${focusRing} ${itemLayout}`} data-testid="button-user-profile" aria-label="Open user menu">
            <div className={`flex shrink-0 items-center justify-center rounded-full bg-[#25611f] font-bold text-white shadow-sm ${collapsed ? 'h-8 w-8 text-xs' : 'h-10 w-10 text-sm'}`}>
              {userView?.initials ?? 'CU'}
            </div>
            {!collapsed && (
              <>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold leading-tight text-slate-950" data-testid="text-username">{userView?.name ?? 'CIAL User'}</div>
                  <div className="truncate text-xs leading-tight text-slate-500" data-testid="text-department">{userView?.department ?? 'CIAL'}</div>
                </div>
                <ChevronDown size={14} className="text-muted-foreground" />
              </>
            )}
          </button>
        </RailTooltip>
        <RailTooltip collapsed={collapsed} label="Log Out">
          <button type="button" onClick={() => void logout()} className={`flex h-10 w-full items-center rounded-xl text-sm font-medium text-slate-700 transition-colors hover:bg-[#f6f8f5] hover:text-slate-950 ${focusRing} ${itemLayout}`} data-testid="button-logout" aria-label="Log out">
            <LogOut size={18} className="text-slate-500" />
            {!collapsed && <span>Log Out</span>}
          </button>
        </RailTooltip>
        <RailTooltip collapsed={collapsed} label={collapsed ? 'Expand navigation' : 'Collapse navigation'}>
          <button
            type="button"
            onClick={() => onCollapsedChange(!collapsed)}
            className={`flex h-10 w-full items-center rounded-xl text-sm font-medium text-slate-600 transition-colors hover:bg-[#f6f8f5] hover:text-slate-950 ${focusRing} ${itemLayout}`}
            aria-label={collapsed ? 'Expand global navigation' : 'Collapse global navigation'}
            aria-expanded={!collapsed}
            data-testid="button-toggle-global-navigation"
          >
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            {!collapsed && <span>Collapse navigation</span>}
          </button>
        </RailTooltip>
      </div>
    </aside>
  );
}
