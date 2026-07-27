import { useState } from 'react';
import { ChevronRight, FileText, Folder } from 'lucide-react';
import { useLocation } from 'wouter';
import type { CorpusTreeNode } from '@/api/types';
import { cn } from '@/lib/utils';

function containsDocument(node: CorpusTreeNode, documentId: string): boolean {
  const documents = node.documents ?? node.files ?? [];
  return documents.some((document) => document.id === documentId)
    || node.children.some((child) => containsDocument(child, documentId));
}

function TreeNode({node,selectedDocumentId}:{node:CorpusTreeNode;selectedDocumentId:string}){
  const[,navigate]=useLocation();const contains=containsDocument(node,selectedDocumentId);const[open,setOpen]=useState(node.depth<2||contains);const documents=node.documents??node.files??[];
  return <div><button onClick={()=>setOpen((value)=>!value)} className="flex h-8 w-full items-center gap-1.5 rounded-md px-2 text-left text-xs font-medium text-foreground transition-colors duration-[160ms] hover:bg-muted" style={{paddingLeft:`${Math.min(node.depth,6)*12+8}px`}}><ChevronRight size={13} className={cn('text-muted-foreground transition duration-[160ms]',open&&'rotate-90')}/><Folder size={14} className="text-primary/75"/><span className="truncate">{node.name||'Root'}</span></button>{open?<div>{node.children.map((child)=><TreeNode key={child.id??child.relative_path} node={child} selectedDocumentId={selectedDocumentId}/>)}{documents.map((document)=><button key={document.id} onClick={()=>navigate(`/knowledge/document/${document.id}`)} className={cn('flex h-8 w-full items-center gap-2 rounded-md pr-2 text-left text-xs transition-colors duration-[160ms] hover:bg-muted',document.id===selectedDocumentId&&'bg-accent font-semibold text-primary shadow-[inset_2px_0_0_hsl(var(--primary))]')} style={{paddingLeft:`${Math.min(node.depth+1,7)*12+22}px`}}><FileText size={13}/><span className="truncate">{document.name}</span></button>)}</div>:null}</div>;
}

export default function CorpusTreePanel({root,selectedDocumentId}:{root:CorpusTreeNode;selectedDocumentId:string}){return <div className="h-full overflow-y-auto px-2 py-3"><h2 className="mb-2 px-2 text-sm font-semibold">Corpus Tree</h2><TreeNode node={root} selectedDocumentId={selectedDocumentId}/></div>;}
