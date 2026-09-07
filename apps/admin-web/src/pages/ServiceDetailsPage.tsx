import { useEffect, useState, useMemo, useCallback } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import {
  ArrowLeft,
  Route as RouteIcon,
  Banknote,
  Map as MapIcon,
  Bus,
  CalendarClock,
  ExternalLink,
  List,
  AlertCircle,
  Loader2,
  Compass,
  Edit3,
  Check,
  X,
  Info,
} from "lucide-react";
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from "react-leaflet";
import type * as L from "leaflet";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { RouteDetailModal } from "../components/RouteDetailModal";
import { FareDetailModal } from "../components/FareDetailModal";
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

interface RouteOption {
  id: string;
  route_code: string;
  route_name: string;
  status?: string;
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
  service_id: string;
  vehicle_id: string;
  operating_date: string;
  direction: string;
  planned_departure: string;
  actual_departure?: string | null;
  status: string;
  vehicle?: {
    id: string;
    vehicle_number: string;
    registration_number?: string | null;
    vehicle_type: string;
  };
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function formatDaysOfWeek(days: number[] | null | undefined): string {
  if (!days || days.length === 0) return "—";
  if (days.length === 7) return "Every day";
  return days
    .slice()
    .sort()
    .map((d) => DAY_NAMES[d - 1] || `Day ${d}`)
    .join(", ");
}

const formatKm = (val: unknown): string => {
  const num = safeNumber(val);
  if (num === null) return "—";
  return `${num.toFixed(2)} km`;
};

// Leaflet Map Auto-Fit Bounds Wrapper
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
            map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15, animate: false });
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

export default function ServiceDetailsPage() {
  const { serviceId } = useParams<{ serviceId: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const [service, setService] = useState<ServiceDetail | null>(null);
  const [stops, setStops] = useState<RouteStop[]>([]);
  const [routeGeometry, setRouteGeometry] = useState<any | null>(null);
  const [fareConfig, setFareConfig] = useState<FareConfigurationItem | null>(null);
  const [serviceSchedules, setServiceSchedules] = useState<ServiceScheduleItem[]>([]);
  const [fleetSchedules, setFleetSchedules] = useState<FleetScheduleItem[]>([]);
  const [todayFleet, setTodayFleet] = useState<DepotScheduleItem[]>([]);
  const [availableRoutes, setAvailableRoutes] = useState<RouteOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit Service State
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({
    service_code: "",
    service_name: "",
    status: "ACTIVE",
    route_id: "",
    typical_interval_minutes: "",
    days_of_week: [1, 2, 3, 4, 5, 6, 7] as number[],
  });

  // Overlays for Route and Fare details (Origin Context Preservation)
  const [activeOverlayRouteId, setActiveOverlayRouteId] = useState<string | null>(null);
  const [activeOverlayFareId, setActiveOverlayFareId] = useState<string | null>(null);

  // Toggle between Stops Sequence and Map View
  const [activeTab, setActiveTab] = useState<"stops" | "map">("stops");

  const fetchAllDetails = useCallback(async () => {
    if (!serviceId) {
      setError("No Service ID specified.");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // 1. Fetch Service primary details
      const svcData: ServiceDetail = await apiFetch(`/admin/services/${serviceId}`);
      setService(svcData);

      // 2. Concurrently fetch all related entities
      const routeId = svcData.route_id;
      const fareId = svcData.fare_configuration_id;

      const promises: Promise<any>[] = [
        // Route stops
        routeId ? apiFetch(`/admin/routes/${routeId}/stops`).catch(() => []) : Promise.resolve([]),
        // Route geometry
        routeId ? apiFetch(`/admin/routes/${routeId}`).catch(() => null) : Promise.resolve(null),
        // Fare configuration
        fareId ? apiFetch(`/admin/fares/${fareId}`).catch(() => null) : Promise.resolve(null),
        // Passenger ServiceSchedule
        apiFetch(`/admin/services/${serviceId}/schedules`).catch(() => []),
        // Fleet recurring schedules
        apiFetch(`/admin/fleet-schedules?service_id=${serviceId}`).catch(() => []),
        // Today's assigned fleet departures
        apiFetch(`/admin/depot-schedules?service_id=${serviceId}`).catch(() => []),
        // Available routes for route editing selector
        apiFetch("/admin/routes").catch(() => []),
      ];

      const [stopsData, routeData, fareData, svcSchData, fleetSchData, todayData, routesList] =
        await Promise.all(promises);

      // Sort stops by sequence_number
      if (Array.isArray(stopsData)) {
        const sortedStops = [...stopsData].sort(
          (a, b) => Number(a.sequence_number) - Number(b.sequence_number)
        );
        setStops(sortedStops);
      }

      // Set route geometry
      if (routeData && routeData.geometry) {
        setRouteGeometry(routeData.geometry);
      }

      // Set fare configuration
      if (fareData) {
        setFareConfig(fareData);
      }

      // Set service schedules
      if (Array.isArray(svcSchData)) {
        setServiceSchedules(svcSchData);
      }

      // Set fleet schedules
      if (Array.isArray(fleetSchData)) {
        setFleetSchedules(fleetSchData);
      }

      // Set today's fleet departures
      if (Array.isArray(todayData)) {
        setTodayFleet(todayData);
      }

      // Set available routes
      if (Array.isArray(routesList)) {
        setAvailableRoutes(routesList);
      }
    } catch (err: any) {
      console.error("Failed to load service details:", err);
      setError(err.message || "Failed to load service operational details.");
    } finally {
      setLoading(false);
    }
  }, [serviceId]);

  useEffect(() => {
    fetchAllDetails();
  }, [fetchAllDetails]);

  // ─────────────────────────────────────────────────────────────
  // OPERATIONAL SCHEDULE DERIVATION RULES (Section 6, 7, 8, 30)
  // ─────────────────────────────────────────────────────────────
  // 1. First Bus & Last Bus: AUTOMATICALLY DERIVED from FleetSchedule departure times
  // 2. Frequency / Headway: CONFIGURABLE from ServiceSchedule.typical_interval_minutes
  // ─────────────────────────────────────────────────────────────
  const scheduleOverview = useMemo(() => {
    // A. FIRST BUS & LAST BUS (Purely derived from FleetSchedule departure times)
    let firstBus = "—";
    let lastBus = "—";
    if (fleetSchedules.length > 0) {
      const sorted = [...fleetSchedules].sort((a, b) =>
        (a.departure_time || "").localeCompare(b.departure_time || "")
      );
      firstBus =
        sorted[0].formatted_departure_time ||
        (sorted[0].departure_time ? sorted[0].departure_time.slice(0, 5) : "—");
      lastBus =
        sorted[sorted.length - 1].formatted_departure_time ||
        (sorted[sorted.length - 1].departure_time
          ? sorted[sorted.length - 1].departure_time.slice(0, 5)
          : "—");
    }

    // B. FREQUENCY / HEADWAY (From authoritative ServiceSchedule)
    let frequency = "Not configured";
    let operatingDays = "—";
    let primarySchedule: ServiceScheduleItem | null = null;

    if (serviceSchedules.length > 0) {
      const activeScheds = serviceSchedules.filter((s) => s.status === "ACTIVE");
      primarySchedule = activeScheds.length > 0 ? activeScheds[0] : serviceSchedules[0];

      if (primarySchedule.typical_interval_minutes && primarySchedule.typical_interval_minutes > 0) {
        frequency = `${primarySchedule.typical_interval_minutes} mins`;
      }
      operatingDays = formatDaysOfWeek(primarySchedule.days_of_week);
    } else if (fleetSchedules.length > 0) {
      const allEveryDay = fleetSchedules.every((s) => s.every_day);
      operatingDays = allEveryDay ? "Every day" : "Scheduled dates";
    }

    return {
      firstBus,
      lastBus,
      frequency,
      operatingDays,
      primarySchedule,
      hasFleetSchedules: fleetSchedules.length > 0,
      hasServiceSchedules: serviceSchedules.length > 0,
      totalFleetDepartures: fleetSchedules.length,
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
      if (lat !== null && lng !== null && lat !== 0 && lng !== 0) {
        markers.push({
          latlng: [lat, lng],
          stop_name: s.stop_name || "Stop",
          stop_code: s.stop_code || "",
          sequence: s.sequence_number,
        });
      }
    });

    let bounds: L.LatLngBounds | null = null;
    if (positions.length > 0 || markers.length > 0) {
      const allPts = [
        ...positions,
        ...markers.map((m) => m.latlng),
      ];
      if (allPts.length > 0 && typeof window !== "undefined" && (window as any).L) {
        bounds = (window as any).L.latLngBounds(allPts);
      }
    }

    return { polylinePositions: positions, stopMarkers: markers, mapBounds: bounds };
  }, [routeGeometry, stops]);

  // ─────────────────────────────────────────────────────────────
  // NAVIGATION HANDLERS (Origin Context Preservation)
  // ─────────────────────────────────────────────────────────────
  const handleBack = () => {
    if (location.state?.returnTo) {
      navigate(location.state.returnTo, { state: location.state });
    } else {
      navigate("/services");
    }
  };

  const handleViewRoute = () => {
    if (!service?.route_id) return;
    // Navigate to dedicated full-page Route Details preserving return context
    navigate(`/routes/${service.route_id}`, {
      state: {
        returnTo: `/services/${service.id}`,
        returnLabel: `Service ${service.service_code}`,
      },
    });
  };

  const handleManageFare = () => {
    const targetFareId = fareConfig?.id || service?.fare_configuration_id;
    if (!targetFareId) return;
    // Prefer opening Fare Detail overlay directly from Service Details page
    setActiveOverlayFareId(targetFareId);
  };

  const handleManageSchedules = () => {
    if (!service?.id) return;
    // Navigate with return-to-service state
    navigate(`/fleet-schedules?serviceId=${service.id}&returnTo=${encodeURIComponent(`/services/${service.id}`)}`, {
      state: {
        returnTo: `/services/${service.id}`,
        returnLabel: `Service ${service.service_code}`,
      },
    });
  };

  const handleManageFleet = () => {
    if (!service?.id) return;
    // Navigate with return-to-service state
    navigate(`/vehicles?serviceId=${service.id}&returnTo=${encodeURIComponent(`/services/${service.id}`)}`, {
      state: {
        returnTo: `/services/${service.id}`,
        returnLabel: `Service ${service.service_code}`,
      },
    });
  };

  // ─────────────────────────────────────────────────────────────
  // EDIT SERVICE HANDLERS
  // ─────────────────────────────────────────────────────────────
  const handleStartEdit = () => {
    if (!service) return;
    setSaveError(null);
    setSaveSuccess(null);
    setEditForm({
      service_code: service.service_code || "",
      service_name: service.service_name || "",
      status: service.status || "ACTIVE",
      route_id: service.route_id || "",
      typical_interval_minutes: scheduleOverview.primarySchedule?.typical_interval_minutes
        ? String(scheduleOverview.primarySchedule.typical_interval_minutes)
        : "",
      days_of_week:
        scheduleOverview.primarySchedule?.days_of_week &&
        scheduleOverview.primarySchedule.days_of_week.length > 0
          ? scheduleOverview.primarySchedule.days_of_week
          : [1, 2, 3, 4, 5, 6, 7],
    });
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setSaveError(null);
    setIsEditing(false);
  };

  const toggleDay = (dayNum: number) => {
    setEditForm((prev) => {
      const exists = prev.days_of_week.includes(dayNum);
      const updated = exists
        ? prev.days_of_week.filter((d) => d !== dayNum)
        : [...prev.days_of_week, dayNum].sort((a, b) => a - b);
      return { ...prev, days_of_week: updated };
    });
  };

  const handleSelectAllDays = () => {
    setEditForm((prev) => ({ ...prev, days_of_week: [1, 2, 3, 4, 5, 6, 7] }));
  };

  const handleSelectWeekdays = () => {
    setEditForm((prev) => ({ ...prev, days_of_week: [1, 2, 3, 4, 5] }));
  };

  const handleSelectWeekends = () => {
    setEditForm((prev) => ({ ...prev, days_of_week: [6, 7] }));
  };

  const handleSaveEdit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (saving || !service) return;
    setSaveError(null);
    setSaveSuccess(null);

    const trimmedCode = editForm.service_code.trim();
    const trimmedName = editForm.service_name.trim();

    if (!trimmedCode) {
      setSaveError("Service Code cannot be empty.");
      return;
    }
    if (!trimmedName) {
      setSaveError("Service Name cannot be empty.");
      return;
    }
    if (!editForm.route_id) {
      setSaveError("An associated route must be selected.");
      return;
    }

    let freqNum: number | null = null;
    if (editForm.typical_interval_minutes.trim() !== "") {
      freqNum = parseInt(editForm.typical_interval_minutes.trim(), 10);
      if (isNaN(freqNum) || freqNum <= 0) {
        setSaveError("Typical Frequency / Headway must be a positive number of minutes (e.g. 15).");
        return;
      }
    }

    if (editForm.days_of_week.length === 0) {
      setSaveError("At least one operating day must be selected.");
      return;
    }

    try {
      setSaving(true);

      // 1. Save Service core attributes (service_code, service_name, status, route_id)
      await apiFetch(`/admin/services/${service.id}`, {
        method: "PUT",
        body: JSON.stringify({
          service_code: trimmedCode,
          service_name: trimmedName,
          status: editForm.status,
          route_id: editForm.route_id,
        }),
      });

      // 2. Save Frequency & Operating Days to authoritative ServiceSchedule
      if (scheduleOverview.primarySchedule) {
        await apiFetch(
          `/admin/services/${service.id}/schedules/${scheduleOverview.primarySchedule.id}`,
          {
            method: "PUT",
            body: JSON.stringify({
              typical_interval_minutes: freqNum !== null ? freqNum : undefined,
              days_of_week: editForm.days_of_week,
            }),
          }
        );
      } else if (freqNum !== null) {
        // Create initial timetable schedule if frequency was explicitly configured
        await apiFetch(`/admin/services/${service.id}/schedules`, {
          method: "POST",
          body: JSON.stringify({
            direction: "A_TO_B",
            start_time: "06:00:00",
            end_time: "22:00:00",
            typical_interval_minutes: freqNum,
            days_of_week: editForm.days_of_week,
            effective_from: new Date().toISOString(),
            status: "ACTIVE",
          }),
        });
      }

      setSaveSuccess("Service and schedule configuration updated successfully.");
      setIsEditing(false);

      // Reload authoritative service operational details
      await fetchAllDetails();
    } catch (err: any) {
      console.error("Failed to save service edit:", err);
      setSaveError(err.message || "Failed to update service details.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "20px 0" }}>
        <button
          type="button"
          onClick={handleBack}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            background: "none",
            border: "none",
            color: "#94a3b8",
            fontSize: "14px",
            cursor: "pointer",
            marginBottom: "24px",
            padding: "6px 0",
          }}
        >
          <ArrowLeft size={16} /> {location.state?.returnLabel ? `Back to ${location.state.returnLabel}` : "Back to Services"}
        </button>
        <div
          style={{
            padding: "80px 20px",
            textAlign: "center",
            color: "#94a3b8",
            backgroundColor: "#161922",
            borderRadius: "12px",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "14px",
          }}
        >
          <Loader2 size={32} className="animate-spin" style={{ color: "#818cf8" }} />
          <span style={{ fontSize: "15px" }}>Loading service operational details...</span>
        </div>
      </div>
    );
  }

  if (error || !service) {
    return (
      <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "20px 0" }}>
        <button
          type="button"
          onClick={handleBack}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            background: "none",
            border: "none",
            color: "#94a3b8",
            fontSize: "14px",
            cursor: "pointer",
            marginBottom: "24px",
            padding: "6px 0",
          }}
        >
          <ArrowLeft size={16} /> {location.state?.returnLabel ? `Back to ${location.state.returnLabel}` : "Back to Services"}
        </button>
        <div
          style={{
            padding: "32px",
            borderRadius: "12px",
            backgroundColor: "rgba(239, 68, 68, 0.08)",
            border: "1px solid rgba(239, 68, 68, 0.25)",
            color: "#f87171",
            display: "flex",
            flexDirection: "column",
            gap: "16px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "16px", fontWeight: 600 }}>
            <AlertCircle size={22} />
            <span>Service Not Found</span>
          </div>
          <p style={{ margin: 0, color: "#cbd5e1", fontSize: "14px" }}>
            {error || `The requested service with ID "${serviceId}" could not be retrieved.`}
          </p>
          <div>
            <button
              type="button"
              onClick={handleBack}
              style={{
                padding: "8px 16px",
                backgroundColor: "rgba(255, 255, 255, 0.08)",
                border: "1px solid rgba(255, 255, 255, 0.15)",
                borderRadius: "6px",
                color: "#f8fafc",
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Return to Services List
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        maxWidth: "1280px",
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: "24px",
        color: "#f8fafc",
        paddingBottom: "48px",
      }}
    >
      {/* ── BACK NAVIGATION ── */}
      <div>
        <button
          type="button"
          onClick={handleBack}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            background: "transparent",
            border: "none",
            color: "#94a3b8",
            fontSize: "14px",
            fontWeight: 500,
            cursor: "pointer",
            padding: "6px 0",
            transition: "color 0.15s ease",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#f8fafc")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#94a3b8")}
        >
          <ArrowLeft size={16} /> {location.state?.returnLabel ? `Back to ${location.state.returnLabel}` : "Back to Services"}
        </button>
      </div>

      {/* ── SUCCESS NOTIFICATION BANNER ── */}
      {saveSuccess && (
        <div
          style={{
            padding: "14px 18px",
            borderRadius: "10px",
            backgroundColor: "rgba(34, 197, 94, 0.12)",
            border: "1px solid rgba(34, 197, 94, 0.3)",
            color: "#4ade80",
            fontSize: "14px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <Check size={18} />
            <span>{saveSuccess}</span>
          </div>
          <button
            type="button"
            onClick={() => setSaveSuccess(null)}
            style={{
              background: "none",
              border: "none",
              color: "#4ade80",
              cursor: "pointer",
              padding: "4px",
            }}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* ── FULL-PAGE SERVICE HEADER (Section 4 & 14) ── */}
      <div
        style={{
          backgroundColor: "#161922",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          borderRadius: "14px",
          padding: "24px 28px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "20px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px", minWidth: 0 }}>
          <div
            style={{
              width: "52px",
              height: "52px",
              borderRadius: "12px",
              backgroundColor: "rgba(99, 102, 241, 0.15)",
              border: "1px solid rgba(99, 102, 241, 0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Bus size={26} style={{ color: "#818cf8" }} />
          </div>
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: "12px",
                fontWeight: 700,
                color: "#818cf8",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: "4px",
              }}
            >
              SERVICE {isEditing ? "· EDIT MODE" : ""}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
              <h1
                style={{
                  fontSize: "24px",
                  fontWeight: 700,
                  margin: 0,
                  color: "#f8fafc",
                  letterSpacing: "-0.02em",
                }}
              >
                {service.service_code}
              </h1>
              {service.status && (
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: 600,
                    padding: "3px 10px",
                    borderRadius: "6px",
                    backgroundColor:
                      service.status === "ACTIVE"
                        ? "rgba(34, 197, 94, 0.15)"
                        : "rgba(148, 163, 184, 0.12)",
                    color: service.status === "ACTIVE" ? "#4ade80" : "#94a3b8",
                    border:
                      service.status === "ACTIVE"
                        ? "1px solid rgba(34, 197, 94, 0.3)"
                        : "1px solid rgba(148, 163, 184, 0.2)",
                  }}
                >
                  {service.status}
                </span>
              )}
            </div>
            <div style={{ fontSize: "14px", color: "#94a3b8", marginTop: "4px" }}>
              {service.service_name} · {service.service_code}
            </div>
          </div>
        </div>

        {/* Action Controls in Header */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
          {isEditing ? (
            <>
              <button
                type="button"
                onClick={handleCancelEdit}
                disabled={saving}
                style={{
                  padding: "8px 18px",
                  backgroundColor: "rgba(255, 255, 255, 0.05)",
                  border: "1px solid rgba(255, 255, 255, 0.15)",
                  borderRadius: "8px",
                  color: "#cbd5e1",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: saving ? "not-allowed" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  transition: "all 0.15s ease",
                }}
              >
                <X size={15} /> Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveEdit}
                disabled={saving}
                style={{
                  padding: "8px 20px",
                  backgroundColor: "#4f46e5",
                  border: "1px solid #6366f1",
                  borderRadius: "8px",
                  color: "#ffffff",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: saving ? "not-allowed" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  boxShadow: "0 2px 8px rgba(79, 70, 229, 0.35)",
                  transition: "all 0.15s ease",
                }}
              >
                {saving ? (
                  <>
                    <Loader2 size={15} className="animate-spin" /> Saving Changes...
                  </>
                ) : (
                  <>
                    <Check size={15} /> Save Changes
                  </>
                )}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={handleStartEdit}
                style={{
                  padding: "8px 18px",
                  backgroundColor: "rgba(99, 102, 241, 0.15)",
                  border: "1px solid rgba(99, 102, 241, 0.35)",
                  borderRadius: "8px",
                  color: "#a5b4fc",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  transition: "all 0.15s ease",
                }}
              >
                <Edit3 size={14} /> Edit Service
              </button>
              <button
                type="button"
                onClick={handleManageSchedules}
                style={{
                  padding: "8px 16px",
                  backgroundColor: "rgba(168, 85, 247, 0.12)",
                  border: "1px solid rgba(168, 85, 247, 0.3)",
                  borderRadius: "8px",
                  color: "#c084fc",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  transition: "all 0.15s ease",
                }}
              >
                <CalendarClock size={14} /> Manage Schedules
              </button>
              <button
                type="button"
                onClick={handleManageFleet}
                style={{
                  padding: "8px 16px",
                  backgroundColor: "rgba(245, 158, 11, 0.12)",
                  border: "1px solid rgba(245, 158, 11, 0.3)",
                  borderRadius: "8px",
                  color: "#fbbf24",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  transition: "all 0.15s ease",
                }}
              >
                <Bus size={14} /> Manage Fleet
              </button>
            </>
          )}
        </div>
      </div>

      {/* ── EDIT SERVICE FORM VIEW (Section 11, 14, 15, 16) ── */}
      {isEditing ? (
        <div
          style={{
            backgroundColor: "#161922",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "14px",
            padding: "28px 32px",
            display: "flex",
            flexDirection: "column",
            gap: "28px",
          }}
        >
          {/* Error Banner */}
          {saveError && (
            <div
              style={{
                padding: "14px 18px",
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
              <span>{saveError}</span>
            </div>
          )}

          {/* Section 1: Core Service Properties */}
          <div>
            <h2
              style={{
                fontSize: "14px",
                fontWeight: 700,
                color: "#f8fafc",
                margin: "0 0 16px 0",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
                paddingBottom: "8px",
              }}
            >
              Core Service Properties
            </h2>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: "20px",
              }}
            >
              <div>
                <label
                  htmlFor="edit_service_code"
                  style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "6px" }}
                >
                  Service Code *
                </label>
                <input
                  id="edit_service_code"
                  type="text"
                  value={editForm.service_code}
                  onChange={(e) => setEditForm({ ...editForm, service_code: e.target.value })}
                  placeholder="e.g. SVC01-SD5"
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    backgroundColor: "#0d1017",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "8px",
                    color: "#f8fafc",
                    fontSize: "14px",
                    fontFamily: "monospace",
                    outline: "none",
                  }}
                />
              </div>

              <div>
                <label
                  htmlFor="edit_service_name"
                  style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "6px" }}
                >
                  Service Name *
                </label>
                <input
                  id="edit_service_name"
                  type="text"
                  value={editForm.service_name}
                  onChange={(e) => setEditForm({ ...editForm, service_name: e.target.value })}
                  placeholder="e.g. SD5 Express"
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    backgroundColor: "#0d1017",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "8px",
                    color: "#f8fafc",
                    fontSize: "14px",
                    outline: "none",
                  }}
                />
              </div>

              <div>
                <label
                  htmlFor="edit_service_status"
                  style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "6px" }}
                >
                  Status *
                </label>
                <select
                  id="edit_service_status"
                  value={editForm.status}
                  onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    backgroundColor: "#0d1017",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "8px",
                    color: "#f8fafc",
                    fontSize: "14px",
                    outline: "none",
                  }}
                >
                  <option value="ACTIVE">ACTIVE</option>
                  <option value="INACTIVE">INACTIVE</option>
                  <option value="SUSPENDED">SUSPENDED</option>
                  <option value="DRAFT">DRAFT</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="edit_route_id"
                  style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "6px" }}
                >
                  Associated Route *
                </label>
                <select
                  id="edit_route_id"
                  value={editForm.route_id}
                  onChange={(e) => setEditForm({ ...editForm, route_id: e.target.value })}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    backgroundColor: "#0d1017",
                    border: "1px solid rgba(255, 255, 255, 0.12)",
                    borderRadius: "8px",
                    color: "#f8fafc",
                    fontSize: "14px",
                    outline: "none",
                  }}
                >
                  <option value="" disabled>Select route...</option>
                  {availableRoutes.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.route_code} — {r.route_name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Section 2: Configurable Typical Frequency / Headway & Operating Days */}
          <div>
            <h2
              style={{
                fontSize: "14px",
                fontWeight: 700,
                color: "#f8fafc",
                margin: "0 0 8px 0",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
                paddingBottom: "8px",
              }}
            >
              Operating Timetable & Configurable Frequency
            </h2>
            <p style={{ margin: "0 0 16px 0", fontSize: "13px", color: "#94a3b8" }}>
              Authoritative passenger timetable frequency and operational days. First Bus and Last Bus are derived automatically from recurring fleet schedules and are read-only.
            </p>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: "20px",
                alignItems: "flex-start",
              }}
            >
              {/* Typical Frequency Input */}
              <div>
                <label
                  htmlFor="edit_typical_interval"
                  style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "6px" }}
                >
                  Typical Frequency / Headway (minutes)
                </label>
                <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                  <input
                    id="edit_typical_interval"
                    type="number"
                    min="1"
                    step="1"
                    value={editForm.typical_interval_minutes}
                    onChange={(e) =>
                      setEditForm({ ...editForm, typical_interval_minutes: e.target.value })
                    }
                    placeholder="e.g. 15"
                    style={{
                      width: "100%",
                      padding: "10px 48px 10px 14px",
                      backgroundColor: "#0d1017",
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      borderRadius: "8px",
                      color: "#818cf8",
                      fontSize: "14px",
                      fontWeight: 600,
                      outline: "none",
                    }}
                  />
                  <span
                    style={{
                      position: "absolute",
                      right: "14px",
                      fontSize: "12px",
                      color: "#94a3b8",
                      pointerEvents: "none",
                    }}
                  >
                    mins
                  </span>
                </div>
                <div style={{ fontSize: "12px", color: "#64748b", marginTop: "6px" }}>
                  Saved to authoritative <code>ServiceSchedule.typical_interval_minutes</code>. Leave blank if not configured.
                </div>
              </div>

              {/* Operating Days Selector */}
              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#94a3b8" }}>
                    Operating Days
                  </label>
                  <div style={{ display: "flex", gap: "8px", fontSize: "11px" }}>
                    <button
                      type="button"
                      onClick={handleSelectAllDays}
                      style={{ background: "none", border: "none", color: "#818cf8", cursor: "pointer", padding: 0 }}
                    >
                      All
                    </button>
                    <span style={{ color: "#475569" }}>·</span>
                    <button
                      type="button"
                      onClick={handleSelectWeekdays}
                      style={{ background: "none", border: "none", color: "#818cf8", cursor: "pointer", padding: 0 }}
                    >
                      Mon-Fri
                    </button>
                    <span style={{ color: "#475569" }}>·</span>
                    <button
                      type="button"
                      onClick={handleSelectWeekends}
                      style={{ background: "none", border: "none", color: "#818cf8", cursor: "pointer", padding: 0 }}
                    >
                      Sat-Sun
                    </button>
                  </div>
                </div>

                <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                  {DAY_NAMES.map((dayName, idx) => {
                    const dayNum = idx + 1;
                    const isSelected = editForm.days_of_week.includes(dayNum);
                    return (
                      <button
                        key={dayNum}
                        type="button"
                        onClick={() => toggleDay(dayNum)}
                        style={{
                          padding: "7px 12px",
                          borderRadius: "6px",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                          backgroundColor: isSelected
                            ? "rgba(99, 102, 241, 0.2)"
                            : "rgba(255, 255, 255, 0.03)",
                          color: isSelected ? "#a5b4fc" : "#64748b",
                          border: isSelected
                            ? "1px solid rgba(99, 102, 241, 0.4)"
                            : "1px solid rgba(255, 255, 255, 0.08)",
                          transition: "all 0.15s ease",
                        }}
                      >
                        {dayName}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Read-Only Bus Times Explanatory Callout (Section 6, 11, 14) */}
            <div
              style={{
                marginTop: "20px",
                padding: "16px 20px",
                borderRadius: "10px",
                backgroundColor: "rgba(56, 189, 248, 0.06)",
                border: "1px solid rgba(56, 189, 248, 0.2)",
                display: "flex",
                gap: "14px",
                alignItems: "flex-start",
              }}
            >
              <Info size={18} style={{ color: "#38bdf8", flexShrink: 0, marginTop: "2px" }} />
              <div style={{ fontSize: "13px", lineHeight: "1.5", color: "#cbd5e1" }}>
                <div style={{ fontWeight: 600, color: "#38bdf8", marginBottom: "2px" }}>
                  First Bus & Last Bus are Automatically Derived (Read-Only)
                </div>
                <div>
                  Operational bus departure times are derived from the earliest departure (
                  <strong style={{ color: "#f8fafc", fontFamily: "monospace" }}>
                    {scheduleOverview.firstBus}
                  </strong>
                  ) and latest departure (
                  <strong style={{ color: "#f8fafc", fontFamily: "monospace" }}>
                    {scheduleOverview.lastBus}
                  </strong>
                  ) configured across recurring Fleet Schedule records. They cannot be edited manually as Service fields.
                  To update departure times, use <strong>Manage Schedules</strong>.
                </div>
              </div>
            </div>
          </div>

          {/* Form Bottom Save / Cancel Actions */}
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              alignItems: "center",
              gap: "12px",
              paddingTop: "16px",
              borderTop: "1px solid rgba(255, 255, 255, 0.06)",
            }}
          >
            <button
              type="button"
              onClick={handleCancelEdit}
              disabled={saving}
              style={{
                padding: "9px 20px",
                backgroundColor: "rgba(255, 255, 255, 0.05)",
                border: "1px solid rgba(255, 255, 255, 0.12)",
                borderRadius: "8px",
                color: "#cbd5e1",
                fontSize: "13px",
                fontWeight: 600,
                cursor: saving ? "not-allowed" : "pointer",
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSaveEdit}
              disabled={saving}
              style={{
                padding: "9px 24px",
                backgroundColor: "#4f46e5",
                border: "1px solid #6366f1",
                borderRadius: "8px",
                color: "#ffffff",
                fontSize: "13px",
                fontWeight: 600,
                cursor: saving ? "not-allowed" : "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                boxShadow: "0 2px 8px rgba(79, 70, 229, 0.35)",
              }}
            >
              {saving ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Saving Changes...
                </>
              ) : (
                <>
                  <Check size={16} /> Save Changes
                </>
              )}
            </button>
          </div>
        </div>
      ) : (
        /* ── NORMAL SERVICE DETAILS VIEW ── */
        <>
          {/* ── SERVICE OVERVIEW KPI GRID (Section 5) ── */}
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              padding: "20px 24px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
              <Compass size={16} style={{ color: "#818cf8" }} />
              <h2
                style={{
                  fontSize: "12px",
                  fontWeight: 700,
                  color: "#94a3b8",
                  margin: 0,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                Service Overview
              </h2>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
                gap: "14px",
              }}
            >
              <div style={{ padding: "12px 14px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                  Assigned Route
                </div>
                <div style={{ fontWeight: 700, fontSize: "14px", color: "#f8fafc", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {service.route_code || "—"}
                </div>
                <div style={{ fontSize: "12px", color: "#94a3b8", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginTop: "2px" }}>
                  {service.route_name || "—"}
                </div>
              </div>

              <div style={{ padding: "12px 14px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                  Total Distance
                </div>
                <div style={{ fontWeight: 700, fontSize: "14px", color: "#38bdf8", fontFamily: "monospace" }}>
                  {totalRouteDistance}
                </div>
                <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "2px" }}>
                  {stops.length} stops in sequence
                </div>
              </div>

              <div style={{ padding: "12px 14px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                  Attached Fare
                </div>
                <div style={{ fontWeight: 700, fontSize: "14px", color: "#4ade80", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {fareConfig?.name || service.fare_configuration_name || "No Fare Attached"}
                </div>
                <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "2px" }}>
                  {fareConfig?.slabs?.length != null
                    ? `${fareConfig.slabs.length} distance slabs`
                    : service.fare_slabs_count != null
                    ? `${service.fare_slabs_count} distance slabs`
                    : "Active configuration"}
                </div>
              </div>

              <div style={{ padding: "12px 14px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                  First Bus
                </div>
                <div style={{ fontWeight: 700, fontSize: "14px", color: "#f8fafc", fontFamily: "monospace" }}>
                  {scheduleOverview.firstBus}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                  Derived from Fleet Schedule
                </div>
              </div>

              <div style={{ padding: "12px 14px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                  Last Bus
                </div>
                <div style={{ fontWeight: 700, fontSize: "14px", color: "#f8fafc", fontFamily: "monospace" }}>
                  {scheduleOverview.lastBus}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                  Derived from Fleet Schedule
                </div>
              </div>

              <div style={{ padding: "12px 14px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                  Frequency
                </div>
                <div style={{ fontWeight: 700, fontSize: "14px", color: scheduleOverview.frequency === "Not configured" ? "#94a3b8" : "#818cf8" }}>
                  {scheduleOverview.frequency}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                  {scheduleOverview.hasServiceSchedules ? "Configured Headway" : "Timetable Headway"}
                </div>
              </div>

              <div style={{ padding: "12px 14px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                  Operating Days
                </div>
                <div style={{ fontWeight: 600, fontSize: "13px", color: "#f8fafc" }}>
                  {scheduleOverview.operatingDays}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                  Service timetable
                </div>
              </div>
            </div>
          </div>

          {/* ── CONNECTED OPERATIONAL ENTITIES (2-COLUMN GRID) ── */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(450px, 1fr))", gap: "20px" }}>
            {/* ROUTE CONNECTED CARD (View Route Overlay) */}
            <div
              style={{
                backgroundColor: "#161922",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderRadius: "14px",
                padding: "20px 24px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <RouteIcon size={16} style={{ color: "#38bdf8" }} />
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
                      Connected Route
                    </h3>
                  </div>
                  <button
                    type="button"
                    onClick={handleViewRoute}
                    disabled={!service.route_id}
                    style={{
                      padding: "5px 12px",
                      backgroundColor: "rgba(56, 189, 248, 0.1)",
                      border: "1px solid rgba(56, 189, 248, 0.25)",
                      borderRadius: "6px",
                      color: "#38bdf8",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: service.route_id ? "pointer" : "not-allowed",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <ExternalLink size={12} /> View Route
                  </button>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  <span style={{ fontFamily: "monospace", fontSize: "16px", fontWeight: 700, color: "#f8fafc" }}>
                    {service.route_code || "No Route Code"}
                  </span>
                  <span style={{ fontSize: "14px", color: "#cbd5e1" }}>
                    {service.route_name || "No Route Assigned"}
                  </span>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "16px", marginTop: "16px", paddingTop: "14px", borderTop: "1px solid rgba(255, 255, 255, 0.05)", fontSize: "13px", color: "#94a3b8" }}>
                <div>
                  Distance: <strong style={{ color: "#38bdf8" }}>{totalRouteDistance}</strong>
                </div>
                <div>•</div>
                <div>
                  Stops: <strong style={{ color: "#f8fafc" }}>{stops.length} configured</strong>
                </div>
              </div>
            </div>

            {/* FARE CONNECTED CARD (View Fare Chart Overlay) */}
            <div
              style={{
                backgroundColor: "#161922",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderRadius: "14px",
                padding: "20px 24px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Banknote size={16} style={{ color: "#4ade80" }} />
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
                      Attached Fare
                    </h3>
                  </div>
                  <button
                    type="button"
                    onClick={handleManageFare}
                    disabled={!service.fare_configuration_id && !fareConfig?.id}
                    style={{
                      padding: "5px 12px",
                      backgroundColor: "rgba(34, 197, 94, 0.1)",
                      border: "1px solid rgba(34, 197, 94, 0.25)",
                      borderRadius: "6px",
                      color: "#4ade80",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: (service.fare_configuration_id || fareConfig?.id) ? "pointer" : "not-allowed",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                    }}
                  >
                    <ExternalLink size={12} /> View Fare Chart
                  </button>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  <span style={{ fontSize: "16px", fontWeight: 700, color: "#f8fafc" }}>
                    {fareConfig?.name || service.fare_configuration_name || "No Fare Attached"}
                  </span>
                  <span style={{ fontSize: "14px", color: "#94a3b8" }}>
                    Service: {service.service_name} · {service.service_code}
                  </span>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "16px", marginTop: "16px", paddingTop: "14px", borderTop: "1px solid rgba(255, 255, 255, 0.05)", fontSize: "13px", color: "#94a3b8" }}>
                <div>
                  Slabs:{" "}
                  <strong style={{ color: "#f8fafc" }}>
                    {fareConfig?.slabs?.length != null
                      ? `${fareConfig.slabs.length} slabs`
                      : service.fare_slabs_count != null
                      ? `${service.fare_slabs_count} slabs`
                      : "Active"}
                  </strong>
                </div>
                <div>•</div>
                <div>
                  Status:{" "}
                  <strong style={{ color: (fareConfig?.is_active ?? service.fare_is_active) ? "#4ade80" : "#94a3b8" }}>
                    {(fareConfig?.is_active ?? service.fare_is_active) ? "Active" : "Inactive"}
                  </strong>
                </div>
                <div>•</div>
                <div>
                  Currency: <strong style={{ color: "#f8fafc" }}>{fareConfig?.currency || service.fare_currency || "INR"}</strong>
                </div>
              </div>
            </div>
          </div>

          {/* ── OPERATING SCHEDULE SECTION (Section 22) ── */}
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              padding: "20px 24px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <CalendarClock size={16} style={{ color: "#a855f7" }} />
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
                  Operating Schedule
                </h3>
              </div>
              <button
                type="button"
                onClick={handleManageSchedules}
                style={{
                  padding: "5px 12px",
                  backgroundColor: "rgba(168, 85, 247, 0.1)",
                  border: "1px solid rgba(168, 85, 247, 0.25)",
                  borderRadius: "6px",
                  color: "#c084fc",
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

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                gap: "14px",
              }}
            >
              <div style={{ padding: "12px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.04)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", marginBottom: "4px" }}>First Bus</div>
                <div style={{ fontWeight: 700, fontSize: "14px", color: "#f8fafc", fontFamily: "monospace" }}>
                  {scheduleOverview.firstBus}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                  Derived from Fleet Schedule
                </div>
              </div>
              <div style={{ padding: "12px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.04)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", marginBottom: "4px" }}>Last Bus</div>
                <div style={{ fontWeight: 700, fontSize: "14px", color: "#f8fafc", fontFamily: "monospace" }}>
                  {scheduleOverview.lastBus}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                  Derived from Fleet Schedule
                </div>
              </div>
              <div style={{ padding: "12px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.04)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", marginBottom: "4px" }}>Frequency</div>
                <div style={{ fontWeight: 700, fontSize: "14px", color: scheduleOverview.frequency === "Not configured" ? "#94a3b8" : "#818cf8" }}>
                  {scheduleOverview.frequency}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                  {scheduleOverview.hasServiceSchedules ? "Configured Headway" : "Not configured"}
                </div>
              </div>
              <div style={{ padding: "12px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.04)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", marginBottom: "4px" }}>Operating Days</div>
                <div style={{ fontWeight: 600, fontSize: "13px", color: "#f8fafc" }}>
                  {scheduleOverview.operatingDays}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                  Timetable schedule
                </div>
              </div>
              <div style={{ padding: "12px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.04)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", marginBottom: "4px" }}>Fleet Departures</div>
                <div style={{ fontWeight: 600, fontSize: "13px", color: "#fbbf24" }}>
                  {scheduleOverview.totalFleetDepartures} recurring departures
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                  Active timetable
                </div>
              </div>
            </div>
          </div>

          {/* ── TODAY'S SERVICE FLEET / DISPATCH SECTION (Section 24) ── */}
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              padding: "20px 24px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Bus size={16} style={{ color: "#fbbf24" }} />
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
                  Today's Service Fleet / Dispatch
                </h3>
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

            {todayFleet.length === 0 ? (
              <div style={{ textAlign: "center", padding: "24px 0", color: "#64748b", fontSize: "14px" }}>
                No vehicles assigned to this service today.
              </div>
            ) : (
              <div style={{ border: "1px solid rgba(255, 255, 255, 0.06)", borderRadius: "8px", overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left" }}>
                  <thead>
                    <tr style={{ backgroundColor: "#1b1f2b", borderBottom: "1px solid rgba(255, 255, 255, 0.08)" }}>
                      <th style={{ padding: "10px 14px", color: "#94a3b8", fontWeight: 600 }}>Vehicle</th>
                      <th style={{ padding: "10px 14px", color: "#94a3b8", fontWeight: 600 }}>Registration</th>
                      <th style={{ padding: "10px 14px", color: "#94a3b8", fontWeight: 600 }}>Type</th>
                      <th style={{ padding: "10px 14px", color: "#94a3b8", fontWeight: 600 }}>Planned Departure</th>
                      <th style={{ padding: "10px 14px", color: "#94a3b8", fontWeight: 600 }}>Actual Departure</th>
                      <th style={{ padding: "10px 14px", color: "#94a3b8", fontWeight: 600 }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {todayFleet.map((f, i) => (
                      <tr
                        key={f.id || i}
                        style={{
                          borderBottom: i < todayFleet.length - 1 ? "1px solid rgba(255, 255, 255, 0.04)" : "none",
                          backgroundColor: i % 2 === 1 ? "rgba(255, 255, 255, 0.015)" : "transparent",
                        }}
                      >
                        <td style={{ padding: "10px 14px", fontFamily: "monospace", fontWeight: 600, color: "#f8fafc" }}>
                          {f.vehicle?.vehicle_number || f.vehicle_id?.slice(0, 8) || "—"}
                        </td>
                        <td style={{ padding: "10px 14px", color: "#cbd5e1", fontFamily: "monospace" }}>
                          {f.vehicle?.registration_number || "—"}
                        </td>
                        <td style={{ padding: "10px 14px", color: "#94a3b8" }}>
                          {f.vehicle?.vehicle_type || "Standard"}
                        </td>
                        <td style={{ padding: "10px 14px", color: "#cbd5e1" }}>
                          {f.planned_departure ? new Date(f.planned_departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
                        </td>
                        <td style={{ padding: "10px 14px", color: "#cbd5e1" }}>
                          {f.actual_departure ? new Date(f.actual_departure).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
                        </td>
                        <td style={{ padding: "10px 14px" }}>
                          <span
                            style={{
                              fontSize: "11px",
                              fontWeight: 600,
                              padding: "3px 8px",
                              borderRadius: "4px",
                              backgroundColor:
                                f.status === "DEPARTED"
                                  ? "rgba(34, 197, 94, 0.15)"
                                  : f.status === "CANCELLED"
                                  ? "rgba(239, 68, 68, 0.15)"
                                  : "rgba(59, 130, 246, 0.15)",
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

          {/* ── ROUTE STOPS & MAP VIEW SECTION (Natural Flow, NO Nested Scrollbar) ── */}
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              overflow: "hidden",
            }}
          >
            {/* Section Header with Segmented View Toggle */}
            <div
              style={{
                padding: "16px 24px",
                borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                backgroundColor: "rgba(255, 255, 255, 0.02)",
                flexWrap: "wrap",
                gap: "12px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <MapIcon size={16} style={{ color: "#f43f5e" }} />
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
                  Route Stops ({stops.length})
                </h3>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
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
                      padding: "5px 12px",
                      borderRadius: "4px",
                      border: "none",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      backgroundColor: activeTab === "stops" ? "#4f46e5" : "transparent",
                      color: activeTab === "stops" ? "#ffffff" : "#94a3b8",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <List size={14} /> Stops Sequence
                  </button>

                  <button
                    type="button"
                    onClick={() => setActiveTab("map")}
                    style={{
                      padding: "5px 12px",
                      borderRadius: "4px",
                      border: "none",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                      backgroundColor: activeTab === "map" ? "#4f46e5" : "transparent",
                      color: activeTab === "map" ? "#ffffff" : "#94a3b8",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <MapIcon size={14} /> Map View
                  </button>
                </div>

                <button
                  type="button"
                  onClick={handleViewRoute}
                  disabled={!service.route_id}
                  style={{
                    padding: "5px 12px",
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
                  <div style={{ textAlign: "center", padding: "32px 0", color: "#64748b", fontSize: "14px" }}>
                    No stops defined for this service's route.
                  </div>
                ) : (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left" }}>
                    <thead>
                      <tr
                        style={{
                          backgroundColor: "#1b1f2b",
                          borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                        }}
                      >
                        <th style={{ padding: "10px 16px", color: "#94a3b8", fontWeight: 600, width: "60px", textAlign: "center" }}>Seq</th>
                        <th style={{ padding: "10px 16px", color: "#94a3b8", fontWeight: 600, width: "140px" }}>Stop Code</th>
                        <th style={{ padding: "10px 16px", color: "#94a3b8", fontWeight: 600 }}>Stop Name</th>
                        <th style={{ padding: "10px 16px", color: "#94a3b8", fontWeight: 600, textAlign: "right", width: "120px" }}>Distance</th>
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
                          <td style={{ padding: "10px 16px", textAlign: "center", color: "#818cf8", fontFamily: "monospace", fontWeight: 600 }}>
                            {stop.sequence_number}
                          </td>
                          <td style={{ padding: "10px 16px" }}>
                            <span
                              style={{
                                fontFamily: "monospace",
                                fontSize: "12px",
                                color: "#cbd5e1",
                                backgroundColor: "rgba(255, 255, 255, 0.05)",
                                padding: "3px 8px",
                                borderRadius: "4px",
                              }}
                            >
                              {stop.stop_code || "—"}
                            </span>
                          </td>
                          <td style={{ padding: "10px 16px", color: "#f8fafc", fontWeight: 500 }}>
                            {stop.stop_name || "Unknown Stop"}
                          </td>
                          <td style={{ padding: "10px 16px", textAlign: "right", color: "#94a3b8", fontFamily: "monospace" }}>
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
              <div style={{ height: "420px", width: "100%", position: "relative", backgroundColor: "#11141c" }}>
                {stopMarkers.length === 0 && polylinePositions.length === 0 ? (
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#64748b", fontSize: "14px" }}>
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

      {/* ── ORIGIN-CONTEXT OVERLAYS (Section 18) ── */}
      {activeOverlayRouteId && (
        <RouteDetailModal
          routeId={activeOverlayRouteId}
          onClose={() => setActiveOverlayRouteId(null)}
        />
      )}

      {activeOverlayFareId && (
        <FareDetailModal
          fareId={activeOverlayFareId}
          onClose={() => setActiveOverlayFareId(null)}
          onFareUpdated={(updated) => {
            setFareConfig(updated);
          }}
        />
      )}
    </div>
  );
}
