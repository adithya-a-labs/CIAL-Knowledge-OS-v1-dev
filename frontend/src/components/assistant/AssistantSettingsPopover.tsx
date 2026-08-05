import { useMemo, useRef, useState } from 'react';
import type { ComponentType, KeyboardEvent } from 'react';
import {
  Building2,
  ChevronDown,
  FileText,
  Folder,
  Layers,
  ListChecks,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Zap,
} from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import type { ResponseLength, SearchScope } from '@/types/assistant';

type IconType = ComponentType<{ size?: number; className?: string }>;

interface SettingsOption<T extends string> {
  value: T;
  title: string;
  description: string;
  icon: IconType;
  recommended?: boolean;
  iconTone?: string;
}

interface SettingsPopoverProps<T extends string> {
  eyebrow: string;
  title: string;
  subtitle: string;
  value: T;
  options: SettingsOption<T>[];
  defaultNote: string;
  triggerIcon: IconType;
  onChange: (value: T) => void;
  disabled?: boolean;
}

const searchModeOptions: SettingsOption<SearchScope>[] = [
  {
    value: 'enterprise',
    title: 'Enterprise Only',
    description: 'Search only the enterprise knowledge base.',
    icon: Building2,
    iconTone: 'bg-primary/10 text-primary',
  },
  {
    value: 'workspace',
    title: 'My Workspace Only',
    description: 'Search only documents in your personal workspace.',
    icon: Folder,
    iconTone: 'bg-accent text-accent-foreground',
  },
  {
    value: 'hybrid',
    title: 'Hybrid',
    description: 'Search across enterprise knowledge and your workspace.',
    icon: Layers,
    recommended: true,
    iconTone: 'bg-primary/10 text-primary',
  },
  {
    value: 'current_upload',
    title: 'Current Upload Only',
    description: 'Search only files uploaded in this conversation.',
    icon: FileText,
    iconTone: 'bg-info/10 text-info-foreground',
  },
];

const responseLengthOptions: SettingsOption<ResponseLength>[] = [
  {
    value: 'quick',
    title: 'Quick',
    description: 'Short concise answers.',
    icon: Zap,
    iconTone: 'bg-warning/10 text-warning-foreground',
  },
  {
    value: 'standard',
    title: 'Standard',
    description: 'Balanced responses for everyday work.',
    icon: SlidersHorizontal,
    iconTone: 'bg-info/10 text-info-foreground',
  },
  {
    value: 'detailed',
    title: 'Detailed',
    description: 'Comprehensive explanations with supporting context.',
    icon: ListChecks,
    recommended: true,
    iconTone: 'bg-primary/10 text-primary',
  },
  {
    value: 'operational',
    title: 'Operational',
    description: 'Enterprise decision-ready responses with risks, citations and actionable recommendations.',
    icon: ShieldCheck,
    iconTone: 'bg-accent text-accent-foreground',
  },
];

function OptionCard<T extends string>({
  option,
  selected,
  onSelect,
  buttonRef,
}: {
  option: SettingsOption<T>;
  selected: boolean;
  onSelect: () => void;
  buttonRef: (node: HTMLButtonElement | null) => void;
}) {
  const Icon = option.icon;

  return (
    <button
      ref={buttonRef}
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className={cn(
        'group flex w-full items-center gap-4 rounded-xl border px-4 py-4 text-left transition-[border-color,background-color,box-shadow,color] duration-[var(--motion-duration-standard)] ease-[var(--motion-ease-enter)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
        selected
          ? 'border-primary/55 bg-primary/10 shadow-sm'
          : 'border-border bg-card hover:border-border-strong hover:bg-muted hover:shadow-sm'
      )}
    >
      <span
        className={cn(
          'flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-colors duration-[var(--motion-duration-standard)] ease-[var(--motion-ease-enter)]',
          selected ? 'bg-primary text-white' : option.iconTone ?? 'bg-muted text-muted-foreground'
        )}
      >
        <Icon size={20} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2">
          <span className={cn('text-sm font-semibold', selected ? 'text-primary' : 'text-foreground')}>
            {option.title}
          </span>
          {option.recommended && (
            <span className="ce-badge ce-badge-accent text-[10px]">Recommended</span>
          )}
        </span>
        <span className="safe-text mt-1 block text-xs leading-5 text-muted-foreground">
          {option.description}
        </span>
      </span>
      <span
        aria-hidden="true"
        className={cn(
          'flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-colors duration-[var(--motion-duration-standard)] ease-[var(--motion-ease-enter)]',
          selected ? 'border-primary bg-primary' : 'border-border-strong bg-card group-hover:border-primary'
        )}
      >
        {selected && <span className="h-1.5 w-1.5 rounded-full bg-card" />}
      </span>
    </button>
  );
}

function SettingsPopover<T extends string>({
  eyebrow,
  title,
  subtitle,
  value,
  options,
  defaultNote,
  triggerIcon: TriggerIcon,
  onChange,
  disabled = false,
}: SettingsPopoverProps<T>) {
  const [open, setOpen] = useState(false);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const selectedOption = useMemo(
    () => options.find((option) => option.value === value) ?? options[0],
    [options, value]
  );

  const focusOption = (index: number) => {
    const nextIndex = (index + options.length) % options.length;
    optionRefs.current[nextIndex]?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const currentIndex = options.findIndex((option, index) => optionRefs.current[index] === document.activeElement);

    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
      event.preventDefault();
      focusOption(currentIndex >= 0 ? currentIndex + 1 : 0);
    }

    if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
      event.preventDefault();
      focusOption(currentIndex >= 0 ? currentIndex - 1 : options.length - 1);
    }

    if (event.key === 'Enter' || event.key === ' ') {
      if (currentIndex >= 0) {
        event.preventDefault();
        onChange(options[currentIndex].value);
        setOpen(false);
      }
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className="flex h-8 min-w-0 shrink-0 items-center gap-2 rounded-lg px-2 text-left transition hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:text-foreground disabled:opacity-100"
          aria-label={`Open ${title} selector`}
          aria-haspopup="dialog"
        >
          <TriggerIcon size={14} className="sr-only" />
          <span className="sr-only">
            {eyebrow}:
          </span>
          <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
            {selectedOption.title}
          </span>
          <ChevronDown size={13} className="shrink-0 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        sideOffset={10}
        className="w-[min(calc(100vw-2rem),34rem)] rounded-xl border-popover-border bg-popover p-0 shadow-lg"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          const selectedIndex = options.findIndex((option) => option.value === value);
          window.requestAnimationFrame(() => focusOption(selectedIndex >= 0 ? selectedIndex : 0));
        }}
      >
        <div className="p-6">
          <h3 className="text-lg font-semibold tracking-normal text-foreground">{title}</h3>
          <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">{subtitle}</p>
          <div
            role="radiogroup"
            aria-label={title}
            className="mt-5 space-y-3"
            onKeyDown={handleKeyDown}
          >
            {options.map((option, index) => (
              <OptionCard
                key={option.value}
                option={option}
                selected={value === option.value}
                onSelect={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                buttonRef={(node) => {
                  optionRefs.current[index] = node;
                }}
              />
            ))}
          </div>
          <p className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
            <Sparkles size={14} className="text-primary" />
            {defaultNote}
          </p>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function SearchModePopover({
  value,
  onChange,
  disabled = false,
}: {
  value: SearchScope;
  onChange: (value: SearchScope) => void;
  disabled?: boolean;
}) {
  return (
    <SettingsPopover
      eyebrow="Scope"
      title="AI Search Mode"
      subtitle="Choose where the assistant searches for information."
      value={value}
      options={searchModeOptions}
      defaultNote="Hybrid is your default search mode."
      triggerIcon={Layers}
      onChange={onChange}
      disabled={disabled}
    />
  );
}

export function ResponseLengthPopover({
  value,
  onChange,
}: {
  value: ResponseLength;
  onChange: (value: ResponseLength) => void;
}) {
  return (
    <SettingsPopover
      eyebrow="Length"
      title="Response Length"
      subtitle="Choose the depth and detail of the answer."
      value={value}
      options={responseLengthOptions}
      defaultNote="Detailed is your default response length."
      triggerIcon={SlidersHorizontal}
      onChange={onChange}
    />
  );
}
