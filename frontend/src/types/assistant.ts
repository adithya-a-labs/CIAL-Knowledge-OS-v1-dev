export type SearchScope = 'enterprise' | 'workspace' | 'hybrid' | 'current_upload';

export type ResponseLength = 'quick' | 'standard' | 'detailed' | 'operational';

export type ContextSourceType = 'enterprise' | 'workspace' | 'upload';

export type FeedbackType =
  | 'helpful'
  | 'not_helpful'
  | 'incorrect'
  | 'missing_sources'
  | 'hallucination';

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
  uploadStatus: 'mock_uploaded';
}

export interface ChatRequestPayload {
  query: string;
  searchScope: SearchScope;
  responseLength: ResponseLength;
  selectedContextIds: string[];
  uploadedFileIds: string[];
}

export interface ChatSource {
  id: string;
  citationIndex: number;
  documentId: string;
  documentTitle: string;
  sourceType: ContextSourceType;
  department?: string;
  pageNumber?: number;
  chunkId?: string;
  score?: number;
  reason?: string;
  excerpt?: string;
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
