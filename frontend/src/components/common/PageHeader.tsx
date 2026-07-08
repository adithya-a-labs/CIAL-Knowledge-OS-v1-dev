interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}

export default function PageHeader({ title, subtitle, action }: PageHeaderProps) {
  return (
    <div className="mb-5 flex flex-col justify-between gap-3 sm:mb-6 sm:flex-row sm:items-start">
      <div className="min-w-0">
        <h1 className="safe-text text-xl font-semibold leading-tight text-foreground sm:text-2xl" data-testid="page-title">{title}</h1>
        {subtitle && <p className="safe-text mt-1 max-w-3xl text-sm leading-6 text-muted-foreground" data-testid="page-subtitle">{subtitle}</p>}
      </div>
      {action && <div className="flex w-full flex-shrink-0 sm:w-auto sm:justify-end">{action}</div>}
    </div>
  );
}
