import { useMemo, useState } from 'react';
import {
  Bot,
  ChevronRight,
  Clock3,
  HelpCircle,
  Search,
  Sparkles,
  ThumbsUp,
  X,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  buildMockAnswer,
  popularQuestions,
  quickAnswerCategories,
  recentlyAsked,
  suggestionChips,
  type QuickAnswerQuestion,
} from '@/data/quickAnswersData';

function CategoryBadge({ category }: { category: string }) {
  const badgeClass = useMemo(() => {
    if (category.includes('Safety')) return 'bg-destructive/10 text-destructive';
    if (category.includes('IT')) return 'bg-info/10 text-info-foreground';
    if (category.includes('Airfield')) return 'bg-accent text-primary';
    if (category.includes('People')) return 'bg-success/10 text-success-foreground';
    if (category.includes('HVAC')) return 'bg-cyan-50 text-cyan-700';
    if (category.includes('Baggage')) return 'bg-emerald-50 text-emerald-700';
    return 'bg-muted text-foreground';
  }, [category]);

  return <span className={cn('rounded-full px-2.5 py-1 text-[11px] font-semibold', badgeClass)}>{category}</span>;
}

function SectionHeader({
  icon,
  title,
  subtitle,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  subtitle: string;
  action: string;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="text-base font-semibold text-foreground">{title}</h2>
        </div>
        <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>
      </div>
      <button type="button" className="mt-1 hidden flex-shrink-0 text-xs font-semibold text-primary transition-colors hover:text-[#2f5626] sm:inline-flex">
        {action}
      </button>
    </div>
  );
}

function AskResultPanel({
  answer,
  onOpen,
  onDismiss,
}: {
  answer: QuickAnswerQuestion;
  onOpen: (answer: QuickAnswerQuestion) => void;
  onDismiss: () => void;
}) {
  return (
    <div className="rounded-xl border border-border bg-muted p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-card text-primary shadow-sm">
              <Sparkles size={16} />
            </span>
            <div>
              <p className="text-sm font-semibold text-foreground">{answer.question}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">Mock instant answer</p>
            </div>
          </div>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-foreground">{answer.preview}</p>
        </div>
        <button type="button" onClick={onDismiss} className="ce-icon-button h-8 min-h-8 min-w-8" aria-label="Dismiss answer">
          <X size={16} />
        </button>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => onOpen(answer)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-[#3d6834]"
        >
          View full answer
          <ChevronRight size={14} />
        </button>
        <button type="button" className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs font-semibold text-primary hover:bg-card/80">
          <Bot size={14} />
          Ask AI Assistant
        </button>
      </div>
    </div>
  );
}

function PopularQuestionCard({
  item,
  onOpen,
}: {
  item: QuickAnswerQuestion;
  onOpen: (item: QuickAnswerQuestion) => void;
}) {
  const Icon = item.icon;

  return (
    <article className="flex min-h-64 min-w-[17rem] flex-1 flex-col rounded-xl border border-border bg-card p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:border-border hover:shadow-md lg:min-w-0">
      <div className="mb-4 flex items-start gap-3">
        <span className={cn('inline-flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl', item.iconClassName)}>
          <Icon size={24} />
        </span>
        <h3 className="min-w-0 text-sm font-semibold leading-5 text-foreground">{item.question}</h3>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <CategoryBadge category={item.category} />
        <span className="text-xs text-muted-foreground">{item.helpful}</span>
      </div>

      <p className="line-clamp-4 flex-1 text-sm leading-6 text-foreground">{item.preview}</p>

      <button
        type="button"
        onClick={() => onOpen(item)}
        className="mt-4 inline-flex items-center gap-1.5 self-start text-sm font-semibold text-primary transition-colors hover:text-[#2f5626]"
      >
        View Answer
        <ChevronRight size={14} />
      </button>
    </article>
  );
}

function CategoryCard({ category }: { category: (typeof quickAnswerCategories)[number] }) {
  const Icon = category.icon;

  return (
    <button
      type="button"
      className="flex min-h-20 items-center gap-3 rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-border hover:bg-muted hover:shadow-md"
    >
      <span className={cn('inline-flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl', category.iconClassName)}>
        <Icon size={22} />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold text-foreground">{category.name}</span>
        <span className="mt-1 block text-sm text-muted-foreground">{category.count} questions</span>
      </span>
    </button>
  );
}

function RecentlyAskedRow({ item }: { item: (typeof recentlyAsked)[number] }) {
  return (
    <button type="button" className="flex w-full items-center gap-3 border-b border-border px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-muted">
      <Clock3 size={18} className="flex-shrink-0 text-muted-foreground" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-foreground">{item.question}</span>
      </span>
      <span className="hidden flex-shrink-0 sm:block">
        <CategoryBadge category={item.category} />
      </span>
      <span className="hidden w-20 flex-shrink-0 text-xs text-muted-foreground sm:block">{item.timestamp}</span>
      <ChevronRight size={16} className="flex-shrink-0 text-muted-foreground" />
    </button>
  );
}

function AnswerModal({
  answer,
  onClose,
}: {
  answer: QuickAnswerQuestion | null;
  onClose: () => void;
}) {
  if (!answer) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-overlay p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="quick-answer-title">
      <div className="w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-card shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-border p-5">
          <div className="min-w-0">
            <div className="mb-2">
              <CategoryBadge category={answer.category} />
            </div>
            <h2 id="quick-answer-title" className="text-lg font-semibold leading-6 text-foreground">
              {answer.question}
            </h2>
          </div>
          <button type="button" onClick={onClose} className="ce-icon-button" aria-label="Close answer">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-5 p-5">
          <div>
            <h3 className="text-sm font-semibold text-foreground">Answer</h3>
            <p className="mt-2 text-sm leading-6 text-foreground">{answer.fullAnswer}</p>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-foreground">Related sources</h3>
            <div className="mt-2 space-y-2">
              {answer.sources.map((source) => (
                <div key={source} className="flex items-center gap-2 rounded-lg border border-border bg-muted px-3 py-2 text-sm text-foreground">
                  <HelpCircle size={15} className="text-primary" />
                  {source}
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-2 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
            <button type="button" className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm font-semibold text-primary transition-colors hover:bg-muted">
              <Bot size={16} />
              Ask AI Assistant
            </button>
            <button type="button" className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#3d6834]">
              <ThumbsUp size={16} />
              Mark helpful
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function FAQsPage() {
  const [question, setQuestion] = useState('');
  const [mockAnswer, setMockAnswer] = useState<QuickAnswerQuestion | null>(null);
  const [activeAnswer, setActiveAnswer] = useState<QuickAnswerQuestion | null>(null);

  const handleAsk = () => {
    const answer = buildMockAnswer(question);
    setMockAnswer(answer);
  };

  return (
    <div className="fluid-section space-y-7" data-testid="quick-answers-page">
      <header>
        <h1 className="text-2xl font-semibold tracking-normal text-foreground">Quick Answers</h1>
        <p className="mt-1 text-sm text-muted-foreground">Get instant answers to common questions. Powered by CIAL AI and trusted enterprise knowledge.</p>
      </header>

      <section className="space-y-4">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div className="flex min-h-16 items-center gap-3 rounded-xl border border-border bg-card p-2 shadow-sm transition-colors focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/15">
            <Search size={22} className="ml-3 flex-shrink-0 text-muted-foreground" />
            <label className="min-w-0 flex-1">
              <span className="sr-only">Ask a question</span>
              <input
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') handleAsk();
                }}
                placeholder="Ask a question..."
                className="h-11 w-full bg-transparent text-sm font-medium text-foreground placeholder:text-muted-foreground"
              />
            </label>
            <button
              type="button"
              onClick={handleAsk}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-accent px-5 text-sm font-semibold text-primary transition-colors hover:bg-accent"
            >
              <Sparkles size={16} />
              Ask
            </button>
          </div>

          <button
            type="button"
            className="inline-flex min-h-16 items-center justify-center gap-3 rounded-xl border border-primary/30 bg-card px-6 text-sm font-semibold text-primary shadow-sm transition-colors hover:bg-muted"
          >
            <Bot size={18} />
            Ask AI Assistant
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 text-sm font-semibold text-foreground">Try asking:</span>
          {suggestionChips.map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => setQuestion(chip)}
              className="rounded-full border border-border bg-card px-4 py-2 text-xs font-medium text-foreground shadow-sm transition-colors hover:border-primary/30 hover:bg-muted hover:text-primary"
            >
              {chip}
            </button>
          ))}
        </div>

        {mockAnswer && <AskResultPanel answer={mockAnswer} onOpen={setActiveAnswer} onDismiss={() => setMockAnswer(null)} />}
      </section>

      <section>
        <SectionHeader icon={<Zap size={18} className="text-foreground" />} title="Popular Questions" subtitle="Frequently asked by your colleagues" action="View all FAQs ->" />
        <div className="scrollbar-soft flex gap-3 overflow-x-auto pb-1 xl:grid xl:grid-cols-5 xl:overflow-visible">
          {popularQuestions.map((item) => (
            <PopularQuestionCard key={item.id} item={item} onOpen={setActiveAnswer} />
          ))}
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(24rem,0.95fr)]">
        <div>
          <SectionHeader title="Browse by Category" subtitle="Find answers by topic" action="View all categories ->" />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {quickAnswerCategories.map((category) => (
              <CategoryCard key={category.id} category={category} />
            ))}
          </div>
        </div>

        <div className="xl:border-l xl:border-border xl:pl-6">
          <SectionHeader title="Recently Asked" subtitle="Your recent questions" action="View all history ->" />
          <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
            {recentlyAsked.map((item) => (
              <RecentlyAskedRow key={item.id} item={item} />
            ))}
          </div>
        </div>
      </section>

      <AnswerModal answer={activeAnswer} onClose={() => setActiveAnswer(null)} />
    </div>
  );
}
