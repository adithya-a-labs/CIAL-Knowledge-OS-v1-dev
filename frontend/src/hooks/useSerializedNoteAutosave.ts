import { useCallback, useEffect, useRef, useState } from 'react';
import type { WorkspaceNote } from '@/data/workspace/workspaceTypes';
import { ApiError } from '@/api/types';

export type NoteSaveState = 'idle' | 'unsaved' | 'saving' | 'saved' | 'conflict' | 'error';

type SaveDraft = Pick<WorkspaceNote, 'id' | 'title' | 'content_json' | 'content_markdown' | 'is_pinned' | 'is_archived'>;
type SavePayload = Partial<WorkspaceNote> & { expected_revision: number; force?: boolean };

export interface NoteConflictState {
  local: SaveDraft;
  current: WorkspaceNote;
}

function fingerprint(value: SaveDraft) {
  return JSON.stringify([value.title, value.content_json, value.content_markdown, value.is_pinned, value.is_archived]);
}

function conflictFrom(error: unknown): WorkspaceNote | null {
  if (!(error instanceof ApiError) || error.status !== 409 || typeof error.detail !== 'object' || error.detail === null) return null;
  const envelope = error.detail as { detail?: unknown };
  const detail = (typeof envelope.detail === 'object' && envelope.detail !== null ? envelope.detail : error.detail) as { code?: unknown; current?: unknown };
  return detail.code === 'revision_conflict' && typeof detail.current === 'object' && detail.current !== null
    ? detail.current as WorkspaceNote
    : null;
}

export function useSerializedNoteAutosave({
  note,
  save,
  onServerUpdate,
  debounceMs = 750,
}: {
  note: WorkspaceNote | null;
  save: (id: string, payload: SavePayload) => Promise<WorkspaceNote>;
  onServerUpdate: (saved: WorkspaceNote, sent: SaveDraft, hasNewerDraft: boolean) => void;
  debounceMs?: number;
}) {
  const [state, setState] = useState<NoteSaveState>('idle');
  const [conflict, setConflict] = useState<NoteConflictState | null>(null);
  const generation = useRef(0);
  const noteId = useRef<string | null>(null);
  const revision = useRef(0);
  const lastSaved = useRef('');
  const pending = useRef<SaveDraft | null>(null);
  const inFlight = useRef(false);
  const blocked = useRef(false);
  const timer = useRef<number | null>(null);
  const deleted = useRef(new Set<string>());
  const runRef = useRef<(force?: boolean) => Promise<void>>(async () => undefined);

  const clearTimer = useCallback(() => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const schedule = useCallback((delay = debounceMs) => {
    clearTimer();
    timer.current = window.setTimeout(() => void runRef.current(), delay);
  }, [clearTimer, debounceMs]);

  runRef.current = async (force = false) => {
    clearTimer();
    const draft = pending.current;
    if (!draft || inFlight.current || blocked.current || deleted.current.has(draft.id) || draft.id !== noteId.current) return;
    pending.current = null;
    inFlight.current = true;
    setState('saving');
    const requestGeneration = generation.current;
    try {
      const saved = await save(draft.id, {
        expected_revision: revision.current,
        force,
        title: draft.title,
        content_json: draft.content_json,
        content_markdown: draft.content_markdown,
        content_format: 'editor_json',
        is_pinned: draft.is_pinned,
        is_archived: draft.is_archived,
      });
      if (requestGeneration !== generation.current || saved.id !== noteId.current || deleted.current.has(saved.id)) return;
      revision.current = saved.revision;
      lastSaved.current = fingerprint(draft);
      const hasNewerDraft = Boolean(pending.current && fingerprint(pending.current) !== lastSaved.current);
      onServerUpdate(saved, draft, hasNewerDraft);
      setConflict(null);
      setState(hasNewerDraft ? 'unsaved' : 'saved');
    } catch (error) {
      if (requestGeneration !== generation.current || draft.id !== noteId.current) return;
      const current = conflictFrom(error);
      if (current) {
        pending.current = pending.current ?? draft;
        blocked.current = true;
        setConflict({ local: pending.current, current });
        setState('conflict');
      } else {
        pending.current = pending.current ?? draft;
        blocked.current = true;
        setState('error');
      }
    } finally {
      if (requestGeneration === generation.current) {
        inFlight.current = false;
        if (!blocked.current && pending.current) void runRef.current();
      }
    }
  };

  useEffect(() => {
    generation.current += 1;
    clearTimer();
    pending.current = null;
    inFlight.current = false;
    blocked.current = false;
    setConflict(null);
    noteId.current = note?.id ?? null;
    revision.current = note?.revision ?? 0;
    lastSaved.current = note ? fingerprint(note) : '';
    setState(note ? 'saved' : 'idle');
  }, [clearTimer, note?.id]);

  useEffect(() => () => {
    generation.current += 1;
    clearTimer();
    pending.current = null;
  }, [clearTimer]);

  const enqueue = useCallback((draft: SaveDraft) => {
    if (draft.id !== noteId.current || deleted.current.has(draft.id) || blocked.current) return;
    if (fingerprint(draft) === lastSaved.current && !inFlight.current) {
      setState('saved');
      return;
    }
    pending.current = draft;
    setState('unsaved');
    if (!inFlight.current) schedule();
  }, [schedule]);

  const flush = useCallback(() => {
    if (!blocked.current) void runRef.current();
  }, []);

  const reviewServer = useCallback(() => {
    if (!conflict) return null;
    generation.current += 1;
    blocked.current = false;
    pending.current = null;
    revision.current = conflict.current.revision;
    lastSaved.current = fingerprint(conflict.current);
    setConflict(null);
    setState('saved');
    return conflict.current;
  }, [conflict]);

  const keepMine = useCallback(() => {
    if (!conflict) return;
    revision.current = conflict.current.revision;
    pending.current = conflict.local;
    blocked.current = false;
    setConflict(null);
    void runRef.current(true);
  }, [conflict]);

  const retry = useCallback(() => {
    blocked.current = false;
    setState('unsaved');
    void runRef.current();
  }, []);

  const markDeleted = useCallback((id: string) => {
    deleted.current.add(id);
    if (noteId.current === id) {
      generation.current += 1;
      clearTimer();
      pending.current = null;
      blocked.current = true;
      setState('idle');
    }
  }, [clearTimer]);

  return { state, conflict, enqueue, flush, reviewServer, keepMine, retry, markDeleted };
}
