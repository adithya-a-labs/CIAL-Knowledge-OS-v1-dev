import { Search, X } from 'lucide-react';

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export default function SearchBar({ value, onChange, placeholder = 'Search...', className = '' }: SearchBarProps) {
  return (
    <div className={`relative min-w-0 ${className}`}>
      <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
      <input
        type="search"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-border bg-card py-2 pl-9 pr-8 text-sm text-foreground transition-colors placeholder:text-[#9ab88e] focus:border-ring focus:ring-2 focus:ring-ring/30"
        data-testid="input-search"
      />
      {value && (
        <button
          onClick={() => onChange('')}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#9ab88e] hover:text-muted-foreground"
          data-testid="button-clear-search"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}
