import { FileText, FileSpreadsheet, File, MoreVertical } from 'lucide-react';
import type { WorkspaceDocument, FileType } from '@/data/workspace/workspaceTypes';

const FILE_ICON_MAP: Record<FileType, React.ComponentType<{ size?: number; className?: string }>> = {
  pdf: FileText,
  docx: FileText,
  xlsx: FileSpreadsheet,
  pptx: FileText,
  txt: FileText,
  other: File,
};

const FILE_COLOR_MAP: Record<FileType, string> = {
  pdf: 'text-red-500 bg-destructive/10',
  docx: 'text-blue-500 bg-info/10',
  xlsx: 'text-success bg-success/10',
  pptx: 'text-orange-500 bg-warning/10',
  txt: 'bg-muted text-muted-foreground',
  other: 'bg-muted text-muted-foreground',
};

interface RecentUploadsTableProps {
  documents: WorkspaceDocument[];
  onViewAll?: () => void;
}

export default function RecentUploadsTable({ documents, onViewAll }: RecentUploadsTableProps) {
  return (
    <div className="responsive-card overflow-hidden border border-border bg-card shadow-sm" data-testid="recent-uploads-table">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h3 className="text-sm font-semibold text-foreground">Recent Uploads</h3>
        <button
          onClick={onViewAll}
          className="text-xs text-primary hover:underline font-medium"
          data-testid="button-uploads-viewall"
        >
          View all
        </button>
      </div>

      {/* Desktop table */}
      <div className="scrollbar-soft hidden overflow-x-auto sm:block">
        <table className="w-full min-w-[35rem] text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide py-2 px-4">File</th>
              <th className="text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide py-2 px-3">Category</th>
              <th className="text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide py-2 px-3">Size</th>
              <th className="text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide py-2 px-3">Uploaded</th>
              <th className="py-2 px-3" />
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => {
              const Icon = FILE_ICON_MAP[doc.fileType];
              const colorCls = FILE_COLOR_MAP[doc.fileType];
              return (
                <tr key={doc.id} className="border-b border-border hover:bg-muted transition-colors" data-testid={`upload-row-${doc.id}`}>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${colorCls}`}>
                        <Icon size={16} />
                      </div>
                      <span className="max-w-[200px] truncate text-sm font-medium text-foreground">{doc.name}</span>
                    </div>
                  </td>
                  <td className="py-3 px-3 text-xs text-muted-foreground">{doc.category}</td>
                  <td className="py-3 px-3 text-xs text-muted-foreground">{doc.size}</td>
                  <td className="py-3 px-3 text-xs text-[#7a9a72]">{doc.uploadedAt}</td>
                  <td className="py-3 px-3">
                    <button className="p-1 rounded hover:bg-accent text-muted-foreground">
                      <MoreVertical size={14} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="sm:hidden divide-y divide-border">
        {documents.map((doc) => {
          const Icon = FILE_ICON_MAP[doc.fileType];
          const colorCls = FILE_COLOR_MAP[doc.fileType];
          return (
            <div key={doc.id} className="flex items-center gap-3 px-4 py-3">
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${colorCls}`}>
                <Icon size={16} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">{doc.name}</p>
                <p className="text-xs text-muted-foreground">{doc.category} · {doc.size} · {doc.uploadedAt}</p>
              </div>
              <button className="p-1 rounded hover:bg-accent text-muted-foreground flex-shrink-0">
                <MoreVertical size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
