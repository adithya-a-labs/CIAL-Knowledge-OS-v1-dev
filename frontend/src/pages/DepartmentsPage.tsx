import { Link } from 'wouter';
import {
  ArrowRight,
  Building2,
  ClipboardList,
  FileText,
  MessageSquare,
  Monitor,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Wrench,
} from 'lucide-react';
import type React from 'react';
import { DEPARTMENTS } from '@/data/departmentsData';

const ICON_MAP: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  Wrench,
  ShieldCheck,
  Settings2,
  Monitor,
  Building2,
  TrendingUp,
};

const recentDepartmentDocs = [
  'Airside inspection checklist',
  'Fire alarm escalation procedure',
  'Passenger boarding bridge SOP',
  'Network outage first response',
];

const departmentActivity = [
  'Engineering updated AGL controller manual',
  'Safety added emergency muster checklist',
  'Operations revised baggage handover SOP',
  'IT published network outage response',
];

export default function DepartmentsPage() {
  return (
    <div className="mx-auto flex w-full max-w-[86rem] flex-col gap-6" data-testid="departments-page">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-slate-500">Departments</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-950">Organizational knowledge spaces</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Browse department-owned documents, folders, activity, and AI context scopes.
          </p>
        </div>
        <label className="flex h-11 min-w-0 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-500 shadow-sm lg:w-80">
          <Search size={16} />
          <input className="min-w-0 flex-1 bg-transparent text-slate-800 placeholder:text-slate-400" placeholder="Search departments" type="search" />
        </label>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <main className="space-y-6">
          <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-4 py-3">
              <h2 className="text-sm font-semibold text-slate-950">Department directory</h2>
            </div>
            <div className="divide-y divide-slate-100">
              {DEPARTMENTS.map((dept) => {
                const IconComp = ICON_MAP[dept.icon] || Building2;
                return (
                  <article key={dept.id} className="grid gap-3 px-4 py-4 transition hover:bg-slate-50 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                    <div className="flex min-w-0 items-start gap-3">
                      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-primary">
                        <IconComp size={20} />
                      </span>
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold text-slate-950">{dept.name}</h3>
                        <p className="mt-1 text-xs text-slate-500">Head: {dept.headName}</p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <span className="ce-badge"><FileText size={12} />{dept.stats.documents.toLocaleString()} docs</span>
                          <span className="ce-badge"><ClipboardList size={12} />{dept.stats.sops} SOPs</span>
                          <span className="ce-badge"><MessageSquare size={12} />{dept.stats.unresolvedQuestions} open questions</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2 lg:justify-end">
                      <Link href="/knowledge-center" className="ce-action h-9 px-3">Documents</Link>
                      <Link href="/assistant/new" className="ce-action ce-action-primary h-9 px-3"><Sparkles size={14} />Ask in scope</Link>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-950">Department documents</h2>
              <div className="mt-3 divide-y divide-slate-100">
                {recentDepartmentDocs.map((doc) => (
                  <Link key={doc} href="/knowledge-center" className="flex items-center gap-3 py-3 text-sm hover:text-primary">
                    <FileText size={16} className="text-primary" />
                    <span className="min-w-0 flex-1 truncate">{doc}</span>
                    <ArrowRight size={14} className="text-slate-300" />
                  </Link>
                ))}
              </div>
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-950">Department folders</h2>
              <div className="mt-3 divide-y divide-slate-100">
                {['Emergency SOPs', 'Runway Maintenance', 'Operations', 'Security Policies'].map((folder) => (
                  <Link key={folder} href="/knowledge-center" className="flex items-center gap-3 py-3 text-sm hover:text-primary">
                    <Building2 size={16} className="text-primary" />
                    <span className="min-w-0 flex-1 truncate">{folder}</span>
                    <ArrowRight size={14} className="text-slate-300" />
                  </Link>
                ))}
              </div>
            </section>
          </div>
        </main>

        <aside className="space-y-4">
          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-950">Recent activity</h2>
            <div className="mt-3 space-y-3">
              {departmentActivity.map((activity) => (
                <div key={activity} className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs leading-5 text-slate-700">
                  {activity}
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-950">AI scope hook</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">Start from a department to keep answers grounded to that organizational space.</p>
            <Link href="/assistant/new" className="ce-action ce-action-primary mt-4 h-10 w-full px-3"><Sparkles size={15} />Ask with department scope</Link>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-950">Permissions hooks</h2>
            <p className="mt-2 text-xs leading-5 text-slate-500">Department-level access and ownership metadata can plug into this surface without changing the browsing model.</p>
          </section>
        </aside>
      </div>
    </div>
  );
}
