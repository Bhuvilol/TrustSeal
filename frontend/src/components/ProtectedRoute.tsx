import { useEffect } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import LoadingState from '@/components/LoadingState';
import { useAuth } from '@/hooks/useAuth';
import { isTokenExpired } from '@/utils/token';

function ProtectedRoute() {
  const { token, user, isInitializing, logout } = useAuth();
  const location = useLocation();

  const tokenExpired = token ? isTokenExpired(token) : true;

  useEffect(() => {
    if (token && tokenExpired) {
      logout();
    }
  }, [token, tokenExpired, logout]);

  if (isInitializing) {
    return <LoadingState fullscreen message="Restoring session..." />;
  }

  if (!token || !user || tokenExpired) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}

export default ProtectedRoute;

