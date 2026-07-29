import { useLayoutEffect, useRef, type ComponentType, type KeyboardEvent } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

export type AppearanceMode = 'light' | 'system' | 'dark';
export type AppearanceToggleVariant = 'expanded' | 'collapsed' | 'mobile';

const APPEARANCE_OPTIONS: ReadonlyArray<{
  value: AppearanceMode;
  label: string;
  icon: ComponentType<{ size?: number; className?: string; 'aria-hidden'?: boolean }>;
}> = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'system', label: 'System', icon: Monitor },
  { value: 'dark', label: 'Dark', icon: Moon },
];

const isAppearanceMode = (value: string | undefined): value is AppearanceMode =>
  value === 'light' || value === 'system' || value === 'dark';

interface AppearanceToggleProps {
  variant?: AppearanceToggleVariant;
  className?: string;
}

export default function AppearanceToggle({
  variant = 'expanded',
  className,
}: AppearanceToggleProps) {
  const { theme, setTheme } = useTheme();
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const restoreFocusIndexRef = useRef<number | null>(null);
  const selectedMode: AppearanceMode = isAppearanceMode(theme) ? theme : 'system';
  const selectedIndex = APPEARANCE_OPTIONS.findIndex((option) => option.value === selectedMode);
  const orientation = variant === 'collapsed' ? 'vertical' : 'horizontal';
  const focusedOptionIndex = optionRefs.current.findIndex(
    (element) => element === document.activeElement,
  );
  if (focusedOptionIndex >= 0) restoreFocusIndexRef.current = focusedOptionIndex;

  useLayoutEffect(() => {
    const restoreIndex = restoreFocusIndexRef.current;
    if (restoreIndex === null) return;
    optionRefs.current[restoreIndex]?.focus();
    restoreFocusIndexRef.current = null;
  }, [variant]);

  const selectAt = (index: number) => {
    const option = APPEARANCE_OPTIONS[index];
    if (!option) return;
    setTheme(option.value);
    optionRefs.current[index]?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number | null = null;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = APPEARANCE_OPTIONS.length - 1;
    if (orientation === 'horizontal' && event.key === 'ArrowLeft') {
      nextIndex = (index - 1 + APPEARANCE_OPTIONS.length) % APPEARANCE_OPTIONS.length;
    }
    if (orientation === 'horizontal' && event.key === 'ArrowRight') {
      nextIndex = (index + 1) % APPEARANCE_OPTIONS.length;
    }
    if (orientation === 'vertical' && event.key === 'ArrowUp') {
      nextIndex = (index - 1 + APPEARANCE_OPTIONS.length) % APPEARANCE_OPTIONS.length;
    }
    if (orientation === 'vertical' && event.key === 'ArrowDown') {
      nextIndex = (index + 1) % APPEARANCE_OPTIONS.length;
    }
    if (nextIndex === null) return;
    event.preventDefault();
    selectAt(nextIndex);
  };

  const options = APPEARANCE_OPTIONS.map((option, index) => {
    const Icon = option.icon;
    const selected = option.value === selectedMode;
    const button = (
      <button
        key={option.value}
        ref={(element) => {
          optionRefs.current[index] = element;
        }}
        type="button"
        role="radio"
        aria-checked={selected}
        aria-label={option.label}
        tabIndex={selected ? 0 : -1}
        className="appearance-option"
        data-testid={`appearance-option-${option.value}`}
        onClick={() => setTheme(option.value)}
        onKeyDown={(event) => handleKeyDown(event, index)}
      >
        <Icon size={16} aria-hidden />
        <span className="appearance-option-label">{option.label}</span>
      </button>
    );

    if (variant !== 'collapsed') return button;
    return (
      <Tooltip key={option.value}>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent side="right" sideOffset={10}>{option.label}</TooltipContent>
      </Tooltip>
    );
  });

  return (
    <div
      className={cn('appearance-toggle', className)}
      data-appearance-variant={variant}
      data-appearance-mode={selectedMode}
      data-selected-index={selectedIndex}
      data-testid={`appearance-toggle-${variant}`}
    >
      {variant !== 'collapsed' ? (
        <span className="appearance-toggle-label">Appearance</span>
      ) : null}
      <div
        className="appearance-toggle-track"
        role="radiogroup"
        aria-label="Appearance"
        aria-orientation={orientation}
      >
        <span className="appearance-toggle-thumb" aria-hidden />
        {options}
      </div>
      <span className="sr-only" role="status" aria-live="polite">
        Appearance preference: {APPEARANCE_OPTIONS[selectedIndex]?.label ?? 'System'}
      </span>
    </div>
  );
}
