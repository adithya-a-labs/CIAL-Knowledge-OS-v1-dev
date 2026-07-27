import { useMemo } from 'react';
import { highlightHtml, zoomStyle } from './highlight-utils';

interface SlideRecord {
  index: string;
  title: string;
  body: string;
}

interface PptxViewerProps {
  slides: SlideRecord[];
  activePage: number;
  searchQuery: string;
  zoomLevel: number;
  onSelectPage: (value: number) => void;
}

export default function PptxViewer({
  slides,
  activePage,
  searchQuery,
  zoomLevel,
  onSelectPage,
}: PptxViewerProps) {
  const activeSlideIndex = Math.max(0, Math.min(activePage - 1, slides.length - 1));
  const activeSlide = slides[activeSlideIndex];
  const bodyHtml = useMemo(
    () => highlightHtml(activeSlide?.body || 'No speaker notes or body text available for this slide.', searchQuery),
    [activeSlide?.body, searchQuery],
  );

  return (
    <div className="grid h-full min-h-0 gap-4 lg:grid-cols-[9rem_minmax(0,1fr)]">
      <div className="scrollbar-soft flex gap-2 overflow-auto lg:flex-col">
        {slides.map((slide, index) => (
          <button
            key={`${slide.index}-${slide.title}`}
            type="button"
            onClick={() => onSelectPage(index + 1)}
            className={`min-w-[7rem] rounded-2xl border p-3 text-left ${index === activeSlideIndex ? 'border-primary bg-accent' : 'border-border bg-card'}`}
          >
            <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Slide {slide.index}</p>
            <p className="mt-2 line-clamp-2 text-sm font-semibold text-foreground">{slide.title}</p>
          </button>
        ))}
      </div>
      <div className="scrollbar-soft overflow-auto rounded-[1.5rem] border border-border bg-card p-5">
        <div style={zoomStyle(zoomLevel)} className="space-y-4">
          <div className="document-paper rounded-[1.25rem] border border-border p-6 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">Slide {activeSlide.index}</p>
            <h3 className="mt-3 text-2xl font-semibold text-foreground">{activeSlide.title}</h3>
            <div
              className="safe-text mt-5 whitespace-pre-wrap text-sm leading-7 text-foreground"
              dangerouslySetInnerHTML={{ __html: bodyHtml }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
