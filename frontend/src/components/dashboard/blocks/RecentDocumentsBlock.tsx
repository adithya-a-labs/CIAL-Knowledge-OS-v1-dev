import { useLocation } from 'wouter';
import { FileText, ArrowRight } from 'lucide-react';
import DashboardBlock from '@/components/common/DashboardBlock';
import { DOCUMENTS, DOC_TYPE_COLORS } from '@/data/documentsData';

export default function RecentDocumentsBlock() {
  const [, setLocation] = useLocation();
  const recent = DOCUMENTS.slice(0, 5);

  return (
    <DashboardBlock
      title="Recent Documents"
      viewAllLabel="View All"
      onViewAll={() => setLocation('/documents')}
    >
      <div className="divide-y divide-[#f0f7ed]">
        {recent.map(doc => (
          <div key={doc.id} className="flex items-center gap-3 py-2.5 group cursor-pointer" data-testid={`doc-row-${doc.id}`}>
            <div className="w-7 h-7 rounded-md bg-[#f0f7ed] flex items-center justify-center flex-shrink-0">
              <FileText size={13} className="text-[#4a7c3f]" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-[#1a2e14] truncate group-hover:text-[#4a7c3f] transition-colors">{doc.name}</p>
              <p className="text-xs text-[#9ab88e]">{doc.department} · {doc.lastUpdated}</p>
            </div>
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${DOC_TYPE_COLORS[doc.type] ?? 'bg-gray-100 text-gray-600'}`}>
              {doc.type}
            </span>
          </div>
        ))}
      </div>
    </DashboardBlock>
  );
}
