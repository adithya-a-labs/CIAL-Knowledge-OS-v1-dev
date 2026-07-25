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
  api_ready: boolean;
  retrieval_ready: boolean;
  engine_available: boolean;
  engine_ready: boolean;
  stage?: string;
  knowledge_engine?: { status: string; ready: boolean; stage: string };
  qdrant_ready: boolean;
  models_ready: boolean;
  database_ready: boolean;
  indexer_seen: boolean;
  indexer_state: 'starting' | 'reconciling' | 'active' | 'watching' | 'degraded' | 'stopped' | 'unknown' | string;
  worker_heartbeat_at?: string | null;
  queue_counts?: Record<string, number>;
  queue_depth?: number;
  latest_index_generation?: number;
  bm25_generation?: number;
  documents_seen: number;
  documents_indexed: number;
  index_fresh: boolean;
  message: string;
}

export type SystemHealthColor = 'green' | 'blue' | 'yellow' | 'red';

export interface SystemStatusComponent {
  status: 'available' | 'degraded' | 'unavailable' | 'unknown';
  available: boolean | null;
  detail: string;
  checked_at: string;
  latency_ms: number;
}

export interface SystemStatusResponse {
  status: SystemHealthColor;
  label: 'System ready' | 'Updating knowledge' | 'Degraded' | 'Unavailable';
  chat_available: boolean;
  indexing_active: boolean;
  components: Record<string, SystemStatusComponent>;
  index: {
    generation: number;
    bm25_generation: number;
    published_at: string | null;
    point_count: number;
  };
  indexing: {
    worker_state: string;
    worker_seen: boolean;
    worker_heartbeat_at: string | null;
    queue_depth: number;
    queue_counts: Record<string, number>;
    active_jobs: Array<Record<string, unknown>>;
    last_successful_index_at: string | null;
  };
  models: {
    ollama: string;
    embedding: string;
    embedding_device: string;
    embedding_ready: boolean;
  };
  gpu: {
    available: boolean | null;
    requested: boolean;
    device: string;
    utilization_percent: number | null;
    memory_used_mb: number | null;
    memory_total_mb: number | null;
  };
  timestamps: {
    generated_at: string;
    worker_heartbeat_at: string | null;
    generation_published_at: string | null;
    last_successful_index_at: string | null;
  };
  latency_ms: Record<string, number>;
}

export type OperationsStatus = 'green' | 'blue' | 'yellow' | 'red';

export interface OperationsComponent {
  status: 'available' | 'degraded' | 'unavailable' | 'unknown';
  available: boolean | null;
  detail: string;
  checked_at: string;
  latency_ms: number;
}

export interface OperationsEvent {
  id: string;
  type: string;
  severity: 'info' | 'warning' | 'error';
  message: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface AdminSystemMonitor {
  status: OperationsStatus;
  label: string;
  generated_at: string;
  uptime_seconds: number;
  stale: boolean;
  connection_hint_seconds: number;
  infrastructure: {
    backend: OperationsComponent;
    postgresql: OperationsComponent;
    qdrant: OperationsComponent;
    service_latency_ms: number;
    uptime_seconds: number;
  };
  indexing: {
    worker_status: string;
    worker_heartbeat_at: string | null;
    worker_heartbeat_age_seconds: number | null;
    worker_stale: boolean;
    active_workers: number;
    queue_depth: number;
    priority_queues: Record<string, number>;
    pending_jobs: number;
    active_jobs_count: number;
    completed_jobs: number;
    failed_jobs: number;
    active_jobs: Array<Record<string, unknown>>;
    recent_errors: Array<Record<string, unknown>>;
    active_published_generation: number;
    bm25_generation: number;
    state: string;
    last_successful_publish: string | null;
    throughput: Record<string, number>;
    internal_queue_depths: Record<string, number>;
  };
  gpu: {
    cuda_available: boolean;
    device: string;
    utilization_percent: number | null;
    memory_used_mb: number | null;
    memory_total_mb: number | null;
    embedding_device: string;
    precision: string;
    batch_size: number;
    embedding_throughput_chunks_per_minute: number | null;
    state?: string | null;
    embedding_model_gpu_resident?: boolean | null;
    active_embedding_jobs?: number | null;
    chat_priority_active?: boolean | null;
    embedding_model_memory?: Record<string, number | boolean>;
    generation_start?: Record<string, unknown>;
    generation_end?: Record<string, unknown>;
  };
  cpu: {
    utilization_percent?: number;
    process_utilization_percent?: number;
    logical_cores?: number;
    indexer: Record<string, number>;
    extraction_workers: number;
    active_worker_count: number;
    current_tasks: number;
    ocr_workers: number;
  };
  models: {
    ollama_available: boolean | null;
    loaded_models: string[];
    embedding_model: string;
    embedding_model_ready: boolean;
    query_embedding_device?: string;
    reranker_model: string;
    reranker_ready: boolean;
  };
  query: {
    active_chat_requests: number;
    status: string;
    current_stage: string | null;
    current_stage_duration_ms: number | null;
    failed_stage: string | null;
    timeout_reason: string | null;
    validation_latency_ms: number | null;
    retrieval_latency_ms: number | null;
    reranker_latency_ms: number | null;
    generation_latency_ms: number | null;
    generation_metrics?: {
      prompt_tokens?: number;
      context_tokens?: number;
      system_prompt_tokens?: number;
      output_tokens?: number;
      first_token_ms?: number;
      tokens_per_second?: number;
      model_load_ms?: number;
      prompt_eval_ms?: number;
      ollama_total_ms?: number;
      keep_alive?: string;
      retry_count?: number;
      ollama_processor_type?: string;
      gpu_layers_used?: number | null;
      gpu_layers_requested?: number;
      gpu_memory_used?: number;
      gpu_memory_total?: number;
      cpu_offload_detected?: boolean | null;
      generation_gpu_utilization?: number;
      generation_gpu_utilization_peak?: number;
      generation_gpu_memory_peak?: number;
      generation_gpu_samples?: number;
    };
    total_latency_ms: number | null;
    last_error: string | null;
  };
  events: OperationsEvent[];
}

export interface ChatRequest {
  session_id?: string;
  question: string;
  search_scope?: 'enterprise' | 'workspace' | 'hybrid' | 'current_upload';
  selected_document_ids: string[];
  selected_folder_ids?: string[];
  selected_note_ids?: string[];
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
  source_type?: 'document' | 'note';
  note_id?: string | null;
  note_revision?: number | null;
  workspace_id?: string | null;
  block_id?: string | null;
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
  source_type?: 'document' | 'note';
  note_id?: string | null;
  note_revision?: number | null;
  workspace_id?: string | null;
  block_id?: string | null;
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
  selected_note_count?: number;
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

export interface GenerationEvent {
  request_id: string;
  type: 'stage' | 'token' | 'citation' | 'result' | 'error' | 'cancelled';
  stage_id: string;
  status: 'started' | 'completed' | 'failed';
  elapsed_ms: number;
  metrics?: Record<string, number | string | boolean | null>;
  delta?: string;
  payload?: ChatResponse | {
    message?: string;
    failed_stage?: string | null;
    reason?: string | null;
    timeout_state?: string | null;
    retry_allowed?: boolean;
  };
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
  origin: string;
  created_from_document: string | null;
  context_scope: string;
  selected_document_ids: string[];
  selected_note_ids: string[];
  context_snapshot: SelectedContextItem[];
}

export interface ChatHistoryList { sessions: ChatHistorySession[]; }

export interface ChatSessionCreatePayload {
  title: string;
  origin: 'assistant' | 'homepage' | 'knowledge_center' | 'global_search' | 'saved_knowledge';
  created_from_document?: string | null;
  context_scope: 'all_accessible' | 'selected_documents' | 'selected_context';
  selected_document_ids: string[];
  selected_note_ids?: string[];
}

export type GlobalSearchType = 'document' | 'passage' | 'note' | 'conversation' | 'summary' | 'saved_knowledge' | 'folder';
export interface GlobalSearchFilters { types: GlobalSearchType[]; scope: 'all_accessible' | 'enterprise' | 'my_workspace'; file_types: string[]; updated_after?: string | null; department_ids: string[]; workspace_ids: string[]; }
export interface GlobalSearchResult { id:string; type:GlobalSearchType; title:string; excerpt:string|null; match_reasons:string[]; relevance:'Highly relevant'|'Relevant'|'Related'; workspace:string|null; department:string|null; file_type:string|null; updated_at:string|null; document_id:string|null; page:number|null; chunk_id:string|null; summary_type?:string|null;summary_length?:string|null;can_use_as_context:boolean; deep_link:string; }
export interface GlobalSearchResponse { query:string; items:GlobalSearchResult[]; counts:Record<string,number>; next_cursor:string|null; interpretation:{applied:boolean;explanation:string|null;chips:string[]}; lexical_available:boolean; semantic_available:boolean; }
export interface RecentSearchList { items:Array<{id:string;query:string;updated_at:string}>; }

export interface SavedKnowledgeRecord { id:string; item_type:'summary'|'answer'; title:string; description:string|null; body_markdown:string; original_question:string|null; citations:Array<Record<string,unknown>>; source_references:Array<Record<string,unknown>>; selected_document_ids:string[]; context_scope:string|null; conversation_id:string|null; source_message_id:string|null; summary_id:string|null; profile:string|null; model_name:string|null; prompt_version:string|null; collection:string|null; tags:string[]; visibility:string; is_favorite:boolean; version:number; state:string; source_count:number; created_at:string; updated_at:string; }
export interface SavedKnowledgeList { items:SavedKnowledgeRecord[]; next_cursor:string|null; }

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
  indexing_error_code?: string | null;
  indexing_job_id?: string | null;
  document_version_id?: string | null;
  retry_allowed?: boolean;
  indexing_updated_at?: string;
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
  indexing_error_code?: string | null; indexing_updated_at: string; retry_allowed: boolean;
}

export interface DocumentListResponse {
  documents: ApiDocument[];
}

export interface RebuildIndexRequest {
  force: boolean;
  confirm: boolean;
  scope?: Record<string, string>;
}

export interface RebuildIndexResponse {
  status: 'accepted';
  job_id: string;
  message: string;
}

export interface IndexStatusResponse {
  status: RuntimeStatus;
  api_ready: boolean;
  retrieval_ready: boolean;
  engine_available: boolean;
  engine_ready: boolean;
  documents_seen: number;
  documents_indexed: number;
  index_fresh: boolean;
  qdrant_ready: boolean;
  models_ready: boolean;
  database_ready: boolean;
  indexer_seen: boolean;
  indexer_state: string;
  worker_id: string | null;
  worker_heartbeat_at: string | null;
  reconciliation_state: string | null;
  last_reconciliation_at: string | null;
  queue_counts: Record<string, number>;
  queue_by_operation: Record<string, number>;
  queue_depth: number;
  active_jobs: Array<Record<string, unknown>>;
  recent_errors: Array<Record<string, unknown>>;
  latest_index_generation: number;
  bm25_generation: number;
  generation_published_at: string | null;
  qdrant_collection: string | null;
  qdrant_point_count: number;
  embedding_device: string | null;
  embedding_precision: string | null;
  active_batch_limit: number;
  cpu_extraction_workers: number;
  internal_queue_depths: Record<string, number>;
  throughput: Record<string, number>;
  reconciliation_metrics: Record<string, unknown>;
  bm25_metrics: Record<string, unknown>;
  gpu_metrics: Record<string, number>;
  last_successful_index_at: string | null;
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
  current_version_id?: string | null;
  modified_at: string | null;
  indexed: boolean;
  indexing_status: 'pending' | 'indexing' | 'indexed' | 'failed' | 'deleted' | string;
  indexing_stage?: string | null;
  indexing_safe_message?: string | null;
  indexing_error_code?: string | null;
  retry_allowed?: boolean;
  indexing_updated_at?: string;
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
  type: 'document' | 'folder' | 'note';
  title: string;
  relative_path: string;
  document_count?: number;
  updated_at?: string;
  is_pinned?: boolean;
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
