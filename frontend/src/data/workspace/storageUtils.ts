import type { StorageInfo } from './workspaceTypes';

export const STORAGE_LIMIT_BYTES = 5 * 1024 * 1024 * 1024;

export function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`;
}

export function formatGB(gb: number): string {
  return `${gb.toFixed(1)} GB`;
}

export function isStorageFull(storage: StorageInfo): boolean {
  return storage.usedBytes >= storage.totalBytes;
}

export function isStorageNearFull(storage: StorageInfo, thresholdPercent = 90): boolean {
  return storage.percentUsed >= thresholdPercent;
}

export function getStoragePercent(usedBytes: number, totalBytes: number): number {
  if (totalBytes === 0) return 0;
  return Math.min(100, Math.round((usedBytes / totalBytes) * 100));
}

export function getStorageColor(percent: number): string {
  if (percent >= 90) return '#e8820c';
  if (percent >= 75) return '#f59e0b';
  return '#4a7c3f';
}
