import { FolderOpen, MoreVertical, Plus } from 'lucide-react';
import type { WorkspaceCollection } from '@/data/workspace/workspaceTypes';

interface CollectionCardProps {
  collection: WorkspaceCollection;
}

export function CollectionCard({ collection }: CollectionCardProps) {
  return (
    <div
      className="fluid-card responsive-card flex min-h-32 cursor-pointer flex-col gap-2 border border-[#e2eedd] bg-white p-4 shadow-sm transition-all hover:border-[#4a7c3f] hover:shadow-md"
      data-testid={`collection-card-${collection.id}`}
    >
      <div className="flex items-start justify-between">
        <div className="w-9 h-9 rounded-lg bg-[#f0f7ed] flex items-center justify-center">
          <FolderOpen size={18} className="text-[#4a7c3f]" />
        </div>
        <button className="p-1 rounded hover:bg-[#f0f7ed] text-[#5a7a52]">
          <MoreVertical size={14} />
        </button>
      </div>
      <div>
        <p className="safe-text text-sm font-semibold text-[#1a2e14]">{collection.name}</p>
        <p className="text-xs text-[#5a7a52]">{collection.itemCount} items</p>
      </div>
    </div>
  );
}

export function NewCollectionCard({ onClick }: { onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="fluid-card responsive-card flex min-h-32 w-full cursor-pointer flex-col items-center justify-center gap-2 border border-dashed border-[#b8d9b0] bg-white p-4 transition-all hover:border-[#4a7c3f] hover:bg-[#f8fdf6]"
      data-testid="button-new-collection"
    >
      <div className="w-9 h-9 rounded-full bg-[#f0f7ed] flex items-center justify-center">
        <Plus size={18} className="text-[#4a7c3f]" />
      </div>
      <p className="text-sm font-medium text-[#4a7c3f]">New Collection</p>
    </button>
  );
}
