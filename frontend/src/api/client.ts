import type {
  ApiDocument,
  ChatRequest,
  ChatResponse,
  DocumentListResponse,
  EvaluationRunRequest,
  EvaluationRunResponse,
  EvaluationRunsResponse,
  ExportListResponse,
  HealthResponse,
  IndexStatusResponse,
  RebuildIndexResponse,
} from './types';
import { ApiError } from './types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...init.headers,
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
    throw new ApiError(message, response.status, detail);
  }

  return response.json() as Promise<T>;
}

export function getHealth() {
  return request<HealthResponse>('/api/health');
}

export function askQuestion(payload: ChatRequest) {
  return request<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
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
