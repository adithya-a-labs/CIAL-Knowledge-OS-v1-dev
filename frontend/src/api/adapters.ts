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
  return value;
}

export function toChatRequest(payload: ChatRequestPayload) {
  return {
    question: payload.query,
    selected_document_ids: [...payload.selectedDocumentIds],
    selected_folder_ids: [...payload.selectedFolderIds],
    response_length: toApiResponseLength(payload.activeProfile),
    profile: payload.activeProfile,
    include_sources: true,
    include_debug: import.meta.env.DEV,
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
    activeProfile: request.activeProfile,
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
  return source.document_name || source.relative_path?.split('/').pop() || source.path?.split('/').pop() || 'Unknown document';
}

function resolvedPageNumber(pageNumber?: number | null, page?: number | null, pageIndex?: number | null): number | undefined {
  if (typeof pageNumber === 'number' && Number.isFinite(pageNumber) && pageNumber > 0) return Math.trunc(pageNumber);
  if (typeof page === 'number' && Number.isFinite(page) && page > 0) return Math.trunc(page);
  if (typeof pageIndex === 'number' && Number.isFinite(pageIndex) && pageIndex >= 0) return Math.trunc(pageIndex) + 1;
  return undefined;
}

export function toUiChatCitations(response: ChatResponse): UiChatCitation[] {
  const citations = Array.isArray(response.citations) ? response.citations : [];
  const sources = Array.isArray(response.sources) ? response.sources : [];
  const sourceById = new Map(sources.map((source) => [source.id, source]));
  return citations.map((citation, index) => ({
    id: citation.id || `citation-${index + 1}`,
    citationIndex: index + 1,
    documentTitle: citation.document_name || 'Unknown document',
    documentId: citation.document_id || undefined,
    documentVersionId: citation.document_version_id || undefined,
    repositoryId: citation.repository_id || undefined,
    relativePath: citation.relative_path || undefined,
    pageNumber: resolvedPageNumber(citation.page_number, citation.page, citation.page_index)
      ?? resolvedPageNumber(undefined, sourceById.get(citation.id || `S${index + 1}`)?.page, sourceById.get(citation.id || `S${index + 1}`)?.page_index),
    pageIndex: citation.page_index ?? sourceById.get(citation.id || `S${index + 1}`)?.page_index ?? undefined,
    locationLabel: citation.location_label ?? undefined,
    pageCount: citation.page_count ?? sourceById.get(citation.id || `S${index + 1}`)?.page_count ?? undefined,
    sheetName: citation.sheet_name ?? undefined,
    sheetIndex: citation.sheet_index ?? undefined,
    slideNumber: citation.slide_number ?? undefined,
    anchor: citation.anchor ?? citation.chunk_id ?? undefined,
    chunkId: citation.chunk_id ?? undefined,
    snippet: citation.snippet || undefined,
    highlightText: citation.highlight_text ?? undefined,
    previewText: citation.preview_text ?? undefined,
    fileType: citation.file_type ?? undefined,
    mimeType: citation.mime_type ?? undefined,
    fileUrl: citation.file_url ?? undefined,
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
      citationId: source.id || `source-${index + 1}`,
      citationIndex,
      documentId:
        source.document_id ||
        source.relative_path ||
        source.path ||
        source.id ||
        documentTitleFromSource(source),
      documentVersionId: source.document_version_id || undefined,
      repositoryId: source.repository_id || undefined,
      relativePath: source.relative_path || source.path || undefined,
      documentTitle: documentTitleFromSource(source),
      sourceType: 'enterprise',
      pageNumber: resolvedPageNumber(source.page_number, source.page, source.page_index),
      pageIndex: source.page_index ?? undefined,
      locationLabel: source.location_label ?? undefined,
      pageCount: source.page_count ?? undefined,
      sheetName: source.sheet_name ?? undefined,
      sheetIndex: source.sheet_index ?? undefined,
      slideNumber: source.slide_number ?? undefined,
      anchor: source.anchor ?? source.chunk_id ?? undefined,
      chunkId: source.chunk_id || undefined,
      score: source.score ?? undefined,
      excerpt: source.text || undefined,
      highlightText: source.highlight_text || undefined,
      previewText: source.preview_text || undefined,
      fileType: source.file_type || undefined,
      mimeType: source.mime_type || undefined,
      fileUrl: source.file_url || undefined,
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

function stripRawReferencesSection(value: string): string {
  const normalized = value.replace(/\r\n/g, '\n');
  const lines = normalized.split('\n');
  const headingIndex = lines.findIndex((line, index) =>
    index >= Math.max(lines.length - 12, 0) && /^\s*references\s*:?\s*$/i.test(line.trim()),
  );

  if (headingIndex === -1) return value;

  const trailingLines = lines.slice(headingIndex + 1).filter((line) => line.trim().length > 0);
  if (trailingLines.length === 0) {
    return lines.slice(0, headingIndex).join('\n').trimEnd();
  }

  const looksInternal = trailingLines.every((line) =>
    /^\s*\[(?:\d+(?:\([^)]+\))?(?:\s*-\s*\d+)?)(?:\s*,\s*\d+(?:\([^)]+\))?(?:\s*-\s*\d+)?)*\]\s+/.test(line)
    || /file:\/\//i.test(line)
    || /\bchunk(?:_id| id)?\b/i.test(line)
    || /\bscore\b/i.test(line)
    || /\brelative[_ ]path\b/i.test(line)
    || /\bpna[\w-]*\b/i.test(line),
  );

  if (!looksInternal) return value;
  return lines.slice(0, headingIndex).join('\n').trimEnd();
}

function safeAnswer(response: ChatResponse): string {
  const raw = response.answer;
  if (typeof raw !== 'string') return 'No answer returned.';
  const answer = stripRawReferencesSection(raw).trim();
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
