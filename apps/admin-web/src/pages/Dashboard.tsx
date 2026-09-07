import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { MapPin, Route, Network, Truck, AlertTriangle, TrendingUp } from "lucide-react";
import { apiFetch, getInsights } from "../api/api";
import { fetchAlerts, AlertStatus } from "../api/alerts";

export default function Dashboard() {
  const navigate = useNavigate();
  const [fleetStats, setFleetStats] = useState({ total: 0, active: 0, maintenance: 0 });
  const [alertStats, setAlertStats] = useState({ open: 0, acknowledged: 0 });

  const [insightStats, setInsightStats] = useState({ total: 0, topRecommendation: "" });

  useEffect(() => {
    loadFleetStats();
    loadAlertStats();
    loadInsightStats();
  }, []);

  const loadFleetStats = async () => {
    try {
      const vehicles = await apiFetch("/admin/vehicles");
      setFleetStats({
        total: vehicles.length,
        active: vehicles.filter((v: any) => v.status === "ACTIVE").length,
        maintenance: vehicles.filter((v: any) => v.status === "MAINTENANCE").length,
      });
    } catch (err) {
      console.error("Failed to load fleet stats", err);
    }
  };

  const loadAlertStats = async () => {
    try {
      const [openRes, ackRes] = await Promise.all([
        fetchAlerts({ status: AlertStatus.OPEN, limit: 1 }),
        fetchAlerts({ status: AlertStatus.ACKNOWLEDGED, limit: 1 })
      ]);
      setAlertStats({
        open: openRes.total,
        acknowledged: ackRes.total,
      });
    } catch (err) {
      console.error("Failed to load alert stats", err);
    }
  };
  const loadInsightStats = async () => {
    try {
      const res = await getInsights("summary");
      if (res && res.insights) {
        setInsightStats({
          total: res.insights.length,
          topRecommendation: res.insights.length > 0 ? res.insights[0].title : "No recent issues",
        });
      }
    } catch (err) {
      console.error("Failed to load insight stats", err);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Welcome to GoBus Admin Network Control</p>
        </div>
      </div>
      
      <div className="dashboard-grid">
        <div className="stat-card" style={{ cursor: "pointer" }} onClick={() => navigate("/stops")}>
          <div className="stat-icon-wrapper blue">
            <MapPin size={24} className="stat-icon" />
          </div>
          <div className="stat-content">
            <h3>Manage Stops</h3>
            <p>Create and update physical stop locations</p>
          </div>
        </div>
        
        <div className="stat-card" style={{ cursor: "pointer" }} onClick={() => navigate("/routes")}>
          <div className="stat-icon-wrapper green">
            <Route size={24} className="stat-icon" />
          </div>
          <div className="stat-content">
            <h3>Manage Routes</h3>
            <p>Define transit lines and paths</p>
          </div>
        </div>

        <div className="stat-card" style={{ cursor: "pointer" }} onClick={() => navigate("/services")}>
          <div className="stat-icon-wrapper purple">
            <Network size={24} className="stat-icon" />
          </div>
          <div className="stat-content">
            <h3>Manage Services</h3>
            <p>Assign services to specific routes</p>
          </div>
        </div>

        <div className="stat-card" style={{ cursor: "pointer" }} onClick={() => navigate("/vehicles")}>
          <div className="stat-icon-wrapper yellow">
            <Truck size={24} className="stat-icon" />
          </div>
          <div className="stat-content">
            <h3>Fleet Summary</h3>
            <p>
              <strong>{fleetStats.total}</strong> Total | <strong>{fleetStats.active}</strong> Active | <strong>{fleetStats.maintenance}</strong> Maintenance
            </p>
          </div>
        </div>

        <div className={`stat-card alert-card ${alertStats.open > 0 ? "has-open-alerts" : ""}`} style={{ cursor: "pointer" }} onClick={() => navigate("/alerts")}>
          <div className="stat-icon-wrapper red">
            <AlertTriangle size={24} className="stat-icon" />
          </div>
          <div className="stat-content">
            <h3>Active Alerts</h3>
            <p>
              <strong>{alertStats.open}</strong> Open | <strong>{alertStats.acknowledged}</strong> Acknowledged
            </p>
          </div>
        </div>

        <div className="stat-card" style={{ borderColor: insightStats.total > 0 ? "var(--color-warning)" : "", cursor: "pointer" }} onClick={() => navigate("/insights")}>
          <div className="stat-icon-wrapper orange">
            <TrendingUp size={24} className="stat-icon" />
          </div>
          <div className="stat-content">
            <h3>Operational Insights</h3>
            <p>
              <strong>{insightStats.total}</strong> Active Insights | {insightStats.topRecommendation}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
