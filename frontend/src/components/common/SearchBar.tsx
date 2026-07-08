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
      <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#5a7a52]" />
      <input
        type="search"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-[#ddecd6] bg-white py-2 pl-9 pr-8 text-sm text-[#1a2e14] transition-colors placeholder:text-[#9ab88e] focus:border-[#4a7c3f] focus:ring-2 focus:ring-[#4a7c3f]/30"
        data-testid="input-search"
      />
      {value && (
        <button
          onClick={() => onChange('')}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#9ab88e] hover:text-[#5a7a52]"
          data-testid="button-clear-search"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}
