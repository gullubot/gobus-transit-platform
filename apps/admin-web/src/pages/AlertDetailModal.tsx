import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertOctagon,
  AlertTriangle,
  Info,
  Copy,
  Check,
  ArrowUpRight,
  Bus,
  Route as RouteIcon,
  X,
  FileText,
  Zap,
  CheckCheck,
} from "lucide-react";
import type { ServiceAlert } from "../api/alerts";
import { AlertStatus, AlertSeverity } from "../api/alerts";
import {
  formatAlertType,
  formatGoBusDateTime,
} from "../utils/alertUtils";

interface AlertDetailModalProps {
  alert: ServiceAlert;
  onClose: () => void;
  onAcknowledge: (id: string) => Promise<void>;
  onResolve: (id: string) => Promise<void>;
}

export default function AlertDetailModal({
  alert,
  onClose,
  onAcknowledge,
  onResolve,
}: AlertDetailModalProps) {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"details" | "resolution">("details");
  const [copiedFingerprint, setCopiedFingerprint] = useState(false);
  const [copiedId, setCopiedId] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const copyToClipboard = (text: string, isFingerprint: boolean) => {
    navigator.clipboard.writeText(text);
    if (isFingerprint) {
      setCopiedFingerprint(true);
      setTimeout(() => setCopiedFingerprint(false), 2000);
    } else {
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    }
  };

  const handleActionNavigate = (destination: string) => {
    // Preserve origin context back to this specific alert case
    navigate(destination, {
      state: {
        returnTo: `/alerts?alertId=${alert.id}`,
        returnState: { alertId: alert.id },
        returnLabel: "Alerts & Triage",
      },
    });
  };

  const handleAckClick = async () => {
    try {
      setActionLoading(true);
      await onAcknowledge(alert.id);
    } finally {
      setActionLoading(false);
    }
  };

  const handleResolveClick = async () => {
    try {
      setActionLoading(true);
      await onResolve(alert.id);
    } finally {
      setActionLoading(false);
    }
  };

  const entity = alert.entity_context;
  const resolution = alert.suggested_resolution;

  // Severity styling
  const severityConfig = {
    [AlertSeverity.CRITICAL]: {
      label: "CRITICAL",
      icon: <AlertOctagon size={14} />,
      bg: "rgba(239, 68, 68, 0.15)",
      text: "#ef4444",
      border: "rgba(239, 68, 68, 0.3)",
    },
    [AlertSeverity.WARNING]: {
      label: "WARNING",
      icon: <AlertTriangle size={14} />,
      bg: "rgba(245, 158, 11, 0.15)",
      text: "#f59e0b",
      border: "rgba(245, 158, 11, 0.3)",
    },
    [AlertSeverity.INFO]: {
      label: "INFO",
      icon: <Info size={14} />,
      bg: "rgba(6, 182, 212, 0.15)",
      text: "#06b6d4",
      border: "rgba(6, 182, 212, 0.3)",
    },
  }[alert.severity] || {
    label: alert.severity,
    icon: <Info size={14} />,
    bg: "rgba(148, 163, 184, 0.15)",
    text: "#94a3b8",
    border: "rgba(148, 163, 184, 0.3)",
  };

  // Status styling
  const statusConfig = {
    [AlertStatus.OPEN]: {
      label: "OPEN",
      bg: "rgba(239, 68, 68, 0.15)",
      text: "#f87171",
      border: "rgba(239, 68, 68, 0.3)",
      dot: "#ef4444",
    },
    [AlertStatus.ACKNOWLEDGED]: {
      label: "ACKNOWLEDGED",
      bg: "rgba(168, 85, 247, 0.15)",
      text: "#c084fc",
      border: "rgba(168, 85, 247, 0.3)",
      dot: "#a855f7",
    },
    [AlertStatus.RESOLVED]: {
      label: "RESOLVED",
      bg: "rgba(16, 185, 129, 0.15)",
      text: "#34d399",
      border: "rgba(16, 185, 129, 0.3)",
      dot: "#10b981",
    },
  }[alert.status] || {
    label: alert.status,
    bg: "rgba(148, 163, 184, 0.15)",
    text: "#94a3b8",
    border: "rgba(148, 163, 184, 0.3)",
    dot: "#94a3b8",
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(6px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: "1rem",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "760px",
          maxHeight: "90vh",
          backgroundColor: "#0f172a",
          border: "1px solid #334155",
          borderRadius: "12px",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.6)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* FIXED HEADER */}
        <div
          style={{
            flexShrink: 0,
            padding: "1.25rem 1.5rem",
            borderBottom: "1px solid #1e293b",
            backgroundColor: "#111c34",
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: "1rem",
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Badges strip */}
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
              {alert.urgency_rank && (
                <span
                  style={{
                    backgroundColor: "rgba(255, 255, 255, 0.08)",
                    color: "#f8fafc",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: "4px",
                    letterSpacing: "0.05em",
                  }}
                >
                  {alert.urgency_rank}
                </span>
              )}
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                  backgroundColor: severityConfig.bg,
                  color: severityConfig.text,
                  border: `1px solid ${severityConfig.border}`,
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  padding: "2px 8px",
                  borderRadius: "4px",
                }}
              >
                {severityConfig.icon}
                {severityConfig.label}
              </span>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  backgroundColor: statusConfig.bg,
                  color: statusConfig.text,
                  border: `1px solid ${statusConfig.border}`,
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  padding: "2px 8px",
                  borderRadius: "4px",
                }}
              >
                <span
                  style={{
                    width: "6px",
                    height: "6px",
                    borderRadius: "50%",
                    backgroundColor: statusConfig.dot,
                  }}
                />
                {statusConfig.label}
              </span>
            </div>

            {/* Dominant Incident Title */}
            <h2
              style={{
                margin: 0,
                color: "#f8fafc",
                fontSize: "1.25rem",
                fontWeight: 600,
                lineHeight: 1.35,
                wordBreak: "break-word",
              }}
            >
              {alert.title}
            </h2>

            {/* Connected entities preview */}
            {(entity?.vehicle_number || entity?.service_code || entity?.route_code) && (
              <div
                style={{
                  marginTop: "0.35rem",
                  display: "flex",
                  flexWrap: "wrap",
                  alignItems: "center",
                  gap: "0.75rem",
                  fontSize: "0.8125rem",
                  color: "#94a3b8",
                }}
              >
                {entity.vehicle_number && (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                    <Bus size={13} color="#38bdf8" /> Vehicle: <strong style={{ color: "#e2e8f0" }}>{entity.vehicle_number}</strong>
                  </span>
                )}
                {entity.service_code && (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                    <RouteIcon size={13} color="#818cf8" /> Service: <strong style={{ color: "#e2e8f0" }}>{entity.service_code}</strong>
                  </span>
                )}
                {entity.route_code && (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "4px" }}>
                    <RouteIcon size={13} color="#a78bfa" /> Route: <strong style={{ color: "#e2e8f0" }}>{entity.route_code}</strong>
                  </span>
                )}
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              padding: "4px",
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "#f8fafc";
              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.08)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "#94a3b8";
              e.currentTarget.style.backgroundColor = "transparent";
            }}
            title="Close modal"
          >
            <X size={20} />
          </button>
        </div>

        {/* TABS SWITCHER */}
        <div
          style={{
            flexShrink: 0,
            display: "flex",
            borderBottom: "1px solid #1e293b",
            backgroundColor: "#0d1527",
            padding: "0 1.5rem",
          }}
        >
          <button
            type="button"
            onClick={() => setActiveTab("details")}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "0.75rem 1rem",
              background: "transparent",
              border: "none",
              borderBottom: activeTab === "details" ? "2px solid #38bdf8" : "2px solid transparent",
              color: activeTab === "details" ? "#38bdf8" : "#94a3b8",
              fontWeight: 600,
              fontSize: "0.875rem",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            <FileText size={15} /> Case Details
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("resolution")}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "0.75rem 1rem",
              background: "transparent",
              border: "none",
              borderBottom: activeTab === "resolution" ? "2px solid #38bdf8" : "2px solid transparent",
              color: activeTab === "resolution" ? "#38bdf8" : "#94a3b8",
              fontWeight: 600,
              fontSize: "0.875rem",
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
          >
            <Zap size={15} /> Suggested Resolution
            {resolution && resolution.actions.length > 0 && (
              <span
                style={{
                  backgroundColor: "rgba(56, 189, 248, 0.15)",
                  color: "#38bdf8",
                  fontSize: "0.6875rem",
                  padding: "1px 6px",
                  borderRadius: "999px",
                  fontWeight: 700,
                }}
              >
                {resolution.actions.length}
              </span>
            )}
          </button>
        </div>

        {/* SCROLLABLE BODY */}
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            padding: "1.5rem",
            display: "flex",
            flexDirection: "column",
            gap: "1.25rem",
          }}
        >
          {activeTab === "details" ? (
            <>
              {/* CASE OVERVIEW GRID */}
              <div>
                <h4
                  style={{
                    margin: "0 0 0.65rem 0",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.075em",
                    color: "#64748b",
                  }}
                >
                  Case Overview
                </h4>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
                    gap: "0.75rem",
                  }}
                >
                  <div
                    style={{
                      backgroundColor: "#1e293b",
                      padding: "0.75rem 1rem",
                      borderRadius: "8px",
                      border: "1px solid #334155",
                    }}
                  >
                    <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "2px" }}>Incident Type</div>
                    <div style={{ color: "#f8fafc", fontSize: "0.875rem", fontWeight: 600 }}>
                      {formatAlertType(alert.type)}
                    </div>
                  </div>

                  <div
                    style={{
                      backgroundColor: "#1e293b",
                      padding: "0.75rem 1rem",
                      borderRadius: "8px",
                      border: "1px solid #334155",
                    }}
                  >
                    <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "2px" }}>Detected At</div>
                    <div style={{ color: "#f8fafc", fontSize: "0.875rem", fontWeight: 500 }}>
                      {formatGoBusDateTime(alert.created_at)}
                    </div>
                  </div>

                  <div
                    style={{
                      backgroundColor: "#1e293b",
                      padding: "0.75rem 1rem",
                      borderRadius: "8px",
                      border: "1px solid #334155",
                    }}
                  >
                    <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "2px" }}>Operational Scope</div>
                    <div style={{ color: "#f8fafc", fontSize: "0.875rem", fontWeight: 600 }}>
                      {alert.scope}
                    </div>
                  </div>

                  {entity?.vehicle_number && (
                    <div
                      style={{
                        backgroundColor: "#1e293b",
                        padding: "0.75rem 1rem",
                        borderRadius: "8px",
                        border: "1px solid #334155",
                      }}
                    >
                      <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "2px" }}>Affected Vehicle</div>
                      <div style={{ color: "#38bdf8", fontSize: "0.875rem", fontWeight: 600 }}>
                        {entity.vehicle_number}
                      </div>
                    </div>
                  )}

                  {entity?.service_code && (
                    <div
                      style={{
                        backgroundColor: "#1e293b",
                        padding: "0.75rem 1rem",
                        borderRadius: "8px",
                        border: "1px solid #334155",
                      }}
                    >
                      <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "2px" }}>Affected Service</div>
                      <div style={{ color: "#818cf8", fontSize: "0.875rem", fontWeight: 600 }}>
                        {entity.service_code} {entity.service_name ? `(${entity.service_name})` : ""}
                      </div>
                    </div>
                  )}

                  {entity?.route_code && (
                    <div
                      style={{
                        backgroundColor: "#1e293b",
                        padding: "0.75rem 1rem",
                        borderRadius: "8px",
                        border: "1px solid #334155",
                      }}
                    >
                      <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "2px" }}>Assigned Route</div>
                      <div style={{ color: "#a78bfa", fontSize: "0.875rem", fontWeight: 600 }}>
                        {entity.route_code} {entity.route_name ? `(${entity.route_name})` : ""}
                      </div>
                    </div>
                  )}

                  {entity?.stop_code && (
                    <div
                      style={{
                        backgroundColor: "#1e293b",
                        padding: "0.75rem 1rem",
                        borderRadius: "8px",
                        border: "1px solid #334155",
                      }}
                    >
                      <div style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: "2px" }}>Stop Location</div>
                      <div style={{ color: "#f8fafc", fontSize: "0.875rem", fontWeight: 600 }}>
                        {entity.stop_code} {entity.stop_name ? `(${entity.stop_name})` : ""}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* FACTUAL EVIDENCE */}
              <div>
                <h4
                  style={{
                    margin: "0 0 0.65rem 0",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.075em",
                    color: "#64748b",
                  }}
                >
                  Factual Evidence
                </h4>
                <div
                  style={{
                    backgroundColor: "rgba(15, 23, 42, 0.8)",
                    border: "1px solid #334155",
                    borderLeft: "4px solid #38bdf8",
                    borderRadius: "8px",
                    padding: "1rem 1.25rem",
                  }}
                >
                  <p
                    style={{
                      margin: 0,
                      color: "#f1f5f9",
                      fontSize: "0.9375rem",
                      lineHeight: 1.6,
                    }}
                  >
                    {alert.message}
                  </p>
                </div>
              </div>

              {/* TECHNICAL METADATA (SUBORDINATE) */}
              <div
                style={{
                  marginTop: "0.5rem",
                  paddingTop: "1rem",
                  borderTop: "1px solid #1e293b",
                }}
              >
                <h4
                  style={{
                    margin: "0 0 0.65rem 0",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.075em",
                    color: "#64748b",
                  }}
                >
                  Technical Details
                </h4>

                <div
                  style={{
                    backgroundColor: "#0d1527",
                    borderRadius: "8px",
                    border: "1px solid #1e293b",
                    padding: "0.75rem 1rem",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.5rem",
                  }}
                >
                  {/* Fingerprint row */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "1rem",
                    }}
                  >
                    <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                      <span style={{ fontSize: "0.6875rem", color: "#64748b", textTransform: "uppercase" }}>
                        Fingerprint
                      </span>
                      <code
                        style={{
                          fontFamily: "monospace",
                          fontSize: "0.75rem",
                          color: "#94a3b8",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {alert.incident_fingerprint}
                      </code>
                    </div>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(alert.incident_fingerprint, true)}
                      style={{
                        background: "rgba(255, 255, 255, 0.05)",
                        border: "1px solid #334155",
                        borderRadius: "4px",
                        color: copiedFingerprint ? "#34d399" : "#94a3b8",
                        padding: "4px 8px",
                        fontSize: "0.6875rem",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                        cursor: "pointer",
                        flexShrink: 0,
                      }}
                      title="Copy fingerprint to clipboard"
                    >
                      {copiedFingerprint ? <Check size={12} /> : <Copy size={12} />}
                      {copiedFingerprint ? "Copied" : "Copy"}
                    </button>
                  </div>

                  {/* Incident ID row */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "1rem",
                      paddingTop: "0.35rem",
                      borderTop: "1px dashed #1e293b",
                    }}
                  >
                    <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                      <span style={{ fontSize: "0.6875rem", color: "#64748b", textTransform: "uppercase" }}>
                        Case ID
                      </span>
                      <code
                        style={{
                          fontFamily: "monospace",
                          fontSize: "0.75rem",
                          color: "#64748b",
                        }}
                      >
                        {alert.id}
                      </code>
                    </div>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(alert.id, false)}
                      style={{
                        background: "rgba(255, 255, 255, 0.05)",
                        border: "1px solid #334155",
                        borderRadius: "4px",
                        color: copiedId ? "#34d399" : "#94a3b8",
                        padding: "4px 8px",
                        fontSize: "0.6875rem",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                        cursor: "pointer",
                        flexShrink: 0,
                      }}
                      title="Copy case ID to clipboard"
                    >
                      {copiedId ? <Check size={12} /> : <Copy size={12} />}
                      {copiedId ? "Copied" : "Copy"}
                    </button>
                  </div>
                </div>
              </div>
            </>
          ) : (
            /* SUGGESTED RESOLUTION TAB */
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              {resolution ? (
                <>
                  {/* OBSERVED VS RECOMMENDED SECTION */}
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "1rem",
                    }}
                  >
                    {/* OBSERVED BOX */}
                    <div
                      style={{
                        backgroundColor: "#1e293b",
                        border: "1px solid #334155",
                        borderRadius: "8px",
                        padding: "1rem 1.25rem",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "0.75rem",
                          fontWeight: 700,
                          textTransform: "uppercase",
                          letterSpacing: "0.075em",
                          color: "#94a3b8",
                          marginBottom: "0.35rem",
                        }}
                      >
                        Observed Condition
                      </div>
                      <p
                        style={{
                          margin: 0,
                          color: "#f8fafc",
                          fontSize: "0.9375rem",
                          lineHeight: 1.5,
                        }}
                      >
                        {resolution.observed}
                      </p>
                    </div>

                    {/* RECOMMENDED ACTION BOX */}
                    <div
                      style={{
                        backgroundColor: "rgba(56, 189, 248, 0.08)",
                        border: "1px solid rgba(56, 189, 248, 0.3)",
                        borderLeft: "4px solid #38bdf8",
                        borderRadius: "8px",
                        padding: "1rem 1.25rem",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "0.75rem",
                          fontWeight: 700,
                          textTransform: "uppercase",
                          letterSpacing: "0.075em",
                          color: "#38bdf8",
                          marginBottom: "0.35rem",
                        }}
                      >
                        Recommended Action
                      </div>
                      <p
                        style={{
                          margin: 0,
                          color: "#f8fafc",
                          fontSize: "0.9375rem",
                          fontWeight: 500,
                          lineHeight: 1.5,
                        }}
                      >
                        {resolution.recommended_action}
                      </p>

                      {/* WHY SUB-BOX */}
                      <div
                        style={{
                          marginTop: "0.75rem",
                          paddingTop: "0.75rem",
                          borderTop: "1px dashed rgba(56, 189, 248, 0.2)",
                        }}
                      >
                        <span
                          style={{
                            fontSize: "0.75rem",
                            fontWeight: 700,
                            textTransform: "uppercase",
                            letterSpacing: "0.05em",
                            color: "#94a3b8",
                            display: "block",
                            marginBottom: "2px",
                          }}
                        >
                          Why:
                        </span>
                        <span style={{ fontSize: "0.875rem", color: "#cbd5e1", lineHeight: 1.5 }}>
                          {resolution.reason}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* ACTION LINKS / DESTINATIONS */}
                  <div>
                    <h4
                      style={{
                        margin: "0 0 0.75rem 0",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: "0.075em",
                        color: "#64748b",
                      }}
                    >
                      Admin Actions & Investigations
                    </h4>

                    {resolution.actions.length === 0 ? (
                      <div
                        style={{
                          backgroundColor: "#1e293b",
                          padding: "1rem",
                          borderRadius: "8px",
                          color: "#94a3b8",
                          fontSize: "0.875rem",
                        }}
                      >
                        No predefined action links are registered for this alert. Review the incident details and take manual action as needed.
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                        {resolution.actions.map((act, index) => (
                          <div
                            key={index}
                            style={{
                              backgroundColor: "#1e293b",
                              border: "1px solid #334155",
                              borderRadius: "8px",
                              padding: "1rem 1.25rem",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              gap: "1rem",
                              transition: "all 0.15s ease",
                            }}
                          >
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ color: "#f8fafc", fontSize: "0.9375rem", fontWeight: 600, marginBottom: "2px" }}>
                                {act.label}
                              </div>
                              <div style={{ color: "#94a3b8", fontSize: "0.8125rem", lineHeight: 1.4 }}>
                                {act.reason}
                              </div>
                            </div>

                            <button
                              type="button"
                              onClick={() => handleActionNavigate(act.destination)}
                              style={{
                                backgroundColor: "#0284c7",
                                color: "#ffffff",
                                border: "none",
                                borderRadius: "6px",
                                padding: "0.5rem 0.875rem",
                                fontSize: "0.8125rem",
                                fontWeight: 600,
                                cursor: "pointer",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "6px",
                                flexShrink: 0,
                                transition: "background-color 0.15s ease",
                              }}
                              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#0369a1")}
                              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "#0284c7")}
                            >
                              {act.label} <ArrowUpRight size={15} />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div
                  style={{
                    backgroundColor: "#1e293b",
                    padding: "2rem",
                    borderRadius: "8px",
                    textAlign: "center",
                    color: "#94a3b8",
                  }}
                >
                  <p style={{ margin: 0, fontSize: "0.9375rem" }}>
                    No predefined resolution guidance is available for this alert type.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* FIXED FOOTER */}
        <div
          style={{
            flexShrink: 0,
            padding: "1rem 1.5rem",
            borderTop: "1px solid #1e293b",
            backgroundColor: "#0d1527",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "1rem",
          }}
        >
          {/* Status audit text */}
          <div style={{ fontSize: "0.8125rem", color: "#64748b" }}>
            {alert.status === AlertStatus.ACKNOWLEDGED && alert.acknowledged_at && (
              <span>Acknowledged: {formatGoBusDateTime(alert.acknowledged_at)}</span>
            )}
            {alert.status === AlertStatus.RESOLVED && alert.resolved_at && (
              <span>Resolved: {formatGoBusDateTime(alert.resolved_at)}</span>
            )}
            {alert.status === AlertStatus.OPEN && (
              <span style={{ color: "#f87171" }}>Incident awaiting triage</span>
            )}
          </div>

          {/* Action buttons (explicit mutations only) */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            {alert.status === AlertStatus.OPEN && (
              <button
                type="button"
                onClick={handleAckClick}
                disabled={actionLoading}
                style={{
                  backgroundColor: "rgba(245, 158, 11, 0.15)",
                  color: "#f59e0b",
                  border: "1px solid rgba(245, 158, 11, 0.4)",
                  borderRadius: "6px",
                  padding: "0.5rem 1rem",
                  fontSize: "0.875rem",
                  fontWeight: 600,
                  cursor: actionLoading ? "not-allowed" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <Check size={16} /> Acknowledge Incident
              </button>
            )}

            {alert.status !== AlertStatus.RESOLVED && (
              <button
                type="button"
                onClick={handleResolveClick}
                disabled={actionLoading}
                style={{
                  backgroundColor: "#059669",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  padding: "0.5rem 1rem",
                  fontSize: "0.875rem",
                  fontWeight: 600,
                  cursor: actionLoading ? "not-allowed" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#047857")}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "#059669")}
              >
                <CheckCheck size={16} /> Mark as Resolved
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              style={{
                backgroundColor: "rgba(255, 255, 255, 0.08)",
                color: "#e2e8f0",
                border: "1px solid #334155",
                borderRadius: "6px",
                padding: "0.5rem 1rem",
                fontSize: "0.875rem",
                fontWeight: 500,
                cursor: "pointer",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.15)")}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.08)")}
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
