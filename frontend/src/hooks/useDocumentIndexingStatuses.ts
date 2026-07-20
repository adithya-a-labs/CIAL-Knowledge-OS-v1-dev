import { useQuery } from '@tanstack/react-query';
import { getDocumentIndexingStatus } from '@/api/client';

export function useDocumentIndexingStatuses(documentIds: string[]) {
  const ids = [...new Set(documentIds)].sort();
  return useQuery({
    queryKey: ['document-indexing-statuses', ids], enabled: ids.length > 0,
    queryFn: async ({ signal }) => Object.fromEntries((await Promise.all(ids.map((id) => getDocumentIndexingStatus(id, signal)))).map((item) => [item.document_id, item])),
    refetchInterval: (query) => Object.values(query.state.data ?? {}).some((item) => item.indexing_status === 'pending' || item.indexing_status === 'indexing') ? 1500 : false,
    retry: false,
  });
}
