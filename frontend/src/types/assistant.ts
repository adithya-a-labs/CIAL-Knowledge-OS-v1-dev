import type { SelectedContextItem } from '@/api/types';

export type SearchScope = 'enterprise' | 'workspace' | 'hybrid' | 'current_upload';

export type ResponseLength = 'quick' | 'standard' | 'detailed' | 'operational';

export type ContextSourceType = 'enterprise' | 'workspace' | 'upload';

export type FeedbackType =
  | 'helpful'
  | 'not_helpful'
  | 'incorrect'
  | 'missing_sources'
  | 'hallucination';

export interface AssistantChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  citations?: ChatCitation[];
  sources?: ChatSource[];
  metadata?: AssistantMessageMetadata;
  relatedQuestions?: string[];
}

export interface ContextDocument {
  id: string;
  title: string;
  sourceType: ContextSourceType;
  groupLabel: string;
  department?: string;
}

export interface UploadedFileContext {
  id: string;
  name: string;
  size: number;
  type: string;
  sourceType: 'upload';
  uploadStatus: 'uploading' | 'uploaded' | 'upload_failed';
  backendDocumentId?: string;
  backendDocumentVersionId?: string;
  indexingStatus?: 'pending' | 'indexing' | 'indexed' | 'failed' | 'deleted';
  indexingStage?: string;
  indexingSafeMessage?: string;
  indexingErrorCode?: string;
  retryAllowed?: boolean;
}

export interface ChatRequestPayload {
  query: string;
  searchScope: SearchScope;
  activeProfile: ResponseLength;
  selectedDocumentIds: string[];
  selectedFolderIds: string[];
  uploadedFileIds: string[];
}

export interface ChatSource {
  id: string;
  citationId?: string;
  citationIndex: number;
  documentId: string;
  documentVersionId?: string;
  repositoryId?: string;
  relativePath?: string;
  documentTitle: string;
  sourceType: ContextSourceType;
  department?: string;
  pageNumber?: number;
  pageIndex?: number;
  locationLabel?: string;
  pageCount?: number;
  sheetName?: string;
  sheetIndex?: number;
  slideNumber?: number;
  anchor?: string;
  chunkId?: string;
  score?: number;
  reason?: string;
  excerpt?: string;
  highlightText?: string;
  previewText?: string;
  fileType?: string;
  mimeType?: string;
  fileUrl?: string;
}

export interface ChatCitation {
  id: string;
  citationIndex: number;
  documentTitle: string;
  documentId?: string;
  documentVersionId?: string;
  repositoryId?: string;
  relativePath?: string;
  pageNumber?: number;
  pageIndex?: number;
  locationLabel?: string;
  pageCount?: number;
  sheetName?: string;
  sheetIndex?: number;
  slideNumber?: number;
  anchor?: string;
  chunkId?: string;
  snippet?: string;
  highlightText?: string;
  previewText?: string;
  fileType?: string;
  mimeType?: string;
  fileUrl?: string;
  score?: number;
}

export interface AssistantMessageMetadata {
  searchScope: SearchScope;
  activeProfile: ResponseLength;
  documentsSearched: number;
  chunksRetrieved: number;
  sourcesUsed: number;
  citationCount?: number;
  confidence: number;
  generationTimeSeconds: number;
  transformationLabel?: string;
}

export interface AssistantSession {
  id: string;
  title: string;
  messages: AssistantChatMessage[];
  selectedContextItems: SelectedContextItem[];
  uploadedFiles: UploadedFileContext[];
  searchScope: SearchScope;
  activeProfile: ResponseLength;
  feedbackByMessageId: Record<string, FeedbackType[]>;
  createdAt: string;
  updatedAt: string;
}
