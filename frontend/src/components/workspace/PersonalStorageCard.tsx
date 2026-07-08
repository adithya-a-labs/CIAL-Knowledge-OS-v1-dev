import { ShieldCheck, RefreshCw } from 'lucide-react';
import StorageRing from './StorageRing';
import { WORKSPACE_STORAGE, STORAGE_PRIVACY_BULLETS } from '@/data/workspace/workspaceData';

export default function PersonalStorageCard() {
  const s = WORKSPACE_STORAGE;

  return (
    <div className="responsive-card border border-[#e2eedd] bg-white p-4 shadow-sm sm:p-5" data-testid="personal-storage-card">
      <h2 className="text-sm font-semibold text-[#1a2e14] mb-4">Your Personal Storage</h2>

      <div className="flex flex-col items-center gap-5 md:flex-row md:items-center md:gap-6">
        {/* Ring */}
        <div className="flex-shrink-0">
          <StorageRing
            percent={s.percentUsed}
            usedGB={s.usedGB}
            totalGB={s.totalGB}
            size={140}
            strokeWidth={13}
          />
        </div>

        {/* Details */}
        <div className="min-w-0 flex-1 self-stretch">
          <div className="mb-1">
            <span className="text-2xl font-bold text-[#1a2e14]">{s.usedGB} GB</span>
            <span className="text-sm text-[#5a7a52] ml-1">/ {s.totalGB} GB used</span>
          </div>

          {/* Progress bar */}
          <div className="mb-2 h-2 w-full max-w-md overflow-hidden rounded-full bg-[#e2eedd]">
            <div
              className="h-full rounded-full bg-[#4a7c3f] transition-all duration-700"
              style={{ width: `${s.percentUsed}%` }}
            />
          </div>

          <p className="text-xs text-[#5a7a52] mb-3">{s.availableGB} GB available</p>

          {/* Privacy bullets */}
          <ul className="space-y-1.5">
            {STORAGE_PRIVACY_BULLETS.map((bullet) => (
              <li key={bullet} className="flex items-start gap-2">
                <ShieldCheck size={13} className="text-[#4a7c3f] flex-shrink-0 mt-0.5" />
                <span className="safe-text text-xs text-[#3d5c30]">{bullet}</span>
              </li>
            ))}
          </ul>

          <div className="flex items-center gap-1.5 mt-3 text-[10px] text-[#7a9a72]">
            <RefreshCw size={10} />
            {s.resetNote}
          </div>
        </div>
      </div>
    </div>
  );
}
