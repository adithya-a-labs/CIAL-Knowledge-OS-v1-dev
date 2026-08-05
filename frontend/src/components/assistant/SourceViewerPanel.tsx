import { useEffect, useRef, useState } from 'react';
import DocumentViewerPanel from './DocumentViewerPanel';
import type { ChatSource } from '@/types/assistant';
import { useReversiblePresence } from './useReversiblePresence';

interface SourceViewerPanelProps {
  open: boolean;
  source: ChatSource | null;
  sources: ChatSource[];
  onClose: () => void;
  onSelectSource: (source: ChatSource) => void;
}

export default function SourceViewerPanel({
  open,
  source,
  sources,
  onClose,
  onSelectSource,
}: SourceViewerPanelProps) {
  const [isDesktopViewport, setIsDesktopViewport] = useState(() => window.innerWidth >= 1024);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const mobilePanelRef = useRef<HTMLDivElement>(null);
  const presence = useReversiblePresence(open);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(min-width: 1024px)');
    const onChange = () => setIsDesktopViewport(mediaQuery.matches);
    onChange();
    mediaQuery.addEventListener('change', onChange);
    return () => mediaQuery.removeEventListener('change', onChange);
  }, []);

  useEffect(() => {
    if (!open) {
      const target = previouslyFocused.current;
      previouslyFocused.current = null;
      if (target?.isConnected) window.setTimeout(() => target.focus(), 0);
      return;
    }

    previouslyFocused.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose, open]);

  useEffect(() => {
    if (!open || isDesktopViewport) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const frame = window.requestAnimationFrame(() => {
      mobilePanelRef.current?.querySelector<HTMLElement>('[aria-label="Close source drawer"]')?.focus();
    });
    return () => {
      window.cancelAnimationFrame(frame);
      document.body.style.overflow = previousOverflow;
    };
  }, [isDesktopViewport, open]);

  if (!presence.mounted) return null;

  if (isDesktopViewport) {
    return (
      <aside
        className={`h-full min-h-0 w-full overflow-hidden bg-card transition-opacity duration-[var(--motion-duration-standard)] ease-[var(--motion-ease-enter)] ${presence.visible ? 'opacity-100' : 'pointer-events-none opacity-0'}`}
        aria-hidden={!presence.visible}
        inert={!presence.visible}
        data-testid="source-viewer-panel"
      >
        <DocumentViewerPanel source={source} sources={sources} onClose={onClose} onSelectSource={onSelectSource} />
      </aside>
    );
  }

  return (
    <div
      className={`fixed inset-0 z-50 ${presence.visible ? '' : 'pointer-events-none'}`}
      role="dialog"
      aria-modal="true"
      aria-label="Source viewer"
      aria-hidden={!presence.visible}
      data-testid="source-viewer-mobile"
    >
      <button
        className={`absolute inset-0 bg-black/45 transition-opacity duration-[var(--motion-duration-standard)] ease-[var(--motion-ease-enter)] ${presence.visible ? 'opacity-100' : 'opacity-0'}`}
        onClick={onClose}
        aria-label="Close source viewer overlay"
        tabIndex={presence.visible ? 0 : -1}
      />
      <div
        ref={mobilePanelRef}
        className={`relative ml-auto flex h-full w-full max-w-[32rem] flex-col border-l border-border bg-card shadow-2xl transition-[opacity,transform] duration-[var(--motion-duration-panel)] ease-[var(--motion-ease-drawer)] ${presence.visible ? 'translate-x-0 opacity-100' : 'translate-x-6 opacity-0'} ${presence.reducedMotion ? '!translate-x-0' : ''}`}
        inert={!presence.visible}
      >
        <DocumentViewerPanel source={source} sources={sources} onClose={onClose} onSelectSource={onSelectSource} />
      </div>
    </div>
  );
}
