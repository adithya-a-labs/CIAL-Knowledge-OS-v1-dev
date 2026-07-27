import { Eye, Edit, Download, FileText } from 'lucide-react';
import { Document } from '@/types';
import { DOC_TYPE_COLORS } from '@/data/documentsData';

interface DocumentRowProps {
  doc: Document;
  index: number;
  canEdit: boolean;
  canDelete: boolean;
}

export default function DocumentRow({ doc, index, canEdit }: DocumentRowProps) {
  return (
    <tr
      className="border-b border-border hover:bg-muted transition-colors"
      data-testid={`table-row-${doc.id}`}
    >
      <td className="px-5 py-3 text-sm text-[#9ab88e]">{index}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-accent flex items-center justify-center flex-shrink-0">
            <FileText size={13} className="text-primary" />
          </div>
          <span className="text-sm font-medium text-foreground">{doc.name}</span>
        </div>
      </td>
      <td className="px-4 py-3 text-sm text-muted-foreground">{doc.category}</td>
      <td className="px-4 py-3 text-sm text-muted-foreground">{doc.department}</td>
      <td className="px-4 py-3">
        <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${DOC_TYPE_COLORS[doc.type] || 'bg-muted text-muted-foreground'}`}>
          {doc.type}
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-muted-foreground">{doc.lastUpdated}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1.5">
          <button
            className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-primary transition-colors"
            data-testid={`button-view-${doc.id}`}
          >
            <Eye size={14} />
          </button>
          {canEdit && (
            <button
              className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-primary transition-colors"
              data-testid={`button-edit-${doc.id}`}
            >
              <Edit size={14} />
            </button>
          )}
          <button
            className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-primary transition-colors"
            data-testid={`button-download-${doc.id}`}
          >
            <Download size={14} />
          </button>
        </div>
      </td>
    </tr>
  );
}
