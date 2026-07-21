import type { ReactNode } from 'react';
import { ResponseLengthPopover, SearchModePopover } from './AssistantSettingsPopover';
import ComposerMoreMenu from './ComposerMoreMenu';
import { DEFAULT_RESPONSE_LENGTH, DEFAULT_SEARCH_SCOPE } from '@/data/assistantData';
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
  onResetQuerySettings: () => void;
  attachedContext?: ReactNode;
  includeSourceExcerpts: boolean;
  showRetrievalDetails: boolean;
  onIncludeSourceExcerptsChange: (value: boolean) => void;
  onShowRetrievalDetailsChange: (value: boolean) => void;
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
  onResetQuerySettings,
  attachedContext,
  includeSourceExcerpts,
  showRetrievalDetails,
  onIncludeSourceExcerptsChange,
  onShowRetrievalDetailsChange,
}: ChatControlBarProps) {
  const totalContextCount = selectedContextCount + uploadedFileCount;
  const scopeLocked = totalContextCount > 0;

  return (
    <div className="flex w-max min-w-full items-center gap-1" data-testid="assistant-composer-controls">
      {attachedContext}
      <div className="shrink-0" data-testid="select-search-scope">
        <SearchModePopover value={searchScope} onChange={onSearchScopeChange} disabled={scopeLocked} />
      </div>

      <div data-testid="select-response-length">
        <ResponseLengthPopover value={activeProfile} onChange={onActiveProfileChange} />
      </div>

      <ComposerMoreMenu
        hasContext={totalContextCount > 0}
        includeSourceExcerpts={includeSourceExcerpts}
        showRetrievalDetails={showRetrievalDetails}
        querySettingsAreDefault={searchScope === DEFAULT_SEARCH_SCOPE && activeProfile === DEFAULT_RESPONSE_LENGTH && includeSourceExcerpts && showRetrievalDetails}
        onManageContext={onManageContext}
        onClearContext={onClearContext ?? (() => undefined)}
        onIncludeSourceExcerptsChange={onIncludeSourceExcerptsChange}
        onShowRetrievalDetailsChange={onShowRetrievalDetailsChange}
        onResetQuerySettings={onResetQuerySettings}
      />
    </div>
  );
}
