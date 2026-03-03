import { createContext, useCallback, useEffect, useMemo, useState, type PropsWithChildren } from 'react';
import { getCurrentUser, login as loginRequest, register as registerRequest } from '@/api/auth';
import type { RegisterPayload, RegisterResponse, User } from '@/types';
import {
  clearStoredToken,
  getStoredToken,
  isTokenExpired,
  setStoredToken,
  setStoredRole,
  setStoredUserId,
} from '@/utils/token';

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isInitializing: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<RegisterResponse>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const AUTH_BOOTSTRAP_TIMEOUT_MS = 8_000;

function getCurrentUserWithTimeout(timeoutMs: number): Promise<User> {
  return new Promise((resolve, reject) => {
    const timeoutHandle = window.setTimeout(() => {
      reject(new Error('Auth bootstrap timed out.'));
    }, timeoutMs);

    getCurrentUser()
      .then((currentUser) => {
        window.clearTimeout(timeoutHandle);
        resolve(currentUser);
      })
      .catch((error) => {
        window.clearTimeout(timeoutHandle);
        reject(error);
      });
  });
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [isInitializing, setIsInitializing] = useState(true);

  const logout = useCallback(() => {
    clearStoredToken();
    setToken(null);
    setUser(null);
  }, []);

  const bootstrapAuth = useCallback(async () => {
    const existingToken = getStoredToken();
    if (!existingToken || isTokenExpired(existingToken)) {
      logout();
      setIsInitializing(false);
      return;
    }

    setToken(existingToken);
    try {
      const currentUser = await getCurrentUserWithTimeout(AUTH_BOOTSTRAP_TIMEOUT_MS);
      setUser(currentUser);
    } catch {
      logout();
    } finally {
      setIsInitializing(false);
    }
  }, [logout]);

  useEffect(() => {
    void bootstrapAuth();
  }, [bootstrapAuth]);

  useEffect(() => {
    const handleUnauthorized = () => logout();
    window.addEventListener('trustseal:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('trustseal:unauthorized', handleUnauthorized);
  }, [logout]);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await loginRequest(email, password);
      setStoredToken(response.access_token);
      if (response.role) setStoredRole(response.role);
      if (response.user_id) setStoredUserId(response.user_id);
      setToken(response.access_token);

      try {
        const currentUser = await getCurrentUser();
        setUser(currentUser);
      } catch (error) {
        logout();
        throw error;
      }
    },
    [logout],
  );

  const register = useCallback((payload: RegisterPayload) => registerRequest(payload), []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isInitializing,
      isAuthenticated: Boolean(token && user),
      login,
      register,
      logout,
    }),
    [user, token, isInitializing, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default AuthContext;
