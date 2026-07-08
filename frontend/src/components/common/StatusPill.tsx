type StatusType = 'Operational' | 'Under Maintenance' | 'Out of Service' | 'Active' | 'Under Review' | 'Archived' | 'Published' | 'Draft' | 'Success' | 'Failed';

interface StatusPillProps {
  status: StatusType | string;
  size?: 'sm' | 'md';
}

const STATUS_STYLES: Record<string, string> = {
  'Operational': 'bg-[#d4f0d8] text-[#1e7e34]',
  'Active': 'bg-[#d4f0d8] text-[#1e7e34]',
  'Published': 'bg-[#d4f0d8] text-[#1e7e34]',
  'Success': 'bg-[#d4f0d8] text-[#1e7e34]',
  'Under Maintenance': 'bg-[#fde8c8] text-[#b35900]',
  'Under Review': 'bg-[#fde8c8] text-[#b35900]',
  'Draft': 'bg-[#fde8c8] text-[#b35900]',
  'Out of Service': 'bg-[#fdd8d8] text-[#991b1b]',
  'Failed': 'bg-[#fdd8d8] text-[#991b1b]',
  'Archived': 'bg-[#e8e8e8] text-[#555]',
};

export default function StatusPill({ status, size = 'sm' }: StatusPillProps) {
  const style = STATUS_STYLES[status] || 'bg-[#e2eedd] text-[#5a7a52]';
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
