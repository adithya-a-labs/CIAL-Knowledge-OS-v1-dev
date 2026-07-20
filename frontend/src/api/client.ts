import type {
  ApiDocument,
  ChatRequest,
  ChatResponse,
  CorpusDocument,
  CorpusFolderResponse,
  CorpusSyncResponse,
  CorpusTreeResponse,
  DocumentPreview,
  DocumentListResponse,
  EvaluationRunRequest,
  EvaluationRunResponse,
  EvaluationRunsResponse,
  ExportListResponse,
  HealthResponse,
  IndexStatusResponse,
  EnterpriseRepositoryRequest,
  EnterpriseRepositorySettings,
  LoginRequest,
  LogoutResponse,
  RebuildIndexResponse,
  SignupRequest,
  AuthResponse,
} from './types';
import type { WorkspaceFolderResponse, WorkspacePreferences, WorkspaceSummaryResponse, WorkspaceTreeResponse } from '@/data/workspace/workspaceTypes';
import { ApiError } from './types';

const CONFIGURED_API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');
export const AUTH_INVALIDATED_EVENT = 'cial-auth-invalidated';
let authInvalidationDispatched = false;

type AuthInvalidationMode = 'none' | 'protected';
type ApiRequestInit = RequestInit & {
  authInvalidation?: AuthInvalidationMode;
};

function isLoopbackHost(hostname: string) {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0' || hostname === '::1' || hostname === '[::1]';
}

function resolveApiBaseUrl() {
  if (typeof window === 'undefined') {
    return CONFIGURED_API_BASE_URL;
  }
  try {
    const apiUrlValue = new URL(CONFIGURED_API_BASE_URL);
    const pageHostname = window.location.hostname;
    if (isLoopbackHost(apiUrlValue.hostname) && pageHostname && apiUrlValue.hostname !== pageHostname) {
      apiUrlValue.hostname = pageHostname;
      return apiUrlValue.toString().replace(/\/$/, '');
    }
  } catch {
    return CONFIGURED_API_BASE_URL;
  }
  return CONFIGURED_API_BASE_URL;
}

export function apiUrl(path: string) {
  if (/^https?:\/\//i.test(path)) return path;
  return `${resolveApiBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`;
}

export function resetAuthInvalidationGuard() {
  authInvalidationDispatched = false;
}

async function request<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const { authInvalidation = 'protected', ...fetchInit } = init;
  const response = await fetch(`${resolveApiBaseUrl()}${path}`, {
    credentials: 'include',
    ...fetchInit,
    headers: {
      ...(fetchInit.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...fetchInit.headers,
    },
  });

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    const rawDetail =
      typeof detail === 'object' && detail !== null && 'detail' in detail
        ? (detail as { detail: unknown }).detail
        : detail;
    const message =
      typeof rawDetail === 'object' && rawDetail !== null && 'message' in rawDetail
        ? String((rawDetail as { message: unknown }).message)
        : typeof rawDetail === 'string'
          ? rawDetail
          : `Request failed with status ${response.status}`;
    if (
      response.status === 401 &&
      authInvalidation === 'protected' &&
      typeof window !== 'undefined' &&
      !authInvalidationDispatched
    ) {
      authInvalidationDispatched = true;
      window.dispatchEvent(new Event(AUTH_INVALIDATED_EVENT));
    }
    throw new ApiError(message, response.status, detail);
  }

  return response.json() as Promise<T>;
}

export function getHealth() {
  return request<HealthResponse>('/api/health', { cache: 'no-store', authInvalidation: 'none' });
}

export function signUp(payload: SignupRequest) {
  return request<AuthResponse>('/api/auth/signup', {
    method: 'POST',
    body: JSON.stringify(payload),
    authInvalidation: 'none',
  });
}

export function logIn(payload: LoginRequest) {
  return request<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
    authInvalidation: 'none',
  });
}

export function getCurrentUser() {
  return request<AuthResponse>('/api/auth/me', { authInvalidation: 'none' });
}

export function logOut() {
  return request<LogoutResponse>('/api/auth/logout', {
    method: 'POST',
    authInvalidation: 'none',
  });
}

export function getMyWorkspaceTree() {
  return request<WorkspaceTreeResponse>('/api/workspaces/me/tree');
}

export function getMyWorkspaceFolder(folderId?: string | null) {
  return request<WorkspaceFolderResponse>(folderId ? `/api/workspaces/me/folders/${folderId}` : '/api/workspaces/me/root');
}

export function getMyWorkspaceSummary() {
  return request<WorkspaceSummaryResponse>('/api/workspaces/me/summary');
}

export function getMyWorkspacePreferences() {
  return request<WorkspacePreferences>('/api/workspaces/me/preferences');
}

export function saveMyWorkspacePreferences(preferences: WorkspacePreferences) {
  return request<WorkspacePreferences>('/api/workspaces/me/preferences', { method: 'PATCH', body: JSON.stringify(preferences) });
}

export function resetMyWorkspacePreferences() {
  return request<WorkspacePreferences>('/api/workspaces/me/preferences/reset', { method: 'POST' });
}

export function createMyWorkspaceFolder(name: string, parentId?: string | null) {
  return request('/api/workspaces/me/folders', { method: 'POST', body: JSON.stringify({ name, parent_id: parentId ?? null }) });
}

export function uploadMyWorkspaceFiles(files: File[], folderId?: string | null) {
  return Promise.all(files.map((file) => {
    const body = new FormData();
    body.append('file', file);
    if (folderId) body.append('folder_id', folderId);
    return request('/api/workspaces/me/documents/upload', { method: 'POST', body });
  }));
}

export function askQuestion(payload: ChatRequest, signal?: AbortSignal) {
  // Chat generation deliberately has no deadline. The caller supplies a
  // per-request signal solely for an explicit user Stop action.
  return request<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal,
  });
}

export function listChatSessions(signal?: AbortSignal) {
  return request<import('./types').ChatHistoryList>('/api/chat/sessions', { signal });
}

export function regenerateMessage(messageId: string, signal?: AbortSignal) {
  return request<ChatResponse>(`/api/chat/messages/${encodeURIComponent(messageId)}/regenerate`, { method: 'POST', signal });
}

export function transformMessage(messageId: string, operation: 'explain_simpler' | 'create_checklist') {
  return request<import('./types').ChatHistoryMessage>(`/api/chat/messages/${encodeURIComponent(messageId)}/transform`, { method: 'POST', body: JSON.stringify({ operation }) });
}

export function toggleMessageFeedback(messageId: string, feedback: string) {
  return request<import('./types').MessageFeedbackResponse>(`/api/chat/messages/${encodeURIComponent(messageId)}/feedback`, { method: 'PUT', body: JSON.stringify({ feedback }) });
}

export function exportMessage(messageId: string, format: 'pdf' | 'docx') {
  return request<import('./types').MessageExportResponse>(`/api/chat/messages/${encodeURIComponent(messageId)}/export`, { method: 'POST', body: JSON.stringify({ format, include_sources: true, include_metadata: true }) });
}

export function getCorpusTree() {
  return request<CorpusTreeResponse>('/api/corpus/tree');
}

export function getCorpusFolder(path = '') {
  const query = path ? `?path=${encodeURIComponent(path)}` : '';
  return request<CorpusFolderResponse>(`/api/corpus/folder${query}`);
}

export function getCorpusDocument(id: string) {
  return request<CorpusDocument>(`/api/corpus/document/${encodeURIComponent(id)}`);
}

export function getDocumentFileUrl(documentId: string) {
  return apiUrl(`/api/corpus/document/${encodeURIComponent(documentId)}/file`);
}

export function getDocumentViewUrl(documentId: string) {
  return apiUrl(`/api/corpus/document/${encodeURIComponent(documentId)}/view`);
}

export function getDocumentDownloadUrl(documentId: string) {
  return apiUrl(`/api/corpus/document/${encodeURIComponent(documentId)}/download`);
}

export function getDocumentThumbnailUrl(documentId: string, page = 1) {
  return apiUrl(`/api/corpus/document/${encodeURIComponent(documentId)}/thumbnail?page=${encodeURIComponent(String(page))}`);
}

export function getDocumentPreview(
  documentId: string,
  options: {
    chunkId?: string;
    page?: number;
    sheetName?: string;
    sheetIndex?: number;
    slideNumber?: number;
  } = {},
) {
  const params = new URLSearchParams();
  if (options.chunkId) params.set('chunk_id', options.chunkId);
  if (options.page !== undefined) params.set('page', String(options.page));
  if (options.sheetName) params.set('sheet_name', options.sheetName);
  if (options.sheetIndex !== undefined) params.set('sheet_index', String(options.sheetIndex));
  if (options.slideNumber !== undefined) params.set('slide_number', String(options.slideNumber));
  const query = params.toString();
  return request<DocumentPreview>(
    `/api/corpus/document/${encodeURIComponent(documentId)}/preview${query ? `?${query}` : ''}`,
  );
}

export function syncCorpus() {
  return request<CorpusSyncResponse>('/api/corpus/sync', { method: 'POST' });
}

export function listDocuments() {
  return request<DocumentListResponse>('/api/documents');
}

export function uploadDocument(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return request<ApiDocument>('/api/documents/upload', {
    method: 'POST',
    body: formData,
  });
}

export function rebuildIndex(force: boolean) {
  return request<RebuildIndexResponse>('/api/index/rebuild', {
    method: 'POST',
    body: JSON.stringify({ force }),
  });
}

export function getIndexStatus() {
  return request<IndexStatusResponse>('/api/index/status');
}

export function getEnterpriseRepositorySettings() {
  return request<EnterpriseRepositorySettings>('/api/settings/enterprise-repository');
}

export function validateEnterpriseRepository(payload: EnterpriseRepositoryRequest) {
  return request<EnterpriseRepositorySettings>('/api/settings/enterprise-repository/validate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function saveEnterpriseRepository(payload: EnterpriseRepositoryRequest) {
  return request<EnterpriseRepositorySettings>('/api/settings/enterprise-repository', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function runEvaluation(payload: EvaluationRunRequest) {
  return request<EvaluationRunResponse>('/api/evaluation/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listEvaluationRuns() {
  return request<EvaluationRunsResponse>('/api/evaluation/runs');
}

export function listExports() {
  return request<ExportListResponse>('/api/exports');
}
