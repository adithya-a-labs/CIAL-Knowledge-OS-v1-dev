import { useState } from 'react';
import { Plane, Package, Zap, Wind, Shield, Monitor, Building2, ExternalLink } from 'lucide-react';
import PageHeader from '@/components/common/PageHeader';
import SearchBar from '@/components/common/SearchBar';
import EmptyState from '@/components/common/EmptyState';
import { KB_CATEGORIES, POPULAR_ARTICLES } from '@/data/knowledgeBaseData';

const ICON_MAP: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  Plane, Package, Zap, Wind, Shield, Monitor, Building2
};

const CATEGORY_COLORS = [
  'from-blue-50 to-blue-100 border-blue-200',
  'from-amber-50 to-amber-100 border-amber-200',
  'from-yellow-50 to-yellow-100 border-yellow-200',
  'from-cyan-50 to-cyan-100 border-cyan-200',
  'from-red-50 to-red-100 border-red-200',
  'from-indigo-50 to-indigo-100 border-indigo-200',
  'from-green-50 to-green-100 border-green-200',
];

const ICON_COLORS = ['text-blue-600', 'text-amber-600', 'text-yellow-600', 'text-cyan-600', 'text-red-600', 'text-indigo-600', 'text-green-600'];

export default function KnowledgeBasePage() {
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');

  const filteredArticles = POPULAR_ARTICLES.filter(a => {
    if (search && !a.title.toLowerCase().includes(search.toLowerCase())) return false;
    if (selectedCategory && a.category !== selectedCategory) return false;
    return true;
  });

  return (
    <div className="fluid-section" data-testid="knowledge-base-page">
      <PageHeader title="Knowledge Base" subtitle="Explore articles and knowledge base." />

      {/* Search + filter */}
      <div className="mb-6 grid grid-cols-1 gap-3 md:grid-cols-[minmax(16rem,1fr)_minmax(10rem,14rem)_minmax(10rem,12rem)]">
        <SearchBar value={search} onChange={setSearch} placeholder="Search articles..." className="flex-1" />
        <select
          value={selectedCategory}
          onChange={e => setSelectedCategory(e.target.value)}
          className="rounded-lg border border-[#ddecd6] bg-white px-3 py-2 text-sm text-[#1a2e14] transition-colors focus:ring-2 focus:ring-[#4a7c3f]/30"
          data-testid="filter-category"
        >
          <option value="">All Categories</option>
          {KB_CATEGORIES.map(c => <option key={c.id} value={c.name}>{c.name}</option>)}
        </select>
        <select className="rounded-lg border border-[#ddecd6] bg-white px-3 py-2 text-sm text-[#1a2e14] transition-colors focus:ring-2 focus:ring-[#4a7c3f]/30" data-testid="filter-sort">
          <option>Sort: Popular</option>
          <option>Sort: Recent</option>
          <option>Sort: A–Z</option>
        </select>
      </div>

      {/* Categories Grid */}
      <div className="mb-6">
        <h2 className="text-sm font-semibold text-[#1a2e14] mb-3">Categories</h2>
        <div className="fluid-grid-sm">
          {KB_CATEGORIES.map((cat, idx) => {
            const IconComp = ICON_MAP[cat.icon] || Monitor;
            return (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(selectedCategory === cat.name ? '' : cat.name)}
                className={`fluid-card min-h-28 rounded-xl border bg-gradient-to-br p-4 text-left transition-all hover:shadow-md ${CATEGORY_COLORS[idx % CATEGORY_COLORS.length]} ${selectedCategory === cat.name ? 'ring-2 ring-[#4a7c3f] ring-offset-1' : ''}`}
                data-testid={`category-card-${cat.id}`}
              >
                <IconComp size={20} className={`${ICON_COLORS[idx % ICON_COLORS.length]} mb-2`} />
                <p className="text-xs font-semibold text-[#1a2e14] leading-tight">{cat.name}</p>
                <p className="text-[10px] text-[#5a7a52] mt-1">{cat.count} articles</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Popular Articles */}
      <div className="responsive-card border border-[#e2eedd] bg-white shadow-sm">
        <div className="flex items-center justify-between gap-3 border-b border-[#e2eedd] p-4">
          <h2 className="text-sm font-semibold text-[#1a2e14]">Popular Articles</h2>
          <span className="text-xs text-[#5a7a52]">{filteredArticles.length} articles</span>
        </div>
        <div className="divide-y divide-[#f0f7ed]">
          {filteredArticles.length === 0 ? (
            <EmptyState />
          ) : (
            filteredArticles.map((article) => (
              <div
                key={article.id}
                className="group flex flex-col gap-2 px-4 py-3 transition-colors hover:bg-[#f8fdf6] sm:flex-row sm:items-center sm:justify-between sm:gap-4"
                data-testid={`article-${article.id}`}
              >
                <div className="min-w-0 flex-1">
                  <p className="safe-text flex items-center gap-1.5 text-sm font-medium text-[#1a2e14] transition-colors group-hover:text-[#4a7c3f]">
                    {article.title}
                    <ExternalLink size={11} className="text-[#9ab88e] flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </p>
                  <span className="text-[11px] text-[#5a7a52] mt-0.5 inline-block">{article.category}</span>
                </div>
                <span className="text-xs text-[#9ab88e] flex-shrink-0 whitespace-nowrap">Viewed {article.views.toLocaleString()} times</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
