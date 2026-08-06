import { FolderOpen, MoreVertical, Plus } from 'lucide-react';
import type { WorkspaceCollection } from '@/data/workspace/workspaceTypes';

interface CollectionCardProps {
  collection: WorkspaceCollection;
}

export function CollectionCard({ collection }: CollectionCardProps) {
  return (
    <div
      className="fluid-card responsive-card flex min-h-32 flex-col gap-2 border border-border bg-card p-4 shadow-sm"
      data-testid={`collection-card-${collection.id}`}
    >
      <div className="flex items-start justify-between">
        <div className="w-9 h-9 rounded-lg bg-accent flex items-center justify-center">
          <FolderOpen size={18} className="text-primary" />
        </div>
        <button className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring" aria-label={`More actions for ${collection.name}`}>
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
      className="fluid-card responsive-card flex min-h-32 w-full cursor-pointer flex-col items-center justify-center gap-2 border border-dashed border-primary/35 bg-card p-4 hover:border-primary hover:bg-muted"
      data-testid="button-new-collection"
    >
      <div className="w-9 h-9 rounded-full bg-accent flex items-center justify-center">
        <Plus size={18} className="text-primary" />
      </div>
      <p className="text-sm font-medium text-primary">New Collection</p>
    </button>
  );
}
