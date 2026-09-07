import { useEffect, useState, useMemo, useCallback } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import {
  ArrowLeft,
  Route as RouteIcon,
  MapPin,
  Banknote,
  Bus,
  Map as MapIcon,
  Edit2,
  Check,
  X,
  AlertCircle,
  Loader2,
  Compass,
  ExternalLink,
  List,
  Navigation,
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from "react-leaflet";
import type * as L from "leaflet";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { StopDetailModal } from "../components/StopDetailModal";
import { FareDetailModal } from "../components/FareDetailModal";
import { SearchableStopSelect } from "../components/SearchableStopSelect";
import {
  apiFetch,
  safeNumber,
  previewRoute,
  updateRoute,
} from "../api/api";

interface RouteDetail {
  id: string;
  route_code: string;
  route_name: string;
  distance_km: number | null;
  status: string;
  geometry: any | null;
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

interface ServiceItem {
  id: string;
  service_code: string;
  service_name: string;
  status: string;
  route_id: string;
  fare_configuration_id: string | null;
  fare_configuration_name?: string;
  fare_is_active?: boolean;
  fare_slabs_count?: number;
  fare_currency?: string;
}

interface FullStopItem {
  id: string;
  stop_code: string;
  name: string;
  latitude: number;
  longitude: number;
  status?: string;
}

interface EditStopItem {
  stop_id: string;
  stop_code: string;
  stop_name: string;
  sequence_number: number;
  latitude?: number | null;
  longitude?: number | null;
}

const formatKm = (val: unknown): string => {
  const num = safeNumber(val);
  if (num === null) return "—";
  return `${num.toFixed(2)} km`;
};

const formatDuration = (sec: unknown): string => {
  const s = safeNumber(sec);
  if (s === null || s < 0) return "—";
  if (s === 0) return "0 min";
  const totalSec = Math.round(s);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const secLeft = totalSec % 60;
  const parts = [];
  if (h > 0) parts.push(`${h} hr`);
  if (m > 0) parts.push(`${m} min`);
  if (secLeft > 0 && h === 0) parts.push(`${secLeft} sec`);
  return parts.length > 0 ? parts.join(" ") : "0 min";
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

export default function RouteDetailsPage() {
  const { routeId } = useParams<{ routeId: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const [route, setRoute] = useState<RouteDetail | null>(null);
  const [stops, setStops] = useState<RouteStop[]>([]);
  const [allStopsCatalog, setAllStopsCatalog] = useState<FullStopItem[]>([]);
  const [operatingServices, setOperatingServices] = useState<ServiceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit Route State
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({
    route_code: "",
    route_name: "",
    status: "ACTIVE",
  });

  // Edit Route Configuration & Stop Sequence State
  const [editStops, setEditStops] = useState<EditStopItem[]>([]);
  const [editCalculationResult, setEditCalculationResult] = useState<any | null>(null);
  const [isEditCalculationStale, setIsEditCalculationStale] = useState(false);
  const [editCalculating, setEditCalculating] = useState(false);
  const [editCalculationError, setEditCalculationError] = useState<string | null>(null);
  const [editDuplicateIgnored, setEditDuplicateIgnored] = useState(false);

  // Add Existing Stop Panel State
  const [isAddingStop, setIsAddingStop] = useState(false);
  const [selectedNewStopId, setSelectedNewStopId] = useState("");
  const [newStopPosition, setNewStopPosition] = useState<string>("end");

  // Remove Stop Confirmation Modal State
  const [stopToRemove, setStopToRemove] = useState<EditStopItem | null>(null);

  // Overlays for Stop and Fare Details (Origin Context Preservation)
  const [activeOverlayStopId, setActiveOverlayStopId] = useState<string | null>(null);
  const [activeOverlayFareId, setActiveOverlayFareId] = useState<string | null>(null);

  // Segmented View Toggle: Stops Sequence vs Map View
  const [activeTab, setActiveTab] = useState<"stops" | "map">("stops");

  const fetchRouteDetails = useCallback(async () => {
    if (!routeId) {
      setError("No Route ID specified.");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Fetch route, stops, all services, and stops catalog concurrently
      const [routeData, stopsData, allServices, allStops] = await Promise.all([
        apiFetch(`/admin/routes/${routeId}`),
        apiFetch(`/admin/routes/${routeId}/stops`).catch(() => []),
        apiFetch("/admin/services").catch(() => []),
        apiFetch("/admin/stops").catch(() => []),
      ]);

      setRoute(routeData);

      // Sort stops by sequence_number
      if (Array.isArray(stopsData)) {
        const sortedStops = [...stopsData].sort(
          (a, b) => Number(a.sequence_number) - Number(b.sequence_number)
        );
        setStops(sortedStops);
      }

      // Filter services operating on this route
      if (Array.isArray(allServices)) {
        const matchingServices = allServices.filter(
          (s: any) => s.route_id === routeId
        );
        setOperatingServices(matchingServices);
      }

      if (Array.isArray(allStops)) {
        setAllStopsCatalog(allStops);
      }
    } catch (err: any) {
      console.error("Failed to load route details:", err);
      setError(err.message || "Failed to load route operational details.");
    } finally {
      setLoading(false);
    }
  }, [routeId]);

  useEffect(() => {
    fetchRouteDetails();
  }, [fetchRouteDetails]);

  // ─────────────────────────────────────────────────────────────
  // OPERATIONAL DERIVATIONS & TRAVEL-TIME AUDIT (Section 8, 9, 10, 21, 25)
  // ─────────────────────────────────────────────────────────────
  // The database table route_stops stores:
  // - distance_from_start: Cumulative distance from route origin (km)
  // - nominal_travel_time_seconds: Cumulative travel time from route origin (sec)
  //
  // Total Travel Time is authoritatively the final stop's nominal_travel_time_seconds.
  // It must NOT sum every stop's already-cumulative time!
  // ─────────────────────────────────────────────────────────────
  const operationalOverview = useMemo(() => {
    let originStop: RouteStop | null = null;
    let destStop: RouteStop | null = null;
    let totalTravelTimeFormatted = "—";
    let totalTravelTimeSeconds: number | null = null;
    let totalDist = "—";

    if (stops.length > 0) {
      originStop = stops[0];
      destStop = stops[stops.length - 1];

      // Total distance from route or final stop distance
      const distFromRoute = safeNumber(route?.distance_km);
      const distFromStop = safeNumber(destStop.distance_from_start);
      if (distFromRoute !== null) {
        totalDist = formatKm(distFromRoute);
      } else if (distFromStop !== null) {
        totalDist = formatKm(distFromStop);
      }

      // Authoritative Total Travel Time = final stop cumulative time
      const finalTimeSec = safeNumber(destStop.nominal_travel_time_seconds);
      if (finalTimeSec !== null && finalTimeSec > 0) {
        totalTravelTimeSeconds = finalTimeSec;
        totalTravelTimeFormatted = formatDuration(finalTimeSec);
      }
    }

    return {
      originStop,
      destStop,
      totalDistance: totalDist,
      totalTravelTime: totalTravelTimeFormatted,
      totalTravelTimeSeconds,
      stopCount: stops.length,
      serviceCount: operatingServices.length,
    };
  }, [stops, route, operatingServices]);

  // Map Polyline and Stop Markers
  const { polylinePositions, stopMarkers, mapBounds } = useMemo(() => {
    let positions: [number, number][] = [];
    if (
      route?.geometry &&
      route.geometry.type === "LineString" &&
      Array.isArray(route.geometry.coordinates)
    ) {
      positions = route.geometry.coordinates
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
      let lat = safeNumber(s.latitude);
      let lng = safeNumber(s.longitude);

      // If lat/lng missing on route_stop, look up in allStopsCatalog
      if ((lat === null || lng === null || lat === 0) && allStopsCatalog.length > 0) {
        const catalogEntry = allStopsCatalog.find((st) => st.id === s.stop_id);
        if (catalogEntry) {
          lat = safeNumber(catalogEntry.latitude);
          lng = safeNumber(catalogEntry.longitude);
        }
      }

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
  }, [route?.geometry, stops, allStopsCatalog]);

  // ─────────────────────────────────────────────────────────────
  // NAVIGATION HANDLERS (Origin Context Preservation)
  // ─────────────────────────────────────────────────────────────
  const handleBack = () => {
    if (location.state?.returnTo) {
      navigate(location.state.returnTo, { state: location.state });
    } else {
      navigate("/routes");
    }
  };

  const handleViewService = (serviceId: string) => {
    if (!route) return;
    // Navigate to Service Details passing origin-context state
    navigate(`/services/${serviceId}`, {
      state: {
        returnTo: `/routes/${route.id}`,
        returnLabel: `Route ${route.route_code}`,
      },
    });
  };

  const handleViewFareChart = (fareId: string | null) => {
    if (!fareId) return;
    // Open Fare Detail overlay directly on RouteDetailsPage
    setActiveOverlayFareId(fareId);
  };

  const handleViewStop = (stopId: string) => {
    if (!stopId) return;
    // Open Stop Detail overlay directly on RouteDetailsPage
    setActiveOverlayStopId(stopId);
  };

  // ─────────────────────────────────────────────────────────────
  // EDIT ROUTE HOOKS & DERIVATIONS
  // ─────────────────────────────────────────────────────────────
  const isDirty = useMemo(() => {
    if (!isEditing || !route) return false;
    const metaChanged =
      editForm.route_code.trim() !== (route.route_code || "").trim() ||
      editForm.route_name.trim() !== (route.route_name || "").trim() ||
      editForm.status !== route.status;

    const originalStopsKey = stops.map((s) => s.stop_id).join(",");
    const currentStopsKey = editStops.map((s) => s.stop_id).join(",");
    const stopsChanged = originalStopsKey !== currentStopsKey;

    return metaChanged || stopsChanged;
  }, [isEditing, route, editForm, editStops, stops]);

  const { editPolylinePositions, editStopMarkers, editMapBounds } = useMemo(() => {
    if (!isEditing) {
      return { editPolylinePositions: [], editStopMarkers: [], editMapBounds: null };
    }

    let positions: [number, number][] = [];
    const geom = editCalculationResult?.geometry || route?.geometry;
    if (
      geom &&
      geom.type === "LineString" &&
      Array.isArray(geom.coordinates)
    ) {
      positions = geom.coordinates
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
      isStart: boolean;
      isEnd: boolean;
    }[] = [];

    editStops.forEach((s, idx) => {
      let lat = safeNumber(s.latitude);
      let lng = safeNumber(s.longitude);

      if ((lat === null || lng === null || lat === 0) && allStopsCatalog.length > 0) {
        const cat = allStopsCatalog.find((st) => st.id === s.stop_id);
        if (cat) {
          lat = safeNumber(cat.latitude);
          lng = safeNumber(cat.longitude);
        }
      }

      if (lat !== null && lng !== null && lat !== 0 && lng !== 0) {
        markers.push({
          latlng: [lat, lng],
          stop_name: s.stop_name || "Stop",
          stop_code: s.stop_code || "",
          sequence: idx + 1,
          isStart: idx === 0,
          isEnd: idx === editStops.length - 1,
        });
      }
    });

    let bounds: L.LatLngBounds | null = null;
    if (positions.length > 0 || markers.length > 0) {
      const allPts = [...positions, ...markers.map((m) => m.latlng)];
      if (allPts.length > 0 && typeof window !== "undefined" && (window as any).L) {
        bounds = (window as any).L.latLngBounds(allPts);
      }
    }

    return { editPolylinePositions: positions, editStopMarkers: markers, editMapBounds: bounds };
  }, [isEditing, editCalculationResult?.geometry, route?.geometry, editStops, allStopsCatalog]);

  const editDerivedOverview = useMemo(() => {
    let fromStop: EditStopItem | null = null;
    let toStop: EditStopItem | null = null;
    let distFormatted = "—";
    let travelTimeFormatted = "—";

    if (editStops.length > 0) {
      fromStop = editStops[0];
      toStop = editStops[editStops.length - 1];

      if (editCalculationResult?.distance_km != null) {
        distFormatted = formatKm(editCalculationResult.distance_km);
      } else if (route?.distance_km != null) {
        distFormatted = formatKm(route.distance_km);
      }

      if (editCalculationResult?.duration_seconds != null && editCalculationResult.duration_seconds > 0) {
        travelTimeFormatted = formatDuration(editCalculationResult.duration_seconds);
      } else if (operationalOverview.totalTravelTimeSeconds != null) {
        travelTimeFormatted = formatDuration(operationalOverview.totalTravelTimeSeconds);
      }
    }

    return {
      fromStop,
      toStop,
      totalDistance: distFormatted,
      totalTravelTime: travelTimeFormatted,
      stopCount: editStops.length,
    };
  }, [editStops, editCalculationResult, route, operationalOverview]);

  // ─────────────────────────────────────────────────────────────
  // EDIT ROUTE HANDLERS
  // ─────────────────────────────────────────────────────────────
  const handleStartEdit = () => {
    if (!route) return;
    setSaveError(null);
    setSaveSuccess(null);
    setEditForm({
      route_code: route.route_code || "",
      route_name: route.route_name || "",
      status: route.status || "ACTIVE",
    });

    const initialStops: EditStopItem[] = stops.map((s, idx) => ({
      stop_id: s.stop_id,
      stop_code: s.stop_code || "",
      stop_name: s.stop_name || "",
      sequence_number: idx + 1,
      latitude: s.latitude,
      longitude: s.longitude,
    }));
    setEditStops(initialStops);

    // Authoritative initial preview
    setEditCalculationResult({
      distance_km: route.distance_km || 0,
      duration_seconds: operationalOverview.totalTravelTimeSeconds || 0,
      geometry: route.geometry,
      stops: initialStops.map((s) => ({
        stop_id: s.stop_id,
        stop_code: s.stop_code,
        stop_name: s.stop_name,
        sequence_number: s.sequence_number,
        latitude: s.latitude || 0,
        longitude: s.longitude || 0,
      })),
    });

    setIsEditCalculationStale(false);
    setEditCalculationError(null);
    setEditDuplicateIgnored(false);
    setIsAddingStop(false);
    setSelectedNewStopId("");
    setStopToRemove(null);
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setSaveError(null);
    setStopToRemove(null);
    setIsAddingStop(false);
    setIsEditing(false);
  };

  const handleMoveStop = (index: number, direction: "up" | "down") => {
    if (direction === "up" && index === 0) return;
    if (direction === "down" && index === editStops.length - 1) return;
    const targetIdx = direction === "up" ? index - 1 : index + 1;
    const updated = [...editStops];
    [updated[index], updated[targetIdx]] = [updated[targetIdx], updated[index]];
    const resequenced = updated.map((s, idx) => ({ ...s, sequence_number: idx + 1 }));
    setEditStops(resequenced);
    setIsEditCalculationStale(true);
  };

  const handlePromptRemoveStop = (stop: EditStopItem) => {
    if (editStops.length <= 2) {
      setSaveError("A route must contain at least 2 stops (Start and End). Cannot remove further stops.");
      return;
    }
    setSaveError(null);
    setStopToRemove(stop);
  };

  const handleConfirmRemoveStop = (stopId: string) => {
    const updated = editStops.filter((s) => s.stop_id !== stopId);
    const resequenced = updated.map((s, idx) => ({ ...s, sequence_number: idx + 1 }));
    setEditStops(resequenced);
    setIsEditCalculationStale(true);
    setStopToRemove(null);
  };

  const handleConfirmAddStop = () => {
    if (!selectedNewStopId) return;
    const catalogStop = allStopsCatalog.find((s) => s.id === selectedNewStopId);
    if (!catalogStop) return;

    const newEntry: EditStopItem = {
      stop_id: catalogStop.id,
      stop_code: catalogStop.stop_code,
      stop_name: catalogStop.name,
      sequence_number: 1,
      latitude: catalogStop.latitude,
      longitude: catalogStop.longitude,
    };

    let updated = [...editStops];
    if (newStopPosition === "start") {
      updated = [newEntry, ...updated];
    } else if (newStopPosition === "end") {
      updated = [...updated, newEntry];
    } else {
      const idx = parseInt(newStopPosition, 10);
      updated.splice(idx, 0, newEntry);
    }

    const resequenced = updated.map((s, idx) => ({ ...s, sequence_number: idx + 1 }));
    setEditStops(resequenced);
    setSelectedNewStopId("");
    setIsAddingStop(false);
    setIsEditCalculationStale(true);
  };

  const handleChangeStopAtIndex = (index: number, newStopId: string) => {
    const catalogStop = allStopsCatalog.find((s) => s.id === newStopId);
    if (!catalogStop) return;

    const updated = [...editStops];
    updated[index] = {
      ...updated[index],
      stop_id: catalogStop.id,
      stop_code: catalogStop.stop_code,
      stop_name: catalogStop.name,
      latitude: catalogStop.latitude,
      longitude: catalogStop.longitude,
    };
    setEditStops(updated);
    setIsEditCalculationStale(true);
  };

  const handleRecalculateEditRoute = async () => {
    if (editStops.length < 2) {
      setEditCalculationError("A route must contain at least 2 stops.");
      return;
    }
    const stopIds = editStops.map((s) => s.stop_id);
    const uniqueIds = new Set(stopIds);
    if (uniqueIds.size !== stopIds.length) {
      setEditCalculationError("Duplicate stops in route sequence are not permitted.");
      return;
    }

    setEditCalculating(true);
    setEditCalculationError(null);
    setEditDuplicateIgnored(false);

    try {
      const start_stop_id = stopIds[0];
      const end_stop_id = stopIds[stopIds.length - 1];
      const intermediate_stop_ids = stopIds.slice(1, -1);

      const result = await previewRoute({
        start_stop_id,
        end_stop_id,
        intermediate_stop_ids,
        exclude_route_id: route?.id,
      });

      setEditCalculationResult(result);
      setIsEditCalculationStale(false);
    } catch (err: any) {
      setEditCalculationError(err.message || "Failed to calculate road route.");
    } finally {
      setEditCalculating(false);
    }
  };

  const handleSaveEdit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (saving || !route) return;
    setSaveError(null);
    setSaveSuccess(null);

    const trimmedCode = editForm.route_code.trim();
    const trimmedName = editForm.route_name.trim();

    if (!trimmedCode) {
      setSaveError("Route Code cannot be empty.");
      return;
    }
    if (!trimmedName) {
      setSaveError("Route Name cannot be empty.");
      return;
    }
    if (editStops.length < 2) {
      setSaveError("A route requires at least 2 stops (Start and End).");
      return;
    }

    const stopIds = editStops.map((s) => s.stop_id);
    const uniqueIds = new Set(stopIds);
    if (uniqueIds.size !== stopIds.length) {
      setSaveError("Duplicate stops in route sequence are not permitted.");
      return;
    }

    if (
      editCalculationResult?.duplicate_match?.is_duplicate &&
      !editDuplicateIgnored
    ) {
      setSaveError("Please review the duplicate route warning before proceeding.");
      return;
    }

    const originalStopsKey = stops.map((s) => s.stop_id).join(",");
    const currentStopsKey = stopIds.join(",");
    const stopsChanged = originalStopsKey !== currentStopsKey;

    try {
      setSaving(true);

      const payload: any = {
        route_code: trimmedCode,
        route_name: trimmedName,
        status: editForm.status,
      };

      if (stopsChanged) {
        payload.start_stop_id = stopIds[0];
        payload.end_stop_id = stopIds[stopIds.length - 1];
        payload.intermediate_stop_ids = stopIds.slice(1, -1);
      }

      const updated = await updateRoute(route.id, payload);

      setRoute((prev) => (prev ? { ...prev, ...updated } : updated));
      setSaveSuccess("Route configuration and topology updated successfully.");
      setIsEditing(false);

      // Refresh to ensure all dependencies and sequences remain authoritative
      await fetchRouteDetails();
    } catch (err: any) {
      console.error("Failed to save route edit:", err);
      setSaveError(err.message || "Failed to update route.");
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
          <ArrowLeft size={16} /> Back to Routes
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
          <Loader2 size={32} className="animate-spin" style={{ color: "#38bdf8" }} />
          <span style={{ fontSize: "15px" }}>Loading route operational details...</span>
        </div>
      </div>
    );
  }

  if (error || !route) {
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
          <ArrowLeft size={16} /> Back to Routes
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
            <span>Route Not Found</span>
          </div>
          <p style={{ margin: 0, color: "#cbd5e1", fontSize: "14px" }}>
            {error || `The requested route with ID "${routeId}" could not be retrieved.`}
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
              Return to Routes List
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
          <ArrowLeft size={16} /> Back to Routes
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

      {/* ── FULL-PAGE ROUTE HEADER (Section 7) ── */}
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
              backgroundColor: "rgba(56, 189, 248, 0.15)",
              border: "1px solid rgba(56, 189, 248, 0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <RouteIcon size={26} style={{ color: "#38bdf8" }} />
          </div>
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: "12px",
                fontWeight: 700,
                color: "#38bdf8",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: "4px",
              }}
            >
              ROUTE {isEditing ? "· EDIT MODE" : ""}
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
                {route.route_code}
              </h1>
              {route.status && (
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: 600,
                    padding: "3px 10px",
                    borderRadius: "6px",
                    backgroundColor:
                      route.status === "ACTIVE"
                        ? "rgba(34, 197, 94, 0.15)"
                        : "rgba(148, 163, 184, 0.12)",
                    color: route.status === "ACTIVE" ? "#4ade80" : "#94a3b8",
                    border:
                      route.status === "ACTIVE"
                        ? "1px solid rgba(34, 197, 94, 0.3)"
                        : "1px solid rgba(148, 163, 184, 0.2)",
                  }}
                >
                  {route.status}
                </span>
              )}
            </div>
            <div style={{ fontSize: "14px", color: "#cbd5e1", marginTop: "4px" }}>
              {route.route_name}
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
                disabled={saving || !isDirty}
                style={{
                  padding: "8px 20px",
                  backgroundColor: "#0284c7",
                  border: "1px solid #38bdf8",
                  borderRadius: "8px",
                  color: "#ffffff",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: saving || !isDirty ? "not-allowed" : "pointer",
                  opacity: saving || !isDirty ? 0.6 : 1,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  boxShadow: "0 2px 8px rgba(2, 132, 199, 0.35)",
                  transition: "all 0.15s ease",
                }}
              >
                {saving ? (
                  <>
                    <Loader2 size={15} className="animate-spin" /> Saving...
                  </>
                ) : (
                  <>
                    <Check size={15} /> Save Changes
                  </>
                )}
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={handleStartEdit}
              style={{
                padding: "8px 18px",
                backgroundColor: "rgba(56, 189, 248, 0.15)",
                border: "1px solid rgba(56, 189, 248, 0.35)",
                borderRadius: "8px",
                color: "#7dd3fc",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                transition: "all 0.15s ease",
              }}
            >
              <Edit2 size={14} /> Edit Route
            </button>
          )}
        </div>
      </div>

      {/* ── EDIT ROUTE FORM VIEW (Section 19, 20) ── */}
      {isEditing ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "24px",
          }}
        >
          {/* Error Banner */}
          {saveError && (
            <div
              style={{
                padding: "14px 18px",
                borderRadius: "10px",
                backgroundColor: "rgba(239, 68, 68, 0.12)",
                border: "1px solid rgba(239, 68, 68, 0.35)",
                color: "#f87171",
                fontSize: "14px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <AlertCircle size={18} style={{ flexShrink: 0 }} />
              <span>{saveError}</span>
            </div>
          )}

          {/* 1. ROUTE METADATA CARD */}
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              padding: "24px 28px",
              display: "flex",
              flexDirection: "column",
              gap: "20px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", borderBottom: "1px solid rgba(255, 255, 255, 0.06)", paddingBottom: "12px" }}>
              <Edit2 size={16} style={{ color: "#38bdf8" }} />
              <h2
                style={{
                  fontSize: "13px",
                  fontWeight: 700,
                  color: "#f8fafc",
                  margin: 0,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                Route Configuration & Metadata
              </h2>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: "20px",
              }}
            >
              <div>
                <label
                  htmlFor="edit_route_code"
                  style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "6px" }}
                >
                  Route Code *
                </label>
                <input
                  id="edit_route_code"
                  type="text"
                  value={editForm.route_code}
                  onChange={(e) => setEditForm({ ...editForm, route_code: e.target.value })}
                  placeholder="e.g. R001-SD5"
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
                  htmlFor="edit_route_status"
                  style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "6px" }}
                >
                  Status *
                </label>
                <select
                  id="edit_route_status"
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
                  <option value="DRAFT">DRAFT</option>
                </select>
              </div>

              <div style={{ gridColumn: "1 / -1" }}>
                <label
                  htmlFor="edit_route_name"
                  style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#94a3b8", marginBottom: "6px" }}
                >
                  Route Name / Description *
                </label>
                <input
                  id="edit_route_name"
                  type="text"
                  value={editForm.route_name}
                  onChange={(e) => setEditForm({ ...editForm, route_name: e.target.value })}
                  placeholder="e.g. Sonarpur Station - Khariberea, via Tollygunge & New Alipore"
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
            </div>
          </div>

          {/* 2. ORDERED ROUTE STOPS SEQUENCE (NATURAL PAGE SCROLL) */}
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              padding: "24px 28px",
              display: "flex",
              flexDirection: "column",
              gap: "20px",
            }}
          >
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                justifyContent: "space-between",
                alignItems: "center",
                gap: "12px",
                borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
                paddingBottom: "14px",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <MapPin size={18} style={{ color: "#38bdf8" }} />
                  <h3
                    style={{
                      fontSize: "14px",
                      fontWeight: 700,
                      color: "#f8fafc",
                      margin: 0,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                    }}
                  >
                    Route Stops Sequence
                  </h3>
                  <span
                    style={{
                      fontSize: "12px",
                      fontWeight: 600,
                      padding: "2px 8px",
                      borderRadius: "6px",
                      backgroundColor: "rgba(56, 189, 248, 0.15)",
                      color: "#38bdf8",
                      border: "1px solid rgba(56, 189, 248, 0.3)",
                    }}
                  >
                    {editStops.length} Total Stops
                  </span>
                </div>
                <p style={{ fontSize: "13px", color: "#94a3b8", margin: "4px 0 0 0" }}>
                  Existing stops only. The ordered sequence defines authentic route topology from Start (#1) to End (#{editStops.length}).
                </p>
              </div>

              {!isAddingStop && (
                <button
                  type="button"
                  onClick={() => setIsAddingStop(true)}
                  style={{
                    padding: "8px 16px",
                    backgroundColor: "rgba(56, 189, 248, 0.12)",
                    border: "1px solid rgba(56, 189, 248, 0.35)",
                    borderRadius: "8px",
                    color: "#7dd3fc",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    transition: "all 0.15s ease",
                  }}
                >
                  <Plus size={15} /> + Add Existing Stop
                </button>
              )}
            </div>

            {/* ADD EXISTING STOP CARD (Section 7) */}
            {isAddingStop && (
              <div
                style={{
                  padding: "18px 20px",
                  borderRadius: "10px",
                  backgroundColor: "rgba(56, 189, 248, 0.05)",
                  border: "1px solid rgba(56, 189, 248, 0.3)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "12px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "13px", fontWeight: 700, color: "#38bdf8", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    + Add Existing Stop to Route Sequence
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setIsAddingStop(false);
                      setSelectedNewStopId("");
                    }}
                    style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", padding: "4px" }}
                  >
                    <X size={16} />
                  </button>
                </div>
                <p style={{ fontSize: "12px", color: "#cbd5e1", margin: 0 }}>
                  Select an existing stop entity from the catalog. This adds it to this route's sequence and <strong style={{ color: "#4ade80" }}>does NOT create a new Stop entity</strong> in the database.
                </p>
                <div style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
                  <div style={{ flex: 1, minWidth: "280px" }}>
                    <SearchableStopSelect
                      stops={allStopsCatalog}
                      value={selectedNewStopId}
                      onChange={(val) => setSelectedNewStopId(val)}
                      placeholder="-- Search catalog by code or name --"
                      disabledStopIds={editStops.map((s) => s.stop_id)}
                      accentColor="#38bdf8"
                    />
                  </div>
                  <div style={{ width: "220px" }}>
                    <select
                      value={newStopPosition}
                      onChange={(e) => setNewStopPosition(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "10px 14px",
                        backgroundColor: "#0d1017",
                        border: "1px solid rgba(255, 255, 255, 0.15)",
                        borderRadius: "8px",
                        color: "#f8fafc",
                        fontSize: "13px",
                        outline: "none",
                      }}
                    >
                      <option value="end">Add at End (Pos {editStops.length + 1})</option>
                      <option value="start">Add at Beginning (Pos 1)</option>
                      {editStops.slice(0, -1).map((st, i) => (
                        <option key={i} value={String(i + 1)}>
                          Insert after #{i + 1} ({st.stop_code || `Stop ${i + 1}`})
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="button"
                    onClick={handleConfirmAddStop}
                    disabled={!selectedNewStopId}
                    style={{
                      padding: "10px 18px",
                      backgroundColor: selectedNewStopId ? "#0284c7" : "rgba(255, 255, 255, 0.05)",
                      border: selectedNewStopId ? "1px solid #38bdf8" : "1px solid rgba(255, 255, 255, 0.1)",
                      borderRadius: "8px",
                      color: selectedNewStopId ? "#ffffff" : "#64748b",
                      fontSize: "13px",
                      fontWeight: 600,
                      cursor: selectedNewStopId ? "pointer" : "not-allowed",
                      transition: "all 0.15s ease",
                    }}
                  >
                    Add to Route
                  </button>
                </div>
              </div>
            )}

            {/* ORDERED STOPS LIST (FULL LIST FLOWS NATURALLY IN PAGE) */}
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {editStops.map((stop, idx) => {
                const isFirst = idx === 0;
                const isLast = idx === editStops.length - 1;

                return (
                  <div
                    key={`${stop.stop_id}-${idx}`}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      backgroundColor: isFirst
                        ? "rgba(16, 185, 129, 0.06)"
                        : isLast
                        ? "rgba(239, 68, 68, 0.06)"
                        : "rgba(255, 255, 255, 0.02)",
                      border: isFirst
                        ? "1px solid rgba(16, 185, 129, 0.25)"
                        : isLast
                        ? "1px solid rgba(239, 68, 68, 0.25)"
                        : "1px solid rgba(255, 255, 255, 0.06)",
                      borderRadius: "10px",
                      padding: "12px 16px",
                      transition: "background-color 0.15s ease",
                    }}
                  >
                    {/* Sequence Badge */}
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", width: "110px", flexShrink: 0 }}>
                      <span
                        style={{
                          fontSize: "14px",
                          fontWeight: 700,
                          color: isFirst ? "#10b981" : isLast ? "#ef4444" : "#94a3b8",
                          width: "28px",
                          textAlign: "center",
                          fontFamily: "monospace",
                        }}
                      >
                        #{idx + 1}
                      </span>
                      {isFirst ? (
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: 700,
                            padding: "2px 6px",
                            borderRadius: "4px",
                            backgroundColor: "rgba(16, 185, 129, 0.18)",
                            color: "#10b981",
                            border: "1px solid rgba(16, 185, 129, 0.4)",
                            letterSpacing: "0.04em",
                          }}
                        >
                          ORIGIN
                        </span>
                      ) : isLast ? (
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: 700,
                            padding: "2px 6px",
                            borderRadius: "4px",
                            backgroundColor: "rgba(239, 68, 68, 0.18)",
                            color: "#ef4444",
                            border: "1px solid rgba(239, 68, 68, 0.4)",
                            letterSpacing: "0.04em",
                          }}
                        >
                          FINAL
                        </span>
                      ) : (
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: 600,
                            padding: "2px 6px",
                            borderRadius: "4px",
                            backgroundColor: "rgba(148, 163, 184, 0.12)",
                            color: "#94a3b8",
                          }}
                        >
                          STOP
                        </span>
                      )}
                    </div>

                    {/* Searchable Stop Selector */}
                    <div style={{ flex: 1, minWidth: "220px" }}>
                      <SearchableStopSelect
                        stops={allStopsCatalog}
                        value={stop.stop_id}
                        onChange={(val) => handleChangeStopAtIndex(idx, val)}
                        disabledStopIds={editStops.map((s) => s.stop_id).filter((id) => id !== stop.stop_id)}
                        accentColor={isFirst ? "#10b981" : isLast ? "#ef4444" : "#38bdf8"}
                        required
                      />
                    </div>

                    {/* Reorder & Action Controls */}
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
                      <button
                        type="button"
                        onClick={() => handleMoveStop(idx, "up")}
                        disabled={idx === 0}
                        title={idx === 0 ? "Already first stop" : "Move Up"}
                        style={{
                          padding: "7px 9px",
                          backgroundColor: "rgba(255, 255, 255, 0.05)",
                          border: "1px solid rgba(255, 255, 255, 0.12)",
                          borderRadius: "6px",
                          color: idx === 0 ? "#475569" : "#cbd5e1",
                          cursor: idx === 0 ? "not-allowed" : "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        <ArrowUp size={15} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleMoveStop(idx, "down")}
                        disabled={idx === editStops.length - 1}
                        title={idx === editStops.length - 1 ? "Already final stop" : "Move Down"}
                        style={{
                          padding: "7px 9px",
                          backgroundColor: "rgba(255, 255, 255, 0.05)",
                          border: "1px solid rgba(255, 255, 255, 0.12)",
                          borderRadius: "6px",
                          color: idx === editStops.length - 1 ? "#475569" : "#cbd5e1",
                          cursor: idx === editStops.length - 1 ? "not-allowed" : "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        <ArrowDown size={15} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handlePromptRemoveStop(stop)}
                        title="Remove from Route (does not delete stop entity)"
                        style={{
                          padding: "7px 12px",
                          backgroundColor: "rgba(239, 68, 68, 0.1)",
                          border: "1px solid rgba(239, 68, 68, 0.25)",
                          borderRadius: "6px",
                          color: "#f87171",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "5px",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <Trash2 size={13} />
                        <span style={{ display: "inline" }}>Remove from Route</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Convenience bottom + Add Existing Stop button */}
            {!isAddingStop && editStops.length > 4 && (
              <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: "8px" }}>
                <button
                  type="button"
                  onClick={() => setIsAddingStop(true)}
                  style={{
                    padding: "8px 16px",
                    backgroundColor: "rgba(56, 189, 248, 0.12)",
                    border: "1px solid rgba(56, 189, 248, 0.35)",
                    borderRadius: "8px",
                    color: "#7dd3fc",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <Plus size={15} /> + Add Existing Stop
                </button>
              </div>
            )}
          </div>

          {/* 3. ROUTE CALCULATION & TOPOLOGY CARD */}
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              padding: "24px 28px",
              display: "flex",
              flexDirection: "column",
              gap: "20px",
            }}
          >
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "12px",
                borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
                paddingBottom: "14px",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <RefreshCw size={16} style={{ color: "#38bdf8" }} />
                  <h3
                    style={{
                      fontSize: "14px",
                      fontWeight: 700,
                      color: "#f8fafc",
                      margin: 0,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                    }}
                  >
                    Route Topology & Calculation
                  </h3>
                </div>
                <p style={{ fontSize: "13px", color: "#94a3b8", margin: "4px 0 0 0" }}>
                  Calculates authoritative road distance and road-following geometry via the routing engine.
                </p>
              </div>

              <button
                type="button"
                onClick={handleRecalculateEditRoute}
                disabled={editCalculating || editStops.length < 2}
                style={{
                  padding: "9px 20px",
                  backgroundColor: isEditCalculationStale ? "#0284c7" : "rgba(56, 189, 248, 0.15)",
                  border: isEditCalculationStale ? "1px solid #38bdf8" : "1px solid rgba(56, 189, 248, 0.35)",
                  borderRadius: "8px",
                  color: isEditCalculationStale ? "#ffffff" : "#7dd3fc",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: editCalculating || editStops.length < 2 ? "not-allowed" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  boxShadow: isEditCalculationStale ? "0 2px 8px rgba(2, 132, 199, 0.35)" : "none",
                  opacity: editCalculating || editStops.length < 2 ? 0.5 : 1,
                  transition: "all 0.15s ease",
                }}
              >
                <RefreshCw size={15} className={editCalculating ? "animate-spin" : ""} />
                {editCalculating
                  ? "Calculating road route..."
                  : isEditCalculationStale
                  ? "Recalculate Route Topology"
                  : editCalculationResult
                  ? "Refresh Route Calculation"
                  : "Calculate Route"}
              </button>
            </div>

            {/* METRICS & STATUS GRID */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                gap: "16px",
              }}
            >
              <div
                style={{
                  backgroundColor: "#0d1017",
                  padding: "16px 20px",
                  borderRadius: "10px",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                }}
              >
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    color: "#94a3b8",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    display: "block",
                    marginBottom: "6px",
                  }}
                >
                  Calculated Road Distance
                </span>
                <span style={{ fontSize: "22px", fontWeight: 700, color: "#f8fafc", fontFamily: "monospace" }}>
                  {editCalculationResult ? formatKm(editCalculationResult.distance_km) : formatKm(route?.distance_km)}
                </span>
                <span style={{ fontSize: "11px", color: "#64748b", display: "block", marginTop: "4px" }}>
                  Road-routing distance
                </span>
              </div>

              <div
                style={{
                  backgroundColor: "#0d1017",
                  padding: "16px 20px",
                  borderRadius: "10px",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                }}
              >
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    color: "#94a3b8",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    display: "block",
                    marginBottom: "6px",
                  }}
                >
                  Estimated Road Duration
                </span>
                <span style={{ fontSize: "22px", fontWeight: 700, color: "#c084fc", fontFamily: "monospace" }}>
                  {editCalculationResult ? formatDuration(editCalculationResult.duration_seconds) : operationalOverview.totalTravelTime}
                </span>
                <span style={{ fontSize: "11px", color: "#64748b", display: "block", marginTop: "4px" }}>
                  Final cumulative duration
                </span>
              </div>

              <div
                style={{
                  backgroundColor: "#0d1017",
                  padding: "16px 20px",
                  borderRadius: "10px",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "center",
                }}
              >
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    color: "#94a3b8",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    display: "block",
                    marginBottom: "6px",
                  }}
                >
                  Routing Engine Status
                </span>
                {editCalculating ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#38bdf8", fontWeight: 600, fontSize: "13px" }}>
                    <RefreshCw size={16} className="animate-spin" />
                    <span>Calculating road route...</span>
                  </div>
                ) : isEditCalculationStale ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#f59e0b", fontWeight: 600, fontSize: "13px" }}>
                    <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                    <span>Sequence modified — Refresh required</span>
                  </div>
                ) : editCalculationResult ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#4ade80", fontWeight: 700, fontSize: "13px" }}>
                    <CheckCircle2 size={16} style={{ flexShrink: 0 }} />
                    <span>✓ Road topology synchronized</span>
                  </div>
                ) : editCalculationError ? (
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#f87171", fontWeight: 600, fontSize: "12px" }}>
                    <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                    <span>{editCalculationError}</span>
                  </div>
                ) : (
                  <span style={{ fontSize: "13px", color: "#94a3b8" }}>Ready for calculation</span>
                )}
              </div>
            </div>

            {/* DUPLICATE ROUTE DETECTION WARNING */}
            {editCalculationResult?.duplicate_match?.is_duplicate && (
              <div
                style={{
                  padding: "16px 20px",
                  backgroundColor: "rgba(245, 158, 11, 0.1)",
                  border: "1px solid rgba(245, 158, 11, 0.35)",
                  borderRadius: "10px",
                  color: "#fef3c7",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700, fontSize: "14px", color: "#f59e0b", marginBottom: "8px" }}>
                  <AlertTriangle size={18} style={{ flexShrink: 0 }} />
                  <span>EXISTING ROUTE SEQUENCE MATCH</span>
                </div>
                <p style={{ fontSize: "13px", color: "#cbd5e1", margin: "0 0 10px 0" }}>
                  Another existing route in your organization already has this exact ordered stop sequence:
                </p>
                <div
                  style={{
                    backgroundColor: "#0d1017",
                    padding: "12px 16px",
                    borderRadius: "8px",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    fontSize: "12px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "6px",
                    marginBottom: "12px",
                  }}
                >
                  <div>
                    <span style={{ fontWeight: 600, color: "#94a3b8" }}>Route Code:</span>{" "}
                    <span style={{ fontFamily: "monospace", color: "#38bdf8", fontWeight: 700 }}>
                      {editCalculationResult.duplicate_match.route_code}
                    </span>
                  </div>
                  <div>
                    <span style={{ fontWeight: 600, color: "#94a3b8" }}>Route Name:</span>{" "}
                    <span style={{ color: "#f8fafc" }}>{editCalculationResult.duplicate_match.route_name}</span>
                  </div>
                  <div>
                    <span style={{ fontWeight: 600, color: "#94a3b8" }}>Route ID:</span>{" "}
                    <span style={{ fontFamily: "monospace", color: "#64748b" }}>{editCalculationResult.duplicate_match.existing_route_id}</span>
                  </div>
                  <div>
                    <span style={{ fontWeight: 600, color: "#94a3b8" }}>Matching sequence:</span>{" "}
                    <span style={{ color: "#f8fafc" }}>{editCalculationResult.duplicate_match.matching_stops?.join(" → ")}</span>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <button
                    type="button"
                    onClick={() => {
                      const dupId = editCalculationResult.duplicate_match?.existing_route_id;
                      if (dupId) navigate(`/routes/${dupId}`);
                    }}
                    style={{
                      padding: "7px 14px",
                      backgroundColor: "rgba(56, 189, 248, 0.15)",
                      border: "1px solid rgba(56, 189, 248, 0.35)",
                      borderRadius: "6px",
                      color: "#7dd3fc",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <ExternalLink size={13} /> View Matching Route
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditDuplicateIgnored(true)}
                    style={{
                      padding: "7px 14px",
                      backgroundColor: editDuplicateIgnored ? "rgba(16, 185, 129, 0.2)" : "rgba(255, 255, 255, 0.05)",
                      border: editDuplicateIgnored ? "1px solid #10b981" : "1px solid rgba(255, 255, 255, 0.15)",
                      borderRadius: "6px",
                      color: editDuplicateIgnored ? "#4ade80" : "#cbd5e1",
                      fontSize: "12px",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    {editDuplicateIgnored ? "✓ Confirmed to Proceed" : "Confirm to Proceed"}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* 4. ROUTE MAP / TOPOLOGY PREVIEW CARD */}
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              style={{
                padding: "16px 24px",
                borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                backgroundColor: "rgba(255, 255, 255, 0.02)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <MapIcon size={16} style={{ color: "#38bdf8" }} />
                <h3
                  style={{
                    fontSize: "13px",
                    fontWeight: 700,
                    color: "#f8fafc",
                    margin: 0,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                  }}
                >
                  Route Map / Topology Preview
                </h3>
              </div>
              <span
                style={{
                  fontSize: "12px",
                  color: isEditCalculationStale ? "#f59e0b" : "#94a3b8",
                  fontWeight: 500,
                }}
              >
                {isEditCalculationStale && "⚠️ Needs Refresh • "}
                {editStops.length} Stops • {editDerivedOverview.totalDistance}
              </span>
            </div>

            <div style={{ height: "420px", width: "100%", position: "relative", backgroundColor: "#11141c" }}>
              {editStopMarkers.length === 0 && editPolylinePositions.length === 0 ? (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#64748b", fontSize: "14px" }}>
                  Route map preview is not available.
                </div>
              ) : (
                <ErrorBoundary fallbackTitle="Map View Unavailable" fallbackMessage="Route map preview could not be rendered.">
                  <MapContainer
                    key={isEditing ? "edit-mode-map" : "view-mode-map"}
                    center={[22.5726, 88.3639]}
                    zoom={12}
                    style={{ height: "100%", width: "100%", zIndex: 0 }}
                    scrollWheelZoom={false}
                  >
                    <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />
                    {editPolylinePositions.length > 0 && (
                      <Polyline positions={editPolylinePositions} color="#0284c7" weight={5} opacity={0.85} />
                    )}
                    {editStopMarkers.map((sm, i) => (
                      <Marker key={i} position={sm.latlng}>
                        <Popup>
                          <div style={{ color: "#0f172a", fontSize: "12px", lineHeight: "1.4" }}>
                            <strong style={{ fontSize: "13px" }}>{sm.stop_name}</strong>
                            <div>Code: <code>{sm.stop_code}</code></div>
                            <div>
                              Sequence: #{sm.sequence}{" "}
                              {sm.isStart ? "(Origin)" : sm.isEnd ? "(Final)" : ""}
                            </div>
                          </div>
                        </Popup>
                      </Marker>
                    ))}
                    <BoundsWrapper bounds={editMapBounds} />
                  </MapContainer>
                </ErrorBoundary>
              )}
            </div>
          </div>

          {/* 5. DERIVED ROUTE INFORMATION CARD */}
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              padding: "20px 24px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
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
                Derived Route Information
              </h3>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "16px",
              }}
            >
              {/* FROM */}
              <div
                style={{
                  padding: "16px",
                  borderRadius: "10px",
                  backgroundColor: "rgba(255, 255, 255, 0.02)",
                  border: "1px solid rgba(255, 255, 255, 0.06)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 600, color: "#10b981", textTransform: "uppercase", marginBottom: "6px" }}>
                  FROM (Origin Depot / Stop #1)
                </div>
                <div style={{ fontSize: "15px", fontWeight: 700, color: "#f8fafc" }}>
                  {editDerivedOverview.fromStop?.stop_name || "—"}
                </div>
                <div style={{ fontSize: "12px", color: "#94a3b8", fontFamily: "monospace", marginTop: "2px" }}>
                  {editDerivedOverview.fromStop?.stop_code || "—"}
                </div>
              </div>

              {/* TO */}
              <div
                style={{
                  padding: "16px",
                  borderRadius: "10px",
                  backgroundColor: "rgba(255, 255, 255, 0.02)",
                  border: "1px solid rgba(255, 255, 255, 0.06)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 600, color: "#ef4444", textTransform: "uppercase", marginBottom: "6px" }}>
                  TO (Destination Depot / Final Stop)
                </div>
                <div style={{ fontSize: "15px", fontWeight: 700, color: "#f8fafc" }}>
                  {editDerivedOverview.toStop?.stop_name || "—"}
                </div>
                <div style={{ fontSize: "12px", color: "#94a3b8", fontFamily: "monospace", marginTop: "2px" }}>
                  {editDerivedOverview.toStop?.stop_code || "—"}
                </div>
              </div>

              {/* TOTAL DISTANCE */}
              <div
                style={{
                  padding: "16px",
                  borderRadius: "10px",
                  backgroundColor: "rgba(255, 255, 255, 0.02)",
                  border: "1px solid rgba(255, 255, 255, 0.06)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", marginBottom: "6px" }}>
                  Total Route Distance
                </div>
                <div style={{ fontSize: "18px", fontWeight: 700, color: "#f8fafc", fontFamily: "monospace" }}>
                  {editDerivedOverview.totalDistance}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                  Authoritative road distance
                </div>
              </div>

              {/* TOTAL STOPS */}
              <div
                style={{
                  padding: "16px",
                  borderRadius: "10px",
                  backgroundColor: "rgba(255, 255, 255, 0.02)",
                  border: "1px solid rgba(255, 255, 255, 0.06)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", marginBottom: "6px" }}>
                  Total Stops
                </div>
                <div style={{ fontSize: "18px", fontWeight: 700, color: "#f8fafc", fontFamily: "monospace" }}>
                  {editDerivedOverview.stopCount}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                  Active sequence count
                </div>
              </div>

              {/* TOTAL TRAVEL TIME */}
              <div
                style={{
                  padding: "16px",
                  borderRadius: "10px",
                  backgroundColor: "rgba(255, 255, 255, 0.02)",
                  border: "1px solid rgba(255, 255, 255, 0.06)",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: 600, color: "#c084fc", textTransform: "uppercase", marginBottom: "6px" }}>
                  Total Travel Time
                </div>
                <div style={{ fontSize: "18px", fontWeight: 700, color: "#c084fc", fontFamily: "monospace" }}>
                  {editDerivedOverview.totalTravelTime}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                  Cumulative from origin
                </div>
              </div>
            </div>
          </div>

          {/* 6. BOTTOM FORM ACTIONS */}
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              alignItems: "center",
              gap: "12px",
              padding: "20px 28px",
              backgroundColor: "#161922",
              borderRadius: "14px",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            <button
              type="button"
              onClick={handleCancelEdit}
              disabled={saving}
              style={{
                padding: "10px 22px",
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
              }}
            >
              <X size={15} /> Cancel
            </button>
            <button
              type="button"
              onClick={handleSaveEdit}
              disabled={saving || !isDirty}
              style={{
                padding: "10px 26px",
                backgroundColor: "#0284c7",
                border: "1px solid #38bdf8",
                borderRadius: "8px",
                color: "#ffffff",
                fontSize: "13px",
                fontWeight: 600,
                cursor: saving || !isDirty ? "not-allowed" : "pointer",
                opacity: saving || !isDirty ? 0.6 : 1,
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                boxShadow: "0 2px 8px rgba(2, 132, 199, 0.35)",
                transition: "all 0.15s ease",
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
        /* ── NORMAL ROUTE DETAILS VIEW ── */
        <>
          {/* ── ROUTE OVERVIEW KPI GRID (Section 8) ── */}
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              padding: "20px 24px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
              <Compass size={16} style={{ color: "#38bdf8" }} />
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
                Route Overview
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
                  Total Distance
                </div>
                <div style={{ fontWeight: 700, fontSize: "16px", color: "#38bdf8", fontFamily: "monospace" }}>
                  {operationalOverview.totalDistance}
                </div>
                <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "2px" }}>
                  Official alignment
                </div>
              </div>

              <div style={{ padding: "12px 14px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                  Total Stops
                </div>
                <div style={{ fontWeight: 700, fontSize: "16px", color: "#f8fafc", fontFamily: "monospace" }}>
                  {operationalOverview.stopCount} Stops
                </div>
                <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "2px" }}>
                  Ordered sequence
                </div>
              </div>

              <div style={{ padding: "12px 14px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                  Total Travel Time
                </div>
                <div style={{ fontWeight: 700, fontSize: "16px", color: "#a855f7", fontFamily: "monospace" }}>
                  {operationalOverview.totalTravelTime}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                  Final cumulative time
                </div>
              </div>

              <div style={{ padding: "12px 14px", backgroundColor: "rgba(255, 255, 255, 0.02)", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.05)" }}>
                <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: "4px" }}>
                  Operating Services
                </div>
                <div style={{ fontWeight: 700, fontSize: "16px", color: "#fbbf24", fontFamily: "monospace" }}>
                  {operationalOverview.serviceCount} Active
                </div>
                <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "2px" }}>
                  Assigned to route
                </div>
              </div>
            </div>
          </div>

          {/* ── ROUTE ENDPOINTS / MAJOR DEPOTS CARD (Section 9) ── */}
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              padding: "20px 24px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
              <Navigation size={16} style={{ color: "#4ade80" }} />
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
                Route Endpoints & Major Depots
              </h2>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: "16px",
              }}
            >
              {/* Origin Major Depot A */}
              <div
                style={{
                  padding: "16px",
                  borderRadius: "10px",
                  backgroundColor: "rgba(34, 197, 94, 0.06)",
                  border: "1px solid rgba(34, 197, 94, 0.2)",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "12px",
                }}
              >
                <div
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(34, 197, 94, 0.15)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#4ade80",
                    fontWeight: 700,
                    fontSize: "12px",
                    flexShrink: 0,
                  }}
                >
                  DEPOT A
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: "11px", color: "#4ade80", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    FROM (Origin Stop #1)
                  </div>
                  <div style={{ fontSize: "15px", fontWeight: 700, color: "#f8fafc", marginTop: "2px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {operationalOverview.originStop?.stop_name || "—"}
                  </div>
                  <div style={{ fontSize: "12px", color: "#94a3b8", fontFamily: "monospace", marginTop: "2px" }}>
                    {operationalOverview.originStop?.stop_code || "No Stop Code"} · 0.00 km
                  </div>
                </div>
              </div>

              {/* Destination Major Depot B */}
              <div
                style={{
                  padding: "16px",
                  borderRadius: "10px",
                  backgroundColor: "rgba(244, 63, 94, 0.06)",
                  border: "1px solid rgba(244, 63, 94, 0.2)",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "12px",
                }}
              >
                <div
                  style={{
                    width: "36px",
                    height: "36px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(244, 63, 94, 0.15)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#f43f5e",
                    fontWeight: 700,
                    fontSize: "12px",
                    flexShrink: 0,
                  }}
                >
                  DEPOT B
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: "11px", color: "#f43f5e", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                    TO (Destination Stop #{operationalOverview.stopCount})
                  </div>
                  <div style={{ fontSize: "15px", fontWeight: 700, color: "#f8fafc", marginTop: "2px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {operationalOverview.destStop?.stop_name || "—"}
                  </div>
                  <div style={{ fontSize: "12px", color: "#94a3b8", fontFamily: "monospace", marginTop: "2px" }}>
                    {operationalOverview.destStop?.stop_code || "No Stop Code"} · {operationalOverview.totalDistance}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ── SERVICES OPERATING ON THIS ROUTE (Section 14, 15, 17) ── */}
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
                <Bus size={16} style={{ color: "#818cf8" }} />
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
                  Services Operating On This Route ({operatingServices.length})
                </h3>
              </div>
            </div>

            {operatingServices.length === 0 ? (
              <div style={{ textAlign: "center", padding: "28px 0", color: "#64748b", fontSize: "14px" }}>
                No services currently operate on this route.
              </div>
            ) : (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
                  gap: "16px",
                }}
              >
                {operatingServices.map((svc) => (
                  <div
                    key={svc.id}
                    style={{
                      padding: "16px 20px",
                      borderRadius: "10px",
                      backgroundColor: "rgba(255, 255, 255, 0.02)",
                      border: "1px solid rgba(255, 255, 255, 0.06)",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      gap: "14px",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                          <span style={{ fontFamily: "monospace", fontSize: "15px", fontWeight: 700, color: "#f8fafc" }}>
                            {svc.service_code}
                          </span>
                          <span
                            style={{
                              fontSize: "11px",
                              fontWeight: 600,
                              padding: "2px 8px",
                              borderRadius: "4px",
                              backgroundColor:
                                svc.status === "ACTIVE"
                                  ? "rgba(34, 197, 94, 0.15)"
                                  : "rgba(148, 163, 184, 0.12)",
                              color: svc.status === "ACTIVE" ? "#4ade80" : "#94a3b8",
                            }}
                          >
                            {svc.status}
                          </span>
                        </div>
                      </div>

                      <div style={{ fontSize: "14px", color: "#cbd5e1" }}>
                        {svc.service_name}
                      </div>

                      {/* Attached Fare Info (Fare belongs to Service) */}
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "10px", fontSize: "12px", color: "#94a3b8" }}>
                        <Banknote size={14} style={{ color: "#4ade80" }} />
                        <span>
                          {svc.fare_configuration_name ? (
                            <>
                              Attached Fare: <strong style={{ color: "#f8fafc" }}>{svc.fare_configuration_name}</strong>
                              {svc.fare_slabs_count != null ? ` (${svc.fare_slabs_count} slabs)` : ""}
                            </>
                          ) : (
                            "No Fare Attached"
                          )}
                        </span>
                      </div>
                    </div>

                    {/* Operational Action Buttons */}
                    <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap", borderTop: "1px solid rgba(255, 255, 255, 0.05)", paddingTop: "12px" }}>
                      <button
                        type="button"
                        onClick={() => handleViewService(svc.id)}
                        style={{
                          padding: "6px 12px",
                          backgroundColor: "rgba(99, 102, 241, 0.12)",
                          border: "1px solid rgba(99, 102, 241, 0.3)",
                          borderRadius: "6px",
                          color: "#a5b4fc",
                          fontSize: "12px",
                          fontWeight: 600,
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "5px",
                        }}
                      >
                        <ExternalLink size={12} /> View Service
                      </button>

                      {svc.fare_configuration_id && (
                        <button
                          type="button"
                          onClick={() => handleViewFareChart(svc.fare_configuration_id)}
                          style={{
                            padding: "6px 12px",
                            backgroundColor: "rgba(34, 197, 94, 0.1)",
                            border: "1px solid rgba(34, 197, 94, 0.25)",
                            borderRadius: "6px",
                            color: "#4ade80",
                            fontSize: "12px",
                            fontWeight: 600,
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "5px",
                          }}
                        >
                          <Banknote size={12} /> View Fare Chart
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── ORDERED ROUTE STOPS & MAP VIEW (Section 11, 12, 13) ── */}
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "14px",
              overflow: "hidden",
            }}
          >
            {/* Section Header with Segmented View Controls */}
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
                <MapPin size={16} style={{ color: "#38bdf8" }} />
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
                  Ordered Route Stops ({stops.length})
                </h3>
              </div>

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
                    backgroundColor: activeTab === "stops" ? "#0284c7" : "transparent",
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
                    backgroundColor: activeTab === "map" ? "#0284c7" : "transparent",
                    color: activeTab === "map" ? "#ffffff" : "#94a3b8",
                    transition: "all 0.15s ease",
                  }}
                >
                  <MapIcon size={14} /> Map View
                </button>
              </div>
            </div>

            {/* Tab Content: Stops Sequence Table OR Interactive Map */}
            {activeTab === "stops" ? (
              <div style={{ width: "100%" }}>
                {stops.length === 0 ? (
                  <div style={{ textAlign: "center", padding: "36px 0", color: "#64748b", fontSize: "14px" }}>
                    No stops currently assigned to this route.
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
                        <th style={{ padding: "10px 16px", color: "#94a3b8", fontWeight: 600, width: "50px", textAlign: "center" }}>#</th>
                        <th style={{ padding: "10px 16px", color: "#94a3b8", fontWeight: 600, width: "130px" }}>Stop Code</th>
                        <th style={{ padding: "10px 16px", color: "#94a3b8", fontWeight: 600 }}>Stop Name</th>
                        <th style={{ padding: "10px 16px", color: "#94a3b8", fontWeight: 600, textAlign: "right", width: "130px" }}>Distance</th>
                        <th style={{ padding: "10px 16px", color: "#94a3b8", fontWeight: 600, textAlign: "right", width: "150px" }}>From Origin</th>
                        <th style={{ padding: "10px 16px", color: "#94a3b8", fontWeight: 600, textAlign: "right", width: "140px" }}>Segment Time</th>
                        <th style={{ padding: "10px 16px", color: "#94a3b8", fontWeight: 600, textAlign: "center", width: "110px" }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stops.map((stop, idx) => {
                        const currentSec = safeNumber(stop.nominal_travel_time_seconds);
                        const prevSec = idx > 0 ? safeNumber(stops[idx - 1].nominal_travel_time_seconds) : 0;
                        const segmentSec =
                          currentSec !== null && prevSec !== null
                            ? Math.max(0, currentSec - prevSec)
                            : null;

                        return (
                          <tr
                            key={stop.id || idx}
                            style={{
                              borderBottom: idx < stops.length - 1 ? "1px solid rgba(255, 255, 255, 0.04)" : "none",
                              backgroundColor: idx % 2 === 1 ? "rgba(255, 255, 255, 0.015)" : "transparent",
                            }}
                          >
                            <td style={{ padding: "10px 16px", textAlign: "center", color: "#38bdf8", fontFamily: "monospace", fontWeight: 600 }}>
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
                              {idx === 0 && (
                                <span style={{ marginLeft: "8px", fontSize: "10px", fontWeight: 700, padding: "2px 6px", borderRadius: "4px", backgroundColor: "rgba(34, 197, 94, 0.15)", color: "#4ade80" }}>
                                  DEPOT A
                                </span>
                              )}
                              {idx === stops.length - 1 && idx > 0 && (
                                <span style={{ marginLeft: "8px", fontSize: "10px", fontWeight: 700, padding: "2px 6px", borderRadius: "4px", backgroundColor: "rgba(244, 63, 94, 0.15)", color: "#f43f5e" }}>
                                  DEPOT B
                                </span>
                              )}
                            </td>
                            <td style={{ padding: "10px 16px", textAlign: "right", color: "#94a3b8", fontFamily: "monospace" }}>
                              {formatKm(stop.distance_from_start)}
                            </td>
                            <td style={{ padding: "10px 16px", textAlign: "right", color: "#c084fc", fontFamily: "monospace", fontWeight: 500 }}>
                              {formatDuration(stop.nominal_travel_time_seconds)}
                            </td>
                            <td style={{ padding: "10px 16px", textAlign: "right", color: "#94a3b8", fontFamily: "monospace" }}>
                              {idx === 0 ? "Origin" : formatDuration(segmentSec)}
                            </td>
                            <td style={{ padding: "10px 16px", textAlign: "center" }}>
                              <button
                                type="button"
                                onClick={() => handleViewStop(stop.stop_id)}
                                style={{
                                  padding: "4px 10px",
                                  backgroundColor: "rgba(56, 189, 248, 0.08)",
                                  border: "1px solid rgba(56, 189, 248, 0.2)",
                                  borderRadius: "5px",
                                  color: "#38bdf8",
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  cursor: "pointer",
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                }}
                              >
                                <ExternalLink size={11} /> View Stop
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            ) : (
              /* MAP VIEW: Route Geometry & Stop Markers (Section 13) */
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
                        <Polyline positions={polylinePositions} color="#0284c7" weight={5} opacity={0.85} />
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

      {/* ── ORIGIN-CONTEXT OVERLAYS (Section 18, 23) ── */}
      {activeOverlayStopId && (
        <StopDetailModal
          stopId={activeOverlayStopId}
          onClose={() => setActiveOverlayStopId(null)}
          onRouteClick={(clickedRouteId) => {
            if (clickedRouteId === routeId) {
              // Same route: reveal current Route Details
              setActiveOverlayStopId(null);
            } else {
              // Different route: navigate with return context
              setActiveOverlayStopId(null);
              navigate(`/routes/${clickedRouteId}`, {
                state: {
                  returnTo: `/routes/${routeId}`,
                  returnLabel: route?.route_code ? `Route ${route.route_code}` : "Route",
                },
              });
            }
          }}
        />
      )}

      {activeOverlayFareId && (
        <FareDetailModal
          fareId={activeOverlayFareId}
          onClose={() => setActiveOverlayFareId(null)}
        />
      )}

      {/* ── REMOVE STOP FROM ROUTE CONFIRMATION MODAL (Section 8, 20) ── */}
      {stopToRemove && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(4px)",
            zIndex: 9999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              backgroundColor: "#161922",
              border: "1px solid rgba(239, 68, 68, 0.4)",
              borderRadius: "14px",
              padding: "24px 28px",
              maxWidth: "480px",
              width: "100%",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.6)",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "#f87171", fontSize: "16px", fontWeight: 700 }}>
              <AlertCircle size={22} />
              <span>Remove Stop from Route?</span>
            </div>

            <div
              style={{
                backgroundColor: "#0d1017",
                padding: "12px 16px",
                borderRadius: "8px",
                border: "1px solid rgba(255, 255, 255, 0.08)",
              }}
            >
              <div style={{ fontSize: "13px", fontWeight: 700, color: "#38bdf8", fontFamily: "monospace" }}>
                {stopToRemove.stop_code}
              </div>
              <div style={{ fontSize: "14px", color: "#f8fafc", fontWeight: 600, marginTop: "2px" }}>
                {stopToRemove.stop_name}
              </div>
            </div>

            <p style={{ fontSize: "13px", color: "#cbd5e1", lineHeight: 1.5, margin: 0 }}>
              This removes the stop from this Route sequence.{" "}
              <strong style={{ color: "#4ade80" }}>The Stop itself will NOT be deleted</strong> and will remain active in the global stops catalog.
            </p>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "8px" }}>
              <button
                type="button"
                onClick={() => setStopToRemove(null)}
                style={{
                  padding: "8px 16px",
                  backgroundColor: "rgba(255, 255, 255, 0.06)",
                  border: "1px solid rgba(255, 255, 255, 0.15)",
                  borderRadius: "8px",
                  color: "#cbd5e1",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleConfirmRemoveStop(stopToRemove.stop_id)}
                style={{
                  padding: "8px 18px",
                  backgroundColor: "#dc2626",
                  border: "1px solid #ef4444",
                  borderRadius: "8px",
                  color: "#ffffff",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <Trash2 size={14} /> Remove from Route
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
