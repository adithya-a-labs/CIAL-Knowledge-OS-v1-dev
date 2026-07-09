import { Menu } from 'lucide-react';

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

      <div className="min-w-0 flex-1" />
    </header>
  );
}
