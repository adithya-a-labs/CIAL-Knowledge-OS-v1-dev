interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}

export default function ChartCard({ title, subtitle, children, className = '' }: ChartCardProps) {
  return (
    <div
      className={`responsive-card min-w-0 border border-border bg-card p-4 shadow-sm sm:p-5 ${className}`}
      data-testid={`chart-card-${title.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <div className="mb-4">
        <h3 className="safe-text text-sm font-semibold text-foreground">{title}</h3>
        {subtitle && <p className="safe-text mt-0.5 text-xs text-muted-foreground">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}
