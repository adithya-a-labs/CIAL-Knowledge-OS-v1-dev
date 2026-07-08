export type ResponseLength = 'short' | 'medium' | 'long';

export interface HealthResponse {
  status: 'ok';
  service: string;
  phase: string;
  engine_available: boolean;
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
  status: 'started' | 'completed' | 'failed';
  message: string;
}

export interface IndexStatusResponse {
  status: 'idle' | 'indexing' | 'completed' | 'failed';
  documents_seen: number;
  documents_indexed: number;
  last_run_at: string | null;
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
