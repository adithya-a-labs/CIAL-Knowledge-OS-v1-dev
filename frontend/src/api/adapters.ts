import type { ChatMessageData } from '@/components/assistant/ChatMessage';
import type { Document } from '@/types';
import type {
  AssistantMessageMetadata,
  ChatCitation as UiChatCitation,
  ChatRequestPayload,
  ChatSource as UiChatSource,
  ResponseLength as UiResponseLength,
} from '@/types/assistant';
import type {
  ApiDocument,
  ChatCitation,
  ChatResponse,
  ChatSource,
  CorpusDocument,
  CorpusFolder,
  CorpusFolderResponse,
  CorpusTreeNode,
  ResponseLength,
  SelectedContextItem,
} from './types';

export function toApiResponseLength(value: UiResponseLength): ResponseLength {
  if (value === 'quick') return 'short';
  if (value === 'operational' || value === 'detailed') return 'long';
  return 'medium';
}

export function toChatRequest(payload: ChatRequestPayload) {
  const maxAnswerWords = payload.responseLength === 'quick' ? 200 : undefined;
  return {
    question: payload.query,
    selected_document_ids: [...payload.selectedDocumentIds, ...payload.uploadedFileIds],
    selected_folder_ids: [...payload.selectedFolderIds],
    response_length: toApiResponseLength(payload.responseLength),
    profile: payload.responseLength,
    max_answer_words: maxAnswerWords,
    include_sources: true,
  };
}

export function toAssistantMessageMetadata(
  response: ChatResponse,
  request: ChatRequestPayload,
): AssistantMessageMetadata {
  const sources = Array.isArray(response.sources) ? response.sources : [];
  const citations = Array.isArray(response.citations) ? response.citations : [];
  const metadata = response.metadata ?? {
    retrieval_mode: 'unknown',
    phase: '4.5',
    latency_ms: 0,
    model: '',
  };
  return {
    searchScope: request.searchScope,
    responseLength: request.responseLength,
    documentsSearched: request.selectedDocumentIds.length + request.uploadedFileIds.length + request.selectedFolderIds.length,
    chunksRetrieved: sources.length,
    sourcesUsed: citations.length,
    confidence: citations.length > 0 ? 84 : 0,
    generationTimeSeconds: Number(metadata.latency_ms || 0) / 1000,
  };
}

function normalizeChatResponse(response: ChatResponse): ChatResponse {
  if (!response || typeof response !== 'object') {
    return {
      answer: 'No answer returned.',
      citations: [],
      sources: [],
      metadata: {
        retrieval_mode: 'unknown',
        phase: '4.5',
        latency_ms: 0,
        model: '',
      },
    };
  }

  const payload = response as Partial<ChatResponse>;
  return {
    answer: typeof payload.answer === 'string' ? payload.answer : '',
    citations: Array.isArray(payload.citations) ? payload.citations : [],
    sources: Array.isArray(payload.sources) ? payload.sources : [],
    metadata: payload.metadata ?? {
      retrieval_mode: 'unknown',
      phase: '4.5',
      latency_ms: 0,
      model: '',
    },
  };
}

function citationIndexById(citations: ChatCitation[]): Map<string, number> {
  return new Map(citations.map((citation, index) => [citation.id, index + 1]));
}

function documentTitleFromSource(source: ChatSource): string {
  return source.document_name || source.path?.split('/').pop() || 'Unknown document';
}

export function toUiChatCitations(response: ChatResponse): UiChatCitation[] {
  const citations = Array.isArray(response.citations) ? response.citations : [];
  return citations.map((citation, index) => ({
    id: citation.id || `citation-${index + 1}`,
    citationIndex: index + 1,
    documentTitle: citation.document_name || 'Unknown document',
    pageNumber: citation.page ?? undefined,
    snippet: citation.snippet || undefined,
    score: citation.score ?? undefined,
  }));
}

export function toUiChatSources(response: ChatResponse): UiChatSource[] {
  const sources = Array.isArray(response.sources) ? response.sources : [];
  const citations = Array.isArray(response.citations) ? response.citations : [];
  const citationIndexes = citationIndexById(citations);
  const metadata = response.metadata ?? {
    retrieval_mode: 'unknown',
    phase: '4.5',
    latency_ms: 0,
    model: '',
  };

  return sources.map((source, index) => {
    const citationIndex = citationIndexes.get(source.id) ?? index + 1;
    return {
      id: source.id || `source-${index + 1}`,
      citationIndex,
      documentId: source.path || source.id || documentTitleFromSource(source),
      relativePath: source.path || undefined,
      documentTitle: documentTitleFromSource(source),
      sourceType: 'enterprise',
      pageNumber: source.page ?? undefined,
      chunkId: source.chunk_id || undefined,
      score: source.score ?? undefined,
      excerpt: source.text || undefined,
      reason: `Retrieved through ${metadata.retrieval_mode} / Phase ${metadata.phase}.`,
    };
  });
}

export function corpusDocumentToContext(document: CorpusDocument): SelectedContextItem {
  return {
    id: document.id,
    type: 'document',
    title: document.name,
    relative_path: document.relative_path,
  };
}

export function corpusFolderToContext(folder: CorpusFolder): SelectedContextItem {
  return {
    id: folder.id ?? folder.relative_path,
    type: 'folder',
    title: folder.name || 'Root',
    relative_path: folder.relative_path,
    document_count: folder.document_count,
  };
}

export function flattenCorpusTree(root: CorpusTreeNode): { folders: CorpusFolder[]; documents: CorpusDocument[] } {
  const folders: CorpusFolder[] = [];
  const documents: CorpusDocument[] = [];
  const visit = (node: CorpusTreeNode) => {
    folders.push(node);
    (node.documents ?? node.files ?? []).forEach((document) => documents.push(document));
    node.children.forEach(visit);
  };
  visit(root);
  return { folders, documents };
}

export function normalizeCorpusFolderResponse(response: CorpusFolderResponse): CorpusFolderResponse {
  return {
    ...response,
    files: response.files ?? response.documents ?? [],
  };
}

function looksLikeStructuredDump(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return false;
  const startsStructured = trimmed.startsWith('{') || trimmed.startsWith('[');
  return startsStructured && /"?(answer|citations|sources|metadata)"?\s*[:=]/i.test(trimmed.slice(0, 1000));
}

function safeAnswer(response: ChatResponse): string {
  const raw = response.answer;
  if (typeof raw !== 'string') return 'No answer returned.';
  const answer = raw.trim();
  if (!answer) return 'No answer returned.';

  if (looksLikeStructuredDump(answer)) {
    try {
      const parsed = JSON.parse(answer);
      if (
        parsed &&
        typeof parsed === 'object' &&
        'answer' in parsed &&
        typeof (parsed as { answer?: unknown }).answer === 'string'
      ) {
        const nestedAnswer = (parsed as { answer: string }).answer.trim();
        return nestedAnswer || 'No answer returned.';
      }
    } catch {
      return 'The backend returned an unexpected structured response instead of answer text.';
    }
  }

  return answer;
}

export function toAssistantMessage(
  response: ChatResponse,
  request: ChatRequestPayload,
): Omit<ChatMessageData, 'id' | 'role' | 'timestamp'> {
  const normalizedResponse = normalizeChatResponse(response);
  return {
    content: safeAnswer(normalizedResponse),
    citations: toUiChatCitations(normalizedResponse),
    sources: toUiChatSources(normalizedResponse),
    metadata: toAssistantMessageMetadata(normalizedResponse, request),
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
    doc: 'Manual',
    xlsx: 'Report',
    xls: 'Report',
    csv: 'Report',
    pptx: 'Manual',
    ppt: 'Manual',
    txt: 'Manual',
    md: 'Manual',
    html: 'Manual',
    json: 'Report',
    xml: 'Report',
    yaml: 'Report',
    png: 'Manual',
    jpg: 'Manual',
    jpeg: 'Manual',
    tiff: 'Manual',
    bmp: 'Manual',
    webp: 'Manual',
    gif: 'Manual',
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
