import { FolderOpen, MoreVertical, Plus } from 'lucide-react';
import type { WorkspaceCollection } from '@/data/workspace/workspaceTypes';

interface CollectionCardProps {
  collection: WorkspaceCollection;
}

export function CollectionCard({ collection }: CollectionCardProps) {
  return (
    <div
      className="fluid-card responsive-card flex min-h-32 cursor-pointer flex-col gap-2 border border-border bg-card p-4 shadow-sm transition-all hover:border-primary hover:shadow-md"
      data-testid={`collection-card-${collection.id}`}
    >
      <div className="flex items-start justify-between">
        <div className="w-9 h-9 rounded-lg bg-accent flex items-center justify-center">
          <FolderOpen size={18} className="text-primary" />
        </div>
        <button className="p-1 rounded hover:bg-accent text-muted-foreground">
          <MoreVertical size={14} />
        </button>
      </div>
      <div>
        <p className="safe-text text-sm font-semibold text-foreground">{collection.name}</p>
        <p className="text-xs text-muted-foreground">{collection.itemCount} items</p>
      </div>
    </div>
  );
}

export function NewCollectionCard({ onClick }: { onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="fluid-card responsive-card flex min-h-32 w-full cursor-pointer flex-col items-center justify-center gap-2 border border-dashed border-primary/35 bg-card p-4 transition-all hover:border-primary hover:bg-muted"
      data-testid="button-new-collection"
    >
      <div className="w-9 h-9 rounded-full bg-accent flex items-center justify-center">
        <Plus size={18} className="text-primary" />
      </div>
      <p className="text-sm font-medium text-primary">New Collection</p>
    </button>
  );
}
