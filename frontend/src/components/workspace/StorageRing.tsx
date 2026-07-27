import { getStorageColor } from '@/data/workspace/storageUtils';

interface StorageRingProps {
  percent: number;
  usedGB: number;
  totalGB: number;
  size?: number;
  strokeWidth?: number;
}

export default function StorageRing({
  percent,
  usedGB,
  totalGB,
  size = 140,
  strokeWidth = 12,
}: StorageRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (percent / 100) * circumference;
  const color = getStorageColor(percent);
  const cx = size / 2;
  const cy = size / 2;

  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke="#e2eedd"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          className="transition-all duration-700"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-foreground">{percent}%</span>
        <span className="text-[10px] text-muted-foreground mt-0.5">
          {usedGB} / {totalGB} GB
        </span>
      </div>
    </div>
  );
}
