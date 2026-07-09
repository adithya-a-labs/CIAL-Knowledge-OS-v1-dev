import { useEffect, useMemo, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { buildHighlightNeedles, clearTextMarks } from './highlight-utils';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

interface PdfViewerProps {
  fileUrl: string;
  title: string;
  activePage: number;
  requestedPage: number;
  searchQuery: string;
  highlightText: string;
  zoomLevel: number;
  onPageCountChange: (value: number) => void;
  onVisiblePageChange: (value: number) => void;
}

function normalize(value: string) {
  return value.toLowerCase().replace(/\s+/g, ' ').trim();
}

function pageWidth(containerWidth: number, zoomLevel: number) {
  const baseWidth = Math.max(containerWidth - 48, 320);
  return Math.round(baseWidth * zoomLevel);
}

export default function PdfViewer({
  fileUrl,
  title,
  activePage,
  requestedPage,
  searchQuery,
  highlightText,
  zoomLevel,
  onPageCountChange,
  onVisiblePageChange,
}: PdfViewerProps) {
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const pagesRef = useRef(new Map<number, HTMLDivElement>());
  const [numPages, setNumPages] = useState<number>(0);
  const [containerWidth, setContainerWidth] = useState(860);
  const [highlightResolved, setHighlightResolved] = useState<boolean | null>(null);
  const needles = useMemo(() => buildHighlightNeedles(searchQuery, highlightText), [searchQuery, highlightText]);

  useEffect(() => {
    setNumPages(0);
    setHighlightResolved(null);
    pagesRef.current.clear();
  }, [fileUrl]);

  useEffect(() => {
    if (!viewportRef.current) return undefined;
    const observer = new ResizeObserver((entries) => {
      const nextWidth = entries[0]?.contentRect.width;
      if (nextWidth) setContainerWidth(nextWidth);
    });
    observer.observe(viewportRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!viewportRef.current) return undefined;
    const shells = Array.from(pagesRef.current.entries());
    if (shells.length === 0) return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
        if (!visible) return;
        const page = Number((visible.target as HTMLElement).dataset.pageNumber);
        if (Number.isFinite(page) && page > 0) {
          onVisiblePageChange(page);
        }
      },
      {
        root: viewportRef.current,
        threshold: [0.2, 0.5, 0.8],
      },
    );

    shells.forEach(([, element]) => observer.observe(element));
    return () => observer.disconnect();
  }, [numPages, onVisiblePageChange]);

  useEffect(() => {
    const target = pagesRef.current.get(requestedPage);
    if (!target) return;
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [numPages, requestedPage]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    clearTextMarks(viewport);
    if (needles.length === 0) {
      setHighlightResolved(null);
      return;
    }

    const spans = Array.from(viewport.querySelectorAll('.react-pdf__Page__textContent span'));
    let firstHighlightNode: HTMLElement | null = null;
    let matched = false;
    const activePageElement = pagesRef.current.get(activePage);

    spans.forEach((node) => {
      if (!(node instanceof HTMLElement)) return;
      const text = normalize(node.textContent || '');
      if (!text) return;
      const matchingNeedle = needles.find((needle) => text.includes(needle) || needle.includes(text));
      if (!matchingNeedle) return;

      const onActivePage = activePageElement?.contains(node) ?? false;
      if (searchQuery.trim()) {
        node.dataset.pdfSearch = 'true';
        node.classList.add('bg-[#f9e6a5]', 'rounded', 'transition-colors', 'duration-700');
      }
      if (highlightText.trim() && onActivePage) {
        node.dataset.pdfHighlight = 'true';
        node.classList.add('bg-[#f7df79]', 'rounded', 'transition-colors', 'duration-700');
        matched = true;
        if (!firstHighlightNode) firstHighlightNode = node;
      }
    });

    const highlightTarget: HTMLElement | null = firstHighlightNode;
    if (highlightTarget) {
      (highlightTarget as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    }
    setHighlightResolved(highlightText.trim() ? matched : null);
  }, [activePage, highlightText, needles, numPages, searchQuery]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-[1.5rem] border border-border bg-[linear-gradient(180deg,#f8fafc_0%,#f3f6f8_100%)]">
      {highlightResolved === false ? (
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900">
          Jumped to the cited page. Exact text location was not detected, so the synced excerpt remains below.
        </div>
      ) : null}
      <div ref={viewportRef} className="scrollbar-soft min-h-0 flex-1 overflow-auto p-4">
        <Document
          file={fileUrl}
          loading={<div className="rounded-2xl border border-border bg-white p-4 text-sm text-muted-foreground">Loading PDF...</div>}
          error={<div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">The PDF could not be rendered.</div>}
          onLoadSuccess={({ numPages: totalPages }) => {
            setNumPages(totalPages);
            onPageCountChange(totalPages);
          }}
          onLoadError={() => {
            setNumPages(0);
            setHighlightResolved(null);
          }}
        >
          <div className="space-y-4">
            {Array.from({ length: numPages || 1 }, (_, index) => {
              const pageNumber = index + 1;
              return (
                <div
                  key={pageNumber}
                  ref={(node) => {
                    if (node) {
                      pagesRef.current.set(pageNumber, node);
                    } else {
                      pagesRef.current.delete(pageNumber);
                    }
                  }}
                  data-page-number={pageNumber}
                  className={`pdf-page-shell rounded-[1.35rem] border bg-white p-3 shadow-sm ${pageNumber === activePage ? 'border-primary/50 shadow-[0_0_0_4px_rgba(74,124,63,0.08)]' : 'border-border'}`}
                >
                  <div className="mb-2 flex items-center justify-between px-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                    <span>{title}</span>
                    <span>Page {pageNumber}</span>
                  </div>
                  <Page
                    pageNumber={pageNumber}
                    width={pageWidth(containerWidth, zoomLevel)}
                    renderAnnotationLayer
                    renderTextLayer
                  />
                </div>
              );
            })}
          </div>
        </Document>
      </div>
    </div>
  );
}
