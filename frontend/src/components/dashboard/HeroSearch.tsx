import { useState } from 'react';
import { Search, Mic, Send } from 'lucide-react';
import { useLocation } from 'wouter';
import { useAuth } from '@/auth/AuthContext';
import { HERO_QUICK_SEARCHES } from '@/data/dashboardData';
import { createConversationHandoff } from '@/lib/conversationHandoff';

export default function HeroSearch() {
  const [searchQuery, setSearchQuery] = useState('');
  const [, setLocation] = useLocation();
  const { userView } = useAuth();
  const firstName = userView?.name.split(' ')[0] ?? 'there';

  const handleSearch = () => {
    if (searchQuery.trim()) createConversationHandoff(setLocation, {
      title: searchQuery.trim().slice(0, 72),
      origin: 'homepage',
      context_scope: 'all_accessible',
      selected_document_ids: [],
      question: searchQuery.trim(),
      autoSubmit: true,
    });
  };

  return (
    <div className="responsive-card overflow-hidden border border-border bg-card shadow-sm" data-testid="hero-search">
      <div className="grid grid-cols-1 lg:grid-cols-5">
        {/* Left: Greeting + Search */}
        <div className="p-4 sm:p-6 lg:col-span-3 lg:p-8">
          <h1 className="safe-text text-2xl font-bold leading-tight text-foreground sm:text-3xl" data-testid="text-welcome">
            Welcome back, <span className="text-primary">{firstName}</span> 👋
          </h1>
          <p className="text-sm text-muted-foreground mt-1">How can I help you today?</p>

          <div className="mt-5 flex min-w-0 items-center gap-2 rounded-xl border border-border bg-muted px-3 py-3 transition-[border-color,box-shadow] duration-[var(--motion-duration-short)] ease-[var(--motion-ease-move)] focus-within:border-[#4a7c3f] focus-within:ring-2 focus-within:ring-[#4a7c3f]/30 sm:px-4">
            <Search size={16} className="text-[#9ab88e] flex-shrink-0" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="Ask anything about CIAL knowledge base..."
              className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-[#9ab88e]"
              data-testid="input-hero-search"
            />
            <button
              onClick={() => {}}
              className="text-[#9ab88e] hover:text-primary transition-colors"
              data-testid="button-voice-search"
            >
              <Mic size={16} />
            </button>
            <button
              onClick={handleSearch}
              className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-[#4a7c3f] text-white transition-colors hover:bg-[#3d6834]"
              data-testid="button-submit-search"
            >
              <Send size={14} />
            </button>
          </div>

          {/* Quick search pills */}
          <div className="mt-3 flex flex-wrap gap-2">
            {HERO_QUICK_SEARCHES.map((q) => (
              <button
                key={q}
                onClick={() => setSearchQuery(q)}
                className="px-3 py-1.5 rounded-full bg-accent border border-border text-xs text-primary hover:bg-accent transition-colors"
                data-testid={`chip-search-${q.toLowerCase().replace(/\s+/g, '-').slice(0, 20)}`}
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Right: Decorative airport illustration */}
        <div
          className="relative min-h-[140px] overflow-hidden sm:min-h-[160px] lg:col-span-2 lg:min-h-[220px]"
          aria-hidden="true"
        >
          <div className="absolute inset-0" style={{ background: 'linear-gradient(180deg, #c8e6a0 0%, #8fc85a 60%, #5a8a35 100%)' }} />
          <div className="absolute bottom-0 left-0 right-0 h-16 rounded-tl-3xl" style={{ background: '#4a7c3f' }} />
          <div className="absolute bottom-0 left-0 right-0 h-10 rounded-tl-3xl" style={{ background: '#3d6834' }} />
          <div className="absolute bottom-8 right-16 w-6 h-20 bg-[#2d4f22] rounded-sm" />
          <div className="absolute bottom-28 right-14 w-10 h-6 bg-[#2d4f22] rounded-sm" />
          <div className="absolute bottom-8 right-28 w-4 h-14 bg-[#3d6834] rounded-sm" />
          <div className="absolute bottom-6 left-4 w-8 h-12 rounded-t-full bg-[#2d4f22]" />
          <div className="absolute bottom-6 left-10 w-6 h-10 rounded-t-full bg-[#3d6834]" />
          <div className="absolute top-4 right-4 text-white/80 font-bold text-xl tracking-widest">CIAL</div>
          <div className="absolute top-4 left-8 w-14 h-14 rounded-full bg-card/20 blur-md" />
        </div>
      </div>
    </div>
  );
}
