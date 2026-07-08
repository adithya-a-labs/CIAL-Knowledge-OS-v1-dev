import { LucideIcon } from 'lucide-react';
import { Link } from 'wouter';

interface QuickActionCardProps {
  label: string;
  description?: string;
  icon: LucideIcon;
  href?: string;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'accent';
  testId?: string;
}

const VARIANT_STYLES: Record<string, string> = {
  primary: 'bg-[#4a7c3f] hover:bg-[#2d4f22] text-white',
  secondary: 'bg-white hover:bg-[#f0f7ed] text-[#1a2e14] border border-[#ddecd6]',
  accent: 'bg-[#e8820c] hover:bg-[#c96f0a] text-white',
};

export default function QuickActionCard({
  label,
  description,
  icon: Icon,
  href,
  onClick,
  variant = 'secondary',
  testId,
}: QuickActionCardProps) {
  const cls = `flex flex-col gap-2 rounded-xl p-4 transition-colors cursor-pointer ${VARIANT_STYLES[variant]}`;

  const inner = (
    <>
      <Icon size={20} className="opacity-90" />
      <div>
        <p className="text-sm font-semibold leading-tight">{label}</p>
        {description && <p className="text-xs opacity-75 mt-0.5">{description}</p>}
      </div>
    </>
  );

  if (href) {
    return (
      <Link href={href} className={cls} data-testid={testId}>
        {inner}
      </Link>
    );
  }

  return (
    <button onClick={onClick} className={cls} data-testid={testId}>
      {inner}
    </button>
  );
}
