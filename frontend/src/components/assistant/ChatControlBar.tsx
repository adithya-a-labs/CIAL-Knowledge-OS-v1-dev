import { BookOpenCheck } from 'lucide-react';
import { ResponseLengthPopover, SearchModePopover } from './AssistantSettingsPopover';
import type { ResponseLength, SearchScope } from '@/types/assistant';

interface ChatControlBarProps {
  searchScope: SearchScope;
  responseLength: ResponseLength;
  selectedContextCount: number;
  uploadedFileCount: number;
  onSearchScopeChange: (value: SearchScope) => void;
  onResponseLengthChange: (value: ResponseLength) => void;
  onManageContext: () => void;
}

export default function ChatControlBar({
  searchScope,
  responseLength,
  selectedContextCount,
  uploadedFileCount,
  onSearchScopeChange,
  onResponseLengthChange,
  onManageContext,
}: ChatControlBarProps) {
  return (
    <div className="ce-toolbar flex flex-col gap-2 px-3 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-4">
      <div className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
        <div data-testid="select-search-scope">
          <SearchModePopover value={searchScope} onChange={onSearchScopeChange} />
        </div>

        <div data-testid="select-response-length">
          <ResponseLengthPopover value={responseLength} onChange={onResponseLengthChange} />
        </div>
      </div>

      <button
        type="button"
        onClick={onManageContext}
        className="ce-action ce-action-primary min-h-9 px-3"
        data-testid="button-manage-context"
      >
        <BookOpenCheck size={15} />
        Manage Context
        <span className="rounded-md bg-white/95 px-1.5 py-0.5 text-[10px] text-primary">
          {selectedContextCount + uploadedFileCount}
        </span>
      </button>
    </div>
  );
}
