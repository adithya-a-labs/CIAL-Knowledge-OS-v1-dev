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

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="assistant-composer-controls">
      <button
        type="button"
        onClick={onManageContext}
        className="ce-action min-h-9 rounded-full px-3 text-primary"
        data-testid="button-manage-context"
      >
        <BookOpenCheck size={15} />
        Context
        <span className="rounded-full bg-[hsl(95_24%_94%)] px-1.5 py-0.5 text-[10px] text-primary">
          {totalContextCount}
        </span>
      </button>

      <div data-testid="select-search-scope">
        <SearchModePopover value={searchScope} onChange={onSearchScopeChange} />
      </div>

      <div data-testid="select-response-length">
        <ResponseLengthPopover value={activeProfile} onChange={onActiveProfileChange} />
      </div>

      {totalContextCount > 0 && onClearContext ? (
        <button
          type="button"
          onClick={onClearContext}
          className="ce-action min-h-9 rounded-full px-3"
          data-testid="button-clear-context"
        >
          Clear
        </button>
      ) : null}
    </div>
  );
}
