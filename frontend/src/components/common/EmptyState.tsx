import { FileQuestion } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
}

export default function EmptyState({
  title = 'No results found',
  description = 'Try adjusting your search or filter.',
  icon
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center" data-testid="empty-state">
      <div className="w-12 h-12 rounded-full bg-[#f0f7ed] flex items-center justify-center mb-3">
        {icon || <FileQuestion size={22} className="text-[#5a7a52]" />}
      </div>
      <p className="text-sm font-medium text-[#1a2e14]">{title}</p>
      <p className="text-xs text-[#5a7a52] mt-1">{description}</p>
    </div>
  );
}
