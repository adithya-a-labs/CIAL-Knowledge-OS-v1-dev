import { useQuery } from '@tanstack/react-query';
import { getHealth } from '@/api/client';
import type { HealthResponse } from '@/api/types';

export const BACKEND_HEALTH_QUERY_KEY = ['backend-health'] as const;

export function healthRefetchInterval(status: HealthResponse | undefined, hidden = typeof document !== 'undefined' && document.visibilityState === 'hidden') {
  if (hidden) return 30_000;
  if (!status || status.status === 'starting' || status.status === 'indexing') return 1_500;
  const activeJobs = Object.entries(status.queue_counts ?? {})
    .filter(([value]) => !['completed', 'failed', 'superseded', 'cancelled'].includes(value))
    .reduce((total, [, count]) => total + count, 0);
  if (activeJobs > 0) return 2_000;
  if ((status.retrieval_ready || status.engine_ready) && status.status === 'ready') return 20_000;
  return 15_000;
}

export function useBackendHealth() {
  return useQuery({
    queryKey: BACKEND_HEALTH_QUERY_KEY,
    queryFn: getHealth,
    retry: false,
    staleTime: 1_000,
    refetchInterval: (query) => healthRefetchInterval(query.state.data),
    refetchIntervalInBackground: false,
  });
}
