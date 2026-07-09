export type ResponseMode = 'quick' | 'standard' | 'detailed' | 'operational' | 'elite';
export type ResponseLength = ResponseMode | 'short' | 'medium' | 'long';
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
  selected_folder_ids?: string[];
  response_length: ResponseLength;
  profile?: ResponseMode;
  max_answer_words?: number;
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
  document_id?: string | null;
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
  profile?: ResponseMode | string;
  effective_min_answer_words?: number | null;
  effective_max_answer_words?: number | null;
  answer_detail_level?: string;
  prompt_name?: string;
  adaptive_sections?: boolean;
  citation_mode?: string;
  temperature?: number;
  evidence_token_budget?: number | null;
  max_context_tokens?: number | null;
  retrieved_count?: number;
  selected_evidence_count?: number;
  context_sections?: number;
  weak_evidence?: boolean;
  index_fresh?: boolean | null;
  selected_context_applied?: boolean;
  selected_document_count?: number;
  selected_folder_count?: number;
  effective_document_count?: number;
  selected_context_filter_mode?: string | null;
}

export interface ChatResponse {
  answer: string;
  citations: ChatCitation[];
  sources: ChatSource[];
  metadata: ChatMetadata;
  debug?: Record<string, unknown> | null;
}

export type ApiDocumentType =
  | 'pdf'
  | 'docx'
  | 'doc'
  | 'xlsx'
  | 'xls'
  | 'csv'
  | 'pptx'
  | 'ppt'
  | 'txt'
  | 'md'
  | 'html'
  | 'json'
  | 'xml'
  | 'yaml'
  | 'png'
  | 'jpg'
  | 'jpeg'
  | 'tiff'
  | 'bmp'
  | 'webp'
  | 'gif'
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

export interface CorpusDocument {
  id: string;
  folder_id: string | null;
  name: string;
  relative_path: string;
  extension: string | null;
  mime_type: string | null;
  file_type: string;
  size_bytes: number;
  content_hash: string | null;
  modified_at: string | null;
  indexed: boolean;
  indexing_status: 'pending' | 'indexing' | 'indexed' | 'failed' | 'deleted' | string;
  indexed_at: string | null;
  page_count: number | null;
  created_at: string;
  updated_at: string;
}

export type CorpusFile = CorpusDocument;

export interface CorpusFolder {
  id: string | null;
  parent_id: string | null;
  name: string;
  relative_path: string;
  depth: number;
  document_count: number;
  subfolder_count: number;
  last_scanned_at: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface CorpusTreeNode extends CorpusFolder {
  children: CorpusTreeNode[];
  documents?: CorpusDocument[];
  files?: CorpusDocument[];
}

export interface CorpusTreeResponse {
  root: CorpusTreeNode;
  folders_count: number;
  documents_count: number;
}

export interface CorpusFolderResponse {
  folder: CorpusFolder;
  folders: CorpusFolder[];
  files: CorpusDocument[];
  documents?: CorpusDocument[];
}

export interface CorpusSyncResponse {
  folders_scanned: number;
  files_scanned: number;
  folders_added: number;
  folders_removed: number;
  folders_moved: number;
  files_added: number;
  files_removed: number;
  files_modified: number;
  files_moved: number;
  files_renamed: number;
  files_unchanged: number;
  indexing_jobs_created: number;
  skipped: number;
  elapsed_ms: number;
  differences_found: boolean;
  message: string;
}

export interface DocumentPreview extends CorpusDocument {
  preview_text: string;
  highlight_text: string;
  page: number | null;
  chunk_id: string | null;
  open_url: string | null;
  download_url: string | null;
  file_url?: string | null;
  thumbnail_url?: string | null;
  read_error: string | null;
  render_kind?: 'pdf' | 'image' | 'text' | 'code' | 'table' | 'office_card' | 'card' | string;
  extraction_method?: string;
  table_rows?: string[][];
  supported_preview?: boolean;
  sheet_count?: number;
}

export interface SelectedContextItem {
  id: string;
  type: 'document' | 'folder';
  title: string;
  relative_path: string;
  document_count?: number;
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
