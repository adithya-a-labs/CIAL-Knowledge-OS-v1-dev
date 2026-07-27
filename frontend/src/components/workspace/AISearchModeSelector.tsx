import { Building2, Folder, Layers, ShieldCheck } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { AISearchMode } from '@/data/workspace/workspaceTypes';

const MODES: {
  value: AISearchMode;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  description: string;
}[] = [
  {
    value: 'enterprise',
    icon: Building2,
    label: 'Enterprise Only',
    description: 'Search only the enterprise knowledge base.',
  },
  {
    value: 'workspace',
    icon: Folder,
    label: 'My Workspace Only',
    description: 'Search only documents in your personal workspace.',
  },
  {
    value: 'hybrid',
    icon: Layers,
    label: 'Hybrid',
    description: 'Search across enterprise knowledge and your workspace.',
  },
];

interface AISearchModeSelectorProps {
  value: AISearchMode;
  onChange: (mode: AISearchMode) => void;
}

export default function AISearchModeSelector({ value, onChange }: AISearchModeSelectorProps) {
  return (
    <div className="ce-panel p-5" data-testid="ai-search-mode-selector">
      <h3 className="mb-1 text-base font-semibold text-foreground">AI Search Mode</h3>
      <p className="mb-4 text-sm leading-5 text-muted-foreground">Choose where the assistant searches for information.</p>
      <div className="space-y-3" role="radiogroup" aria-label="AI Search Mode">
        {MODES.map((mode) => {
          const Icon = mode.icon;
          const selected = value === mode.value;
          const recommended = mode.value === 'hybrid';
          return (
            <button
              key={mode.value}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(mode.value)}
              className={cn(
                'group flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-left transition-all duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
                selected
                  ? 'border-primary/55 bg-primary/10 shadow-sm'
                  : 'border-border bg-card hover:border-border-strong hover:bg-muted hover:shadow-sm'
              )}
              data-testid={`mode-${mode.value}`}
            >
              <div className={cn(
                'flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl transition-colors duration-200',
                selected ? 'bg-primary text-primary-foreground' : 'bg-primary/10 text-primary'
              )}>
                <Icon size={14} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className={cn('text-sm font-semibold', selected ? 'text-primary' : 'text-foreground')}>{mode.label}</p>
                  {recommended && <span className="ce-badge ce-badge-accent text-[10px]">Recommended</span>}
                </div>
                <p className="safe-text mt-1 text-xs leading-5 text-muted-foreground">{mode.description}</p>
              </div>
              <div className={cn(
                'flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border-2 transition-colors duration-200',
                selected ? 'border-primary bg-primary' : 'border-border-strong bg-card group-hover:border-primary'
              )}>
                {selected && (
                  <div className="h-1.5 w-1.5 rounded-full bg-card" />
                )}
              </div>
            </button>
          );
        })}
      </div>
      <p className="mt-4 flex items-center gap-2 px-1 text-xs text-muted-foreground">
        <ShieldCheck size={14} className="text-primary" />
        Hybrid is your default mode for AI Assistant.
      </p>
    </div>
  );
}
