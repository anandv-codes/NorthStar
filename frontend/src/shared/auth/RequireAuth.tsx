import type { ReactNode } from "react";
import { useAuthorization } from "./useAuthorization";

interface RequireAuthProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export function RequireAuth({ children, fallback = null }: RequireAuthProps) {
  const { isAuthenticated, isBootstrapping } = useAuthorization();

  if (isBootstrapping) {
    return fallback;
  }

  if (!isAuthenticated) {
    return fallback;
  }

  return <>{children}</>;
}
