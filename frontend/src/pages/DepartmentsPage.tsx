import { Wrench, ShieldCheck, Settings2, Monitor, Building2, TrendingUp, FileText, ClipboardList, HelpCircle } from 'lucide-react';
import PageHeader from '@/components/common/PageHeader';
import { DEPARTMENTS } from '@/data/departmentsData';

const ICON_MAP: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  Wrench, ShieldCheck, Settings2, Monitor, Building2, TrendingUp
};

const DEPT_COLORS = [
  { header: 'from-[#4a7c3f] to-[#5a9a45]', icon: 'bg-white/20 text-white' },
  { header: 'from-[#e8820c] to-[#f09c3a]', icon: 'bg-white/20 text-white' },
  { header: 'from-[#2d4f22] to-[#4a7c3f]', icon: 'bg-white/20 text-white' },
  { header: 'from-[#1a6b8a] to-[#2d9cbc]', icon: 'bg-white/20 text-white' },
  { header: 'from-[#6b3d8a] to-[#9c5abf]', icon: 'bg-white/20 text-white' },
  { header: 'from-[#8a3d3d] to-[#bf5a5a]', icon: 'bg-white/20 text-white' },
];

export default function DepartmentsPage() {
  return (
    <div className="fluid-section" data-testid="departments-page">
      <PageHeader title="Departments" subtitle="Overview of all departments and knowledge data." />

      <div className="fluid-grid-lg">
        {DEPARTMENTS.map((dept, idx) => {
          const IconComp = ICON_MAP[dept.icon] || Building2;
          const colors = DEPT_COLORS[idx % DEPT_COLORS.length];

          return (
            <div
              key={dept.id}
              className="fluid-card responsive-card min-w-0 overflow-hidden border border-[#e2eedd] bg-white shadow-sm hover:shadow-md"
              data-testid={`dept-card-${dept.id}`}
            >
              {/* Colored header */}
              <div className={`bg-gradient-to-r ${colors.header} p-5`}>
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="safe-text text-base font-bold text-white">{dept.name}</h3>
                    <p className="text-xs text-white/75 mt-0.5">Department</p>
                  </div>
                  <div className={`w-10 h-10 rounded-xl ${colors.icon} flex items-center justify-center`}>
                    <IconComp size={20} />
                  </div>
                </div>
              </div>

              {/* Stats */}
              <div className="p-4 space-y-3">
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center p-2 bg-[#f8fdf6] rounded-lg" data-testid={`dept-docs-${dept.id}`}>
                    <FileText size={14} className="text-[#4a7c3f] mx-auto mb-1" />
                    <p className="text-base font-bold text-[#1a2e14]">{dept.stats.documents.toLocaleString()}</p>
                    <p className="text-[10px] text-[#5a7a52]">Documents</p>
                  </div>
                  <div className="text-center p-2 bg-[#f8fdf6] rounded-lg" data-testid={`dept-sops-${dept.id}`}>
                    <ClipboardList size={14} className="text-[#7ab648] mx-auto mb-1" />
                    <p className="text-base font-bold text-[#1a2e14]">{dept.stats.sops}</p>
                    <p className="text-[10px] text-[#5a7a52]">SOPs</p>
                  </div>
                  <div className="text-center p-2 bg-[#fef8f3] rounded-lg" data-testid={`dept-questions-${dept.id}`}>
                    <HelpCircle size={14} className="text-[#e8820c] mx-auto mb-1" />
                    <p className="text-base font-bold text-[#e8820c]">{dept.stats.unresolvedQuestions}</p>
                    <p className="text-[10px] text-[#5a7a52]">Unresolved</p>
                  </div>
                </div>

                {/* Head */}
                <div className="flex items-center gap-3 pt-2 border-t border-[#f0f7ed]">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#4a7c3f] to-[#7ab648] flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                    {dept.headInitials}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-[#1a2e14]">{dept.headName}</p>
                    <p className="text-[10px] text-[#5a7a52]">Department Head</p>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
