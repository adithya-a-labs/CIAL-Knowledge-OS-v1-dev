export type ResponseMode = 'quick' | 'standard' | 'detailed' | 'operational' | 'elite';
export type ResponseLength = ResponseMode | 'short' | 'medium' | 'long';
export type RuntimeStatus = 'starting' | 'ready' | 'indexing' | 'degraded' | 'failed' | 'no_documents';

export interface SignupRequest {
  full_name: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthenticatedUser {
  id: string;
  email: string;
  display_name: string;
  initials: string;
  organization_name?: string | null;
  department_name?: string | null;
  role_names: string[];
  permission_names: string[];
  notifications_count: number;
}

export interface AuthResponse {
  user: AuthenticatedUser;
  message: string;
}

export interface LogoutResponse {
  message: string;
}

export interface HealthResponse {
  status: RuntimeStatus;
  service: string;
  phase: string;
  engine_available: boolean;
  engine_ready: boolean;
  stage?: string;
  knowledge_engine?: { status: string; ready: boolean; stage: string };
  qdrant_ready: boolean;
  models_ready: boolean;
  documents_seen: number;
  documents_indexed: number;
  index_fresh: boolean;
  message: string;
}

export interface ChatRequest {
  session_id?: string;
  question: string;
  search_scope?: 'enterprise' | 'workspace' | 'hybrid' | 'current_upload';
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
  document_id?: string | null;
  document_version_id?: string | null;
  repository_id?: string | null;
  relative_path?: string | null;
  page: number | null;
  page_number?: number | null;
  page_index?: number | null;
  location_label?: string | null;
  page_count?: number | null;
  sheet_name?: string | null;
  sheet_index?: number | null;
  slide_number?: number | null;
  anchor?: string | null;
  chunk_id?: string | null;
  snippet: string;
  highlight_text?: string | null;
  preview_text?: string | null;
  file_type?: string | null;
  mime_type?: string | null;
  file_url?: string | null;
  preview_url?: string | null;
  download_url?: string | null;
  score: number | null;
}

export interface ChatSource {
  id: string;
  document_name: string;
  path: string;
  document_id?: string | null;
  document_version_id?: string | null;
  repository_id?: string | null;
  relative_path?: string | null;
  page: number | null;
  page_number?: number | null;
  page_index?: number | null;
  location_label?: string | null;
  page_count?: number | null;
  sheet_name?: string | null;
  sheet_index?: number | null;
  slide_number?: number | null;
  anchor?: string | null;
  chunk_id: string;
  text: string;
  highlight_text?: string | null;
  preview_text?: string | null;
  file_type?: string | null;
  mime_type?: string | null;
  file_url?: string | null;
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
  label?: string;
}

export interface ChatResponse {
  session_id?: string | null;
  user_message_id?: string | null;
  assistant_message_id?: string | null;
  answer: string;
  citations: ChatCitation[];
  sources: ChatSource[];
  metadata: ChatMetadata;
  debug?: Record<string, unknown> | null;
}

export interface ChatHistoryMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Array<Record<string, unknown>>;
  sources: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
  created_at: string;
  feedback?: string[];
}

export interface MessageFeedbackResponse { active: string[]; }
export interface MessageExportResponse { filename: string; download_url: string; }
export type AssistantExportFormat = 'pdf' | 'docx';
export type AssistantExportStatus = 'queued' | 'processing' | 'ready' | 'failed' | 'expired' | 'cancelled';
export interface AssistantExportCreateResponse { export_id: string; status: 'queued'; }
export interface AssistantExportJob {
  export_id: string; format: AssistantExportFormat; status: AssistantExportStatus;
  progress: { stage: string; percent: number }; error: { code: string; message: string } | null;
  filename?: string | null; mime_type?: string | null; file_size_bytes?: number | null;
  preview?: { type: 'pdf' | 'html'; url: string } | null; download_url?: string | null;
  suggested_workspace_filename?: string | null;
}
export interface AssistantExportWorkspaceSaveRequest { filename?: string | null; folder_id?: string | null; }
export interface AssistantExportWorkspaceSaveResponse { document_id: string; filename: string; folder_id?: string | null; file_type: AssistantExportFormat; size_bytes: number; indexing_status: string; indexing_job_id?: string | null; open_url: string; }

export interface ChatHistorySession {
  id: string;
  title: string;
  messages: ChatHistoryMessage[];
  created_at: string;
  updated_at: string;
}

export interface ChatHistoryList { sessions: ChatHistorySession[]; }

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
  indexing_status?: 'pending' | 'indexing' | 'indexed' | 'failed' | 'deleted';
  indexing_stage?: string | null;
  indexing_safe_message?: string | null;
}

export interface ChatAttachmentResponse {
  document_id: string; document_version_id: string; name: string; size_bytes: number;
  mime_type?: string | null; indexing_status: 'pending' | 'indexing' | 'indexed' | 'failed';
  indexing_job_id: string; indexing_safe_message?: string | null;
}

export interface DocumentIndexingStatus {
  document_id: string; document_version_id?: string | null; name: string;
  indexing_status: 'pending' | 'indexing' | 'indexed' | 'failed' | 'deleted';
  indexing_stage?: string | null; indexing_safe_message?: string | null;
  indexing_updated_at: string; retry_allowed: boolean;
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

export interface EnterpriseRepositorySettings {
  name: string;
  folder: string;
  config_path: string;
  exists: boolean;
  is_directory: boolean;
  readable: boolean;
  writable: boolean;
  valid: boolean;
  message: string;
}

export interface EnterpriseRepositoryRequest {
  folder: string;
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
  document_id?: string;
  relative_path: string;
  preview_text: string;
  highlight_text: string;
  page: number | null;
  page_count: number | null;
  chunk_id: string | null;
  open_url: string | null;
  download_url: string | null;
  file_url?: string | null;
  viewer_url?: string | null;
  viewer_format?: string | null;
  viewer_ready?: boolean;
  thumbnail_url?: string | null;
  rendered_html?: string | null;
  preview_notice?: string | null;
  read_error: string | null;
  render_kind?: 'pdf' | 'image' | 'text' | 'code' | 'table' | 'spreadsheet' | 'slides' | 'docx' | 'markdown' | 'html' | 'card' | string;
  extraction_method?: string;
  table_rows?: string[][];
  supported_preview?: boolean;
  sheet_count?: number;
  sheet_names?: string[];
  active_sheet?: string | null;
  active_sheet_index?: number | null;
  active_slide_number?: number | null;
  slides?: Array<{ index: string; title: string; body: string }>;
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
