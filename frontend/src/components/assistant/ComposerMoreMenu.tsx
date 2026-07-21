import { Eraser, Eye, FileText, MoreHorizontal, RotateCcw, Settings2, ShieldCheck } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface ComposerMoreMenuProps {
  hasContext: boolean;
  querySettingsAreDefault: boolean;
  includeSourceExcerpts: boolean;
  showRetrievalDetails: boolean;
  onManageContext: () => void;
  onClearContext: () => void;
  onIncludeSourceExcerptsChange: (value: boolean) => void;
  onShowRetrievalDetailsChange: (value: boolean) => void;
  onResetQuerySettings: () => void;
}

export default function ComposerMoreMenu({
  hasContext,
  querySettingsAreDefault,
  includeSourceExcerpts,
  showRetrievalDetails,
  onManageContext,
  onClearContext,
  onIncludeSourceExcerptsChange,
  onShowRetrievalDetailsChange,
  onResetQuerySettings,
}: ComposerMoreMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-600 transition hover:bg-[#f1f6ee] hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          aria-label="Open more query settings"
          data-testid="button-composer-more"
        >
          <MoreHorizontal size={16} />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" side="top" sideOffset={10} className="w-64 rounded-xl p-1.5 shadow-lg" data-testid="composer-more-menu">
        <DropdownMenuLabel className="px-2 py-1.5 text-[11px] uppercase tracking-[0.08em] text-muted-foreground">Query controls</DropdownMenuLabel>
        <DropdownMenuItem onSelect={onManageContext}>
          <Settings2 />
          Manage context
        </DropdownMenuItem>
        <DropdownMenuItem disabled={!hasContext} onSelect={onClearContext} data-testid="menu-clear-attached-context">
          <Eraser />
          Clear attached context
        </DropdownMenuItem>
        <DropdownMenuCheckboxItem
          checked={hasContext}
          disabled
          data-testid="menu-hard-retrieval-boundary"
          aria-label={hasContext ? 'Hard retrieval boundary enforced' : 'Hard retrieval boundary requires selected context'}
        >
          <span className="flex items-center gap-2">
            <ShieldCheck size={16} />
            Hard retrieval boundary
          </span>
        </DropdownMenuCheckboxItem>
        {hasContext ? (
          <p className="px-8 pb-1.5 text-[10px] leading-4 text-muted-foreground">Enforced while context is attached.</p>
        ) : null}
        <DropdownMenuCheckboxItem checked={includeSourceExcerpts} onCheckedChange={(value) => onIncludeSourceExcerptsChange(Boolean(value))} data-testid="menu-include-source-excerpts">
          <span className="flex items-center gap-2"><FileText size={16} />Include source excerpts</span>
        </DropdownMenuCheckboxItem>
        <DropdownMenuCheckboxItem checked={showRetrievalDetails} onCheckedChange={(value) => onShowRetrievalDetailsChange(Boolean(value))} data-testid="menu-show-retrieval-details">
          <span className="flex items-center gap-2"><Eye size={16} />Show retrieval details</span>
        </DropdownMenuCheckboxItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={querySettingsAreDefault} onSelect={onResetQuerySettings} data-testid="menu-reset-query-settings">
          <RotateCcw />
          Reset query settings
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
