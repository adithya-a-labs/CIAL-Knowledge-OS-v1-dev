import { Menu, Search } from 'lucide-react';

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

      <label className="hidden min-w-0 max-w-xs flex-1 items-center gap-2 rounded-xl border border-[#e3e9e1] bg-white px-3 py-2 text-slate-500 shadow-sm md:flex">
        <Search size={16} />
        <input
          type="search"
          placeholder="Search this workspace"
          className="min-w-0 flex-1 bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
          aria-label="Search this workspace"
        />
      </label>
    </header>
  );
}
