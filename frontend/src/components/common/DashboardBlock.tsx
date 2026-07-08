interface DashboardBlockProps {
  title: string;
  viewAllLabel?: string;
  viewAllHref?: string;
  onViewAll?: () => void;
  children: React.ReactNode;
  className?: string;
}

export default function DashboardBlock({
  title,
  viewAllLabel = 'View All',
  viewAllHref,
  onViewAll,
  children,
  className = '',
}: DashboardBlockProps) {
  return (
    <div
      className={`fluid-card responsive-card overflow-hidden border border-[#e2eedd] bg-white shadow-sm ${className}`}
      data-testid={`block-${title.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <div className="flex items-center justify-between gap-3 border-b border-[#f0f7ed] px-4 py-3">
        <h3 className="safe-text text-sm font-semibold text-[#1a2e14]">{title}</h3>
        {(viewAllHref || onViewAll) && (
          <button
            onClick={onViewAll}
            className="text-xs text-[#4a7c3f] hover:underline font-medium"
            data-testid={`link-viewall-${title.toLowerCase().replace(/\s+/g, '-')}`}
          >
            {viewAllLabel}
          </button>
        )}
      </div>
      <div className="p-3.5 sm:p-4">{children}</div>
    </div>
  );
}
