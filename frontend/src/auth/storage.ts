export const AUTH_REDIRECT_STORAGE_KEY = 'cial-auth-redirect';
export const AUTH_WELCOME_PENDING_STORAGE_KEY = 'cial-auth-welcome-pending';
export const AUTH_SESSION_ENTRY_STORAGE_KEY = 'cial-auth-session-entry';

const AI_NOTICE_ACK_STORAGE_PREFIX = 'cial-ai-notice-ack';

const USER_SCOPED_STORAGE_KEYS = [
  'cial-assistant-history-sidebar-open',
  'cial-assistant-selected-context',
  'cial-assistant-context-intent',
  'cial-assistant-source-panel-size',
  'cial-assistant-sessions',
  'cial-assistant-active-session',
  'cial-new-conversation-pending',
];

export function setPostAuthRedirect(path: string) {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(AUTH_REDIRECT_STORAGE_KEY, path);
}

export function consumePostAuthRedirect() {
  if (typeof window === 'undefined') return '/';
  const path = window.sessionStorage.getItem(AUTH_REDIRECT_STORAGE_KEY) || '/';
  window.sessionStorage.removeItem(AUTH_REDIRECT_STORAGE_KEY);
  return path;
}

export function markWelcomePending() {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(AUTH_WELCOME_PENDING_STORAGE_KEY, '1');
}

export function consumeWelcomePending() {
  if (typeof window === 'undefined') return false;
  const pending = window.sessionStorage.getItem(AUTH_WELCOME_PENDING_STORAGE_KEY) === '1';
  window.sessionStorage.removeItem(AUTH_WELCOME_PENDING_STORAGE_KEY);
  return pending;
}

export function readSessionEntryUserId() {
  if (typeof window === 'undefined') return null;
  return window.sessionStorage.getItem(AUTH_SESSION_ENTRY_STORAGE_KEY);
}

export function writeSessionEntryUserId(userId: string) {
  if (typeof window === 'undefined') return;
  void userId;
  window.sessionStorage.setItem(AUTH_SESSION_ENTRY_STORAGE_KEY, '1');
}

export function clearSessionEntryUserId() {
  if (typeof window === 'undefined') return;
  window.sessionStorage.removeItem(AUTH_SESSION_ENTRY_STORAGE_KEY);
}

export function aiNoticeAcknowledgementKey(userId: string) {
  void userId;
  return AI_NOTICE_ACK_STORAGE_PREFIX;
}

export function clearUserWorkspaceState() {
  if (typeof window === 'undefined') return;
  USER_SCOPED_STORAGE_KEYS.forEach((key) => window.localStorage.removeItem(key));
  window.sessionStorage.removeItem(AUTH_REDIRECT_STORAGE_KEY);
  window.sessionStorage.removeItem(AUTH_WELCOME_PENDING_STORAGE_KEY);
  window.sessionStorage.removeItem(AUTH_SESSION_ENTRY_STORAGE_KEY);
}
