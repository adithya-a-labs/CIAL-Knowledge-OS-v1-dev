import { useQuery } from '@tanstack/react-query';
import { getSystemStatus } from '@/api/client';
import type { SystemStatusResponse } from '@/api/types';

export const SYSTEM_STATUS_QUERY_KEY = ['system-status'] as const;

export function systemStatusRefetchInterval(
  status: SystemStatusResponse | undefined,
  hidden = typeof document !== 'undefined' && document.visibilityState === 'hidden',
) {
  if (hidden) return 30_000;
  if (!status || status.status === 'blue') return 2_000;
  if (status.status === 'red') return 5_000;
  if (status.status === 'yellow') return 8_000;
  return 15_000;
}

export function useSystemStatus() {
  return useQuery({
    queryKey: SYSTEM_STATUS_QUERY_KEY,
    queryFn: ({ signal }) => getSystemStatus(signal),
    retry: 1,
    staleTime: 1_000,
    refetchInterval: (query) => systemStatusRefetchInterval(query.state.data),
    refetchIntervalInBackground: false,
  });
}
