import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  clearAuthTokens,
  fetchCurrentUser,
  getStoredAccessToken,
  getStoredUserId,
  loginUser,
  logoutUser,
  refreshSession,
  registerUser,
  setAuthTokens,
} from "../api/httpClient";

interface AuthorizationContextValue {
  userId: string | null;
  isAuthenticated: boolean;
  isBootstrapping: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  bootstrap: () => Promise<void>;
}

export const AuthorizationContext = createContext<AuthorizationContextValue | undefined>(undefined);

interface AuthorizationProviderProps {
  children: ReactNode;
}

export function AuthorizationProvider({ children }: AuthorizationProviderProps) {
  const [userId, setUserId] = useState<string | null>(() => getStoredUserId());
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  const bootstrap = useCallback(async () => {
    setIsBootstrapping(true);
    const accessToken = getStoredAccessToken();
    const storedUserId = getStoredUserId();
    if (!accessToken || !storedUserId) {
      clearAuthTokens();
      setUserId(null);
      setIsBootstrapping(false);
      return;
    }

    try {
      const profile = await fetchCurrentUser();
      setUserId(profile.user_id);
    } catch {
      try {
        const refreshed = await refreshSession();
        setAuthTokens(refreshed);
        setUserId(refreshed.user_id);
      } catch {
        clearAuthTokens();
        setUserId(null);
      }
    } finally {
      setIsBootstrapping(false);
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await loginUser(email, password);
    setAuthTokens(tokens);
    setUserId(tokens.user_id);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const tokens = await registerUser(email, password);
    setAuthTokens(tokens);
    setUserId(tokens.user_id);
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutUser();
    } finally {
      clearAuthTokens();
      setUserId(null);
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const value = useMemo(
    () => ({
      userId,
      isAuthenticated: Boolean(userId),
      isBootstrapping,
      login,
      register,
      logout,
      bootstrap,
    }),
    [bootstrap, isBootstrapping, login, logout, register, userId],
  );

  return <AuthorizationContext.Provider value={value}>{children}</AuthorizationContext.Provider>;
}
