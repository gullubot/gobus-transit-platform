import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { CityProvider, useCity } from './contexts/CityContext';

import LoginPage from './pages/LoginPage';
import CitySelectionPage from './pages/CitySelectionPage';
import HomePage from './pages/HomePage';
import HistoryPage from './pages/HistoryPage';
import PlanTripPage from './pages/PlanTripPage';
import ServiceLivePage from './pages/ServiceLivePage';
import ServiceSearchPage from './pages/ServiceSearchPage';
import ServiceDetailsPage from './pages/ServiceDetailsPage';

import './App.css';

/**
 * Route guard: requires authentication.
 * Redirects to /login if not authenticated.
 */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return null; // don't flash login while restoring session
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

/**
 * Route guard: requires city selection.
 * Redirects to /select-city if no city is stored.
 */
function RequireCity({ children }: { children: React.ReactNode }) {
  const { hasCity } = useCity();

  if (!hasCity) {
    return <Navigate to="/select-city" replace />;
  }

  return <>{children}</>;
}

/**
 * Root redirect logic:
 * - Not authenticated → /login
 * - Authenticated but no city → /select-city
 * - Both → /home
 */
function RootRedirect() {
  const { isAuthenticated, isLoading } = useAuth();
  const { hasCity } = useCity();

  if (isLoading) return null;

  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!hasCity) return <Navigate to="/select-city" replace />;
  return <Navigate to="/home" replace />;
}

/**
 * Wraps authenticated pages with the app shell layout (bottom nav, etc.)
 */
function AuthenticatedPage({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <RequireCity>
        {children}
      </RequireCity>
    </RequireAuth>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <CityProvider>
          <Routes>
            {/* Public */}
            <Route path="/login" element={<LoginPage />} />

            {/* Requires auth only */}
            <Route
              path="/select-city"
              element={
                <RequireAuth>
                  <CitySelectionPage />
                </RequireAuth>
              }
            />

            {/* Requires auth + city */}
            <Route path="/home" element={<AuthenticatedPage><HomePage /></AuthenticatedPage>} />
            <Route path="/history" element={<AuthenticatedPage><HistoryPage /></AuthenticatedPage>} />
            <Route path="/plan" element={<AuthenticatedPage><PlanTripPage /></AuthenticatedPage>} />
            <Route path="/service-search" element={<AuthenticatedPage><ServiceSearchPage /></AuthenticatedPage>} />
            <Route path="/service/:serviceId" element={<AuthenticatedPage><ServiceDetailsPage /></AuthenticatedPage>} />
            <Route path="/service/:serviceId/live" element={<AuthenticatedPage><ServiceLivePage /></AuthenticatedPage>} />

            {/* Root → smart redirect */}
            <Route path="/" element={<RootRedirect />} />

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </CityProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
