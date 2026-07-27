interface FilterConfig {
  key: string;
  label: string;
  options: string[];
}

interface FilterBarProps {
  filters: FilterConfig[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  className?: string;
}

export default function FilterBar({ filters, values, onChange, className = '' }: FilterBarProps) {
  return (
    <div className={`grid w-full grid-cols-1 gap-2 sm:grid-cols-[repeat(auto-fit,minmax(10rem,1fr))] ${className}`}>
      {filters.map((filter) => (
        <select
          key={filter.key}
          value={values[filter.key] ?? ''}
          onChange={e => onChange(filter.key, e.target.value)}
          className="w-full cursor-pointer rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30"
          data-testid={`filter-${filter.key}`}
        >
          <option value="">{filter.label}</option>
          {filter.options.map(opt => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      ))}
    </div>
  );
}
