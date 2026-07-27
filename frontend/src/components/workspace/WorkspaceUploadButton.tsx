import { Upload, AlertTriangle } from 'lucide-react';
import { WORKSPACE_STORAGE } from '@/data/workspace/workspaceData';
import { isStorageFull } from '@/data/workspace/storageUtils';

interface WorkspaceUploadButtonProps {
  onClick?: () => void;
  className?: string;
}

export default function WorkspaceUploadButton({ onClick, className = '' }: WorkspaceUploadButtonProps) {
  const full = isStorageFull(WORKSPACE_STORAGE);

  if (full) {
    return (
      <div className={`flex items-center gap-2 px-4 py-2 rounded-lg bg-warning/10 border border-warning/30 text-warning-foreground text-sm font-medium ${className}`}>
        <AlertTriangle size={15} />
        Storage full — cannot upload
      </div>
    );
  }

  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg bg-[#4a7c3f] hover:bg-[#2d4f22] text-white text-sm font-semibold shadow-sm transition-colors ${className}`}
      data-testid="button-workspace-upload"
    >
      <Upload size={15} />
      Upload File
    </button>
  );
}
