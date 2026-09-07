import { Outlet, NavLink } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Bus, Map, Network, Route as RouteIcon, MapPin, LogOut, Truck, Calendar, AlertTriangle, Banknote, TrendingUp, Users, Clock } from "lucide-react";

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="admin-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <Bus className="logo-icon" />
          <h2>GoBus Admin</h2>
        </div>
        <nav className="sidebar-nav">
          <NavLink to="/" className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <Map className="nav-icon" />
            Dashboard
          </NavLink>
          <NavLink to="/stops" className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <MapPin className="nav-icon" />
            Stops
          </NavLink>
          <NavLink to="/routes" className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <RouteIcon className="nav-icon" />
            Routes
          </NavLink>
          <NavLink to="/services" className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <Network className="nav-icon" />
            Services
          </NavLink>
          <NavLink to="/vehicles" className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <Truck className="nav-icon" />
            Fleet
          </NavLink>
          <NavLink to="/fleet-schedules" className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <Clock className="nav-icon" />
            Fleet Schedule
          </NavLink>
          <NavLink to="/depot-schedules" className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <Calendar className="nav-icon" />
            Depot Schedules
          </NavLink>
          <NavLink to="/live-operations" className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <Map className="nav-icon" />
            Live Operations
          </NavLink>
          <NavLink to="/alerts" className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <AlertTriangle className="nav-icon" />
            Alerts & Triage
          </NavLink>
          <NavLink to="/fares" className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <Banknote className="nav-icon" />
            Fares
          </NavLink>
          <NavLink to="/insights" className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <TrendingUp className="nav-icon" />
            Insights
          </NavLink>
          <NavLink to="/users" className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}>
            <Users className="nav-icon" />
            Users & Team
          </NavLink>
        </nav>
        <div className="sidebar-footer">
          <button className="logout-btn" onClick={logout}>
            <LogOut className="nav-icon" />
            Logout
          </button>
        </div>
      </aside>

      <div className="main-content">
        <header className="topbar">
          <div className="topbar-title">Network Management</div>
          <div className="user-profile">
            <div className="user-avatar">{user?.name.charAt(0)}</div>
            <div className="user-info">
              <span className="user-name">{user?.name}</span>
              <span className="user-role">{user?.role.replace("_", " ")}</span>
            </div>
          </div>
        </header>

        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
