import { Eye, Download } from 'lucide-react';
import { Document } from '@/types';
import { DOC_TYPE_COLORS } from '@/data/documentsData';

interface DocumentCardProps {
  doc: Document;
}

export default function DocumentCard({ doc }: DocumentCardProps) {
  return (
    <div
      className="bg-white rounded-xl border border-[#e2eedd] p-4 shadow-sm"
      data-testid={`doc-card-${doc.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold text-sm text-[#1a2e14] truncate">{doc.name}</p>
          <p className="text-xs text-[#5a7a52] mt-0.5">
            {doc.department} — {doc.category}
          </p>
        </div>
        <span
          className={`text-xs px-2.5 py-0.5 rounded-full font-medium flex-shrink-0 ${DOC_TYPE_COLORS[doc.type] || 'bg-gray-100 text-gray-600'}`}
        >
          {doc.type}
        </span>
      </div>
      <div className="flex items-center justify-between mt-3">
        <span className="text-xs text-[#9ab88e]">{doc.lastUpdated}</span>
        <div className="flex gap-2">
          <button
            className="p-1.5 rounded-lg bg-[#f0f7ed] text-[#4a7c3f] hover:bg-[#e0f0d8] transition-colors"
            data-testid={`button-view-mobile-${doc.id}`}
          >
            <Eye size={13} />
          </button>
          <button
            className="p-1.5 rounded-lg bg-[#f0f7ed] text-[#4a7c3f] hover:bg-[#e0f0d8] transition-colors"
            data-testid={`button-download-mobile-${doc.id}`}
          >
            <Download size={13} />
          </button>
        </div>
      </div>
    </div>
  );
}
