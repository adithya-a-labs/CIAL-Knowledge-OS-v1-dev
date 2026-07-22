import { useState } from 'react';
import { useLocation } from 'wouter';
import CorpusExplorer from '@/components/corpus/CorpusExplorer';
import type { SelectedContextItem } from '@/api/types';
import { createConversationHandoff } from '@/lib/conversationHandoff';

export function KnowledgeCenterPage() {
  const [, navigate] = useLocation();
  const [selectedItems, setSelectedItems] = useState<SelectedContextItem[]>([]);

  const useInAssistant = async (items: SelectedContextItem[]) => {
    const documents=items.filter((item)=>item.type==='document').map((item)=>item.id);const notes=items.filter((item)=>item.type==='note').map((item)=>item.id);
    const session=await createConversationHandoff({title:items.length===1?items[0].title:`${items.length} selected knowledge sources`,origin:'knowledge_center',context_scope:'selected_context',selected_document_ids:documents,selected_note_ids:notes,contextItems:items.filter((item)=>item.type==='document'||item.type==='note')});
    navigate(`/assistant?session=${session.id}`);
  };

  return (
    <div className="fluid-section flex h-full min-h-0 flex-col overflow-hidden" data-testid="knowledge-center-page">
      <CorpusExplorer
        mode="browse"
        selectedItems={selectedItems}
        onSelectionChange={setSelectedItems}
        onUseInAssistant={(items)=>void useInAssistant(items)}
      />
    </div>
  );
}
