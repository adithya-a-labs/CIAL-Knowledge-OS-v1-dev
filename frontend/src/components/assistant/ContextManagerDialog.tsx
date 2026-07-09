import { useEffect, useState } from 'react';
import CorpusExplorer from '@/components/corpus/CorpusExplorer';
import type { SelectedContextItem } from '@/api/types';

interface ContextManagerDialogProps {
  open: boolean;
  selectedItems: SelectedContextItem[];
  onApply: (items: SelectedContextItem[]) => void;
  onClose: () => void;
}

export default function ContextManagerDialog({
  open,
  selectedItems,
  onApply,
  onClose,
}: ContextManagerDialogProps) {
  const [draftItems, setDraftItems] = useState<SelectedContextItem[]>(selectedItems);

  useEffect(() => {
    if (open) setDraftItems(selectedItems);
  }, [open, selectedItems]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-3" data-testid="context-manager-dialog">
      <div className="flex h-[min(92dvh,56rem)] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-border bg-white p-4 shadow-2xl">
        <CorpusExplorer
          mode="select"
          selectedItems={draftItems}
          onSelectionChange={setDraftItems}
          onApplySelection={(items) => {
            onApply(items);
            onClose();
          }}
          onCancel={onClose}
        />
      </div>
    </div>
  );
}
