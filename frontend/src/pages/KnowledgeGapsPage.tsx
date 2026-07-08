import { useState } from 'react';
import { AlertTriangle, TrendingUp, TrendingDown, Minus, FileWarning, Building2, ChevronRight, Lightbulb } from 'lucide-react';
import {
  KNOWLEDGE_GAPS, MISSING_DOCUMENTS, DEPT_HEALTH_SCORES, GAP_OVERVIEW_STATS, GAP_SEVERITY_COLORS
} from '@/data/knowledgeGapsData';
import type { GapSeverity } from '@/data/knowledgeGapsData';

const TREND_ICON: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  rising: TrendingUp,
  falling: TrendingDown,
  stable: Minus,
};
const TREND_CLS: Record<string, string> = {
  rising: 'text-red-500',
  falling: 'text-green-500',
  stable: 'text-[#7a9a72]',
};

const PRIORITY_LABEL: Record<GapSeverity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

function CoverageBar({ value }: { value: number }) {
  const color = value >= 85 ? '#27ae60' : value >= 65 ? '#4a7c3f' : value >= 50 ? '#e8820c' : '#dc2626';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-[#e2eedd] overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${value}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs font-bold w-8 text-right" style={{ color }}>{value}%</span>
    </div>
  );
}

export default function KnowledgeGapsPage() {
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'gaps' | 'missing' | 'health'>('gaps');

  const filteredGaps = KNOWLEDGE_GAPS.filter(g => !severityFilter || g.severity === severityFilter);

  return (
    <div className="fluid-section" data-testid="knowledge-gaps-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
        <div>
          <h1 className="text-xl font-bold text-[#1a2e14]">Knowledge Gaps</h1>
          <p className="text-sm text-[#5a7a52] mt-0.5">Identify and resolve missing knowledge across the organization.</p>
        </div>
      </div>

      {/* Overview stats */}
      <div className="fluid-grid-sm mb-5">
        {GAP_OVERVIEW_STATS.map(stat => {
          const TrendIcon = stat.trend === 'up' ? TrendingUp : stat.trend === 'down' ? TrendingDown : Minus;
          return (
            <div key={stat.label} className="fluid-card responsive-card min-w-0 border border-[#e2eedd] bg-white p-4 shadow-sm hover:shadow-md" data-testid={`gap-stat-${stat.label.toLowerCase().replace(/\s+/g, '-')}`}>
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs text-[#5a7a52] font-medium">{stat.label}</p>
                <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ backgroundColor: stat.color + '18' }}>
                  <AlertTriangle size={13} style={{ color: stat.color }} />
                </div>
              </div>
              <p className="text-2xl font-bold" style={{ color: stat.color }}>{stat.value}</p>
              <div className="flex items-center gap-1 mt-1">
                <TrendIcon size={10} className={stat.trend === 'up' ? 'text-red-400' : 'text-green-500'} />
                <span className="text-[10px] text-[#7a9a72]">{stat.delta}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Tabs */}
      <div className="scrollbar-soft mb-4 flex w-full gap-1 overflow-x-auto rounded-xl border border-[#e2eedd] bg-white p-1 shadow-sm sm:w-fit">
        {[
          { key: 'gaps', label: 'Unanswered Questions' },
          { key: 'missing', label: 'Missing Documents' },
          { key: 'health', label: 'Dept. Health' },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as typeof activeTab)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${activeTab === tab.key ? 'bg-[#4a7c3f] text-white' : 'text-[#5a7a52] hover:bg-[#f0f7ed]'}`}
            data-testid={`tab-${tab.key}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'gaps' && (
        <>
          {/* Severity filter */}
          <div className="flex flex-wrap gap-2 mb-4">
            {['', 'critical', 'high', 'medium', 'low'].map(sev => (
              <button
                key={sev || 'all'}
                onClick={() => setSeverityFilter(sev)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
                  severityFilter === sev
                    ? 'bg-[#4a7c3f] text-white border-[#4a7c3f]'
                    : 'bg-white text-[#5a7a52] border-[#ddecd6] hover:border-[#4a7c3f]'
                }`}
              >
                {sev ? PRIORITY_LABEL[sev as GapSeverity] : 'All'}
              </button>
            ))}
          </div>

          <div className="space-y-3">
            {filteredGaps.map(gap => {
              const TrendIcon = TREND_ICON[gap.trend];
              return (
                <div key={gap.id} className="fluid-card responsive-card border border-[#e2eedd] bg-white p-4 shadow-sm transition-colors hover:border-[#4a7c3f]" data-testid={`gap-${gap.id}`}>
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start gap-2 flex-wrap mb-1">
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase tracking-wide ${GAP_SEVERITY_COLORS[gap.severity]}`}>
                          {PRIORITY_LABEL[gap.severity]}
                        </span>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#f0f7ed] text-[#4a7c3f]">{gap.department}</span>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-600">{gap.category}</span>
                      </div>
                      <p className="text-sm font-medium text-[#1a2e14] leading-snug">{gap.question}</p>
                      <div className="flex items-center gap-3 mt-2 text-[10px] text-[#7a9a72]">
                        <span className="flex items-center gap-1">
                          <TrendIcon size={10} className={TREND_CLS[gap.trend]} />
                          {gap.searchCount} searches · {gap.trend}
                        </span>
                        <span>Last asked {gap.lastAsked}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-amber-600 font-semibold bg-amber-50 border border-amber-100 rounded-lg px-2 py-1 flex-shrink-0">
                      <span className="text-base font-bold">{gap.searchCount}</span>
                    </div>
                  </div>
                  <div className="mt-3 pt-3 border-t border-[#f0f7ed] flex items-start gap-2">
                    <Lightbulb size={13} className="text-[#4a7c3f] flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-[#3d5c30]"><span className="font-semibold">Suggested action:</span> {gap.suggestedAction}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {activeTab === 'missing' && (
        <div className="responsive-card overflow-hidden border border-[#e2eedd] bg-white shadow-sm">
          <div className="px-4 py-3 border-b border-[#f0f7ed]">
            <h3 className="text-sm font-semibold text-[#1a2e14]">Missing Documents ({MISSING_DOCUMENTS.length})</h3>
          </div>
          <div className="divide-y divide-[#f0f7ed]">
            {MISSING_DOCUMENTS.map(doc => (
              <div key={doc.id} className="flex flex-col gap-3 px-4 py-3 transition-colors hover:bg-[#f8fdf6] sm:flex-row sm:items-center" data-testid={`missing-${doc.id}`}>
                <div className="w-8 h-8 rounded-lg bg-red-50 flex items-center justify-center flex-shrink-0">
                  <FileWarning size={15} className="text-red-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[#1a2e14] truncate">{doc.title}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#f0f7ed] text-[#4a7c3f]">{doc.type}</span>
                    <span className="text-[10px] text-[#5a7a52]">{doc.department}</span>
                    <span className="text-[10px] text-[#7a9a72]">{doc.requestCount} requests</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${GAP_SEVERITY_COLORS[doc.priority]}`}>
                    {PRIORITY_LABEL[doc.priority]}
                  </span>
                  <button className="flex items-center gap-1 text-xs text-[#4a7c3f] hover:underline font-medium">
                    Create <ChevronRight size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'health' && (
        <div className="responsive-card overflow-hidden border border-[#e2eedd] bg-white shadow-sm">
          <div className="px-4 py-3 border-b border-[#f0f7ed]">
            <h3 className="text-sm font-semibold text-[#1a2e14]">Department Knowledge Health</h3>
          </div>
          <div className="divide-y divide-[#f0f7ed]">
            {DEPT_HEALTH_SCORES.map(dept => {
              const TrendIcon = dept.trend === 'up' ? TrendingUp : dept.trend === 'down' ? TrendingDown : Minus;
              return (
                <div key={dept.department} className="px-4 py-4 hover:bg-[#f8fdf6] transition-colors" data-testid={`health-${dept.department.toLowerCase()}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-[#f0f7ed] flex items-center justify-center">
                        <Building2 size={14} className="text-[#4a7c3f]" />
                      </div>
                      <span className="text-sm font-semibold text-[#1a2e14]">{dept.department}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <TrendIcon size={13} className={dept.trend === 'up' ? 'text-green-500' : dept.trend === 'down' ? 'text-red-400' : 'text-[#7a9a72]'} />
                      <span className="text-xs text-[#5a7a52]">{dept.documents} docs · {dept.sops} SOPs</span>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-[#5a7a52]">Health Score</span>
                      </div>
                      <CoverageBar value={dept.score} />
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-[#5a7a52]">Knowledge Coverage</span>
                      </div>
                      <CoverageBar value={dept.coverage} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
