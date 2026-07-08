import type { ChatMessageData } from '@/components/assistant/ChatMessage';
import type { Document } from '@/types';
import type {
  AssistantMessageMetadata,
  ChatRequestPayload,
  ChatSource as UiChatSource,
  ResponseLength as UiResponseLength,
} from '@/types/assistant';
import type { ApiDocument, ChatResponse, ResponseLength } from './types';

export function toApiResponseLength(value: UiResponseLength): ResponseLength {
  if (value === 'quick') return 'short';
  if (value === 'operational' || value === 'detailed') return 'long';
  return 'medium';
}

export function toChatRequest(payload: ChatRequestPayload) {
  return {
    question: payload.query,
    selected_document_ids: [...payload.selectedContextIds, ...payload.uploadedFileIds],
    response_length: toApiResponseLength(payload.responseLength),
    include_sources: true,
  };
}

export function toAssistantMessageMetadata(
  response: ChatResponse,
  request: ChatRequestPayload,
): AssistantMessageMetadata {
  return {
    searchScope: request.searchScope,
    responseLength: request.responseLength,
    documentsSearched: request.selectedContextIds.length + request.uploadedFileIds.length,
    chunksRetrieved: response.sources.length,
    sourcesUsed: response.citations.length,
    confidence: response.citations.length > 0 ? 84 : 0,
    generationTimeSeconds: response.metadata.latency_ms / 1000,
  };
}

export function toUiChatSources(response: ChatResponse): UiChatSource[] {
  const sourceById = new Map(response.sources.map((source) => [source.id, source]));
  return response.citations.map((citation, index) => {
    const source = sourceById.get(citation.id);
    return {
      id: citation.id,
      citationIndex: index + 1,
      documentId: source?.path || citation.document_name,
      documentTitle: citation.document_name,
      sourceType: 'enterprise',
      pageNumber: citation.page ?? undefined,
      chunkId: source?.chunk_id,
      score: citation.score ?? source?.score ?? undefined,
      excerpt: citation.snippet || source?.text,
      reason: `Retrieved through ${response.metadata.retrieval_mode} / Phase ${response.metadata.phase}.`,
    };
  });
}

export function toAssistantMessage(
  response: ChatResponse,
  request: ChatRequestPayload,
): Omit<ChatMessageData, 'id' | 'role' | 'timestamp'> {
  return {
    content: response.answer,
    sources: toUiChatSources(response),
    metadata: toAssistantMessageMetadata(response, request),
    relatedQuestions: [],
  };
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function toDocumentType(type: ApiDocument['type']): string {
  const map: Record<ApiDocument['type'], string> = {
    pdf: 'Manual',
    docx: 'Manual',
    xlsx: 'Report',
    csv: 'Report',
    pptx: 'Manual',
    txt: 'Manual',
    md: 'Manual',
    html: 'Manual',
    json: 'Report',
    xml: 'Report',
    yaml: 'Report',
    image: 'Manual',
    unknown: 'Manual',
  };
  return map[type] ?? 'Manual';
}

export function toUiDocument(document: ApiDocument): Document {
  return {
    id: document.id,
    name: document.name,
    category: document.path.split('/')[2] || 'Enterprise Corpus',
    department: 'Knowledge OS',
    type: toDocumentType(document.type),
    lastUpdated: formatDate(document.modified_at),
    status: document.indexed ? 'Indexed' : 'Pending Index',
  };
}
