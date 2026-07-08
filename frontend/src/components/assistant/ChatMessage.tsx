import {
  CheckSquare,
  Clipboard,
  Download,
  RefreshCcw,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  XCircle,
} from 'lucide-react';
import SourceCitationCard from './SourceCitationCard';
import {
  RESPONSE_LENGTH_LABELS,
  SEARCH_SCOPE_LABELS,
} from '@/data/assistantData';
import type {
  ChatCitation,
  AssistantMessageMetadata,
  ChatSource,
  FeedbackType,
} from '@/types/assistant';

export interface ChatMessageData {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  citations?: ChatCitation[];
  sources?: ChatSource[];
  metadata?: AssistantMessageMetadata;
  relatedQuestions?: string[];
}

interface ChatMessageProps {
  message: ChatMessageData;
  selectedFeedback?: FeedbackType;
  onCitationClick: (source: ChatSource) => void;
  onSourceOpen: (source: ChatSource) => void;
  onRelatedQuestionClick: (question: string) => void;
  onCopy: (content: string) => void;
  onUnavailableAction: (label: string) => void;
  onFeedback: (messageId: string, feedback: FeedbackType) => void;
}

const feedbackOptions: Array<{ value: FeedbackType; label: string; icon: typeof ThumbsUp }> = [
  { value: 'helpful', label: 'Helpful', icon: ThumbsUp },
  { value: 'not_helpful', label: 'Not helpful', icon: ThumbsDown },
  { value: 'incorrect', label: 'Incorrect', icon: XCircle },
  { value: 'missing_sources', label: 'Missing sources', icon: Clipboard },
  { value: 'hallucination', label: 'Hallucination', icon: Sparkles },
];

function renderContentWithCitations(
  content: string,
  sources: ChatSource[],
  onCitationClick: (source: ChatSource) => void
) {
  const citationPattern = /(\[\d+\])/g;

  return content.split('\n').map((line, lineIndex) => {
    const numbered = line.match(/^(\d+)\.\s(.+)/);
    const text = numbered ? numbered[2] : line;
    const parts = text.split(citationPattern);

    const renderedParts = parts.map((part, index) => {
      const citationNumber = Number(part);
      if (/^\d+$/.test(part) && parts[index - 1]?.startsWith('[') && parts[index + 1] === ']') {
        return null;
      }
      if (/^\[\d+\]$/.test(part)) {
        const indexNumber = Number(part.replace(/\[|\]/g, ''));
        const source = sources.find((candidate) => candidate.citationIndex === indexNumber);
        return (
          <button
            key={`${lineIndex}-${index}`}
            type="button"
            disabled={!source}
            onClick={() => source && onCitationClick(source)}
            className="mx-0.5 inline-flex min-h-5 min-w-5 items-center justify-center rounded-md border border-[hsl(95_28%_78%)] bg-[hsl(95_24%_94%)] px-1.5 text-[11px] font-bold text-primary align-middle hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-40"
            data-testid={`inline-citation-${indexNumber}`}
          >
            {part}
          </button>
        );
      }
      if (part === '[' || part === ']' || !Number.isNaN(citationNumber)) return part;
      return part;
    });

    if (!line.trim()) return null;

    if (numbered) {
      return (
        <div key={`line-${lineIndex}`} className="mt-1.5 flex gap-2">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-primary text-[10px] font-bold text-white">
            {numbered[1]}
          </span>
          <span className="safe-text text-sm text-foreground">{renderedParts}</span>
        </div>
      );
    }

    return (
      <p key={`line-${lineIndex}`} className="safe-text mt-1 text-sm leading-6 text-foreground">
        {renderedParts}
      </p>
    );
  });
}

function MetadataPanel({ metadata }: { metadata: AssistantMessageMetadata }) {
  return (
    <div className="rounded-lg border border-border bg-muted px-3 py-2 text-[11px] font-medium leading-5 text-muted-foreground">
      {SEARCH_SCOPE_LABELS[metadata.searchScope]} / {RESPONSE_LENGTH_LABELS[metadata.responseLength]} /{' '}
      {metadata.documentsSearched} docs / {metadata.chunksRetrieved} chunks / {metadata.sourcesUsed} sources /{' '}
      {metadata.confidence}% confidence / {metadata.generationTimeSeconds.toFixed(1)}s
    </div>
  );
}

function CitationList({
  citations,
  sources,
  onCitationClick,
}: {
  citations: ChatCitation[];
  sources: ChatSource[];
  onCitationClick: (source: ChatSource) => void;
}) {
  if (citations.length === 0) return null;

  return (
    <div className="ce-card p-3" data-testid="assistant-citations">
      <p className="mb-2 text-xs font-semibold text-foreground">Citations</p>
      <div className="flex flex-wrap gap-2">
        {citations.map((citation) => {
          const source = sources.find((candidate) => candidate.citationIndex === citation.citationIndex);
          return (
            <button
              key={citation.id}
              type="button"
              disabled={!source}
              onClick={() => source && onCitationClick(source)}
              className="inline-flex max-w-full items-center gap-1 rounded-lg border border-[hsl(95_28%_78%)] bg-[hsl(95_24%_94%)] px-2.5 py-1.5 text-left text-[11px] font-semibold text-primary hover:bg-accent disabled:cursor-default disabled:opacity-70"
              data-testid={`citation-chip-${citation.citationIndex}`}
            >
              <span>[{citation.citationIndex}]</span>
              <span className="truncate">{citation.documentTitle}</span>
              {citation.pageNumber ? <span className="text-muted-foreground">p. {citation.pageNumber}</span> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function ChatMessage({
  message,
  selectedFeedback,
  onCitationClick,
  onSourceOpen,
  onRelatedQuestionClick,
  onCopy,
  onUnavailableAction,
  onFeedback,
}: ChatMessageProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end" data-testid={`chat-message-user-${message.id}`}>
        <div className="max-w-[92%] sm:max-w-[76%] lg:max-w-[70%]">
          <div className="safe-text rounded-xl border border-primary bg-primary px-4 py-3 text-sm text-white shadow-sm">
            {message.content}
          </div>
          <p className="mt-1 text-right text-[11px] text-muted-foreground">{message.timestamp}</p>
        </div>
      </div>
    );
  }

  const sources = message.sources ?? [];
  const citations = message.citations ?? [];
  const answer = message.content?.trim() || 'No answer returned.';

  return (
    <div className="flex justify-start" data-testid={`chat-message-ai-${message.id}`}>
      <div className="max-w-[94%] space-y-2 sm:max-w-[84%] lg:max-w-[80%]">
        <div className="ce-card px-4 py-3">
          <div className="mb-2 flex items-center justify-between gap-3 border-b border-border pb-2">
            <p className="text-xs font-semibold text-foreground">Grounded response</p>
            <span className="ce-meta-text">{message.timestamp}</span>
          </div>
          <div className="max-w-prose text-sm leading-6">
            {renderContentWithCitations(answer, sources, onCitationClick)}
          </div>
        </div>

        <CitationList citations={citations} sources={sources} onCitationClick={onCitationClick} />

        <SourceCitationCard sources={sources} onOpenSource={onSourceOpen} />

        {message.metadata && <MetadataPanel metadata={message.metadata} />}

        {message.relatedQuestions && message.relatedQuestions.length > 0 && (
          <div className="ce-card p-3">
            <p className="mb-2 text-xs font-semibold text-foreground">Related questions</p>
            <div className="flex flex-wrap gap-2">
              {message.relatedQuestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => onRelatedQuestionClick(question)}
                  className="ce-action min-h-8 text-primary"
                  data-testid="button-related-question"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2 px-1">
          <button
            type="button"
            onClick={() => onCopy(message.content)}
            className="ce-action text-primary"
            data-testid={`button-copy-${message.id}`}
          >
            <Clipboard size={13} />
            Copy
          </button>
          {[
            { label: 'Regenerate', icon: RefreshCcw },
            { label: 'Export', icon: Download },
            { label: 'Explain simpler', icon: Sparkles },
            { label: 'Create checklist', icon: CheckSquare },
          ].map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.label}
                type="button"
                onClick={() => onUnavailableAction(action.label)}
                className="ce-action"
                data-testid={`button-action-${action.label.toLowerCase().replace(/\s+/g, '-')}`}
              >
                <Icon size={13} />
                {action.label}
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-2 px-1">
          <span className="text-[11px] text-muted-foreground">Feedback</span>
          {feedbackOptions.map((option) => {
            const Icon = option.icon;
            const active = selectedFeedback === option.value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  // TODO: Send feedback to backend analytics/evaluation logging.
                  onFeedback(message.id, option.value);
                }}
                className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-[11px] font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
                  active
                    ? 'border-primary bg-primary text-white'
                    : 'border-border bg-white text-muted-foreground hover:bg-muted hover:text-foreground'
                }`}
                data-testid={`button-feedback-${option.value}-${message.id}`}
              >
                <Icon size={12} />
                {option.label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
