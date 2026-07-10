import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import type { AuthenticatedUser, LoginRequest, SignupRequest } from '@/api/types';
import { AUTH_INVALIDATED_EVENT, getCurrentUser, logIn, logOut, signUp } from '@/api/client';
import type { Role, User } from '@/types';
import {
  aiNoticeAcknowledgementKey,
  clearSessionEntryUserId,
  clearUserWorkspaceState,
  consumeWelcomePending,
  markWelcomePending,
  readSessionEntryUserId,
  writeSessionEntryUserId,
} from './storage';

type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthContextValue {
  status: AuthStatus;
  user: AuthenticatedUser | null;
  userView: User | null;
  isAuthenticated: boolean;
  login: (payload: LoginRequest) => Promise<AuthenticatedUser>;
  signup: (payload: SignupRequest) => Promise<AuthenticatedUser>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
  showWelcome: boolean;
  dismissWelcome: () => void;
  aiNoticeAcknowledged: boolean;
  acknowledgeAiNotice: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function deriveRole(user: AuthenticatedUser): Role {
  const permissions = new Set(user.permission_names);
  const roleNames = user.role_names.map((role) => role.toLowerCase());
  if (
    permissions.has('manage_settings') ||
    permissions.has('manage_users') ||
    permissions.has('manage_roles') ||
    roleNames.some((role) => role.includes('admin'))
  ) {
    return 'admin';
  }
  if (
    permissions.has('upload_enterprise_documents') ||
    permissions.has('manage_enterprise_documents')
  ) {
    return 'engineer';
  }
  return 'viewer';
}

function toUserView(user: AuthenticatedUser): User {
  return {
    name: user.display_name,
    role: deriveRole(user),
    department: user.department_name || user.organization_name || 'CIAL',
    avatar: null,
    initials: user.initials,
    notificationsCount: user.notifications_count,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [showWelcome, setShowWelcome] = useState(false);
  const [aiNoticeAcknowledged, setAiNoticeAcknowledged] = useState(false);

  const loadSession = useCallback(async () => {
    setStatus((current) => (current === 'authenticated' ? current : 'loading'));
    try {
      const response = await getCurrentUser();
      setUser(response.user);
      setStatus('authenticated');
    } catch {
      setUser(null);
      setStatus('unauthenticated');
      clearSessionEntryUserId();
    }
  }, []);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  useEffect(() => {
    const handleInvalidation = () => {
      setUser(null);
      setStatus('unauthenticated');
      setShowWelcome(false);
      clearSessionEntryUserId();
    };
    window.addEventListener(AUTH_INVALIDATED_EVENT, handleInvalidation);
    return () => window.removeEventListener(AUTH_INVALIDATED_EVENT, handleInvalidation);
  }, []);

  useEffect(() => {
    if (status !== 'authenticated' || !user) {
      setShowWelcome(false);
      setAiNoticeAcknowledged(false);
      return;
    }
    const acknowledged = window.localStorage.getItem(aiNoticeAcknowledgementKey(user.id)) === '1';
    setAiNoticeAcknowledged(acknowledged);
    const shouldShowWelcome = consumeWelcomePending() || readSessionEntryUserId() !== user.id;
    writeSessionEntryUserId(user.id);
    setShowWelcome(shouldShowWelcome);
  }, [status, user]);

  const finalizeAuthentication = useCallback((nextUser: AuthenticatedUser) => {
    markWelcomePending();
    setUser(nextUser);
    setStatus('authenticated');
  }, []);

  const login = useCallback(async (payload: LoginRequest) => {
    const response = await logIn(payload);
    finalizeAuthentication(response.user);
    return response.user;
  }, [finalizeAuthentication]);

  const signup = useCallback(async (payload: SignupRequest) => {
    const response = await signUp(payload);
    finalizeAuthentication(response.user);
    return response.user;
  }, [finalizeAuthentication]);

  const logout = useCallback(async () => {
    try {
      await logOut();
    } finally {
      clearUserWorkspaceState();
      setUser(null);
      setStatus('unauthenticated');
      setShowWelcome(false);
    }
  }, []);

  const dismissWelcome = useCallback(() => {
    setShowWelcome(false);
  }, []);

  const acknowledgeAiNotice = useCallback(() => {
    if (!user) return;
    window.localStorage.setItem(aiNoticeAcknowledgementKey(user.id), '1');
    setAiNoticeAcknowledged(true);
  }, [user]);

  const userView = useMemo(() => (user ? toUserView(user) : null), [user]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      userView,
      isAuthenticated: status === 'authenticated' && user !== null,
      login,
      signup,
      logout,
      refreshSession: loadSession,
      showWelcome,
      dismissWelcome,
      aiNoticeAcknowledged,
      acknowledgeAiNotice,
    }),
    [
      acknowledgeAiNotice,
      aiNoticeAcknowledged,
      dismissWelcome,
      loadSession,
      login,
      logout,
      showWelcome,
      signup,
      status,
      user,
      userView,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider.');
  }
  return context;
}
