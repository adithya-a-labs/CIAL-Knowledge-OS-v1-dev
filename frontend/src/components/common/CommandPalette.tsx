import * as React from 'react';
import { createContext, useContext, useEffect, useState, useMemo } from 'react';
import { useLocation } from 'wouter';
import { useQuery } from '@tanstack/react-query';
import {
  Search,
  FileText,
  Folder,
  Building2,
  MessageSquare,
  Bookmark,
  User,
  Settings,
  Sparkles,
  UploadCloud,
  FileSpreadsheet,
  PlusCircle,
} from 'lucide-react';
import { getCorpusTree } from '@/api/client';
import { flattenCorpusTree } from '@/api/adapters';
import { DEPARTMENTS } from '@/data/departmentsData';
import { MY_DOCUMENTS, MY_CONVERSATIONS } from '@/data/workspace/workspaceData';
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from '@/components/ui/command';
import { Kbd } from '@/components/ui/kbd';

export interface CommandPaletteItem {
  id: string;
  title: string;
  subtitle?: string;
  category:
    | 'Documents'
    | 'Folders'
    | 'Departments'
    | 'AI Conversations'
    | 'Saved Knowledge'
    | 'My Workspace'
    | 'Policies'
    | 'Settings'
    | 'Recent Items'
    | 'Commands';
  action: () => void;
  icon?: React.ComponentType<{ size?: number; className?: string }>;
}

export interface CommandPaletteSearchProvider {
  search: (query: string) => Promise<CommandPaletteItem[]>;
}

interface CommandPaletteContextProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  provider: CommandPaletteSearchProvider;
  setProvider: (provider: CommandPaletteSearchProvider) => void;
  triggerAction: (item: CommandPaletteItem) => void;
}

const CommandPaletteContext = createContext<CommandPaletteContextProps | null>(null);

export function useCommandPalette() {
  const context = useContext(CommandPaletteContext);
  if (!context) {
    throw new Error('useCommandPalette must be used within a CommandPaletteProvider');
  }
  return context;
}

// Local Storage Keys
const RECENTS_KEY = 'cial-command-palette-recents-v1';
const ASSISTANT_CONTEXT_STORAGE_KEY = 'cial-assistant-selected-context';
const ASSISTANT_NEW_SESSION_PENDING_STORAGE_KEY = 'cial-new-conversation-pending';
const NEW_CONVERSATION_EVENT = 'cial-new-conversation';

export function CommandPaletteProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [, navigate] = useLocation();

  // New session trigger logic helper
  const startNewConversation = () => {
    window.localStorage.removeItem(ASSISTANT_CONTEXT_STORAGE_KEY);
    window.localStorage.setItem(ASSISTANT_NEW_SESSION_PENDING_STORAGE_KEY, String(Date.now()));
    window.dispatchEvent(new Event(NEW_CONVERSATION_EVENT));
  };

  // React Query fetch for documents & folders to keep search context fresh
  const { data: corpusTree } = useQuery({
    queryKey: ['corpus-tree-command-palette'],
    queryFn: getCorpusTree,
    retry: false,
    staleTime: 60_000,
  });

  const corpusDocuments = useMemo(() => {
    if (!corpusTree?.root) return [];
    return flattenCorpusTree(corpusTree.root).documents;
  }, [corpusTree]);

  // Default Client-side Search Provider
  const defaultProvider = useMemo<CommandPaletteSearchProvider>(() => {
    return {
      search: async (query: string) => {
        const lowerQuery = query.toLowerCase().trim();

        // 1. Static Commands list
        const commandsList: CommandPaletteItem[] = [
          {
            id: 'cmd-assistant',
            title: 'Open AI Assistant',
            subtitle: 'Ask questions with grounded sources',
            category: 'Commands',
            icon: Sparkles,
            action: () => navigate('/assistant'),
          },
          {
            id: 'cmd-knowledge-center',
            title: 'Open Knowledge Center',
            subtitle: 'Browse all manuals and SOPs',
            category: 'Commands',
            icon: Bookmark,
            action: () => navigate('/knowledge-center'),
          },
          {
            id: 'cmd-new-chat',
            title: 'New Conversation',
            subtitle: 'Start a clean AI assistant session',
            category: 'Commands',
            icon: PlusCircle,
            action: () => {
              startNewConversation();
              navigate('/assistant');
            },
          },
          {
            id: 'cmd-upload',
            title: 'Upload File',
            subtitle: 'Add new documents to your workspace',
            category: 'Commands',
            icon: UploadCloud,
            action: () => navigate('/workspace/documents'),
          },
          {
            id: 'cmd-search-docs',
            title: 'Search Documents',
            subtitle: 'View and search enterprise documents',
            category: 'Commands',
            icon: FileText,
            action: () => navigate('/documents'),
          },
          {
            id: 'cmd-settings',
            title: 'Go to Settings',
            subtitle: 'Manage profile and workspace configuration',
            category: 'Commands',
            icon: Settings,
            action: () => navigate('/admin'),
          },
        ];

        if (!lowerQuery) {
          return commandsList;
        }

        const results: CommandPaletteItem[] = [];

        // Match commands
        commandsList.forEach((cmd) => {
          if (cmd.title.toLowerCase().includes(lowerQuery) || cmd.subtitle?.toLowerCase().includes(lowerQuery)) {
            results.push(cmd);
          }
        });

        // 2. Documents (Enterprise)
        corpusDocuments.forEach((doc) => {
          if (doc.name.toLowerCase().includes(lowerQuery) || doc.relative_path.toLowerCase().includes(lowerQuery)) {
            const isPolicy =
              doc.name.toLowerCase().includes('sop') ||
              doc.name.toLowerCase().includes('policy') ||
              doc.name.toLowerCase().includes('circular') ||
              doc.relative_path.toLowerCase().includes('policy') ||
              doc.relative_path.toLowerCase().includes('sop');

            results.push({
              id: `doc-${doc.id}`,
              title: doc.name,
              subtitle: `Enterprise / ${doc.file_type.toUpperCase()} / ${doc.relative_path}`,
              category: isPolicy ? 'Policies' : 'Documents',
              icon: doc.file_type === 'xlsx' || doc.file_type === 'csv' ? FileSpreadsheet : FileText,
              action: () => navigate(`/knowledge/document/${doc.id}`),
            });
          }
        });

        // 3. Folders
        if (corpusTree?.root) {
          const findFolders = (node: any) => {
            if (node.type === 'folder') {
              if (node.name.toLowerCase().includes(lowerQuery)) {
                results.push({
                  id: `folder-${node.id || node.name}`,
                  title: node.name,
                  subtitle: `Folder / ${node.relative_path || 'Root'}`,
                  category: 'Folders',
                  icon: Folder,
                  action: () => navigate('/knowledge-center'),
                });
              }
            }
            if (node.children) {
              node.children.forEach(findFolders);
            }
          };
          findFolders(corpusTree.root);
        }

        // 4. Departments
        DEPARTMENTS.forEach((dept) => {
          if (dept.name.toLowerCase().includes(lowerQuery) || dept.headName.toLowerCase().includes(lowerQuery)) {
            results.push({
              id: `dept-${dept.id}`,
              title: `${dept.name} Department`,
              subtitle: `Head: ${dept.headName} / ${dept.stats.documents} documents`,
              category: 'Departments',
              icon: Building2,
              action: () => navigate('/departments'),
            });
          }
        });

        // 5. AI Conversations (from localStorage sessions + Workspace Mock Data)
        const localConversations: any[] = [];
        try {
          const raw = localStorage.getItem('cial-assistant-sessions');
          if (raw) {
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed)) {
              localConversations.push(...parsed);
            }
          }
        } catch {}

        const allConvos = [
          ...localConversations.map((c) => ({ id: c.id, question: c.title })),
          ...MY_CONVERSATIONS,
        ];

        const seenConvoTitles = new Set<string>();
        allConvos.forEach((convo) => {
          if (seenConvoTitles.has(convo.question.toLowerCase())) return;
          if (convo.question.toLowerCase().includes(lowerQuery)) {
            seenConvoTitles.add(convo.question.toLowerCase());
            results.push({
              id: `convo-${convo.id}`,
              title: convo.question,
              subtitle: 'AI Conversation',
              category: 'AI Conversations',
              icon: MessageSquare,
              action: () => navigate('/assistant'),
            });
          }
        });

        // 6. Saved Knowledge & Workspace notes
        const savedKnowledgeItems = [
          'Fire alarm escalation SOP',
          'Runway Lighting System - Maintenance Manual',
          'Baggage Handling Safety SOP',
          'DG set backup failure sequence',
          'PAPI calibration summary',
        ];
        savedKnowledgeItems.forEach((title, idx) => {
          if (title.toLowerCase().includes(lowerQuery)) {
            results.push({
              id: `saved-${idx}`,
              title: title,
              subtitle: 'Saved Bookmarked Knowledge',
              category: 'Saved Knowledge',
              icon: Bookmark,
              action: () => navigate('/saved-knowledge'),
            });
          }
        });

        const workspaceNotes = [
          'PAPI alignment observation',
          'Vendor call notes',
          'AGL controller reset checklist',
        ];
        workspaceNotes.forEach((title, idx) => {
          if (title.toLowerCase().includes(lowerQuery)) {
            results.push({
              id: `note-${idx}`,
              title: title,
              subtitle: 'My Notes',
              category: 'My Workspace',
              icon: User,
              action: () => navigate('/workspace'),
            });
          }
        });

        // 7. Workspace private documents
        MY_DOCUMENTS.forEach((doc) => {
          if (doc.name.toLowerCase().includes(lowerQuery)) {
            results.push({
              id: `my-doc-${doc.id}`,
              title: doc.name,
              subtitle: `Private Workspace Document / ${doc.category}`,
              category: 'My Workspace',
              icon: FileText,
              action: () => navigate('/workspace'),
            });
          }
        });

        return results;
      },
    };
  }, [corpusDocuments, corpusTree, navigate]);

  const [provider, setProvider] = useState<CommandPaletteSearchProvider>(defaultProvider);

  // Register default provider when corpusTree changes
  useEffect(() => {
    setProvider(defaultProvider);
  }, [defaultProvider]);

  // Global keydown listeners for Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const triggerAction = (item: CommandPaletteItem) => {
    item.action();
    setOpen(false);

    // Save to recents in localStorage
    try {
      const recentsRaw = localStorage.getItem(RECENTS_KEY);
      let recents: any[] = recentsRaw ? JSON.parse(recentsRaw) : [];
      // Remove duplicates
      recents = recents.filter((r) => r.id !== item.id);
      // Prepend
      recents.unshift({
        id: item.id,
        title: item.title,
        subtitle: item.subtitle,
        category: item.category,
        actionString: item.action.toString(),
      });
      // Limit to 5
      localStorage.setItem(RECENTS_KEY, JSON.stringify(recents.slice(0, 5)));
    } catch (e) {
      console.error(e);
    }
  };

  const contextValue = useMemo<CommandPaletteContextProps>(
    () => ({
      open,
      setOpen,
      provider,
      setProvider,
      triggerAction,
    }),
    [open, provider]
  );

  return (
    <CommandPaletteContext.Provider value={contextValue}>
      {children}
    </CommandPaletteContext.Provider>
  );
}

export function CommandPalette() {
  const { open, setOpen, provider, triggerAction } = useCommandPalette();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<CommandPaletteItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [, navigate] = useLocation();

  // Load Recents from LocalStorage
  const recentItems = useMemo<CommandPaletteItem[]>(() => {
    if (query) return [];
    try {
      const recentsRaw = localStorage.getItem(RECENTS_KEY);
      if (recentsRaw) {
        const parsed = JSON.parse(recentsRaw);
        if (Array.isArray(parsed)) {
          return parsed.map((item: any) => {
            // Re-bind actions based on category / id
            let action = () => {};
            if (item.id.startsWith('cmd-')) {
              if (item.id === 'cmd-assistant') action = () => navigate('/assistant');
              if (item.id === 'cmd-knowledge-center') action = () => navigate('/knowledge-center');
              if (item.id === 'cmd-new-chat') {
                action = () => {
                  window.localStorage.removeItem(ASSISTANT_CONTEXT_STORAGE_KEY);
                  window.localStorage.setItem(ASSISTANT_NEW_SESSION_PENDING_STORAGE_KEY, String(Date.now()));
                  window.dispatchEvent(new Event(NEW_CONVERSATION_EVENT));
                  navigate('/assistant');
                };
              }
              if (item.id === 'cmd-upload') action = () => navigate('/workspace/documents');
              if (item.id === 'cmd-search-docs') action = () => navigate('/documents');
              if (item.id === 'cmd-settings') action = () => navigate('/admin');
            } else if (item.id.startsWith('doc-')) {
              const docId = item.id.replace('doc-', '');
              action = () => navigate(`/knowledge/document/${docId}`);
            } else if (item.id.startsWith('folder-')) {
              action = () => navigate('/knowledge-center');
            } else if (item.id.startsWith('dept-')) {
              action = () => navigate('/departments');
            } else if (item.id.startsWith('convo-')) {
              action = () => navigate('/assistant');
            } else if (item.id.startsWith('saved-')) {
              action = () => navigate('/saved-knowledge');
            } else if (item.id.startsWith('note-') || item.id.startsWith('my-doc-')) {
              action = () => navigate('/workspace');
            }

            return {
              id: item.id,
              title: item.title,
              subtitle: item.subtitle,
              category: 'Recent Items' as const,
              action,
              icon: item.id.startsWith('cmd-')
                ? Sparkles
                : item.id.startsWith('doc-')
                ? FileText
                : item.id.startsWith('folder-')
                ? Folder
                : item.id.startsWith('dept-')
                ? Building2
                : item.id.startsWith('convo-')
                ? MessageSquare
                : item.id.startsWith('saved-')
                ? Bookmark
                : User,
            };
          });
        }
      }
    } catch {}
    return [];
  }, [query, open, navigate]);

  // Execute Search from Provider on query change
  useEffect(() => {
    let active = true;
    const runSearch = async () => {
      setLoading(true);
      try {
        const searchResults = await provider.search(query);
        if (active) {
          setResults(searchResults);
        }
      } catch (err) {
        console.error('Command Palette Search Error:', err);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    const debounceTimer = setTimeout(() => {
      void runSearch();
    }, 100);

    return () => {
      active = false;
      clearTimeout(debounceTimer);
    };
  }, [query, provider, open]);

  // Reset query on close
  useEffect(() => {
    if (!open) {
      setQuery('');
    }
  }, [open]);

  // Group search results by category
  const groupedResults = useMemo(() => {
    const groups: Record<string, CommandPaletteItem[]> = {};
    results.forEach((item) => {
      if (!groups[item.category]) {
        groups[item.category] = [];
      }
      groups[item.category].push(item);
    });
    return groups;
  }, [results]);

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder="Type a command or search workspace resources..."
        value={query}
        onValueChange={setQuery}
      />
      <CommandList className="max-h-[360px] overflow-y-auto p-2 scrollbar-soft">
        <CommandEmpty>
          {loading ? (
            <div className="py-6 text-center text-sm text-slate-500">Searching workspace...</div>
          ) : (
            <div className="py-6 text-center text-sm text-slate-500">No results found for "{query}"</div>
          )}
        </CommandEmpty>

        {/* 1. Show Recents when query is empty */}
        {recentItems.length > 0 && (
          <CommandGroup heading="Recent Searches & Actions">
            {recentItems.map((item) => {
              const Icon = item.icon || Search;
              return (
                <CommandItem
                  key={item.id}
                  onSelect={() => triggerAction(item)}
                  className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 cursor-pointer transition"
                >
                  <Icon size={16} className="text-slate-400 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-slate-900 truncate">{item.title}</div>
                    {item.subtitle && <div className="text-xs text-slate-500 truncate">{item.subtitle}</div>}
                  </div>
                </CommandItem>
              );
            })}
          </CommandGroup>
        )}

        {/* 2. Show Search results */}
        {Object.entries(groupedResults).map(([category, items]) => (
          <CommandGroup key={category} heading={category}>
            {items.map((item) => {
              const Icon = item.icon || Search;
              return (
                <CommandItem
                  key={item.id}
                  onSelect={() => triggerAction(item)}
                  className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 cursor-pointer transition"
                >
                  <Icon size={16} className="text-slate-400 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-slate-900 truncate">{item.title}</div>
                    {item.subtitle && <div className="text-xs text-slate-500 truncate">{item.subtitle}</div>}
                  </div>
                </CommandItem>
              );
            })}
          </CommandGroup>
        ))}
      </CommandList>
      <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2 text-[10px] text-slate-400 bg-slate-50/50">
        <div className="flex items-center gap-3">
          <span>
            <Kbd className="mr-1 text-[9px] bg-white border border-slate-200">↑↓</Kbd> Navigate
          </span>
          <span>
            <Kbd className="mr-1 text-[9px] bg-white border border-slate-200">Enter</Kbd> Select
          </span>
          <span>
            <Kbd className="mr-1 text-[9px] bg-white border border-slate-200">ESC</Kbd> Close
          </span>
        </div>
        <div>Universal Command Palette</div>
      </div>
    </CommandDialog>
  );
}
