import React, { useEffect, useState, useMemo } from "react";
import {
  X,
  Network,
  Banknote,
  Map as MapIcon,
  Bus,
  CalendarClock,
  ExternalLink,
  List,
  AlertCircle,
  Loader2,
  Compass,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from "react-leaflet";
import type * as L from "leaflet";
import { ErrorBoundary } from "./ErrorBoundary";
import {
  apiFetch,
  safeNumber,
  type FareConfigurationItem,
  type FleetScheduleItem,
} from "../api/api";

interface ServiceDetail {
  id: string;
  service_code: string;
  service_name: string;
  status: string;
  route_id: string;
  route_code?: string;
  route_name?: string;
  fare_configuration_id: string | null;
  fare_configuration_name?: string;
  fare_is_active?: boolean;
  fare_slabs_count?: number;
  fare_currency?: string;
  created_at?: string;
  updated_at?: string;
}

interface RouteStop {
  id: string;
  route_id: string;
  stop_id: string;
  stop_code?: string;
  stop_name?: string;
  sequence_number: number;
  distance_from_start?: number | null;
  nominal_travel_time_seconds?: number | null;
  latitude?: number | null;
  longitude?: number | null;
}

interface ServiceScheduleItem {
  id: string;
  direction: string;
  start_time: string;
  end_time: string;
  typical_interval_minutes: number;
  days_of_week: number[];
  status: string;
}

interface DepotScheduleItem {
  id: string;
  vehicle_id: string;
  planned_departure: string;
  actual_departure?: string;
  status: string;
  vehicle?: {
    id: string;
    vehicle_number: string;
    vehicle_type: string;
    registration_number?: string | null;
  };
}

interface ServiceDetailModalProps {
  serviceId: string;
  onClose: () => void;
  onManageSchedules?: (serviceId: string) => void;
  onManageFare?: (fareId: string) => void;
  onManageFleet?: (serviceId: string) => void;
  onViewRoute?: (routeId: string) => void;
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function formatDays(days: number[] | string[] | undefined): string {
  if (!days || days.length === 0) return "—";
  if (typeof days[0] === "string") return days.join(", ");
  const numDays = (days as number[]).filter((d) => typeof d === "number" && d >= 1 && d <= 7);
  if (numDays.length === 7) return "Every day";
  if (numDays.length === 5 && [1, 2, 3, 4, 5].every((d) => numDays.includes(d))) return "Mon–Fri";
  if (numDays.length === 2 && [6, 7].every((d) => numDays.includes(d))) return "Weekends";

  return numDays
    .sort()
    .map((d) => DAY_NAMES[d - 1])
    .join(", ");
}

const formatKm = (val: unknown): string => {
  const num = safeNumber(val);
  if (num === null) return "—";
  return `${num.toFixed(2)} km`;
};

// Leaflet Map Bounds Auto-Fit Wrapper
const BoundsWrapper = ({ bounds }: { bounds: L.LatLngBounds | null }) => {
  const map = useMap();
  useEffect(() => {
    if (!bounds || !bounds.isValid()) return;
    let timer: ReturnType<typeof setTimeout> | null = null;
    try {
      timer = setTimeout(() => {
        if (map && bounds.isValid()) {
          try {
            map.invalidateSize();
            map.fitBounds(bounds, { padding: [25, 25], maxZoom: 15, animate: false });
          } catch (e) {
            console.warn("fitBounds safely handled:", e);
          }
        }
      }, 150);
    } catch (e) {
      console.warn("BoundsWrapper error:", e);
    }
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [bounds, map]);
  return null;
};

export const ServiceDetailModal: React.FC<ServiceDetailModalProps> = ({
  serviceId,
  onClose,
  onManageSchedules,
  onManageFare,
  onManageFleet,
  onViewRoute,
}) => {
  const navigate = useNavigate();

  const [service, setService] = useState<ServiceDetail | null>(null);
  const [stops, setStops] = useState<RouteStop[]>([]);
  const [routeGeometry, setRouteGeometry] = useState<any | null>(null);
  const [fareConfig, setFareConfig] = useState<FareConfigurationItem | null>(null);
  const [serviceSchedules, setServiceSchedules] = useState<ServiceScheduleItem[]>([]);
  const [fleetSchedules, setFleetSchedules] = useState<FleetScheduleItem[]>([]);
  const [todayFleet, setTodayFleet] = useState<DepotScheduleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Tab toggle between Stops List and Map View
  const [activeTab, setActiveTab] = useState<"stops" | "map">("stops");

  useEffect(() => {
    let isMounted = true;

    async function fetchAllDetails() {
      try {
        setLoading(true);
        setError(null);

        // 1. Fetch Service basic details
        const svcData: ServiceDetail = await apiFetch(`/admin/services/${serviceId}`);
        if (!isMounted) return;
        setService(svcData);

        // 2. Concurrently fetch related entities
        const routeId = svcData.route_id;
        const fareId = svcData.fare_configuration_id;

        const promises: Promise<any>[] = [
          // Route stops
          routeId ? apiFetch(`/admin/routes/${routeId}/stops`).catch(() => []) : Promise.resolve([]),
          // Route details (for geometry)
          routeId ? apiFetch(`/admin/routes/${routeId}`).catch(() => null) : Promise.resolve(null),
          // All stops (for lat/lng coordinates)
          apiFetch("/admin/stops").catch(() => []),
          // Fare config
          fareId ? apiFetch(`/admin/fares/${fareId}`).catch(() => null) : Promise.resolve(null),
          // Service Schedules (passenger timetable)
          apiFetch(`/admin/services/${serviceId}/schedules`).catch(() => []),
          // Fleet Schedules (operational recurring timetable)
          apiFetch(`/admin/fleet-schedules?service_id=${serviceId}`).catch(() => []),
          // Today's Depot dispatch
          apiFetch("/admin/depot-schedules").catch(() => []),
        ];

        const [
          stopsData,
          routeData,
          allStopsData,
          fareData,
          svcSchedData,
          fleetSchedData,
          depotData,
        ] = await Promise.all(promises);

        if (!isMounted) return;

        // Hydrate stops with lat/lng coordinates from allStopsData
        const stopCoordMap = new Map<string, { lat: number; lng: number }>();
        if (Array.isArray(allStopsData)) {
          allStopsData.forEach((s: any) => {
            if (s.id && s.latitude !== undefined && s.longitude !== undefined) {
              stopCoordMap.set(s.id, { lat: s.latitude, lng: s.longitude });
            }
          });
        }

        const hydratedStops: RouteStop[] = Array.isArray(stopsData)
          ? stopsData.map((rs: any) => {
              const coords = stopCoordMap.get(rs.stop_id);
              return {
                ...rs,
                latitude: coords?.lat ?? null,
                longitude: coords?.lng ?? null,
              };
            })
          : [];

        setStops(hydratedStops);
        setRouteGeometry(routeData?.geometry || null);
        setFareConfig(fareData);
        setServiceSchedules(Array.isArray(svcSchedData) ? svcSchedData : []);
        setFleetSchedules(Array.isArray(fleetSchedData) ? fleetSchedData : []);

        // Filter today's fleet for this service
        if (Array.isArray(depotData)) {
          const matching = depotData.filter(
            (d: any) => d.service_id === serviceId || d.service?.id === serviceId
          );
          setTodayFleet(matching);
        } else {
          setTodayFleet([]);
        }
      } catch (err: any) {
        if (!isMounted) return;
        setError(err.message || "Failed to load service details.");
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchAllDetails();

    return () => {
      isMounted = false;
    };
  }, [serviceId]);

  // Derive Schedule Summary strictly according to Product Rule 8:
  // - If ServiceSchedule exists: First Bus = start_time, Last Bus = end_time, Frequency = typical_interval_minutes, Operating Days = days_of_week
  // - When NO ServiceSchedule but FleetSchedule exists: First Bus = earliest departure, Last Bus = latest departure.
  //   Frequency MUST NOT be fabricated from differences between arbitrary departure times -> "Not configured"
  // - When neither exists: "—" and show "No schedules configured for this service."
  const scheduleSummary = useMemo(() => {
    // 1. ServiceSchedule (passenger-facing timetable)
    if (serviceSchedules.length > 0) {
      const sorted = [...serviceSchedules].sort((a, b) =>
        (a.start_time || "").localeCompare(b.start_time || "")
      );
      const firstBus = sorted[0].start_time ? sorted[0].start_time.slice(0, 5) : "—";
      const lastBus = sorted[sorted.length - 1].end_time
        ? sorted[sorted.length - 1].end_time.slice(0, 5)
        : "—";

      const intervals = serviceSchedules
        .map((s) => s.typical_interval_minutes)
        .filter((n) => typeof n === "number" && n > 0);
      const frequency = intervals.length > 0 ? `Every ${intervals[0]} mins` : "Not configured";

      const allDays = new Set<number>();
      serviceSchedules.forEach((s) =>
        (s.days_of_week || []).forEach((d) => allDays.add(d))
      );
      const operatingDays = formatDays(Array.from(allDays));
      const directions = Array.from(new Set(serviceSchedules.map((s) => s.direction)));

      return {
        firstBus,
        lastBus,
        frequency,
        operatingDays,
        directions,
        totalConfigured: serviceSchedules.length,
        hasSchedules: true,
        source: "service_schedule" as const,
      };
    }

    // 2. FleetSchedule (operational recurring timetable departures)
    if (fleetSchedules.length > 0) {
      const sorted = [...fleetSchedules].sort((a, b) =>
        (a.departure_time || "").localeCompare(b.departure_time || "")
      );
      const firstBus =
        sorted[0].formatted_departure_time ||
        (sorted[0].departure_time ? sorted[0].departure_time.slice(0, 5) : "—");
      const lastBus =
        sorted[sorted.length - 1].formatted_departure_time ||
        (sorted[sorted.length - 1].departure_time
          ? sorted[sorted.length - 1].departure_time.slice(0, 5)
          : "—");

      // Requirement 8: Frequency MUST NOT be fabricated from differences between arbitrary departure times.
      const frequency = "Not configured";

      const allEveryDay = fleetSchedules.every((s) => s.every_day);
      const operatingDays = allEveryDay ? "Every day" : "Scheduled dates";
      const directions = Array.from(new Set(fleetSchedules.map((s) => s.direction)));

      return {
        firstBus,
        lastBus,
        frequency,
        operatingDays,
        directions,
        totalConfigured: fleetSchedules.length,
        hasSchedules: true,
        source: "fleet_schedule" as const,
      };
    }

    // 3. Neither source exists
    return {
      firstBus: "—",
      lastBus: "—",
      frequency: "—",
      operatingDays: "—",
      directions: [],
      totalConfigured: 0,
      hasSchedules: false,
      source: "none" as const,
    };
  }, [serviceSchedules, fleetSchedules]);

  // Total Route Distance (derived authoritatively from route stops)
  const totalRouteDistance = useMemo(() => {
    if (stops.length > 0) {
      const lastStop = stops[stops.length - 1];
      const dist = safeNumber(lastStop.distance_from_start);
      if (dist !== null) return formatKm(dist);
    }
    return "—";
  }, [stops]);

  // Map Polyline and Stop Markers
  const { polylinePositions, stopMarkers, mapBounds } = useMemo(() => {
    let positions: [number, number][] = [];
    if (
      routeGeometry &&
      routeGeometry.type === "LineString" &&
      Array.isArray(routeGeometry.coordinates)
    ) {
      positions = routeGeometry.coordinates
        .filter(
          (c: any) =>
            Array.isArray(c) && c.length >= 2 && !isNaN(Number(c[0])) && !isNaN(Number(c[1]))
        )
        .map(([lng, lat]: [number, number]) => [Number(lat), Number(lng)] as [number, number]);
    }

    const markers: {
      latlng: [number, number];
      stop_name: string;
      stop_code: string;
      sequence: number;
    }[] = [];

    stops.forEach((s) => {
      const lat = safeNumber(s.latitude);
      const lng = safeNumber(s.longitude);
      if (lat !== null && lng !== null) {
        markers.push({
          latlng: [lat, lng],
          stop_name: s.stop_name || "Stop",
          stop_code: s.stop_code || "",
          sequence: s.sequence_number,
        });
      }
    });

    // Fall back to connecting stop markers if route polyline coordinates are empty
    if (positions.length === 0 && markers.length >= 2) {
      positions = markers.map((m) => m.latlng);
    }

    // Calculate bounds if any points exist
    let bounds: L.LatLngBounds | null = null;
    const allPoints = positions.length > 0 ? positions : markers.map((m) => m.latlng);
    if (allPoints.length > 0 && typeof window !== "undefined") {
      const lats = allPoints.map((p) => p[0]);
      const lngs = allPoints.map((p) => p[1]);
      const minLat = Math.min(...lats);
      const maxLat = Math.max(...lats);
      const minLng = Math.min(...lngs);
      const maxLng = Math.max(...lngs);
      if (!isNaN(minLat) && !isNaN(maxLat) && !isNaN(minLng) && !isNaN(maxLng)) {
        bounds = [[minLat, minLng], [maxLat, maxLng]] as any;
      }
    }

    return { polylinePositions: positions, stopMarkers: markers, mapBounds: bounds };
  }, [routeGeometry, stops]);

  // Navigation handlers with fallback to direct routing
  const handleViewRoute = () => {
    if (!service?.route_id) return;
    if (onViewRoute) {
      onViewRoute(service.route_id);
    } else {
      navigate(`/routes?routeId=${service.route_id}`);
    }
  };

  const handleManageFare = () => {
    const targetFareId = fareConfig?.id || service?.fare_configuration_id;
    if (!targetFareId) return;
    if (onManageFare) {
      onManageFare(targetFareId);
    } else {
      navigate(`/fares?fareId=${targetFareId}`);
    }
  };

  const handleManageSchedules = () => {
    if (!service?.id) return;
    if (onManageSchedules) {
      onManageSchedules(service.id);
    } else {
      navigate(`/fleet-schedules?serviceId=${service.id}`);
    }
  };

  const handleManageFleet = () => {
    if (!service?.id) return;
    if (onManageFleet) {
      onManageFleet(service.id);
    } else {
      navigate(`/vehicles?serviceId=${service.id}`);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10000,
        padding: "20px",
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: "#161922",
          border: "1px solid rgba(255, 255, 255, 0.15)",
          borderRadius: "14px",
          width: "100%",
          maxWidth: "960px",
          maxHeight: "90vh",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          color: "#f8fafc",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* FIXED HEADER: Answers "What Service is this?", "What is its code?", "Is it active?" */}
        <div
          style={{
            padding: "18px 24px",
            borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            backgroundColor: "rgba(255, 255, 255, 0.02)",
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px", minWidth: 0 }}>
            <div
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "10px",
                backgroundColor: "rgba(99, 102, 241, 0.15)",
                border: "1px solid rgba(99, 102, 241, 0.3)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Bus size={22} style={{ color: "#818cf8" }} />
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <h3
                  style={{
                    fontSize: "18px",
                    fontWeight: 700,
                    margin: 0,
                    color: "#f8fafc",
                    letterSpacing: "-0.01em",
                  }}
                >
                  {loading ? "Loading Service..." : service?.service_code || "Service Details"}
                </h3>
                {service?.status && (
                  <span
                    style={{
                      fontSize: "11px",
                      fontWeight: 600,
                      padding: "2px 8px",
                      borderRadius: "4px",
                      backgroundColor:
                        service.status === "ACTIVE"
                          ? "rgba(34, 197, 94, 0.12)"
                          : "rgba(148, 163, 184, 0.12)",
                      color: service.status === "ACTIVE" ? "#4ade80" : "#94a3b8",
                      border:
                        service.status === "ACTIVE"
                          ? "1px solid rgba(34, 197, 94, 0.25)"
                          : "1px solid rgba(148, 163, 184, 0.2)",
                    }}
                  >
                    {service.status}
                  </span>
                )}
              </div>
              <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "2px" }}>
                {service ? `${service.service_name} · ${service.service_code}` : "Operational Details"}
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            title="Close dialog"
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              padding: "6px",
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.15s ease",
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
            <X size={18} />
          </button>
        </div>

        {/* ONE SCROLLABLE BODY: The parent modal body is the ONLY vertical scrolling container */}
        <div
          style={{
            padding: "24px",
            overflowY: "auto",
            flex: 1,
            minHeight: 0,
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          {loading ? (
            <div
              style={{
                padding: "60px 20px",
                textAlign: "center",
                color: "#94a3b8",
                fontSize: "14px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "12px",
              }}
            >
              <Loader2 size={26} className="animate-spin" style={{ color: "#818cf8" }} />
              <span>Loading service operational details...</span>
            </div>
          ) : error || !service ? (
            <div
              style={{
                padding: "20px",
                borderRadius: "8px",
                backgroundColor: "rgba(239, 68, 68, 0.1)",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                color: "#f87171",
                fontSize: "14px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <AlertCircle size={18} />
              <span>{error || "Service details not found."}</span>
            </div>
          ) : (
            <>
              {/* 1. SERVICE OVERVIEW: Compact operational summary answering basic operational questions */}
              <div
                style={{
                  backgroundColor: "rgba(255, 255, 255, 0.02)",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  borderRadius: "10px",
                  padding: "16px 20px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                  <Compass size={16} style={{ color: "#818cf8" }} />
                  <h4
                    style={{
                      fontSize: "12px",
                      fontWeight: 700,
                      color: "#94a3b8",
                      margin: 0,
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    Service Overview
                  </h4>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                    gap: "14px",
                  }}
                >
                  <div>
                    <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Route</span>
                    <p style={{ margin: "2px 0 0", fontSize: "13px", fontWeight: 600, color: "#f8fafc" }}>
                      {service.route_code || "—"}
                    </p>
                  </div>

                  <div>
                    <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Total Distance</span>
                    <p style={{ margin: "2px 0 0", fontSize: "13px", fontWeight: 600, color: "#f8fafc" }}>
                      {totalRouteDistance}
                    </p>
                  </div>

                  <div>
                    <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>First Bus</span>
                    <p style={{ margin: "2px 0 0", fontSize: "13px", fontWeight: 600, color: "#4ade80" }}>
                      {scheduleSummary.firstBus}
                    </p>
                  </div>

                  <div>
                    <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Last Bus</span>
                    <p style={{ margin: "2px 0 0", fontSize: "13px", fontWeight: 600, color: "#4ade80" }}>
                      {scheduleSummary.lastBus}
                    </p>
                  </div>

                  <div>
                    <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Frequency</span>
                    <p style={{ margin: "2px 0 0", fontSize: "13px", fontWeight: 600, color: "#cbd5e1" }}>
                      {scheduleSummary.frequency}
                    </p>
                  </div>

                  <div>
                    <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Operating Days</span>
                    <p style={{ margin: "2px 0 0", fontSize: "13px", fontWeight: 600, color: "#cbd5e1" }}>
                      {scheduleSummary.operatingDays}
                    </p>
                  </div>
                </div>
              </div>

              {/* 2. CONNECTED ENTITIES: ROUTE & FARE */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }}>
                {/* ROUTE CARD */}
                <div
                  style={{
                    backgroundColor: "rgba(255, 255, 255, 0.02)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: "10px",
                    padding: "16px 20px",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Network size={16} style={{ color: "#818cf8" }} />
                        <span style={{ fontSize: "12px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                          Route
                        </span>
                      </div>
                      <span style={{ fontSize: "12px", color: "#64748b" }}>{stops.length} stops</span>
                    </div>

                    <div style={{ marginTop: "4px" }}>
                      <p style={{ margin: 0, fontSize: "15px", fontWeight: 700, color: "#f8fafc" }}>
                        {service.route_code || "Unknown Route"}
                      </p>
                      <p style={{ margin: "4px 0 0", fontSize: "13px", color: "#cbd5e1" }}>
                        {service.route_name || "—"}
                      </p>
                    </div>

                    <div style={{ marginTop: "8px", display: "flex", alignItems: "center", gap: "12px", fontSize: "12px", color: "#94a3b8" }}>
                      <span>Distance: <strong style={{ color: "#f8fafc" }}>{totalRouteDistance}</strong></span>
                    </div>
                  </div>

                  <div style={{ marginTop: "16px", borderTop: "1px solid rgba(255, 255, 255, 0.06)", paddingTop: "12px" }}>
                    <button
                      type="button"
                      onClick={handleViewRoute}
                      disabled={!service.route_id}
                      style={{
                        padding: "6px 14px",
                        backgroundColor: "rgba(99, 102, 241, 0.1)",
                        border: "1px solid rgba(99, 102, 241, 0.25)",
                        borderRadius: "6px",
                        color: "#818cf8",
                        fontSize: "12px",
                        fontWeight: 600,
                        cursor: service.route_id ? "pointer" : "not-allowed",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        transition: "all 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        if (service.route_id) {
                          e.currentTarget.style.backgroundColor = "rgba(99, 102, 241, 0.2)";
                          e.currentTarget.style.color = "#a5b4fc";
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (service.route_id) {
                          e.currentTarget.style.backgroundColor = "rgba(99, 102, 241, 0.1)";
                          e.currentTarget.style.color = "#818cf8";
                        }
                      }}
                    >
                      <ExternalLink size={13} /> View Route
                    </button>
                  </div>
                </div>

                {/* FARE CARD */}
                <div
                  style={{
                    backgroundColor: "rgba(255, 255, 255, 0.02)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: "10px",
                    padding: "16px 20px",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <Banknote size={16} style={{ color: "#34d399" }} />
                        <span style={{ fontSize: "12px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                          Fare
                        </span>
                      </div>
                      {fareConfig && (
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: 600,
                            padding: "2px 6px",
                            borderRadius: "4px",
                            backgroundColor: fareConfig.is_active ? "rgba(34, 197, 94, 0.12)" : "rgba(148, 163, 184, 0.12)",
                            color: fareConfig.is_active ? "#4ade80" : "#94a3b8",
                            border: fareConfig.is_active ? "1px solid rgba(34, 197, 94, 0.25)" : "1px solid rgba(148, 163, 184, 0.2)",
                          }}
                        >
                          {fareConfig.is_active ? "Active" : "Inactive"}
                        </span>
                      )}
                    </div>

                    <div style={{ marginTop: "4px" }}>
                      <p style={{ margin: 0, fontSize: "15px", fontWeight: 700, color: "#f8fafc" }}>
                        {fareConfig?.name || service.fare_configuration_name || "No fare attached"}
                      </p>
                      <div style={{ marginTop: "4px", display: "flex", alignItems: "center", gap: "10px", fontSize: "12px", color: "#cbd5e1" }}>
                        <span>
                          {fareConfig?.slabs?.length ?? service.fare_slabs_count ?? 0} slabs
                        </span>
                        <span>•</span>
                        <span>Currency: {fareConfig?.currency || service.fare_currency || "INR"}</span>
                      </div>
                    </div>
                  </div>

                  <div style={{ marginTop: "16px", borderTop: "1px solid rgba(255, 255, 255, 0.06)", paddingTop: "12px" }}>
                    <button
                      type="button"
                      onClick={handleManageFare}
                      disabled={!fareConfig && !service.fare_configuration_id}
                      style={{
                        padding: "6px 14px",
                        backgroundColor: "rgba(52, 211, 153, 0.1)",
                        border: "1px solid rgba(52, 211, 153, 0.25)",
                        borderRadius: "6px",
                        color: "#34d399",
                        fontSize: "12px",
                        fontWeight: 600,
                        cursor: fareConfig || service.fare_configuration_id ? "pointer" : "not-allowed",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        transition: "all 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        if (fareConfig || service.fare_configuration_id) {
                          e.currentTarget.style.backgroundColor = "rgba(52, 211, 153, 0.18)";
                          e.currentTarget.style.color = "#6ee7b7";
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (fareConfig || service.fare_configuration_id) {
                          e.currentTarget.style.backgroundColor = "rgba(52, 211, 153, 0.1)";
                          e.currentTarget.style.color = "#34d399";
                        }
                      }}
                    >
                      <ExternalLink size={13} /> View Fare Chart
                    </button>
                  </div>
                </div>
              </div>

              {/* 3. OPERATING SCHEDULE SECTION */}
              <div
                style={{
                  backgroundColor: "rgba(255, 255, 255, 0.02)",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  borderRadius: "10px",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    padding: "14px 20px",
                    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    backgroundColor: "rgba(255, 255, 255, 0.02)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <CalendarClock size={16} style={{ color: "#60a5fa" }} />
                    <h4
                      style={{
                        fontSize: "12px",
                        fontWeight: 700,
                        color: "#94a3b8",
                        margin: 0,
                        textTransform: "uppercase",
                        letterSpacing: "0.04em",
                      }}
                    >
                      Operating Schedule
                    </h4>
                  </div>
                  <button
                    type="button"
                    onClick={handleManageSchedules}
                    style={{
                      padding: "5px 12px",
                      backgroundColor: "rgba(99, 102, 241, 0.1)",
                      border: "1px solid rgba(99, 102, 241, 0.25)",
                      borderRadius: "6px",
                      color: "#818cf8",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <ExternalLink size={12} /> Manage Schedules
                  </button>
                </div>

                <div style={{ padding: "16px 20px" }}>
                  {!scheduleSummary.hasSchedules ? (
                    <div style={{ textAlign: "center", padding: "16px 0", color: "#64748b", fontSize: "13px" }}>
                      No schedules configured for this service.
                    </div>
                  ) : (
                    <div>
                      {/* Operational Schedule Overview Grid */}
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                          gap: "12px",
                          marginBottom: "16px",
                        }}
                      >
                        <div style={{ backgroundColor: "rgba(0, 0, 0, 0.2)", padding: "10px 14px", borderRadius: "6px" }}>
                          <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>First Departure</span>
                          <p style={{ margin: "2px 0 0", fontSize: "13px", fontWeight: 700, color: "#4ade80" }}>
                            {scheduleSummary.firstBus}
                          </p>
                        </div>

                        <div style={{ backgroundColor: "rgba(0, 0, 0, 0.2)", padding: "10px 14px", borderRadius: "6px" }}>
                          <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Last Departure</span>
                          <p style={{ margin: "2px 0 0", fontSize: "13px", fontWeight: 700, color: "#4ade80" }}>
                            {scheduleSummary.lastBus}
                          </p>
                        </div>

                        <div style={{ backgroundColor: "rgba(0, 0, 0, 0.2)", padding: "10px 14px", borderRadius: "6px" }}>
                          <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Frequency / Headway</span>
                          <p style={{ margin: "2px 0 0", fontSize: "13px", fontWeight: 600, color: "#f8fafc" }}>
                            {scheduleSummary.frequency}
                          </p>
                        </div>

                        <div style={{ backgroundColor: "rgba(0, 0, 0, 0.2)", padding: "10px 14px", borderRadius: "6px" }}>
                          <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Operating Days</span>
                          <p style={{ margin: "2px 0 0", fontSize: "13px", fontWeight: 600, color: "#f8fafc" }}>
                            {scheduleSummary.operatingDays}
                          </p>
                        </div>

                        <div style={{ backgroundColor: "rgba(0, 0, 0, 0.2)", padding: "10px 14px", borderRadius: "6px" }}>
                          <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Direction(s)</span>
                          <p style={{ margin: "2px 0 0", fontSize: "13px", fontWeight: 600, color: "#f8fafc" }}>
                            {scheduleSummary.directions.length > 0 ? scheduleSummary.directions.join(", ") : "Both"}
                          </p>
                        </div>
                      </div>

                      {/* Departures Table / List */}
                      {fleetSchedules.length > 0 && (
                        <div style={{ border: "1px solid rgba(255, 255, 255, 0.06)", borderRadius: "6px", overflow: "hidden" }}>
                          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", textAlign: "left" }}>
                            <thead>
                              <tr style={{ backgroundColor: "#1b1f2b", borderBottom: "1px solid rgba(255, 255, 255, 0.08)" }}>
                                <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600 }}>Departure</th>
                                <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600 }}>Vehicle</th>
                                <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600 }}>Direction</th>
                                <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600 }}>Frequency Mode</th>
                              </tr>
                            </thead>
                            <tbody>
                              {fleetSchedules.slice(0, 5).map((fs) => (
                                <tr key={fs.id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                                  <td style={{ padding: "8px 12px", fontFamily: "monospace", fontWeight: 600, color: "#4ade80" }}>
                                    {fs.formatted_departure_time || fs.departure_time?.slice(0, 5)}
                                  </td>
                                  <td style={{ padding: "8px 12px", color: "#f8fafc" }}>
                                    {fs.vehicle_number}
                                  </td>
                                  <td style={{ padding: "8px 12px" }}>
                                    <span
                                      style={{
                                        fontSize: "11px",
                                        padding: "2px 6px",
                                        borderRadius: "4px",
                                        backgroundColor: fs.direction === "A_TO_B" ? "rgba(99, 102, 241, 0.12)" : "rgba(168, 85, 247, 0.12)",
                                        color: fs.direction === "A_TO_B" ? "#818cf8" : "#c084fc",
                                      }}
                                    >
                                      {fs.direction}
                                    </span>
                                  </td>
                                  <td style={{ padding: "8px 12px", color: "#94a3b8" }}>
                                    {fs.every_day ? "Every Day (Daily)" : "Specific Dates"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {fleetSchedules.length > 5 && (
                            <div style={{ padding: "8px 12px", fontSize: "11px", color: "#64748b", textAlign: "center", backgroundColor: "rgba(0, 0, 0, 0.15)" }}>
                              Showing 5 of {fleetSchedules.length} departures. Click "Manage Schedules" to view all.
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* 4. TODAY'S SERVICE FLEET / DISPATCH SECTION */}
              <div
                style={{
                  backgroundColor: "rgba(255, 255, 255, 0.02)",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  borderRadius: "10px",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    padding: "14px 20px",
                    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    backgroundColor: "rgba(255, 255, 255, 0.02)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Bus size={16} style={{ color: "#f59e0b" }} />
                    <h4
                      style={{
                        fontSize: "12px",
                        fontWeight: 700,
                        color: "#94a3b8",
                        margin: 0,
                        textTransform: "uppercase",
                        letterSpacing: "0.04em",
                      }}
                    >
                      Today's Service Fleet / Dispatch
                    </h4>
                  </div>
                  <button
                    type="button"
                    onClick={handleManageFleet}
                    style={{
                      padding: "5px 12px",
                      backgroundColor: "rgba(245, 158, 11, 0.1)",
                      border: "1px solid rgba(245, 158, 11, 0.25)",
                      borderRadius: "6px",
                      color: "#fbbf24",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <ExternalLink size={12} /> Manage Fleet
                  </button>
                </div>

                <div style={{ padding: "16px 20px" }}>
                  {todayFleet.length === 0 ? (
                    <div style={{ textAlign: "center", padding: "16px 0", color: "#64748b", fontSize: "13px" }}>
                      No vehicles assigned to this service today.
                    </div>
                  ) : (
                    <div style={{ border: "1px solid rgba(255, 255, 255, 0.06)", borderRadius: "6px", overflow: "hidden" }}>
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", textAlign: "left" }}>
                        <thead>
                          <tr style={{ backgroundColor: "#1b1f2b", borderBottom: "1px solid rgba(255, 255, 255, 0.08)" }}>
                            <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600 }}>Vehicle</th>
                            <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600 }}>Registration</th>
                            <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600 }}>Type</th>
                            <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600 }}>Planned Departure</th>
                            <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600 }}>Actual Departure</th>
                            <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600 }}>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {todayFleet.map((f) => (
                            <tr key={f.id} style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                              <td style={{ padding: "8px 12px", fontWeight: 700, color: "#f8fafc" }}>
                                {f.vehicle?.vehicle_number || "—"}
                              </td>
                              <td style={{ padding: "8px 12px", color: "#cbd5e1", fontFamily: "monospace" }}>
                                {f.vehicle?.registration_number || "—"}
                              </td>
                              <td style={{ padding: "8px 12px", color: "#94a3b8" }}>
                                {f.vehicle?.vehicle_type || "Standard"}
                              </td>
                              <td style={{ padding: "8px 12px", color: "#cbd5e1" }}>
                                {f.planned_departure ? new Date(f.planned_departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
                              </td>
                              <td style={{ padding: "8px 12px", color: "#cbd5e1" }}>
                                {f.actual_departure ? new Date(f.actual_departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
                              </td>
                              <td style={{ padding: "8px 12px" }}>
                                <span
                                  style={{
                                    fontSize: "11px",
                                    padding: "2px 6px",
                                    borderRadius: "4px",
                                    backgroundColor:
                                      f.status === "DEPARTED"
                                        ? "rgba(34, 197, 94, 0.12)"
                                        : f.status === "CANCELLED"
                                        ? "rgba(239, 68, 68, 0.12)"
                                        : "rgba(59, 130, 246, 0.12)",
                                    color:
                                      f.status === "DEPARTED"
                                        ? "#4ade80"
                                        : f.status === "CANCELLED"
                                        ? "#f87171"
                                        : "#60a5fa",
                                  }}
                                >
                                  {f.status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>

              {/* 5. ROUTE STOPS & MAP VIEW SECTION */}
              <div
                style={{
                  backgroundColor: "rgba(255, 255, 255, 0.02)",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  borderRadius: "10px",
                  overflow: "hidden",
                }}
              >
                {/* Header with Stops Sequence / Map View Tabs */}
                <div
                  style={{
                    padding: "12px 20px",
                    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    backgroundColor: "rgba(255, 255, 255, 0.02)",
                    flexWrap: "wrap",
                    gap: "10px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <MapIcon size={16} style={{ color: "#f43f5e" }} />
                    <h4
                      style={{
                        fontSize: "12px",
                        fontWeight: 700,
                        color: "#94a3b8",
                        margin: 0,
                        textTransform: "uppercase",
                        letterSpacing: "0.04em",
                      }}
                    >
                      Route Stops ({stops.length})
                    </h4>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    {/* View Mode Segmented Controls */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        backgroundColor: "rgba(0, 0, 0, 0.4)",
                        border: "1px solid rgba(255, 255, 255, 0.1)",
                        borderRadius: "6px",
                        padding: "2px",
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => setActiveTab("stops")}
                        style={{
                          padding: "4px 10px",
                          borderRadius: "4px",
                          border: "none",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "5px",
                          backgroundColor: activeTab === "stops" ? "#4f46e5" : "transparent",
                          color: activeTab === "stops" ? "#ffffff" : "#94a3b8",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <List size={13} /> Stops Sequence
                      </button>

                      <button
                        type="button"
                        onClick={() => setActiveTab("map")}
                        style={{
                          padding: "4px 10px",
                          borderRadius: "4px",
                          border: "none",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "5px",
                          backgroundColor: activeTab === "map" ? "#4f46e5" : "transparent",
                          color: activeTab === "map" ? "#ffffff" : "#94a3b8",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <MapIcon size={13} /> Map View
                      </button>
                    </div>

                    <button
                      type="button"
                      onClick={handleViewRoute}
                      disabled={!service.route_id}
                      style={{
                        padding: "5px 10px",
                        backgroundColor: "rgba(255, 255, 255, 0.05)",
                        border: "1px solid rgba(255, 255, 255, 0.1)",
                        borderRadius: "6px",
                        color: "#cbd5e1",
                        fontSize: "12px",
                        cursor: service.route_id ? "pointer" : "not-allowed",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "5px",
                      }}
                    >
                      <ExternalLink size={12} /> View Route
                    </button>
                  </div>
                </div>

                {/* Tab Content: Stops Sequence Table OR Interactive Map */}
                {activeTab === "stops" ? (
                  <div style={{ width: "100%" }}>
                    {stops.length === 0 ? (
                      <div style={{ textAlign: "center", padding: "24px 0", color: "#64748b", fontSize: "13px" }}>
                        No stops defined for this service's route.
                      </div>
                    ) : (
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", textAlign: "left" }}>
                        <thead>
                          <tr
                            style={{
                              backgroundColor: "#1b1f2b",
                              borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                            }}
                          >
                            <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600, width: "50px", textAlign: "center" }}>Seq</th>
                            <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600, width: "120px" }}>Stop Code</th>
                            <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600 }}>Stop Name</th>
                            <th style={{ padding: "8px 12px", color: "#94a3b8", fontWeight: 600, textAlign: "right", width: "100px" }}>Distance</th>
                          </tr>
                        </thead>
                        <tbody>
                          {stops.map((stop, idx) => (
                            <tr
                              key={stop.id || idx}
                              style={{
                                borderBottom: idx < stops.length - 1 ? "1px solid rgba(255, 255, 255, 0.04)" : "none",
                                backgroundColor: idx % 2 === 1 ? "rgba(255, 255, 255, 0.015)" : "transparent",
                              }}
                            >
                              <td style={{ padding: "8px 12px", textAlign: "center", color: "#818cf8", fontFamily: "monospace", fontWeight: 600 }}>
                                {stop.sequence_number}
                              </td>
                              <td style={{ padding: "8px 12px" }}>
                                <span
                                  style={{
                                    fontFamily: "monospace",
                                    fontSize: "11px",
                                    color: "#cbd5e1",
                                    backgroundColor: "rgba(255, 255, 255, 0.05)",
                                    padding: "2px 6px",
                                    borderRadius: "4px",
                                  }}
                                >
                                  {stop.stop_code || "—"}
                                </span>
                              </td>
                              <td style={{ padding: "8px 12px", color: "#f8fafc", fontWeight: 500 }}>
                                {stop.stop_name || "Unknown Stop"}
                              </td>
                              <td style={{ padding: "8px 12px", textAlign: "right", color: "#94a3b8", fontFamily: "monospace" }}>
                                {formatKm(stop.distance_from_start)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                ) : (
                  /* MAP VIEW: Route LineString & Stop Markers */
                  <div style={{ height: "340px", width: "100%", position: "relative", backgroundColor: "#11141c" }}>
                    {stopMarkers.length === 0 && polylinePositions.length === 0 ? (
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#64748b", fontSize: "13px" }}>
                        Route map is not available for this route.
                      </div>
                    ) : (
                      <ErrorBoundary fallbackTitle="Map View Unavailable" fallbackMessage="Route map preview could not be rendered.">
                        <MapContainer
                          center={[22.5726, 88.3639]}
                          zoom={12}
                          style={{ height: "100%", width: "100%", zIndex: 0 }}
                          scrollWheelZoom={false}
                        >
                          <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />
                          {polylinePositions.length > 0 && (
                            <Polyline positions={polylinePositions} color="#4f46e5" weight={5} opacity={0.85} />
                          )}
                          {stopMarkers.map((sm, i) => (
                            <Marker key={i} position={sm.latlng}>
                              <Popup>
                                <div style={{ color: "#0f172a", fontSize: "12px", lineHeight: "1.4" }}>
                                  <strong style={{ fontSize: "13px" }}>{sm.stop_name}</strong>
                                  <div>Code: <code>{sm.stop_code}</code></div>
                                  <div>Sequence: #{sm.sequence}</div>
                                </div>
                              </Popup>
                            </Marker>
                          ))}
                          <BoundsWrapper bounds={mapBounds} />
                        </MapContainer>
                      </ErrorBoundary>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* FIXED FOOTER: Always pinned and reachable */}
        <div
          style={{
            padding: "16px 24px",
            borderTop: "1px solid rgba(255, 255, 255, 0.08)",
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: "10px",
            backgroundColor: "rgba(0, 0, 0, 0.25)",
            flexShrink: 0,
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "8px 20px",
              backgroundColor: "rgba(255, 255, 255, 0.05)",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              borderRadius: "6px",
              color: "#f8fafc",
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer",
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.08)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = "rgba(255, 255, 255, 0.05)";
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
