import type { ComponentType } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

export type AppearanceMode = 'light' | 'system' | 'dark';

const APPEARANCE_OPTIONS: Array<{
  value: AppearanceMode;
  label: string;
  description: string;
  icon: ComponentType<{ size?: number; className?: string }>;
}> = [
  { value: 'light', label: 'Light', description: 'Always use the light palette', icon: Sun },
  { value: 'system', label: 'System', description: 'Follow this device', icon: Monitor },
  { value: 'dark', label: 'Dark', description: 'Always use the dark palette', icon: Moon },
];

const isAppearanceMode = (value: string | undefined): value is AppearanceMode =>
  value === 'light' || value === 'system' || value === 'dark';

interface AppearanceControlProps {
  collapsed?: boolean;
  className?: string;
  triggerClassName?: string;
  menuSide?: 'top' | 'right' | 'bottom' | 'left';
}

export default function AppearanceControl({
  collapsed = false,
  className,
  triggerClassName,
  menuSide,
}: AppearanceControlProps) {
  const { theme, setTheme } = useTheme();
  const selectedMode: AppearanceMode = isAppearanceMode(theme) ? theme : 'system';
  const selectedOption =
    APPEARANCE_OPTIONS.find((option) => option.value === selectedMode) ??
    APPEARANCE_OPTIONS[1];
  const SelectedIcon = selectedOption.icon;
  const accessibleName = `Appearance: ${selectedOption.label}`;

  const trigger = (
    <DropdownMenuTrigger asChild>
      <button
        type="button"
        className={cn(
          'flex h-10 w-full items-center rounded-xl text-sm font-medium text-sidebar-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar',
          collapsed ? 'justify-center px-0' : 'gap-3 px-3',
          triggerClassName,
        )}
        aria-label={accessibleName}
        data-testid={collapsed ? 'appearance-trigger-collapsed' : 'appearance-trigger'}
      >
        <SelectedIcon size={18} className="shrink-0 text-muted-foreground" />
        {!collapsed ? (
          <>
            <span>Appearance</span>
            <span className="ml-auto text-xs text-muted-foreground">{selectedOption.label}</span>
          </>
        ) : null}
      </button>
    </DropdownMenuTrigger>
  );

  return (
    <div className={className} data-appearance-mode={selectedMode}>
      <DropdownMenu>
        {collapsed ? (
          <Tooltip>
            <TooltipTrigger asChild>{trigger}</TooltipTrigger>
            <TooltipContent side="right" sideOffset={10}>Appearance</TooltipContent>
          </Tooltip>
        ) : trigger}
        <DropdownMenuContent
          side={menuSide ?? (collapsed ? 'right' : 'top')}
          align="start"
          sideOffset={10}
          className="w-64 rounded-xl border-popover-border p-1.5 shadow-lg"
          data-testid="appearance-menu"
        >
          <DropdownMenuLabel className="px-2 py-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
            Appearance
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuRadioGroup
            value={selectedMode}
            onValueChange={(value) => {
              if (isAppearanceMode(value)) setTheme(value);
            }}
          >
            {APPEARANCE_OPTIONS.map((option) => {
              const Icon = option.icon;
              return (
                <DropdownMenuRadioItem
                  key={option.value}
                  value={option.value}
                  className="min-h-11 rounded-lg py-2 pl-8 pr-2"
                  data-testid={`appearance-option-${option.value}`}
                >
                  <Icon size={16} className="text-muted-foreground" />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{option.label}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {option.description}
                    </span>
                  </span>
                </DropdownMenuRadioItem>
              );
            })}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
