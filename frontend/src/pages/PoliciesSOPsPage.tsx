import { useState } from 'react';
import { Eye, Edit } from 'lucide-react';
import PageHeader from '@/components/common/PageHeader';
import SearchBar from '@/components/common/SearchBar';
import StatusPill from '@/components/common/StatusPill';
import EmptyState from '@/components/common/EmptyState';
import { SOPS, SOP_DEPARTMENTS, SOP_TYPES, SOP_STATUSES } from '@/data/sopData';

export default function PoliciesSOPsPage() {
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({ department: '', status: '', type: '' });

  const filtered = SOPS.filter(sop => {
    if (search && !sop.title.toLowerCase().includes(search.toLowerCase())) return false;
    if (filters.department && sop.department !== filters.department) return false;
    if (filters.status && sop.status !== filters.status) return false;
    return true;
  });

  return (
    <div className="fluid-section" data-testid="policies-sops-page">
      <PageHeader title="Policies & SOPs" subtitle="Find all policies and standard operating procedures." />

      <div className="mb-4 grid grid-cols-1 gap-3 lg:grid-cols-[minmax(16rem,1fr)_repeat(3,minmax(9rem,12rem))]">
        <SearchBar value={search} onChange={setSearch} placeholder="Search SOPs..." className="min-w-0" />
        {[
          { key: 'department', label: 'All Departments', options: SOP_DEPARTMENTS },
          { key: 'status', label: 'All Status', options: SOP_STATUSES },
          { key: 'type', label: 'All Types', options: SOP_TYPES },
        ].map(f => (
          <select
            key={f.key}
            value={filters[f.key as keyof typeof filters]}
            onChange={e => setFilters(p => ({ ...p, [f.key]: e.target.value }))}
            className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground focus:ring-2 focus:ring-ring/30"
            data-testid={`filter-sop-${f.key}`}
          >
            <option value="">{f.label}</option>
            {f.options.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        ))}
      </div>

      <div className="scrollbar-soft hidden overflow-x-auto rounded-xl border border-border bg-card shadow-sm md:block">
        <table className="w-full min-w-[62rem]" data-testid="sops-table">
          <thead>
            <tr className="border-b border-border bg-muted">
              {['SOP Title', 'Department', 'Version', 'Status', 'Owner', 'Last Review', 'Next Review', 'Actions'].map(h => (
                <th key={h} className="text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide px-4 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={8}><EmptyState /></td></tr>
            ) : filtered.map((sop) => (
              <tr key={sop.id} className="border-b border-border hover:bg-muted transition-colors" data-testid={`sop-row-${sop.id}`}>
                <td className="px-4 py-3 text-sm font-medium text-foreground">{sop.title}</td>
                <td className="px-4 py-3 text-sm text-muted-foreground">{sop.department}</td>
                <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{sop.version}</td>
                <td className="px-4 py-3"><StatusPill status={sop.status} /></td>
                <td className="px-4 py-3 text-sm text-muted-foreground">{sop.owner}</td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{sop.lastReview}</td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{sop.nextReview}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-1.5">
                    <button className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-primary" data-testid={`button-view-sop-${sop.id}`}><Eye size={14} /></button>
                    <button className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-primary" data-testid={`button-edit-sop-${sop.id}`}><Edit size={14} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile */}
      <div className="space-y-3 md:hidden">
        {filtered.length === 0 ? <EmptyState /> : filtered.map((sop) => (
          <div key={sop.id} className="responsive-card border border-border bg-card p-4 shadow-sm" data-testid={`sop-card-${sop.id}`}>
            <div className="flex items-start justify-between gap-2 mb-2">
              <p className="font-semibold text-sm text-foreground flex-1">{sop.title}</p>
              <StatusPill status={sop.status} />
            </div>
            <div className="grid grid-cols-2 gap-1 text-xs text-muted-foreground">
              <span><span className="font-medium text-foreground">Dept:</span> {sop.department}</span>
              <span><span className="font-medium text-foreground">Ver:</span> {sop.version}</span>
              <span><span className="font-medium text-foreground">Owner:</span> {sop.owner}</span>
              <span><span className="font-medium text-foreground">Next:</span> {sop.nextReview}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
