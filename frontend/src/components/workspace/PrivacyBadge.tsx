import { Lock } from 'lucide-react';

interface PrivacyBadgeProps {
  label?: string;
  size?: 'sm' | 'md';
}

export default function PrivacyBadge({ label = 'Private', size = 'sm' }: PrivacyBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full bg-[#f0f7ed] border border-[#ddecd6] text-[#4a7c3f] font-medium
        ${size === 'md' ? 'px-3 py-1 text-xs' : 'px-2 py-0.5 text-[10px]'}`}
    >
      <Lock size={size === 'md' ? 11 : 9} />
      {label}
    </span>
  );
}
