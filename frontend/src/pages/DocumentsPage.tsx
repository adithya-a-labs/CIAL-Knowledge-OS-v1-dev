import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCcw, Upload } from 'lucide-react';
import { getIndexStatus, listDocuments, rebuildIndex } from '@/api/client';
import { toUiDocument } from '@/api/adapters';
import PageHeader from '@/components/common/PageHeader';
import SearchBar from '@/components/common/SearchBar';
import FilterBar from '@/components/common/FilterBar';
import EmptyState from '@/components/common/EmptyState';
import DocumentRow from '@/components/documents/DocumentRow';
import DocumentCard from '@/components/documents/DocumentCard';
import UploadModal from '@/components/documents/UploadModal';
import { DOCUMENTS, DOC_CATEGORIES, DOC_DEPARTMENTS, DOC_TYPES } from '@/data/documentsData';
import { CURRENT_USER } from '@/config/userConfig';
import { hasPermission } from '@/config/securityConfig';
import { Role } from '@/types';

const SORT_OPTIONS = [{ label: 'Latest', value: 'latest' }, { label: 'Name A–Z', value: 'name_asc' }];

export default function DocumentsPage() {
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({ category: '', department: '', type: '', sort: '' });
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [page, setPage] = useState(1);
  const [indexActionMessage, setIndexActionMessage] = useState<string | null>(null);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const PER_PAGE = 10;

  const documentsQuery = useQuery({
    queryKey: ['documents'],
    queryFn: listDocuments,
    retry: false,
  });
  const indexStatusQuery = useQuery({
    queryKey: ['index-status'],
    queryFn: getIndexStatus,
    retry: false,
    refetchInterval: 5000,
  });

  const documents = useMemo(() => {
    if (!documentsQuery.data) return DOCUMENTS;
    return documentsQuery.data.documents.map(toUiDocument);
  }, [documentsQuery.data]);

  const usingMockFallback = documentsQuery.isError || !documentsQuery.data;

  const userRole = CURRENT_USER.role as Role;
  const canUpload = hasPermission(userRole, 'canUpload');
  const canEdit = hasPermission(userRole, 'canEdit');
  const canDelete = hasPermission(userRole, 'canDelete');

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const filtered = documents.filter(doc => {
    if (search && !doc.name.toLowerCase().includes(search.toLowerCase())) return false;
    if (filters.category && doc.category !== filters.category) return false;
    if (filters.department && doc.department !== filters.department) return false;
    if (filters.type && doc.type !== filters.type) return false;
    return true;
  }).sort((a, b) => {
    if (filters.sort === 'name_asc') return a.name.localeCompare(b.name);
    return 0;
  });

  const totalPages = Math.ceil(filtered.length / PER_PAGE);
  const paginated = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  const handleRebuildIndex = async () => {
    setIsRebuilding(true);
    setIndexActionMessage(null);
    try {
      const response = await rebuildIndex(false);
      setIndexActionMessage(response.message);
      await indexStatusQuery.refetch();
    } catch (error) {
      setIndexActionMessage(error instanceof Error ? error.message : 'Index rebuild failed.');
    } finally {
      setIsRebuilding(false);
    }
  };

  return (
    <div className="fluid-section" data-testid="documents-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader title="Documents" subtitle="Search, filter and access all documents." />
        {canUpload && (
          <div className="flex flex-col gap-2 sm:mt-1 sm:flex-row">
            <button
              onClick={handleRebuildIndex}
              disabled={isRebuilding}
              className="flex w-full flex-shrink-0 items-center justify-center gap-2 rounded-xl border border-[#ddecd6] bg-white px-4 py-2.5 text-sm font-medium text-[#4a7c3f] transition-colors hover:bg-[#f0f7ed] disabled:opacity-50 sm:w-auto"
              data-testid="button-rebuild-index"
            >
              <RefreshCcw size={15} />
              {isRebuilding ? 'Indexing...' : 'Rebuild Index'}
            </button>
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex w-full flex-shrink-0 items-center justify-center gap-2 rounded-xl bg-[#4a7c3f] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#3d6834] sm:w-auto"
              data-testid="button-upload"
            >
              <Upload size={15} />
              Upload Document
            </button>
          </div>
        )}
      </div>

      <div className="mb-4 rounded-xl border border-[#e2eedd] bg-white px-4 py-3 text-xs text-[#5a7a52] shadow-sm">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <span>
            Documents source:{' '}
            <strong className="text-[#1a2e14]">
              {documentsQuery.isLoading ? 'Loading backend...' : usingMockFallback ? 'Mock fallback' : 'Backend data/files'}
            </strong>
          </span>
          <span>
            Index status:{' '}
            <strong className="text-[#1a2e14]">
              {indexStatusQuery.data?.status ?? 'unavailable'}
            </strong>
            {indexStatusQuery.data ? ` / ${indexStatusQuery.data.documents_indexed} indexed` : ''}
          </span>
        </div>
        {(indexActionMessage || documentsQuery.isError) && (
          <p className="mt-2 text-[#8a5208]">
            {indexActionMessage ?? 'Backend documents API is unavailable; showing mock documents.'}
          </p>
        )}
      </div>

      {/* Filters */}
      <div className="responsive-card mb-4 grid grid-cols-1 gap-3 border border-[#e2eedd] bg-white p-3 shadow-sm xl:grid-cols-[minmax(16rem,1.2fr)_minmax(26rem,2fr)_auto]">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Search documents..."
          className="min-w-0"
        />
        <FilterBar
          filters={[
            { key: 'category', label: 'All Categories', options: DOC_CATEGORIES },
            { key: 'department', label: 'All Departments', options: DOC_DEPARTMENTS },
            { key: 'type', label: 'All Types', options: DOC_TYPES },
          ]}
          values={filters}
          onChange={handleFilterChange}
        />
        <select
          value={filters.sort}
          onChange={e => handleFilterChange('sort', e.target.value)}
          className="w-full rounded-lg border border-[#ddecd6] px-3 py-2 text-sm transition-colors focus:ring-2 focus:ring-[#4a7c3f]/30 xl:w-auto"
          data-testid="select-sort"
        >
          <option value="">Sort: Latest</option>
          {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {/* Desktop Table */}
      <div className="scrollbar-soft hidden overflow-x-auto rounded-xl border border-[#e2eedd] bg-white shadow-sm md:block">
        <table className="w-full min-w-[58rem]" data-testid="documents-table">
          <thead>
            <tr className="border-b border-[#e2eedd] bg-[#f8fdf6]">
              <th className="px-5 py-3 text-left text-xs font-semibold text-[#5a7a52] uppercase tracking-wider">#</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#5a7a52] uppercase tracking-wider">Document Name</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#5a7a52] uppercase tracking-wider">Category</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#5a7a52] uppercase tracking-wider">Department</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#5a7a52] uppercase tracking-wider">Type</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#5a7a52] uppercase tracking-wider">Last Updated</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-[#5a7a52] uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody>
            {paginated.length > 0 ? paginated.map((doc, i) => (
              <DocumentRow
                key={doc.id}
                doc={doc}
                index={(page - 1) * PER_PAGE + i + 1}
                canEdit={canEdit}
                canDelete={canDelete}
              />
            )) : (
              <tr>
                <td colSpan={7} className="py-12">
                  <EmptyState title="No documents found" description="Try adjusting your search or filter criteria." />
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile Cards */}
      <div className="space-y-3 md:hidden">
        {paginated.length > 0 ? paginated.map(doc => (
          <DocumentCard key={doc.id} doc={doc} />
        )) : (
          <EmptyState title="No documents found" description="Try adjusting your search or filter criteria." />
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-[#5a7a52]">
            Showing {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, filtered.length)} of {filtered.length}
          </p>
          <div className="grid grid-cols-2 gap-2 sm:flex">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 text-sm border border-[#ddecd6] rounded-lg disabled:opacity-40 hover:bg-[#f0f7ed] transition-colors"
              data-testid="button-prev-page"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1.5 text-sm border border-[#ddecd6] rounded-lg disabled:opacity-40 hover:bg-[#f0f7ed] transition-colors"
              data-testid="button-next-page"
            >
              Next
            </button>
          </div>
        </div>
      )}

      <UploadModal open={showUploadModal} onClose={() => setShowUploadModal(false)} />
    </div>
  );
}
