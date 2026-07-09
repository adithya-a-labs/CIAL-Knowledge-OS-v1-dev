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
}

export interface ChatRequestPayload {
  query: string;
  searchScope: SearchScope;
  responseLength: ResponseLength;
  selectedDocumentIds: string[];
  selectedFolderIds: string[];
  uploadedFileIds: string[];
}

export interface ChatSource {
  id: string;
  citationIndex: number;
  documentId: string;
  relativePath?: string;
  documentTitle: string;
  sourceType: ContextSourceType;
  department?: string;
  pageNumber?: number;
  chunkId?: string;
  score?: number;
  reason?: string;
  excerpt?: string;
}

export interface ChatCitation {
  id: string;
  citationIndex: number;
  documentTitle: string;
  pageNumber?: number;
  snippet?: string;
  score?: number;
}

export interface AssistantMessageMetadata {
  searchScope: SearchScope;
  responseLength: ResponseLength;
  documentsSearched: number;
  chunksRetrieved: number;
  sourcesUsed: number;
  confidence: number;
  generationTimeSeconds: number;
}

export interface AssistantSession {
  id: string;
  title: string;
  messages: AssistantChatMessage[];
  selectedContextItems: SelectedContextItem[];
  uploadedFiles: UploadedFileContext[];
  searchScope: SearchScope;
  responseLength: ResponseLength;
  feedbackByMessageId: Record<string, FeedbackType>;
  createdAt: string;
  updatedAt: string;
}
