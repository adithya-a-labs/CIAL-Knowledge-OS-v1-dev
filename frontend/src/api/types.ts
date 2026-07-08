export type ResponseLength = 'short' | 'medium' | 'long';
export type RuntimeStatus = 'starting' | 'ready' | 'indexing' | 'degraded' | 'failed' | 'no_documents';

export interface HealthResponse {
  status: RuntimeStatus;
  service: string;
  phase: string;
  engine_available: boolean;
  engine_ready: boolean;
  qdrant_ready: boolean;
  models_ready: boolean;
  documents_seen: number;
  documents_indexed: number;
  index_fresh: boolean;
  message: string;
}

export interface ChatRequest {
  question: string;
  selected_document_ids: string[];
  response_length: ResponseLength;
  include_sources: boolean;
}

export interface ChatCitation {
  id: string;
  document_name: string;
  page: number | null;
  snippet: string;
  score: number | null;
}

export interface ChatSource {
  id: string;
  document_name: string;
  path: string;
  page: number | null;
  chunk_id: string;
  text: string;
  score: number | null;
}

export interface ChatMetadata {
  retrieval_mode: string;
  phase: string;
  latency_ms: number;
  model: string;
}

export interface ChatResponse {
  answer: string;
  citations: ChatCitation[];
  sources: ChatSource[];
  metadata: ChatMetadata;
}

export type ApiDocumentType =
  | 'pdf'
  | 'docx'
  | 'xlsx'
  | 'csv'
  | 'pptx'
  | 'txt'
  | 'md'
  | 'html'
  | 'json'
  | 'xml'
  | 'yaml'
  | 'image'
  | 'unknown';

export interface ApiDocument {
  id: string;
  name: string;
  path: string;
  type: ApiDocumentType;
  size_bytes: number;
  modified_at: string;
  indexed: boolean;
}

export interface DocumentListResponse {
  documents: ApiDocument[];
}

export interface RebuildIndexRequest {
  force: boolean;
}

export interface RebuildIndexResponse {
  status: RuntimeStatus;
  engine_available: boolean;
  engine_ready: boolean;
  documents_seen: number;
  documents_indexed: number;
  index_fresh: boolean;
  qdrant_ready: boolean;
  models_ready: boolean;
  last_startup_check_at: string | null;
  last_index_run_at: string | null;
  message: string;
}

export interface IndexStatusResponse {
  status: RuntimeStatus;
  engine_available: boolean;
  engine_ready: boolean;
  documents_seen: number;
  documents_indexed: number;
  index_fresh: boolean;
  qdrant_ready: boolean;
  models_ready: boolean;
  last_startup_check_at: string | null;
  last_index_run_at: string | null;
  message: string;
}

export interface EvaluationRunRequest {
  questions_file: string;
  limit: number;
}

export interface EvaluationRunResponse {
  status: 'started' | 'completed' | 'failed';
  run_id: string;
  message: string;
}

export interface EvaluationRunSummary {
  id: string;
  path: string;
  modified_at: string;
}

export interface EvaluationRunsResponse {
  runs: EvaluationRunSummary[];
}

export interface ExportFile {
  id: string;
  name: string;
  path: string;
  type: string;
  size_bytes: number;
  modified_at: string;
}

export interface ExportListResponse {
  exports: ExportFile[];
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}
