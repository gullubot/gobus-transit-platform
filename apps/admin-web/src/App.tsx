import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import StopsPage from "./pages/StopsPage";
import RoutesPage from "./pages/RoutesPage";
import ServicesPage from "./pages/ServicesPage";
import VehiclesPage from "./pages/VehiclesPage";
import FleetSchedulesPage from "./pages/FleetSchedulesPage";
import DepotSchedulesPage from "./pages/DepotSchedulesPage";
import { LiveOperationsPage } from "./pages/live-operations/LiveOperationsPage";
import AlertsPage from "./pages/AlertsPage";
import FaresPage from "./pages/FaresPage";
import InsightsDashboard from "./pages/InsightsDashboard";
import ServiceSchedulesPage from "./pages/ServiceSchedulesPage";
import ServiceDetailsPage from "./pages/ServiceDetailsPage";
import RouteDetailsPage from "./pages/RouteDetailsPage";
import { UsersPage } from "./pages/UsersPage";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./App.css";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token, loading } = useAuth();
  if (loading) return <div className="loading-screen">Loading...</div>;
  if (!token) return <Navigate to="/login" replace />;
  return <ErrorBoundary>{children}</ErrorBoundary>;
}

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="stops" element={<StopsPage />} />
            <Route path="routes" element={<RoutesPage />} />
            <Route path="routes/:routeId" element={<RouteDetailsPage />} />
            <Route path="services" element={<ServicesPage />} />
            <Route path="vehicles" element={<VehiclesPage />} />
            <Route path="fleet-schedules" element={<FleetSchedulesPage />} />
            <Route path="depot-schedules" element={<DepotSchedulesPage />} />
            <Route path="live-operations" element={<LiveOperationsPage />} />
            <Route path="alerts" element={<AlertsPage />} />
            <Route path="fares" element={<FaresPage />} />
            <Route path="insights" element={<InsightsDashboard />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="services/:serviceId" element={<ServiceDetailsPage />} />
            <Route path="services/:id/schedules" element={<ServiceSchedulesPage />} />
          </Route>
        </Routes>
      </Router>
    </AuthProvider>
  );
}
