import { useEffect, useMemo, useRef } from 'react';
import { highlightHtml, zoomStyle } from './highlight-utils';

interface SpreadsheetViewerProps {
  rows: string[][];
  sheetNames?: string[];
  activeSheet?: string | null;
  searchQuery: string;
  zoomLevel: number;
}

export default function SpreadsheetViewer({
  rows,
  sheetNames,
  activeSheet,
  searchQuery,
  zoomLevel,
}: SpreadsheetViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const table = useMemo(
    () => rows.map((row) => row.map((cell) => highlightHtml(cell, searchQuery))),
    [rows, searchQuery],
  );

  useEffect(() => {
    const firstHit = containerRef.current?.querySelector('[data-search-hit="true"]');
    if (firstHit instanceof HTMLElement) {
      firstHit.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
    }
  }, [table]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-[1.5rem] border border-border bg-white">
      {sheetNames?.length ? (
        <div className="flex flex-wrap gap-2 border-b border-border px-4 py-3">
          {sheetNames.map((sheet) => (
            <span
              key={sheet}
              className={`rounded-full px-2.5 py-1 text-xs font-semibold ${sheet === activeSheet ? 'bg-[hsl(95_24%_94%)] text-primary' : 'bg-[hsl(210_20%_98%)] text-muted-foreground'}`}
            >
              {sheet}
            </span>
          ))}
        </div>
      ) : null}
      <div ref={containerRef} className="scrollbar-soft min-h-0 flex-1 overflow-auto">
        <div style={zoomStyle(zoomLevel)}>
          <table className="min-w-full text-left text-xs">
            <tbody>
              {table.map((row, rowIndex) => (
                <tr
                  key={rowIndex}
                  className={rowIndex === 0 ? 'sticky top-0 bg-[hsl(210_20%_98%)] font-semibold text-slate-900' : 'border-t border-border text-slate-700'}
                >
                  {row.map((cell, cellIndex) => (
                    <td
                      key={`${rowIndex}-${cellIndex}`}
                      className="max-w-48 px-3 py-2 align-top"
                      dangerouslySetInnerHTML={{ __html: cell }}
                    />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
