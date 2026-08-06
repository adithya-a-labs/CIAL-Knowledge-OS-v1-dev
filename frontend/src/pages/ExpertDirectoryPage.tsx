import { useState } from 'react';
import { Search, Star, FileText, ClipboardList, MessageSquare, Mail, CheckCircle } from 'lucide-react';
import { EXPERTS, EXPERT_DEPARTMENTS, EXPERT_TAGS } from '@/data/expertData';

function ScoreBar({ score }: { score: number }) {
  const color = score >= 90 ? '#4a7c3f' : score >= 75 ? '#7ab648' : '#e8820c';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${score}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs font-bold" style={{ color }}>{score}</span>
    </div>
  );
}

export default function ExpertDirectoryPage() {
  const [search, setSearch] = useState('');
  const [dept, setDept] = useState('');
  const [tag, setTag] = useState('');

  const filtered = EXPERTS.filter(e => {
    if (search && !e.name.toLowerCase().includes(search.toLowerCase()) && !e.expertiseTags.some(t => t.toLowerCase().includes(search.toLowerCase()))) return false;
    if (dept && e.department !== dept) return false;
    if (tag && !e.expertiseTags.includes(tag)) return false;
    return true;
  });

  return (
    <div className="fluid-section" data-testid="expert-directory-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-xl font-bold text-foreground">Expert Directory</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Discover subject matter experts across CIAL departments.</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground bg-card border border-border rounded-lg px-3 py-2">
          <CheckCircle size={14} className="text-primary" />
          {EXPERTS.filter(e => e.available).length} available now
        </div>
      </div>

      {/* Filters */}
      <div className="mb-5 grid grid-cols-1 gap-2 md:grid-cols-[minmax(16rem,1fr)_minmax(10rem,14rem)_minmax(10rem,14rem)]">
        <div className="relative min-w-0">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#7a9a72]" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name or expertise..."
            className="w-full rounded-lg border border-border bg-card py-2 pl-9 pr-3 text-sm focus:ring-2 focus:ring-ring/30"
            data-testid="expert-search"
          />
        </div>
        <select
          value={dept}
          onChange={e => setDept(e.target.value)}
          className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-ring/30"
          data-testid="filter-department"
        >
          {EXPERT_DEPARTMENTS.map(d => <option key={d} value={d === 'All Departments' ? '' : d}>{d}</option>)}
        </select>
        <select
          value={tag}
          onChange={e => setTag(e.target.value)}
          className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-ring/30"
          data-testid="filter-expertise"
        >
          <option value="">All Expertise</option>
          {EXPERT_TAGS.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">No experts match your search.</div>
      ) : (
        <div className="fluid-grid-lg">
          {filtered.map(expert => (
            <div
              key={expert.id}
              className="fluid-card responsive-card flex min-w-0 flex-col gap-4 border border-border bg-card p-5 shadow-sm"
              data-testid={`expert-card-${expert.id}`}
            >
              {/* Top row */}
              <div className="flex items-start gap-3">
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#4a7c3f] to-[#7ab648] flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                  {expert.initials}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-bold text-foreground truncate">{expert.name}</p>
                    {expert.available && (
                      <span className="w-2 h-2 rounded-full bg-success/100 flex-shrink-0" title="Available" />
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground truncate">{expert.role}</p>
                  <span className="inline-block mt-1 text-[10px] px-2 py-0.5 rounded-full bg-accent text-primary font-medium">{expert.department}</span>
                </div>
              </div>

              {/* Knowledge Score */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-muted-foreground font-medium">Knowledge Score</span>
                  <Star size={12} className="text-amber-400 fill-amber-400" />
                </div>
                <ScoreBar score={expert.knowledgeScore} />
              </div>

              {/* Expertise Tags */}
              <div className="flex flex-wrap gap-1">
                {expert.expertiseTags.slice(0, 3).map(tag => (
                  <span key={tag} className="text-[10px] px-2 py-0.5 rounded-full bg-accent border border-border text-primary">{tag}</span>
                ))}
                {expert.expertiseTags.length > 3 && (
                  <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">+{expert.expertiseTags.length - 3}</span>
                )}
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-border">
                <div className="text-center">
                  <div className="flex items-center justify-center gap-1 text-primary">
                    <FileText size={12} />
                    <span className="text-sm font-bold text-foreground">{expert.documentsContributed}</span>
                  </div>
                  <p className="text-[10px] text-[#7a9a72]">Docs</p>
                </div>
                <div className="text-center">
                  <div className="flex items-center justify-center gap-1 text-[#7ab648]">
                    <ClipboardList size={12} />
                    <span className="text-sm font-bold text-foreground">{expert.sopsAuthored}</span>
                  </div>
                  <p className="text-[10px] text-[#7a9a72]">SOPs</p>
                </div>
                <div className="text-center">
                  <div className="flex items-center justify-center gap-1 text-warning">
                    <MessageSquare size={12} />
                    <span className="text-sm font-bold text-foreground">{expert.helpfulAnswers}</span>
                  </div>
                  <p className="text-[10px] text-[#7a9a72]">Answers</p>
                </div>
              </div>

              {/* Contact */}
              <a
                href={`mailto:${expert.email}`}
                className="flex items-center justify-center gap-2 w-full py-2 rounded-lg border border-border text-xs font-medium text-primary hover:bg-accent transition-colors"
                data-testid={`contact-${expert.id}`}
              >
                <Mail size={13} />
                Contact Expert
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
