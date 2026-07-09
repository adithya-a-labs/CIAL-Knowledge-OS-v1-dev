export const ASSISTANT_HISTORY_SIDEBAR_STORAGE_KEY = 'cial-assistant-history-sidebar-open';
export const ASSISTANT_HISTORY_SIDEBAR_VISIBILITY_EVENT = 'cial-assistant-history-sidebar-visibility-change';
export const ASSISTANT_HISTORY_SIDEBAR_OPEN_EVENT = 'cial-assistant-history-sidebar-open-request';

const DEFAULT_DESKTOP_MIN_WIDTH = 1440;

export function readAssistantHistorySidebarOpen() {
  if (typeof window === 'undefined') return true;

  const storedValue = window.localStorage.getItem(ASSISTANT_HISTORY_SIDEBAR_STORAGE_KEY);
  if (storedValue === 'true') return true;
  if (storedValue === 'false') return false;

  return window.innerWidth >= DEFAULT_DESKTOP_MIN_WIDTH;
}

export function writeAssistantHistorySidebarOpen(open: boolean) {
  if (typeof window === 'undefined') return;

  window.localStorage.setItem(ASSISTANT_HISTORY_SIDEBAR_STORAGE_KEY, String(open));
  window.dispatchEvent(
    new CustomEvent(ASSISTANT_HISTORY_SIDEBAR_VISIBILITY_EVENT, {
      detail: { open },
    }),
  );
}

export function requestAssistantHistorySidebarOpen() {
  if (typeof window === 'undefined') return;

  window.dispatchEvent(new Event(ASSISTANT_HISTORY_SIDEBAR_OPEN_EVENT));
}
