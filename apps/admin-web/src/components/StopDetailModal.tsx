import React, { useEffect, useState, useMemo } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  X,
  MapPin,
  Route as RouteIcon,
  AlertTriangle,
  ExternalLink,
  Loader2,
  Compass,
  Tag,
} from "lucide-react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import { apiFetch, safeNumber } from "../api/api";
import { ErrorBoundary } from "./ErrorBoundary";

interface StopDetail {
  id: string;
  stop_code: string;
  name: string;
  latitude: number | string | null;
  longitude: number | string | null;
  status: string;
  aliases?: string[];
  created_at?: string;
  updated_at?: string;
}

interface RouteItem {
  id: string;
  route_code: string;
  route_name: string;
  distance_km?: number | string | null;
  status: string;
}

interface StopDetailModalProps {
  stopId: string;
  onClose: () => void;
  onRouteClick?: (routeId: string, routeCode?: string) => void;
}

// Leaflet map size invalidator and center updater
const StopMapController: React.FC<{ center: [number, number] }> = ({ center }) => {
  const map = useMap();

  useEffect(() => {
    if (!map) return;
    let timer: ReturnType<typeof setTimeout> | null = null;
    try {
      timer = setTimeout(() => {
        try {
          map.invalidateSize();
          map.setView(center, 15, { animate: false });
        } catch (e) {
          console.warn("Stop map view update error:", e);
        }
      }, 150);
    } catch (e) {
      console.warn("StopMapController error:", e);
    }

    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [center, map]);

  return null;
};

export const StopDetailModal: React.FC<StopDetailModalProps> = ({
  stopId,
  onClose,
  onRouteClick,
}) => {
  const [stop, setStop] = useState<StopDetail | null>(null);
  const [routes, setRoutes] = useState<RouteItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    let isMounted = true;

    const fetchDetails = async () => {
      try {
        setLoading(true);
        setError(null);
        const [stopData, routesData] = await Promise.all([
          apiFetch(`/admin/stops/${stopId}`),
          apiFetch(`/admin/stops/${stopId}/routes`).catch(() => []),
        ]);

        if (isMounted) {
          setStop(stopData);
          setRoutes(Array.isArray(routesData) ? routesData : []);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || "Failed to load stop details");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchDetails();

    return () => {
      isMounted = false;
    };
  }, [stopId]);

  // Coordinate normalization & range validation (-90..90, -180..180)
  const parsedCoords = useMemo(() => {
    if (!stop) return null;
    const lat = safeNumber(stop.latitude);
    const lon = safeNumber(stop.longitude);

    if (lat === null || lon === null) return null;
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;

    return {
      lat,
      lon,
      latFormatted: lat.toFixed(5),
      lonFormatted: lon.toFixed(5),
    };
  }, [stop]);

  // Format distance safely
  const formatRouteDistance = (val: unknown): string => {
    const num = safeNumber(val);
    if (num === null) return "—";
    return `${num.toFixed(2)} km`;
  };

  const handleRouteAction = (route: RouteItem) => {
    if (onRouteClick) {
      onRouteClick(route.id, route.route_code);
    } else {
      // Default fallback navigation with returnTo origin context
      navigate(`/routes/${route.id}`, {
        state: {
          returnTo: location.pathname + location.search,
          returnLabel: stop ? `Stop ${stop.stop_code}` : "Stops",
        },
      });
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="stop-detail-title"
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: "16px",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "840px",
          maxHeight: "90vh",
          backgroundColor: "#161922",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          borderRadius: "14px",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.6)",
        }}
      >
        {/* ── FIXED MODAL HEADER ── */}
        <div
          style={{
            flexShrink: 0,
            padding: "20px 24px",
            borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: "16px",
            backgroundColor: "#161922",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: "14px", minWidth: 0 }}>
            <div
              style={{
                width: "44px",
                height: "44px",
                borderRadius: "10px",
                backgroundColor: "rgba(56, 189, 248, 0.12)",
                border: "1px solid rgba(56, 189, 248, 0.25)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                marginTop: "2px",
              }}
            >
              <MapPin size={22} style={{ color: "#38bdf8" }} />
            </div>

            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  color: "#38bdf8",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  marginBottom: "4px",
                }}
              >
                STOP DETAILS
              </div>

              {loading ? (
                <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#94a3b8", fontSize: "15px" }}>
                  <Loader2 size={16} className="animate-spin" /> Loading stop...
                </div>
              ) : stop ? (
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                    <span
                      style={{
                        fontFamily: "monospace",
                        fontSize: "18px",
                        fontWeight: 700,
                        color: "#38bdf8",
                        backgroundColor: "rgba(56, 189, 248, 0.12)",
                        padding: "2px 8px",
                        borderRadius: "6px",
                        border: "1px solid rgba(56, 189, 248, 0.25)",
                      }}
                    >
                      {stop.stop_code}
                    </span>
                    <h2
                      id="stop-detail-title"
                      style={{
                        margin: 0,
                        fontSize: "18px",
                        fontWeight: 700,
                        color: "#f8fafc",
                        letterSpacing: "-0.01em",
                      }}
                    >
                      {stop.name}
                    </h2>
                    <span
                      style={{
                        fontSize: "11px",
                        fontWeight: 600,
                        padding: "3px 8px",
                        borderRadius: "4px",
                        backgroundColor:
                          stop.status === "ACTIVE"
                            ? "rgba(34, 197, 94, 0.15)"
                            : "rgba(148, 163, 184, 0.12)",
                        color: stop.status === "ACTIVE" ? "#4ade80" : "#94a3b8",
                        border:
                          stop.status === "ACTIVE"
                            ? "1px solid rgba(34, 197, 94, 0.3)"
                            : "1px solid rgba(148, 163, 184, 0.2)",
                      }}
                    >
                      {stop.status}
                    </span>
                  </div>
                </div>
              ) : (
                <div style={{ color: "#ef4444", fontSize: "15px", fontWeight: 600 }}>
                  Stop Not Found
                </div>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            style={{
              background: "none",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              padding: "6px",
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "color 0.15s ease, background-color 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "#f8fafc";
              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.06)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "#94a3b8";
              e.currentTarget.style.backgroundColor = "transparent";
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* ── SCROLLABLE MODAL BODY ── */}
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            overflowX: "hidden",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "24px",
          }}
        >
          {loading ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: "60px 0",
                gap: "12px",
                color: "#94a3b8",
              }}
            >
              <Loader2 size={28} className="animate-spin" style={{ color: "#38bdf8" }} />
              <span style={{ fontSize: "14px" }}>Loading stop location & routes...</span>
            </div>
          ) : error || !stop ? (
            <div
              style={{
                padding: "20px",
                borderRadius: "10px",
                backgroundColor: "rgba(239, 68, 68, 0.1)",
                border: "1px solid rgba(239, 68, 68, 0.25)",
                color: "#fca5a5",
                display: "flex",
                alignItems: "center",
                gap: "12px",
              }}
            >
              <AlertTriangle size={20} style={{ color: "#ef4444", flexShrink: 0 }} />
              <div>
                <strong style={{ display: "block", marginBottom: "4px" }}>Unable to load Stop details</strong>
                <span style={{ fontSize: "13px" }}>{error || "The requested stop was not found."}</span>
              </div>
            </div>
          ) : (
            <>
              {/* ── SECTION 1: STOP OVERVIEW & METADATA ── */}
              <div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginBottom: "14px",
                  }}
                >
                  <Compass size={16} style={{ color: "#38bdf8" }} />
                  <h3
                    style={{
                      fontSize: "12px",
                      fontWeight: 700,
                      color: "#94a3b8",
                      margin: 0,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                    }}
                  >
                    Stop Overview & Location
                  </h3>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                    gap: "12px",
                  }}
                >
                  {/* Latitude */}
                  <div
                    style={{
                      padding: "12px 14px",
                      backgroundColor: "#0d1017",
                      borderRadius: "8px",
                      border: "1px solid rgba(255, 255, 255, 0.05)",
                    }}
                  >
                    <div style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                      Latitude
                    </div>
                    <div style={{ fontWeight: 700, fontSize: "15px", color: "#f8fafc", fontFamily: "monospace" }}>
                      {parsedCoords ? parsedCoords.latFormatted : "—"}
                    </div>
                  </div>

                  {/* Longitude */}
                  <div
                    style={{
                      padding: "12px 14px",
                      backgroundColor: "#0d1017",
                      borderRadius: "8px",
                      border: "1px solid rgba(255, 255, 255, 0.05)",
                    }}
                  >
                    <div style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                      Longitude
                    </div>
                    <div style={{ fontWeight: 700, fontSize: "15px", color: "#f8fafc", fontFamily: "monospace" }}>
                      {parsedCoords ? parsedCoords.lonFormatted : "—"}
                    </div>
                  </div>

                  {/* Routes Using Stop */}
                  <div
                    style={{
                      padding: "12px 14px",
                      backgroundColor: "#0d1017",
                      borderRadius: "8px",
                      border: "1px solid rgba(255, 255, 255, 0.05)",
                    }}
                  >
                    <div style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                      Connected Routes
                    </div>
                    <div style={{ fontWeight: 700, fontSize: "15px", color: "#38bdf8", fontFamily: "monospace" }}>
                      {routes.length} {routes.length === 1 ? "Route" : "Routes"}
                    </div>
                  </div>

                  {/* Status */}
                  <div
                    style={{
                      padding: "12px 14px",
                      backgroundColor: "#0d1017",
                      borderRadius: "8px",
                      border: "1px solid rgba(255, 255, 255, 0.05)",
                    }}
                  >
                    <div style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                      Operational Status
                    </div>
                    <div style={{ fontWeight: 700, fontSize: "15px", color: stop.status === "ACTIVE" ? "#4ade80" : "#94a3b8" }}>
                      {stop.status}
                    </div>
                  </div>
                </div>

                {/* Aliases (if available) */}
                {Array.isArray(stop.aliases) && stop.aliases.length > 0 && (
                  <div style={{ marginTop: "12px", display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                    <span style={{ fontSize: "12px", color: "#64748b", display: "flex", alignItems: "center", gap: "4px" }}>
                      <Tag size={13} /> Aliases:
                    </span>
                    {stop.aliases.map((alias, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: "12px",
                          backgroundColor: "rgba(255, 255, 255, 0.04)",
                          color: "#cbd5e1",
                          padding: "2px 8px",
                          borderRadius: "4px",
                          border: "1px solid rgba(255, 255, 255, 0.06)",
                        }}
                      >
                        {alias}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* ── SECTION 2: STOP LOCATION MAP (Section 8, 9, 10, 21) ── */}
              <div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginBottom: "14px",
                  }}
                >
                  <MapPin size={16} style={{ color: "#4ade80" }} />
                  <h3
                    style={{
                      fontSize: "12px",
                      fontWeight: 700,
                      color: "#94a3b8",
                      margin: 0,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                    }}
                  >
                    Stop Location Map
                  </h3>
                </div>

                {parsedCoords ? (
                  <div
                    style={{
                      height: "300px",
                      width: "100%",
                      borderRadius: "10px",
                      overflow: "hidden",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      position: "relative",
                    }}
                  >
                    <ErrorBoundary fallbackTitle="Map Rendering Error" fallbackMessage="Unable to render map.">
                      <MapContainer
                        center={[parsedCoords.lat, parsedCoords.lon]}
                        zoom={15}
                        scrollWheelZoom={false}
                        style={{ height: "100%", width: "100%", backgroundColor: "#0f172a" }}
                      >
                        <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />
                        <Marker position={[parsedCoords.lat, parsedCoords.lon]}>
                          <Popup>
                            <div style={{ color: "#0f172a", fontSize: "12px", lineHeight: "1.4" }}>
                              <strong style={{ fontSize: "13px" }}>{stop.name}</strong>
                              <div>
                                Code: <code>{stop.stop_code}</code>
                              </div>
                              <div>
                                Coordinates: {parsedCoords.latFormatted}, {parsedCoords.lonFormatted}
                              </div>
                            </div>
                          </Popup>
                        </Marker>
                        <StopMapController center={[parsedCoords.lat, parsedCoords.lon]} />
                      </MapContainer>
                    </ErrorBoundary>
                  </div>
                ) : (
                  <div
                    style={{
                      padding: "24px",
                      borderRadius: "10px",
                      backgroundColor: "rgba(245, 158, 11, 0.06)",
                      border: "1px solid rgba(245, 158, 11, 0.2)",
                      display: "flex",
                      alignItems: "center",
                      gap: "14px",
                    }}
                  >
                    <AlertTriangle size={24} style={{ color: "#f59e0b", flexShrink: 0 }} />
                    <div>
                      <strong style={{ color: "#fbbf24", display: "block", marginBottom: "4px", fontSize: "14px" }}>
                        Map location unavailable
                      </strong>
                      <span style={{ color: "#cbd5e1", fontSize: "13px" }}>
                        This stop does not have valid coordinates configured.
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* ── SECTION 3: ROUTES USING THIS STOP (Section 11, 12, 17, 19, 24) ── */}
              <div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginBottom: "14px",
                  }}
                >
                  <RouteIcon size={16} style={{ color: "#818cf8" }} />
                  <h3
                    style={{
                      fontSize: "12px",
                      fontWeight: 700,
                      color: "#94a3b8",
                      margin: 0,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                    }}
                  >
                    Routes Using This Stop ({routes.length})
                  </h3>
                </div>

                {routes.length === 0 ? (
                  <div
                    style={{
                      padding: "28px 16px",
                      textAlign: "center",
                      color: "#64748b",
                      fontSize: "14px",
                      backgroundColor: "rgba(255, 255, 255, 0.02)",
                      borderRadius: "8px",
                      border: "1px solid rgba(255, 255, 255, 0.04)",
                    }}
                  >
                    No routes currently use this stop.
                  </div>
                ) : (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: "10px",
                    }}
                  >
                    {routes.map((route) => (
                      <div
                        key={route.id}
                        style={{
                          padding: "14px 18px",
                          borderRadius: "10px",
                          backgroundColor: "#0d1017",
                          border: "1px solid rgba(255, 255, 255, 0.06)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          flexWrap: "wrap",
                          gap: "12px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "12px", minWidth: 0 }}>
                          <span
                            style={{
                              fontFamily: "monospace",
                              fontSize: "13px",
                              fontWeight: 700,
                              color: "#38bdf8",
                              backgroundColor: "rgba(56, 189, 248, 0.1)",
                              padding: "3px 8px",
                              borderRadius: "4px",
                              border: "1px solid rgba(56, 189, 248, 0.2)",
                              flexShrink: 0,
                            }}
                          >
                            {route.route_code}
                          </span>

                          <div style={{ minWidth: 0 }}>
                            <div
                              style={{
                                fontSize: "14px",
                                fontWeight: 600,
                                color: "#f8fafc",
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                              }}
                            >
                              {route.route_name}
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginTop: "2px", fontSize: "12px", color: "#64748b" }}>
                              <span>Distance: <strong style={{ color: "#94a3b8" }}>{formatRouteDistance(route.distance_km)}</strong></span>
                              <span>•</span>
                              <span
                                style={{
                                  fontSize: "10px",
                                  fontWeight: 600,
                                  padding: "1px 6px",
                                  borderRadius: "3px",
                                  backgroundColor:
                                    route.status === "ACTIVE"
                                      ? "rgba(34, 197, 94, 0.12)"
                                      : "rgba(148, 163, 184, 0.1)",
                                  color: route.status === "ACTIVE" ? "#4ade80" : "#94a3b8",
                                }}
                              >
                                {route.status}
                              </span>
                            </div>
                          </div>
                        </div>

                        <button
                          type="button"
                          onClick={() => handleRouteAction(route)}
                          style={{
                            padding: "6px 14px",
                            backgroundColor: "rgba(56, 189, 248, 0.12)",
                            border: "1px solid rgba(56, 189, 248, 0.3)",
                            borderRadius: "6px",
                            color: "#38bdf8",
                            fontSize: "13px",
                            fontWeight: 600,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                            transition: "all 0.15s ease",
                            flexShrink: 0,
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = "rgba(56, 189, 248, 0.2)";
                            e.currentTarget.style.borderColor = "#38bdf8";
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = "rgba(56, 189, 248, 0.12)";
                            e.currentTarget.style.borderColor = "rgba(56, 189, 248, 0.3)";
                          }}
                        >
                          <span>View Route</span>
                          <ExternalLink size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
