import { Navigate, Outlet } from "react-router-dom";
import { useAuthorization } from "../../shared/auth/useAuthorization";

export function ProtectedRoute() {
  const { isAuthenticated, isBootstrapping } = useAuthorization();

  if (isBootstrapping) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-50">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-300 border-t-neutral-950" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
