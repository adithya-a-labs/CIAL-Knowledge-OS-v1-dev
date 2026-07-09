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
import type { ReactNode } from 'react';
import SourceCitationCard from './SourceCitationCard';
import {
  RESPONSE_LENGTH_LABELS,
  SEARCH_SCOPE_LABELS,
} from '@/data/assistantData';
import type {
  AssistantChatMessage,
  AssistantMessageMetadata,
  ChatCitation,
  ChatSource,
  FeedbackType,
} from '@/types/assistant';

export type ChatMessageData = AssistantChatMessage;

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
  onCitationClick: (source: ChatSource) => void,
) {
  const renderInline = (text: string, lineIndex: number) => {
    const tokenPattern = /(\[\d+\]|\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
    const parts = text.split(tokenPattern);
    return parts.map((part, index) => {
      if (/^\[\d+\]$/.test(part)) {
        const indexNumber = Number(part.replace(/\[|\]/g, ''));
        const source = sources.find((candidate) => candidate.citationIndex === indexNumber);
        return (
          <button
            key={`${lineIndex}-${index}`}
            type="button"
            disabled={!source}
            onClick={() => source && onCitationClick(source)}
            className="mx-0.5 inline-flex min-h-5 min-w-5 items-center justify-center rounded-full border border-[hsl(95_28%_78%)] bg-[hsl(95_24%_94%)] px-1.5 text-[10px] font-bold text-primary align-middle hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-40"
            data-testid={`inline-citation-${indexNumber}`}
          >
            {part}
          </button>
        );
      }
      if (/^\*\*[^*]+\*\*$/.test(part)) {
        return <strong key={`${lineIndex}-${index}`}>{part.slice(2, -2)}</strong>;
      }
      if (/^`[^`]+`$/.test(part)) {
        return (
          <code key={`${lineIndex}-${index}`} className="rounded-md bg-muted px-1.5 py-0.5 text-[0.9em]">
            {part.slice(1, -1)}
          </code>
        );
      }
      const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (link) {
        const href = link[2].startsWith('http') ? link[2] : '#';
        return (
          <a key={`${lineIndex}-${index}`} href={href} target="_blank" rel="noreferrer" className="font-semibold text-primary underline underline-offset-2">
            {link[1]}
          </a>
        );
      }
      return part;
    });
  };

  const blocks: ReactNode[] = [];
  const codeBuffer: string[] = [];
  let inCodeBlock = false;

  content.split('\n').forEach((rawLine, lineIndex) => {
    const line = rawLine.trimEnd();
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        blocks.push(
          <pre key={`code-${lineIndex}`} className="scrollbar-soft my-3 overflow-x-auto rounded-2xl border border-slate-800 bg-slate-950 px-4 py-3 text-[12px] leading-6 text-slate-100">
            <code>{codeBuffer.splice(0).join('\n')}</code>
          </pre>,
        );
      }
      inCodeBlock = !inCodeBlock;
      return;
    }
    if (inCodeBlock) {
      codeBuffer.push(rawLine);
      return;
    }
    if (!line.trim()) {
      blocks.push(<div key={`space-${lineIndex}`} className="h-1" />);
      return;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)/);
    if (heading) {
      blocks.push(
        <h3 key={`heading-${lineIndex}`} className="mt-3 text-[0.95rem] font-semibold tracking-[-0.01em] text-foreground">
          {renderInline(heading[2], lineIndex)}
        </h3>,
      );
      return;
    }

    const bullet = line.match(/^[-*]\s+(.+)/);
    if (bullet) {
      blocks.push(
        <div key={`bullet-${lineIndex}`} className="mt-1 flex gap-2.5">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
          <span className="safe-text text-sm leading-6 text-foreground">{renderInline(bullet[1], lineIndex)}</span>
        </div>,
      );
      return;
    }

    const numbered = line.match(/^(\d+)\.\s(.+)/);
    if (numbered) {
      blocks.push(
        <div key={`line-${lineIndex}`} className="mt-1.5 flex gap-2.5">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-[hsl(95_24%_94%)] text-[10px] font-bold text-primary">
            {numbered[1]}
          </span>
          <span className="safe-text text-sm leading-6 text-foreground">{renderInline(numbered[2], lineIndex)}</span>
        </div>,
      );
      return;
    }

    blocks.push(
      <p key={`line-${lineIndex}`} className="safe-text mt-1 text-sm leading-6 text-foreground">
        {renderInline(line, lineIndex)}
      </p>,
    );
  });

  return blocks;
}

function MetadataPanel({ metadata }: { metadata: AssistantMessageMetadata }) {
  return (
    <div className="rounded-2xl bg-[hsl(210_20%_98%)] px-3 py-2 text-[11px] font-medium leading-5 text-muted-foreground ring-1 ring-black/5">
      {SEARCH_SCOPE_LABELS[metadata.searchScope]} / {RESPONSE_LENGTH_LABELS[metadata.activeProfile]} /{' '}
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
    <div className="rounded-2xl bg-white/90 p-2.5 ring-1 ring-black/5" data-testid="assistant-citations">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Citations</p>
      <div className="flex flex-wrap gap-2">
        {citations.map((citation) => {
          const source = sources.find((candidate) => candidate.citationIndex === citation.citationIndex);
          return (
            <button
              key={citation.id}
              type="button"
              disabled={!source}
              onClick={() => source && onCitationClick(source)}
              className="inline-flex max-w-full items-center gap-1 rounded-full border border-[hsl(95_28%_78%)] bg-[hsl(95_24%_94%)] px-2.5 py-1.5 text-left text-[11px] font-semibold text-primary hover:bg-accent disabled:cursor-default disabled:opacity-70"
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
          <div className="safe-text rounded-[1.35rem] bg-[linear-gradient(135deg,hsl(95_50%_33%)_0%,hsl(95_45%_28%)_100%)] px-4 py-3 text-sm text-white shadow-[0_18px_38px_-26px_rgba(47,109,37,0.8)]">
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
      <div className="max-w-[95%] space-y-3 sm:max-w-[88%] lg:max-w-[82%]">
        <div className="rounded-[1.5rem] bg-white/95 px-5 py-4 shadow-[0_18px_40px_-34px_rgba(15,23,42,0.4)] ring-1 ring-black/5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Grounded response</p>
            <span className="ce-meta-text">{message.timestamp}</span>
          </div>
          <div className="max-w-[68ch] text-sm leading-7">
            {renderContentWithCitations(answer, sources, onCitationClick)}
          </div>
        </div>

        <CitationList citations={citations} sources={sources} onCitationClick={onCitationClick} />

        <SourceCitationCard sources={sources} onOpenSource={onSourceOpen} />

        {message.metadata && <MetadataPanel metadata={message.metadata} />}

        {message.relatedQuestions && message.relatedQuestions.length > 0 && (
          <div className="rounded-2xl bg-white/90 p-3 ring-1 ring-black/5">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Related questions</p>
            <div className="flex flex-wrap gap-2">
              {message.relatedQuestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => onRelatedQuestionClick(question)}
                  className="ce-action min-h-8 rounded-full px-3 text-primary"
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
            className="ce-action min-h-8 rounded-full px-3 text-primary"
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
                className="ce-action min-h-8 rounded-full px-3"
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
                  onFeedback(message.id, option.value);
                }}
                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${
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
