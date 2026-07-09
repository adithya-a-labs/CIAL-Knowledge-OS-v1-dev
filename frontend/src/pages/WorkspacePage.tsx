import { Link, useLocation } from 'wouter';
import type React from 'react';
import {
  Bookmark,
  Clock3,
  FileText,
  MessageSquare,
  NotebookPen,
  Pin,
  Search,
  Sparkles,
} from 'lucide-react';
import PrivacyBadge from '@/components/workspace/PrivacyBadge';
import WorkspaceUploadButton from '@/components/workspace/WorkspaceUploadButton';
import {
  CURRENT_WORKSPACE_USER_ID,
  MY_CONVERSATIONS,
  MY_DOCUMENTS,
  RECENT_ACTIVITY,
  WORKSPACE_STORAGE,
} from '@/data/workspace/workspaceData';
import { getVisibleDocuments } from '@/data/workspace/workspacePermissions';

const savedItems = {
  documents: ['Fire alarm escalation SOP', 'Runway Lighting System - Maintenance Manual', 'Baggage Handling Safety SOP'],
  answers: ['DG set backup failure sequence', 'PAPI calibration summary'],
  searches: ['CAT III documents', 'wildlife hazard management'],
  conversations: ['Runway edge lights troubleshooting', 'Terminal HVAC preventive maintenance'],
};

function WorkspaceSection({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="min-w-0">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-950">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function DocumentList({ documents }: { documents: typeof MY_DOCUMENTS }) {
  return (
    <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
      {documents.map((doc) => (
        <div key={doc.id} className="flex items-center gap-3 px-4 py-3">
          <FileText size={17} className="shrink-0 text-primary" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-slate-900">{doc.name}</p>
            <p className="mt-0.5 truncate text-xs text-slate-500">{doc.category} / {doc.fileType.toUpperCase()} / {doc.uploadedAt}</p>
          </div>
          <span className="ce-badge hidden sm:inline-flex">{doc.size}</span>
        </div>
      ))}
    </div>
  );
}

function SavedKnowledgeView() {
  const groups = [
    { title: 'Saved Documents', icon: FileText, values: savedItems.documents },
    { title: 'Saved AI Answers', icon: Sparkles, values: savedItems.answers },
    { title: 'Saved Searches', icon: Search, values: savedItems.searches },
    { title: 'Saved Conversations', icon: MessageSquare, values: savedItems.conversations },
  ];

  return (
    <div className="mx-auto flex w-full max-w-[86rem] flex-col gap-6" data-testid="saved-knowledge-page">
      <div>
        <p className="text-xs font-semibold uppercase text-slate-500">Saved Knowledge</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-950">Saved documents, answers, searches, and conversations</h1>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {groups.map((group) => {
          const Icon = group.icon;
          return (
            <section key={group.title} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-950"><Icon size={16} className="text-primary" />{group.title}</h2>
              <div className="mt-3 divide-y divide-slate-100">
                {group.values.map((item) => (
                  <button key={item} className="flex w-full items-center justify-between gap-3 py-3 text-left text-sm text-slate-800 hover:text-primary">
                    <span className="truncate">{item}</span>
                    <Bookmark size={14} className="shrink-0" />
                  </button>
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

export default function WorkspacePage() {
  const [location] = useLocation();
  const currentUser = { id: CURRENT_WORKSPACE_USER_ID, role: 'engineer' };
  const visibleDocs = getVisibleDocuments(currentUser, MY_DOCUMENTS);
  const visibleConvos = MY_CONVERSATIONS.filter((conversation) => conversation.ownerId === currentUser.id);

  if (location === '/saved-knowledge' || location === '/workspace/bookmarks') return <SavedKnowledgeView />;

  return (
    <div className="mx-auto flex w-full max-w-[86rem] flex-col gap-6" data-testid="workspace-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-xs font-semibold uppercase text-slate-500">My Workspace</p>
            <PrivacyBadge size="sm" />
          </div>
          <h1 className="mt-2 text-3xl font-semibold text-slate-950">Personal knowledge workspace</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Private documents, notes, pins, saved knowledge, uploads, and AI work in one place.</p>
        </div>
        <WorkspaceUploadButton onClick={() => {}} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-6">
          <WorkspaceSection title="My Documents" action={<Link href="/knowledge-center" className="text-xs font-semibold text-primary">Browse enterprise</Link>}>
            <DocumentList documents={visibleDocs} />
          </WorkspaceSection>

          <div className="grid gap-6 lg:grid-cols-2">
            <WorkspaceSection title="My Notes">
              <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
                {['PAPI alignment observation', 'Vendor call notes', 'AGL controller reset checklist'].map((note) => (
                  <button key={note} className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left hover:bg-slate-50">
                    <NotebookPen size={16} className="text-primary" />
                    <span className="truncate text-sm font-medium text-slate-900">{note}</span>
                  </button>
                ))}
              </div>
            </WorkspaceSection>

            <WorkspaceSection title="Pinned Knowledge">
              <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
                {['Runway Lighting', 'Electrical Systems', 'Maintenance Notes', 'Vendor Manuals'].map((item) => (
                  <Link key={item} href="/saved-knowledge" className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-slate-50">
                    <Bookmark size={16} className="text-primary" />
                    <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-900">{item}</span>
                  </Link>
                ))}
              </div>
            </WorkspaceSection>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <WorkspaceSection title="Recent Uploads">
              <DocumentList documents={visibleDocs.slice(0, 3)} />
            </WorkspaceSection>

            <WorkspaceSection title="Recent AI Conversations">
              <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
                {visibleConvos.slice(0, 4).map((conversation) => (
                  <Link key={conversation.id} href="/assistant" className="flex items-start gap-3 px-4 py-3 hover:bg-slate-50">
                    <MessageSquare size={16} className="mt-0.5 shrink-0 text-primary" />
                    <span className="min-w-0 flex-1">
                      <span className="line-clamp-2 text-sm font-medium text-slate-900">{conversation.question}</span>
                      <span className="mt-1 block text-xs text-slate-500">{conversation.sources.join(' + ')} / {conversation.time}</span>
                    </span>
                  </Link>
                ))}
              </div>
            </WorkspaceSection>
          </div>
        </div>

        <aside className="space-y-4">
          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-950">Pinned</h2>
            <div className="mt-3 space-y-2">
              {['Runway Lighting', 'Fire Safety SOP', 'Vendor Manuals'].map((item) => (
                <button key={item} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm hover:bg-slate-50">
                  <Pin size={14} className="text-primary" />
                  <span className="truncate">{item}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-950">Storage</h2>
            <p className="mt-2 text-sm text-slate-600">{WORKSPACE_STORAGE.usedGB} GB of {WORKSPACE_STORAGE.totalGB} GB used</p>
            <div className="mt-3 h-2 rounded-full bg-slate-100">
              <div className="h-2 rounded-full bg-primary" style={{ width: `${WORKSPACE_STORAGE.percentUsed}%` }} />
            </div>
            <p className="mt-2 text-xs text-slate-500">{WORKSPACE_STORAGE.availableGB} GB available</p>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-950">Recent activity</h2>
            <div className="mt-3 space-y-3">
              {RECENT_ACTIVITY.map((activity) => (
                <div key={activity.id} className="flex items-start gap-2 text-xs">
                  <Clock3 size={14} className="mt-0.5 shrink-0 text-slate-400" />
                  <span className="min-w-0">
                    <span className="block text-slate-800">{activity.description}</span>
                    <span className="mt-0.5 block text-slate-500">{activity.time}</span>
                  </span>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
