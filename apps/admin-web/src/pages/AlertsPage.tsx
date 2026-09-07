import { useState, useEffect, useCallback } from "react";
import { useSearchParams, useLocation } from "react-router-dom";
import {
  RefreshCw,
  Search,
  AlertOctagon,
  AlertTriangle,
  Info,
  CheckCircle2,
  X,
  Bus,
  Route as RouteIcon,
  ShieldAlert,
} from "lucide-react";
import type {
  ServiceAlert,
  AlertMetrics,
  AlertStatus as AlertStatusType,
  AlertSeverity as AlertSeverityType,
} from "../api/alerts";
import {
  fetchAlerts,
  fetchAlert,
  acknowledgeAlert,
  resolveAlert,
  AlertStatus,
  AlertSeverity,
} from "../api/alerts";
import AlertDetailModal from "./AlertDetailModal";
import {
  formatAlertType,
  formatGoBusDateTime,
  ALERT_TYPE_LABELS,
} from "../utils/alertUtils";

export default function AlertsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();

  const [alerts, setAlerts] = useState<ServiceAlert[]>([]);
  const [total, setTotal] = useState(0);
  const [metrics, setMetrics] = useState<AlertMetrics>({
    active: 0,
    critical: 0,
    warning: 0,
    resolved: 0,
    open: 0,
    acknowledged: 0,
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<ServiceAlert | null>(null);

  // Filters state
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");

  const loadAlerts = useCallback(
    async (isManualRefresh = false) => {
      try {
        if (isManualRefresh) setRefreshing(true);
        else setLoading(true);
        setError(null);

        const res = await fetchAlerts({
          search: searchQuery.trim() || undefined,
          status: (statusFilter as AlertStatusType) || undefined,
          severity: (severityFilter as AlertSeverityType) || undefined,
          type: typeFilter || undefined,
          limit: 100,
        });

        setAlerts(res.data || []);
        setTotal(res.total || 0);
        if (res.metrics) {
          setMetrics(res.metrics);
        }
      } catch (err: any) {
        console.error("Failed to load alerts:", err);
        setError(err.message || "Unable to load incidents.");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [searchQuery, statusFilter, severityFilter, typeFilter]
  );

  // Initial load and filter reaction
  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  // Handle return-context from other screens (e.g. Back to Alerts & Triage with alertId)
  useEffect(() => {
    const targetAlertId =
      (location.state as any)?.returnState?.alertId ||
      (location.state as any)?.alertId ||
      searchParams.get("alertId");

    if (targetAlertId) {
      // If already in loaded alerts, open immediately
      const existing = alerts.find((a) => a.id === targetAlertId);
      if (existing) {
        setSelectedAlert(existing);
      } else {
        // Fetch single alert specifically
        fetchAlert(targetAlertId)
          .then((alert) => {
            if (alert) setSelectedAlert(alert);
          })
          .catch((err) => {
            console.warn("Could not recover target alert case:", err);
          });
      }
    }
  }, [location.state, searchParams, alerts]);

  const handleOpenCase = (alert: ServiceAlert) => {
    setSelectedAlert(alert);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("alertId", alert.id);
      return next;
    }, { replace: true });
  };

  const handleCloseCase = () => {
    setSelectedAlert(null);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("alertId");
      return next;
    }, { replace: true });
  };

  const handleAcknowledge = async (id: string) => {
    try {
      const updated = await acknowledgeAlert(id);
      setAlerts((prev) => prev.map((a) => (a.id === id ? updated : a)));
      if (selectedAlert?.id === id) setSelectedAlert(updated);
      loadAlerts(false);
    } catch (err: any) {
      alert(`Failed to acknowledge alert: ${err.message || "Unknown error"}`);
    }
  };

  const handleResolve = async (id: string) => {
    try {
      const updated = await resolveAlert(id);
      setAlerts((prev) => prev.map((a) => (a.id === id ? updated : a)));
      if (selectedAlert?.id === id) setSelectedAlert(updated);
      loadAlerts(false);
    } catch (err: any) {
      alert(`Failed to resolve alert: ${err.message || "Unknown error"}`);
    }
  };

  const clearFilters = () => {
    setSearchQuery("");
    setStatusFilter("");
    setSeverityFilter("");
    setTypeFilter("");
  };

  const hasActiveFilters = Boolean(
    searchQuery.trim() || statusFilter || severityFilter || typeFilter
  );

  return (
    <div className="page-container" style={{ maxWidth: "1440px", margin: "0 auto", padding: "1.5rem" }}>
      {/* 4. PAGE HEADER */}
      <div
        className="page-header"
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: "1.5rem",
          gap: "1rem",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.25rem" }}>
            <h1
              style={{
                fontSize: "1.75rem",
                fontWeight: 700,
                color: "#f8fafc",
                margin: 0,
                letterSpacing: "-0.02em",
              }}
            >
              ALERTS & TRIAGE
            </h1>
            <span
              style={{
                backgroundColor: "rgba(56, 189, 248, 0.12)",
                color: "#38bdf8",
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "2px 8px",
                borderRadius: "999px",
                border: "1px solid rgba(56, 189, 248, 0.25)",
              }}
            >
              Incident Center
            </span>
          </div>
          <p style={{ margin: 0, color: "#94a3b8", fontSize: "0.9375rem" }}>
            Monitor, prioritize, and act on operational incidents.
          </p>
        </div>

        <button
          type="button"
          onClick={() => loadAlerts(true)}
          disabled={refreshing || loading}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
            backgroundColor: "#1e293b",
            color: "#e2e8f0",
            border: "1px solid #334155",
            borderRadius: "8px",
            padding: "0.5rem 1rem",
            fontSize: "0.875rem",
            fontWeight: 600,
            cursor: refreshing || loading ? "not-allowed" : "pointer",
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => {
            if (!refreshing && !loading) e.currentTarget.style.backgroundColor = "#334155";
          }}
          onMouseLeave={(e) => {
            if (!refreshing && !loading) e.currentTarget.style.backgroundColor = "#1e293b";
          }}
        >
          <RefreshCw size={15} className={refreshing ? "animate-spin" : ""} />
          <span>Refresh</span>
        </button>
      </div>

      {/* 5. SUMMARY METRICS STRIP */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "1rem",
          marginBottom: "1.5rem",
        }}
      >
        {/* ACTIVE METRIC */}
        <div
          style={{
            backgroundColor: "#0f172a",
            border: "1px solid #334155",
            borderTop: "3px solid #38bdf8",
            borderRadius: "10px",
            padding: "1rem 1.25rem",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.8125rem", fontWeight: 700, letterSpacing: "0.05em", color: "#94a3b8" }}>
              ACTIVE INCIDENTS
            </span>
            <ShieldAlert size={18} color="#38bdf8" />
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem" }}>
            <span style={{ fontSize: "1.875rem", fontWeight: 700, color: "#f8fafc" }}>
              {metrics.active}
            </span>
            <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
              {metrics.open} Open · {metrics.acknowledged} Ack
            </span>
          </div>
        </div>

        {/* CRITICAL METRIC */}
        <div
          style={{
            backgroundColor: "#0f172a",
            border: "1px solid #334155",
            borderTop: "3px solid #ef4444",
            borderRadius: "10px",
            padding: "1rem 1.25rem",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.8125rem", fontWeight: 700, letterSpacing: "0.05em", color: "#ef4444" }}>
              CRITICAL URGENCY
            </span>
            <AlertOctagon size={18} color="#ef4444" />
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem" }}>
            <span style={{ fontSize: "1.875rem", fontWeight: 700, color: "#f8fafc" }}>
              {metrics.critical}
            </span>
            <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
              Immediate action required
            </span>
          </div>
        </div>

        {/* WARNING METRIC */}
        <div
          style={{
            backgroundColor: "#0f172a",
            border: "1px solid #334155",
            borderTop: "3px solid #f59e0b",
            borderRadius: "10px",
            padding: "1rem 1.25rem",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.8125rem", fontWeight: 700, letterSpacing: "0.05em", color: "#f59e0b" }}>
              OPERATIONAL WARNINGS
            </span>
            <AlertTriangle size={18} color="#f59e0b" />
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem" }}>
            <span style={{ fontSize: "1.875rem", fontWeight: 700, color: "#f8fafc" }}>
              {metrics.warning}
            </span>
            <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
              Attention needed
            </span>
          </div>
        </div>

        {/* RESOLVED METRIC */}
        <div
          style={{
            backgroundColor: "#0f172a",
            border: "1px solid #334155",
            borderTop: "3px solid #10b981",
            borderRadius: "10px",
            padding: "1rem 1.25rem",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <span style={{ fontSize: "0.8125rem", fontWeight: 700, letterSpacing: "0.05em", color: "#10b981" }}>
              RESOLVED
            </span>
            <CheckCircle2 size={18} color="#10b981" />
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem" }}>
            <span style={{ fontSize: "1.875rem", fontWeight: 700, color: "#f8fafc" }}>
              {metrics.resolved}
            </span>
            <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
              Successfully addressed
            </span>
          </div>
        </div>
      </div>

      {/* 15 & 16. SEARCH AND FILTERS TOOLBAR */}
      <div
        style={{
          backgroundColor: "#0f172a",
          border: "1px solid #334155",
          borderRadius: "10px",
          padding: "1rem 1.25rem",
          marginBottom: "1.5rem",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "0.75rem",
        }}
      >
        {/* Search input */}
        <div
          style={{
            position: "relative",
            flex: "1 1 240px",
            minWidth: "220px",
          }}
        >
          <Search
            size={16}
            color="#64748b"
            style={{
              position: "absolute",
              left: "12px",
              top: "50%",
              transform: "translateY(-50%)",
              pointerEvents: "none",
            }}
          />
          <input
            type="text"
            placeholder="Search incidents by title, message, vehicle..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: "100%",
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "6px",
              padding: "0.5rem 0.75rem 0.5rem 2.25rem",
              color: "#f8fafc",
              fontSize: "0.875rem",
              outline: "none",
            }}
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              style={{
                position: "absolute",
                right: "10px",
                top: "50%",
                transform: "translateY(-50%)",
                background: "transparent",
                border: "none",
                color: "#94a3b8",
                cursor: "pointer",
                padding: "2px",
              }}
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Severity Filter */}
        <div style={{ minWidth: "150px" }}>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            style={{
              width: "100%",
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "6px",
              padding: "0.5rem 0.75rem",
              color: severityFilter ? "#f8fafc" : "#94a3b8",
              fontSize: "0.875rem",
              outline: "none",
              cursor: "pointer",
            }}
          >
            <option value="">All Severities</option>
            <option value={AlertSeverity.CRITICAL}>CRITICAL</option>
            <option value={AlertSeverity.WARNING}>WARNING</option>
            <option value={AlertSeverity.INFO}>INFO</option>
          </select>
        </div>

        {/* Status Filter */}
        <div style={{ minWidth: "160px" }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              width: "100%",
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "6px",
              padding: "0.5rem 0.75rem",
              color: statusFilter ? "#f8fafc" : "#94a3b8",
              fontSize: "0.875rem",
              outline: "none",
              cursor: "pointer",
            }}
          >
            <option value="">All Statuses</option>
            <option value={AlertStatus.OPEN}>OPEN</option>
            <option value={AlertStatus.ACKNOWLEDGED}>ACKNOWLEDGED</option>
            <option value={AlertStatus.RESOLVED}>RESOLVED</option>
          </select>
        </div>

        {/* Type Filter */}
        <div style={{ minWidth: "200px" }}>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            style={{
              width: "100%",
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "6px",
              padding: "0.5rem 0.75rem",
              color: typeFilter ? "#f8fafc" : "#94a3b8",
              fontSize: "0.875rem",
              outline: "none",
              cursor: "pointer",
            }}
          >
            <option value="">All Incident Types</option>
            {Object.entries(ALERT_TYPE_LABELS).map(([val, label]) => (
              <option key={val} value={val}>
                {label}
              </option>
            ))}
          </select>
        </div>

        {/* Clear Filters */}
        {hasActiveFilters && (
          <button
            type="button"
            onClick={clearFilters}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              backgroundColor: "transparent",
              color: "#94a3b8",
              border: "1px dashed #475569",
              borderRadius: "6px",
              padding: "0.5rem 0.875rem",
              fontSize: "0.8125rem",
              fontWeight: 500,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "#f8fafc";
              e.currentTarget.style.borderColor = "#94a3b8";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "#94a3b8";
              e.currentTarget.style.borderColor = "#475569";
            }}
          >
            <X size={14} /> Clear Filters
          </button>
        )}
      </div>

      {/* Incidents Count Indicator */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "0.75rem",
          fontSize: "0.8125rem",
          color: "#94a3b8",
        }}
      >
        <span>
          Showing <strong style={{ color: "#f8fafc" }}>{alerts.length}</strong> {alerts.length === 1 ? "incident" : "incidents"}
          {total > alerts.length && ` of ${total} total`}
        </span>
      </div>

      {/* 8-14. URGENCY-RANKED ALERT TABLE */}
      <div
        style={{
          backgroundColor: "#0f172a",
          border: "1px solid #334155",
          borderRadius: "10px",
          overflow: "hidden",
        }}
      >
        {loading ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "#94a3b8" }}>
            <RefreshCw size={24} className="animate-spin" style={{ margin: "0 auto 1rem auto" }} />
            <p style={{ margin: 0, fontSize: "0.9375rem" }}>Loading incidents...</p>
          </div>
        ) : error ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "#ef4444" }}>
            <AlertOctagon size={28} style={{ margin: "0 auto 1rem auto" }} />
            <p style={{ margin: "0 0 1rem 0", fontSize: "1rem", fontWeight: 600 }}>{error}</p>
            <button
              type="button"
              onClick={() => loadAlerts()}
              style={{
                backgroundColor: "#1e293b",
                color: "#e2e8f0",
                border: "1px solid #334155",
                borderRadius: "6px",
                padding: "0.5rem 1rem",
                cursor: "pointer",
              }}
            >
              Retry
            </button>
          </div>
        ) : alerts.length === 0 ? (
          <div style={{ padding: "3.5rem 2rem", textAlign: "center", color: "#94a3b8" }}>
            <CheckCircle2 size={32} color="#10b981" style={{ margin: "0 auto 1rem auto" }} />
            <h3 style={{ margin: "0 0 0.5rem 0", color: "#f8fafc", fontSize: "1.125rem", fontWeight: 600 }}>
              {hasActiveFilters ? "No incidents match your filters." : "No incidents require attention."}
            </h3>
            <p style={{ margin: 0, fontSize: "0.875rem", color: "#64748b" }}>
              {hasActiveFilters
                ? "Try adjusting search terms or clearing filter dropdowns."
                : "Operational fleet and routes are operating normally."}
            </p>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                style={{
                  marginTop: "1rem",
                  backgroundColor: "#1e293b",
                  color: "#38bdf8",
                  border: "1px solid #334155",
                  borderRadius: "6px",
                  padding: "0.5rem 1rem",
                  fontSize: "0.875rem",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Reset Filters
              </button>
            )}
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                textAlign: "left",
                fontSize: "0.875rem",
              }}
            >
              <thead>
                <tr
                  style={{
                    backgroundColor: "#111c34",
                    borderBottom: "1px solid #1e293b",
                    color: "#94a3b8",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                  }}
                >
                  <th style={{ padding: "0.875rem 1.25rem", width: "90px" }}>Priority</th>
                  <th style={{ padding: "0.875rem 1rem", width: "110px" }}>Severity</th>
                  <th style={{ padding: "0.875rem 1rem", width: "220px" }}>Type</th>
                  <th style={{ padding: "0.875rem 1.25rem" }}>Incident</th>
                  <th style={{ padding: "0.875rem 1rem", width: "170px" }}>Detected</th>
                  <th style={{ padding: "0.875rem 1rem", width: "130px" }}>Status</th>
                  <th style={{ padding: "0.875rem 1.25rem", width: "110px", textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((alert, idx) => {
                  const isResolved = alert.status === AlertStatus.RESOLVED;
                  const isCritical = alert.severity === AlertSeverity.CRITICAL && !isResolved;
                  const isWarning = alert.severity === AlertSeverity.WARNING && !isResolved;

                  // Severity badge config
                  const sevStyle = {
                    [AlertSeverity.CRITICAL]: {
                      bg: "rgba(239, 68, 68, 0.15)",
                      text: "#ef4444",
                      border: "rgba(239, 68, 68, 0.3)",
                      icon: <AlertOctagon size={13} />,
                    },
                    [AlertSeverity.WARNING]: {
                      bg: "rgba(245, 158, 11, 0.15)",
                      text: "#f59e0b",
                      border: "rgba(245, 158, 11, 0.3)",
                      icon: <AlertTriangle size={13} />,
                    },
                    [AlertSeverity.INFO]: {
                      bg: "rgba(6, 182, 212, 0.15)",
                      text: "#06b6d4",
                      border: "rgba(6, 182, 212, 0.3)",
                      icon: <Info size={13} />,
                    },
                  }[alert.severity] || {
                    bg: "rgba(148, 163, 184, 0.15)",
                    text: "#94a3b8",
                    border: "rgba(148, 163, 184, 0.3)",
                    icon: <Info size={13} />,
                  };

                  // Status badge config
                  const statStyle = {
                    [AlertStatus.OPEN]: {
                      bg: "rgba(239, 68, 68, 0.15)",
                      text: "#f87171",
                      border: "rgba(239, 68, 68, 0.3)",
                      dot: "#ef4444",
                    },
                    [AlertStatus.ACKNOWLEDGED]: {
                      bg: "rgba(168, 85, 247, 0.15)",
                      text: "#c084fc",
                      border: "rgba(168, 85, 247, 0.3)",
                      dot: "#a855f7",
                    },
                    [AlertStatus.RESOLVED]: {
                      bg: "rgba(16, 185, 129, 0.15)",
                      text: "#34d399",
                      border: "rgba(16, 185, 129, 0.3)",
                      dot: "#10b981",
                    },
                  }[alert.status] || {
                    bg: "rgba(148, 163, 184, 0.15)",
                    text: "#94a3b8",
                    border: "rgba(148, 163, 184, 0.3)",
                    dot: "#94a3b8",
                  };

                  const entity = alert.entity_context;

                  return (
                    <tr
                      key={alert.id}
                      style={{
                        borderBottom: "1px solid #1e293b",
                        backgroundColor: isCritical
                          ? "rgba(239, 68, 68, 0.04)"
                          : isWarning
                          ? "rgba(245, 158, 11, 0.02)"
                          : "transparent",
                        transition: "background-color 0.15s ease",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.03)")}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = isCritical
                          ? "rgba(239, 68, 68, 0.04)"
                          : isWarning
                          ? "rgba(245, 158, 11, 0.02)"
                          : "transparent";
                      }}
                    >
                      {/* PRIORITY COLUMN */}
                      <td style={{ padding: "1rem 1.25rem", verticalAlign: "middle" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          <span
                            style={{
                              fontFamily: "monospace",
                              fontSize: "0.8125rem",
                              fontWeight: 700,
                              color: isResolved
                                ? "#64748b"
                                : isCritical
                                ? "#f87171"
                                : isWarning
                                ? "#fbbf24"
                                : "#38bdf8",
                              backgroundColor: isResolved
                                ? "rgba(100, 116, 139, 0.12)"
                                : isCritical
                                ? "rgba(239, 68, 68, 0.15)"
                                : isWarning
                                ? "rgba(245, 158, 11, 0.15)"
                                : "rgba(56, 189, 248, 0.15)",
                              padding: "2px 7px",
                              borderRadius: "4px",
                            }}
                          >
                            {alert.urgency_rank || `#${idx + 1}`}
                          </span>
                        </div>
                      </td>

                      {/* SEVERITY COLUMN */}
                      <td style={{ padding: "1rem 1rem", verticalAlign: "middle" }}>
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            backgroundColor: sevStyle.bg,
                            color: sevStyle.text,
                            border: `1px solid ${sevStyle.border}`,
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            padding: "3px 8px",
                            borderRadius: "4px",
                          }}
                        >
                          {sevStyle.icon}
                          {alert.severity}
                        </span>
                      </td>

                      {/* TYPE COLUMN */}
                      <td style={{ padding: "1rem 1rem", verticalAlign: "middle" }}>
                        <div style={{ color: "#e2e8f0", fontWeight: 500 }}>
                          {formatAlertType(alert.type)}
                        </div>
                      </td>

                      {/* INCIDENT COLUMN */}
                      <td style={{ padding: "1rem 1.25rem", verticalAlign: "middle" }}>
                        <div
                          style={{
                            color: "#f8fafc",
                            fontWeight: 600,
                            fontSize: "0.9375rem",
                            marginBottom: "2px",
                          }}
                        >
                          {alert.title}
                        </div>
                        {(entity?.vehicle_number || entity?.service_code) && (
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "0.75rem",
                              fontSize: "0.75rem",
                              color: "#94a3b8",
                            }}
                          >
                            {entity.vehicle_number && (
                              <span style={{ display: "inline-flex", alignItems: "center", gap: "3px" }}>
                                <Bus size={12} color="#38bdf8" /> Vehicle: <strong style={{ color: "#cbd5e1" }}>{entity.vehicle_number}</strong>
                              </span>
                            )}
                            {entity.service_code && (
                              <span style={{ display: "inline-flex", alignItems: "center", gap: "3px" }}>
                                <RouteIcon size={12} color="#818cf8" /> Service: <strong style={{ color: "#cbd5e1" }}>{entity.service_code}</strong>
                              </span>
                            )}
                          </div>
                        )}
                      </td>

                      {/* DETECTED TIME COLUMN */}
                      <td
                        style={{
                          padding: "1rem 1rem",
                          verticalAlign: "middle",
                          color: "#94a3b8",
                          fontSize: "0.8125rem",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {formatGoBusDateTime(alert.created_at)}
                      </td>

                      {/* STATUS COLUMN */}
                      <td style={{ padding: "1rem 1rem", verticalAlign: "middle" }}>
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "5px",
                            backgroundColor: statStyle.bg,
                            color: statStyle.text,
                            border: `1px solid ${statStyle.border}`,
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            padding: "3px 8px",
                            borderRadius: "4px",
                          }}
                        >
                          <span
                            style={{
                              width: "6px",
                              height: "6px",
                              borderRadius: "50%",
                              backgroundColor: statStyle.dot,
                            }}
                          />
                          {alert.status}
                        </span>
                      </td>

                      {/* ACTION COLUMN */}
                      <td style={{ padding: "1rem 1.25rem", verticalAlign: "middle", textAlign: "right" }}>
                        <button
                          type="button"
                          onClick={() => handleOpenCase(alert)}
                          style={{
                            backgroundColor: "#1e293b",
                            color: "#38bdf8",
                            border: "1px solid #334155",
                            borderRadius: "6px",
                            padding: "0.4rem 0.75rem",
                            fontSize: "0.8125rem",
                            fontWeight: 600,
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            transition: "all 0.15s ease",
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = "#334155";
                            e.currentTarget.style.color = "#7dd3fc";
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = "#1e293b";
                            e.currentTarget.style.color = "#38bdf8";
                          }}
                        >
                          View Case
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 18-36. ALERT CASE DETAILS MODAL */}
      {selectedAlert && (
        <AlertDetailModal
          alert={selectedAlert}
          onClose={handleCloseCase}
          onAcknowledge={handleAcknowledge}
          onResolve={handleResolve}
        />
      )}
    </div>
  );
}
