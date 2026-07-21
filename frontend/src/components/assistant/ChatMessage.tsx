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
import type { ComponentPropsWithoutRef, CSSProperties } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import SourceCitationCard from './SourceCitationCard';
import {
  RESPONSE_LENGTH_LABELS,
  SEARCH_SCOPE_LABELS,
} from '@/data/assistantData';
import type {
  AssistantChatMessage,
  AssistantMessageMetadata,
  ChatSource,
  FeedbackType,
} from '@/types/assistant';

export type ChatMessageData = AssistantChatMessage;

interface ChatMessageProps {
  message: ChatMessageData;
  chatWidth?: number;
  selectedFeedback?: FeedbackType[];
  onCitationClick: (source: ChatSource) => void;
  onSourceOpen: (source: ChatSource) => void;
  onRelatedQuestionClick: (question: string) => void;
  onCopy: (message: ChatMessageData) => Promise<void>;
  onAction: (message: ChatMessageData, action: 'regenerate' | 'explain_simpler' | 'create_checklist' | 'export_pdf' | 'export_docx' | 'copy_formatted' | 'export_markdown') => void;
  loadingAction?: string;
  onFeedback: (messageId: string, feedback: FeedbackType) => void;
  includeSourceExcerpts: boolean;
  showRetrievalDetails: boolean;
}

type MarkdownNode = {
  type?: string;
  value?: string;
  url?: string;
  children?: MarkdownNode[];
};

type CitationReference = {
  sourceIndex: number;
  label: string;
};

const feedbackOptions: Array<{ value: FeedbackType; label: string; icon: typeof ThumbsUp }> = [
  { value: 'helpful', label: 'Helpful', icon: ThumbsUp },
  { value: 'not_helpful', label: 'Not helpful', icon: ThumbsDown },
  { value: 'incorrect', label: 'Incorrect', icon: XCircle },
  { value: 'missing_sources', label: 'Missing sources', icon: Clipboard },
  { value: 'hallucination', label: 'Hallucination', icon: Sparkles },
];

const CITATION_LINK_PREFIX = '#citation=';
const CITATION_GROUP_PATTERN = /\[((?:\s*\d+(?:\([^)]+\))?(?:\s*-\s*\d+)?\s*)(?:,\s*\d+(?:\([^)]+\))?(?:\s*-\s*\d+)?\s*)*)\]/g;

function parseCitationGroup(content: string): CitationReference[] {
  const references: CitationReference[] = [];

  for (const rawPart of content.split(',')) {
    const part = rawPart.trim();
    if (!part) continue;

    const rangeMatch = part.match(/^(\d+)\s*-\s*(\d+)$/);
    if (rangeMatch) {
      const start = Number(rangeMatch[1]);
      const end = Number(rangeMatch[2]);
      if (Number.isFinite(start) && Number.isFinite(end) && end >= start && end - start <= 24) {
        for (let index = start; index <= end; index += 1) {
          references.push({ sourceIndex: index, label: String(index) });
        }
      }
      continue;
    }

    const simpleMatch = part.match(/^(\d+)(\([^)]+\))?$/);
    if (!simpleMatch) continue;

    references.push({
      sourceIndex: Number(simpleMatch[1]),
      label: `${simpleMatch[1]}${simpleMatch[2] ?? ''}`,
    });
  }

  return references;
}

function splitTextWithCitationLinks(value: string): MarkdownNode[] | null {
  const matches = Array.from(value.matchAll(CITATION_GROUP_PATTERN));
  if (matches.length === 0) return null;

  const nodes: MarkdownNode[] = [];
  let cursor = 0;

  for (const match of matches) {
    const fullMatch = match[0];
    const group = match[1];
    const index = match.index ?? 0;
    const references = parseCitationGroup(group);
    if (references.length === 0) continue;

    if (index > cursor) {
      nodes.push({ type: 'text', value: value.slice(cursor, index) });
    }

    nodes.push({
      type: 'link',
      url: `${CITATION_LINK_PREFIX}${encodeURIComponent(group)}`,
      children: [{ type: 'text', value: fullMatch }],
    });

    cursor = index + fullMatch.length;
  }

  if (nodes.length === 0) return null;
  if (cursor < value.length) {
    nodes.push({ type: 'text', value: value.slice(cursor) });
  }
  return nodes;
}

function shouldSkipCitationTransform(node: MarkdownNode | null) {
  const type = node?.type;
  return type === 'link' || type === 'linkReference' || type === 'definition' || type === 'inlineCode' || type === 'code' || type === 'html';
}

function walkMarkdownTree(node: MarkdownNode) {
  if (!Array.isArray(node.children)) return;

  for (let index = 0; index < node.children.length;) {
    const child = node.children[index];
    if (
      child?.type === 'text'
      && typeof child.value === 'string'
      && !shouldSkipCitationTransform(node)
    ) {
      const replacement = splitTextWithCitationLinks(child.value);
      if (replacement) {
        node.children.splice(index, 1, ...replacement);
        index += replacement.length;
        continue;
      }
    }

    walkMarkdownTree(child);
    index += 1;
  }
}

function remarkCitationLinks() {
  return (tree: MarkdownNode) => {
    walkMarkdownTree(tree);
  };
}

function CitationInlineGroup({
  content,
  sources,
  onCitationClick,
}: {
  content: string;
  sources: ChatSource[];
  onCitationClick: (source: ChatSource) => void;
}) {
  const references = parseCitationGroup(content);
  if (references.length === 0) return <span>[{content}]</span>;

  return (
    <span className="mx-0.5 inline-flex flex-wrap items-center gap-1 align-middle" data-testid={`inline-citation-group-${content.replace(/\s+/g, '-')}`}>
      {references.map((reference, index) => {
        const source = sources.find((candidate) => candidate.citationIndex === reference.sourceIndex);
        return (
          <span key={`${reference.label}-${index}`} className="inline-flex items-center gap-1">
            {index > 0 ? <span className="text-[10px] font-semibold text-muted-foreground">,</span> : null}
            <button
              type="button"
              disabled={!source}
              onClick={() => source && onCitationClick(source)}
              className="inline-flex min-h-5 items-center justify-center rounded-full border border-[hsl(95_28%_78%)] bg-[hsl(95_24%_94%)] px-1.5 text-[10px] font-bold text-primary align-middle hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:opacity-40"
              data-testid={`inline-citation-${reference.label.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`}
              aria-label={`Open citation ${reference.label}`}
            >
              [{reference.label}]
            </button>
          </span>
        );
      })}
    </span>
  );
}

function createMarkdownComponents(
  sources: ChatSource[],
  onCitationClick: (source: ChatSource) => void,
) {
  return {
    h1: ({ children }: ComponentPropsWithoutRef<'h1'>) => (
      <h1 className="safe-text mt-5 max-w-[76rem] text-xl font-bold tracking-tight text-foreground">{children}</h1>
    ),
    h2: ({ children }: ComponentPropsWithoutRef<'h2'>) => (
      <h2 className="safe-text mt-5 max-w-[76rem] text-lg font-bold tracking-tight text-foreground">{children}</h2>
    ),
    h3: ({ children }: ComponentPropsWithoutRef<'h3'>) => (
      <h3 className="safe-text mt-4 max-w-[76rem] text-[0.95rem] font-semibold tracking-[-0.01em] text-foreground">{children}</h3>
    ),
    h4: ({ children }: ComponentPropsWithoutRef<'h4'>) => (
      <h4 className="safe-text mt-4 max-w-[76rem] text-sm font-semibold text-foreground">{children}</h4>
    ),
    p: ({ children }: ComponentPropsWithoutRef<'p'>) => (
      <p className="safe-text my-2 max-w-[76rem] text-foreground">{children}</p>
    ),
    ol: ({ children }: ComponentPropsWithoutRef<'ol'>) => (
      <ol className="my-3 list-decimal space-y-2 pl-6 marker:font-semibold marker:text-slate-500 [&_ol]:mt-2 [&_ul]:mt-2">
        {children}
      </ol>
    ),
    ul: ({ children }: ComponentPropsWithoutRef<'ul'>) => (
      <ul className="my-3 list-disc space-y-2 pl-6 marker:text-slate-500 [&_ol]:mt-2 [&_ul]:mt-2">
        {children}
      </ul>
    ),
    li: ({ children }: ComponentPropsWithoutRef<'li'>) => (
      <li className="safe-text pl-1 text-foreground [&>p]:my-1.5 [&>p]:max-w-none [&>ul]:my-2 [&>ol]:my-2">
        {children}
      </li>
    ),
    blockquote: ({ children }: ComponentPropsWithoutRef<'blockquote'>) => (
      <blockquote className="my-4 border-l-2 border-[#d8e5ef] bg-[#f7fafc] py-2 pl-4 pr-3 text-slate-700">
        {children}
      </blockquote>
    ),
    pre: ({ children }: ComponentPropsWithoutRef<'pre'>) => (
      <div className="w-full">
        <pre className="scrollbar-soft my-4 w-full overflow-x-auto rounded-2xl border border-slate-800 bg-slate-950 px-4 py-3 text-[12px] leading-6 text-slate-100">
          {children}
        </pre>
      </div>
    ),
    code: ({ children, className }: ComponentPropsWithoutRef<'code'>) => {
      const value = String(children ?? '');
      const isBlockCode = className?.includes('language-') || value.includes('\n');
      if (isBlockCode) {
        return <code className={className}>{children}</code>;
      }
      return <code className="rounded bg-muted px-1.5 py-0.5 text-[0.9em] font-mono text-foreground">{children}</code>;
    },
    table: ({ children }: ComponentPropsWithoutRef<'table'>) => (
      <div className="scrollbar-soft my-4 w-full overflow-x-auto rounded-2xl border border-[#dce4d8] bg-white">
        <table className="w-full min-w-[42rem] border-collapse text-left text-sm">{children}</table>
      </div>
    ),
    thead: ({ children }: ComponentPropsWithoutRef<'thead'>) => (
      <thead className="bg-[hsl(95_24%_96%)]">{children}</thead>
    ),
    tbody: ({ children }: ComponentPropsWithoutRef<'tbody'>) => (
      <tbody>{children}</tbody>
    ),
    tr: ({ children }: ComponentPropsWithoutRef<'tr'>) => (
      <tr className="border-b border-[#eef2eb] last:border-b-0">{children}</tr>
    ),
    th: ({ children }: ComponentPropsWithoutRef<'th'>) => (
      <th className="safe-text border-b border-[#dce4d8] px-3 py-2.5 text-left font-semibold text-foreground [&_p]:my-0 [&_p]:max-w-none">
        {children}
      </th>
    ),
    td: ({ children }: ComponentPropsWithoutRef<'td'>) => (
      <td className="safe-text align-top px-3 py-2.5 text-foreground [&_p]:my-0 [&_p]:max-w-none">
        {children}
      </td>
    ),
    a: ({ href = '', children, ...props }: ComponentPropsWithoutRef<'a'>) => {
      if (href.startsWith(CITATION_LINK_PREFIX)) {
        return (
          <CitationInlineGroup
            content={decodeURIComponent(href.slice(CITATION_LINK_PREFIX.length))}
            sources={sources}
            onCitationClick={onCitationClick}
          />
        );
      }

      const isExternal = /^https?:\/\//i.test(href);
      return (
        <a
          {...props}
          href={href}
          target={isExternal ? '_blank' : props.target}
          rel={isExternal ? 'noreferrer' : props.rel}
          className="font-semibold text-primary underline underline-offset-2 hover:text-primary/80"
        >
          {children}
        </a>
      );
    },
  };
}

function MetadataPanel({ metadata }: { metadata: AssistantMessageMetadata }) {
  return (
    <div className="px-3 text-[11px] font-medium leading-5 text-muted-foreground">
      {SEARCH_SCOPE_LABELS[metadata.searchScope]} / {RESPONSE_LENGTH_LABELS[metadata.activeProfile]} /{' '}
      {metadata.documentsSearched} documents / {metadata.chunksRetrieved} chunks / {metadata.citationCount ?? metadata.sourcesUsed} citations /{' '}
      {metadata.confidence}% evidence confidence / {metadata.generationTimeSeconds.toFixed(1)}s
    </div>
  );
}

export default function ChatMessage({
  message,
  chatWidth,
  selectedFeedback,
  onCitationClick,
  onSourceOpen,
  onRelatedQuestionClick,
  onCopy,
  onAction,
  loadingAction,
  onFeedback,
  includeSourceExcerpts,
  showRetrievalDetails,
}: ChatMessageProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end" data-testid={`chat-message-user-${message.id}`}>
        <div className="max-w-[92%] sm:max-w-[76%] lg:max-w-[70%]">
          <div className="safe-text rounded-[1.35rem] bg-primary px-4 py-3 text-sm text-white shadow-sm">
            {message.content}
          </div>
          <p className="mt-1 text-right text-[11px] text-muted-foreground">{message.timestamp}</p>
        </div>
      </div>
    );
  }

  const sources = message.sources ?? [];
  const answer = message.content?.trim() || 'No answer returned.';
  const hasCitations = (message.citations?.length ?? 0) > 0;
  const markdownComponents = createMarkdownComponents(sources, onCitationClick);
  const width = chatWidth ?? 800;

  let fontSizeClass = 'text-sm leading-7';
  let cardWidthStyle: CSSProperties = { width: '100%' };
  const isCentered = width >= 768;

  if (width >= 1024) {
    fontSizeClass = 'text-[15px] leading-7';
    cardWidthStyle = { width: '92%', marginLeft: 'auto', marginRight: 'auto' };
  } else if (width >= 768) {
    fontSizeClass = 'text-[14px] leading-[1.65rem]';
    cardWidthStyle = { width: '95%', marginLeft: 'auto', marginRight: 'auto' };
  } else {
    fontSizeClass = 'text-[14px] leading-6';
    cardWidthStyle = { width: '100%' };
  }

  return (
    <div className={`flex w-full ${isCentered ? 'justify-center' : 'justify-start'}`} data-testid={`chat-message-ai-${message.id}`}>
      <div style={cardWidthStyle} className="space-y-3 pr-1 transition-all duration-200">
        <div className="rounded-[1.5rem] border border-[#dfe6dc] bg-white px-5 py-4 shadow-sm lg:px-6">
          <div className="flex items-start gap-4">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-white" aria-hidden="true"><Sparkles size={17} /></span>
            <div className="min-w-0 flex-1">
              <div className="mb-2 flex items-center justify-between gap-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{message.metadata?.transformationLabel ?? 'Grounded response'}</p>
                <span className="ce-meta-text">{message.timestamp}</span>
              </div>
              <div className={`w-full ${fontSizeClass}`} data-testid="assistant-markdown">
                <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm, remarkCitationLinks]}>
                  {answer}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        </div>

        {showRetrievalDetails && message.metadata ? <MetadataPanel metadata={message.metadata} /> : null}

        {hasCitations ? <SourceCitationCard sources={sources} onOpenSource={onSourceOpen} includeExcerpts={includeSourceExcerpts} /> : null}

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
            onClick={() => void onCopy(message)}
            disabled={!message.content || Boolean(loadingAction)}
            aria-label="Copy complete response as Markdown"
            className="ce-action min-h-8 rounded-full px-3 text-primary"
            data-testid={`button-copy-${message.id}`}
          >
            <Clipboard size={13} />
            {loadingAction === 'copied' ? 'Copied' : 'Copy'}
          </button>
          {[
            { label: 'Regenerate', action: 'regenerate', icon: RefreshCcw },
            { label: 'Export PDF', action: 'export_pdf', icon: Download },
            { label: 'Export DOCX', action: 'export_docx', icon: Download },
            { label: 'Markdown file', action: 'export_markdown', icon: Download },
            { label: 'Copy formatted', action: 'copy_formatted', icon: Clipboard },
            { label: 'Explain simpler', action: 'explain_simpler', icon: Sparkles },
            { label: 'Create checklist', action: 'create_checklist', icon: CheckSquare },
          ].map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.label}
                type="button"
                onClick={() => onAction(message, action.action as Parameters<ChatMessageProps['onAction']>[1])}
                disabled={Boolean(loadingAction)}
                aria-label={loadingAction === action.action
                  ? action.action === 'explain_simpler' ? 'Creating simpler explanation'
                    : action.action === 'create_checklist' ? 'Creating action checklist'
                      : action.label
                  : action.label}
                className="ce-action min-h-8 rounded-full px-3"
                data-testid={`button-action-${action.label.toLowerCase().replace(/\s+/g, '-')}`}
              >
                <Icon size={13} />
                {loadingAction === action.action ? 'Working…' : action.label}
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-2 px-1">
          <span className="text-[11px] text-muted-foreground">Feedback</span>
          {feedbackOptions.map((option) => {
            const Icon = option.icon;
            const active = selectedFeedback?.includes(option.value) ?? false;
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
                aria-pressed={active}
                aria-label={option.label}
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
