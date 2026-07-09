import { useState } from 'react';
import { useLocation } from 'wouter';
import CorpusExplorer from '@/components/corpus/CorpusExplorer';
import type { SelectedContextItem } from '@/api/types';

const ASSISTANT_CONTEXT_STORAGE_KEY = 'cial-assistant-selected-context';
const ASSISTANT_CONTEXT_INTENT_STORAGE_KEY = 'cial-assistant-context-intent';

export function KnowledgeCenterPage() {
  const [, navigate] = useLocation();
  const [selectedItems, setSelectedItems] = useState<SelectedContextItem[]>([]);

  const useInAssistant = (items: SelectedContextItem[]) => {
    window.localStorage.setItem(ASSISTANT_CONTEXT_STORAGE_KEY, JSON.stringify(items));
    window.localStorage.setItem(ASSISTANT_CONTEXT_INTENT_STORAGE_KEY, String(Date.now()));
    navigate('/assistant');
  };

  return (
    <div className="fluid-section flex h-full min-h-0 flex-col overflow-hidden" data-testid="knowledge-center-page">
      <CorpusExplorer
        mode="browse"
        selectedItems={selectedItems}
        onSelectionChange={setSelectedItems}
        onUseInAssistant={useInAssistant}
      />
    </div>
  );
}
