type StatusType = 'Operational' | 'Under Maintenance' | 'Out of Service' | 'Active' | 'Under Review' | 'Archived' | 'Published' | 'Draft' | 'Success' | 'Failed';

interface StatusPillProps {
  status: StatusType | string;
  size?: 'sm' | 'md';
}

const STATUS_STYLES: Record<string, string> = {
  'Operational': 'bg-success/15 text-success-foreground',
  'Active': 'bg-success/15 text-success-foreground',
  'Published': 'bg-success/15 text-success-foreground',
  'Success': 'bg-success/15 text-success-foreground',
  'Under Maintenance': 'bg-warning/15 text-warning-foreground',
  'Under Review': 'bg-warning/15 text-warning-foreground',
  'Draft': 'bg-warning/15 text-warning-foreground',
  'Out of Service': 'bg-destructive/15 text-destructive',
  'Failed': 'bg-destructive/15 text-destructive',
  'Archived': 'bg-muted text-muted-foreground',
};

export default function StatusPill({ status, size = 'sm' }: StatusPillProps) {
  const style = STATUS_STYLES[status] || 'bg-muted text-muted-foreground';
  const sizeClass = size === 'sm' ? 'px-2.5 py-0.5 text-xs' : 'px-3 py-1 text-sm';

  return (
    <span
      className={`inline-flex items-center rounded-full font-medium ${sizeClass} ${style}`}
      data-testid={`status-pill-${status.toLowerCase().replace(/\s+/g, '-')}`}
    >
      {status}
    </span>
  );
}
