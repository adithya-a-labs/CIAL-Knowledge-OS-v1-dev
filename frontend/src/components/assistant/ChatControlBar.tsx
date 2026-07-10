import { BookOpenCheck } from 'lucide-react';
import { ResponseLengthPopover, SearchModePopover } from './AssistantSettingsPopover';
import type { ResponseLength, SearchScope } from '@/types/assistant';

interface ChatControlBarProps {
  searchScope: SearchScope;
  activeProfile: ResponseLength;
  selectedContextCount: number;
  uploadedFileCount: number;
  onSearchScopeChange: (value: SearchScope) => void;
  onActiveProfileChange: (value: ResponseLength) => void;
  onManageContext: () => void;
  onClearContext?: () => void;
}

export default function ChatControlBar({
  searchScope,
  activeProfile,
  selectedContextCount,
  uploadedFileCount,
  onSearchScopeChange,
  onActiveProfileChange,
  onManageContext,
  onClearContext,
}: ChatControlBarProps) {
  const totalContextCount = selectedContextCount + uploadedFileCount;
  const scopeLocked = totalContextCount > 0;

  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="assistant-composer-controls">
      <button
        type="button"
        onClick={onManageContext}
        className="inline-flex h-7 items-center gap-1.5 rounded-md border border-[#dce4d8] bg-[#f7faf5] px-2 text-[11px] font-medium text-primary transition hover:bg-[#eef5e8]"
        data-testid="button-manage-context"
      >
        <BookOpenCheck size={13} />
        Context
        <span className="rounded-sm bg-white px-1 py-0 text-[10px] text-primary shadow-[inset_0_0_0_1px_rgba(47,109,37,0.08)]">
          {totalContextCount}
        </span>
      </button>

      <div className="flex items-center gap-1.5" data-testid="select-search-scope">
        <SearchModePopover value={searchScope} onChange={onSearchScopeChange} disabled={scopeLocked} />
        {scopeLocked ? (
          <span className="text-[10px] font-medium text-muted-foreground">
            Scope limited to selected context.
          </span>
        ) : null}
      </div>

      <div data-testid="select-response-length">
        <ResponseLengthPopover value={activeProfile} onChange={onActiveProfileChange} />
      </div>

      {totalContextCount > 0 && onClearContext ? (
        <button
          type="button"
          onClick={onClearContext}
          className="inline-flex h-7 items-center rounded-md border border-transparent px-2 text-[11px] font-medium text-muted-foreground transition hover:border-border hover:bg-[#f6f8f5] hover:text-foreground"
          data-testid="button-clear-context"
        >
          Clear
        </button>
      ) : null}
    </div>
  );
}
