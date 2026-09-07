import React, { useState, useEffect, useRef } from "react";
import { apiFetch, previewRoute, createRouteWithStops } from "../api/api";
import {
  Plus,
  Search,
  Map,
  Edit2,
  Trash2,
  ArrowUp,
  ArrowDown,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  X,
  Navigation,
  ExternalLink,
} from "lucide-react";
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { SearchableStopSelect } from "../components/SearchableStopSelect";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { useNavigate } from "react-router-dom";

// Leaflet icon setup
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

const startIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

const endIcon = new L.Icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

interface Stop {
  id: string;
  stop_code: string;
  name: string;
  latitude: number;
  longitude: number;
  status?: string;
  aliases?: string[];
}

interface Route {
  id: string;
  route_code: string;
  route_name: string;
  distance_km: number;
  status: string;
}

interface RoutePreviewStopItem {
  stop_id: string;
  stop_code: string;
  stop_name: string;
  sequence_number: number;
  distance_from_start: number;
  nominal_travel_time_seconds: number;
}

interface RoutePreviewResponse {
  distance_km: number;
  duration_seconds: number;
  geometry: any;
  stops: RoutePreviewStopItem[];
  duplicate_match?: {
    is_duplicate: boolean;
    existing_route_id?: string;
    route_code?: string;
    route_name?: string;
    matching_stops?: string[];
  } | null;
}

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
            map.fitBounds(bounds, { padding: [30, 30], maxZoom: 16, animate: false });
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

const formatKm = (km: number | null | undefined) => {
  if (km === null || km === undefined || isNaN(km)) return "—";
  return `${Number(km).toFixed(2)} km`;
};

const formatDuration = (sec: number | null | undefined) => {
  if (sec === null || sec === undefined || isNaN(sec) || sec <= 0) return "—";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const parts = [];
  if (h > 0) parts.push(`${h}h`);
  if (m > 0 || h === 0) parts.push(`${m}m`);
  return parts.join(" ");
};

export default function RoutesPage() {
  const [routes, setRoutes] = useState<Route[]>([]);
  const [allStops, setAllStops] = useState<Stop[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingRoute, setEditingRoute] = useState<Route | null>(null);
  const [editFormData, setEditFormData] = useState({ route_code: "", route_name: "", status: "ACTIVE" });

  // Create Route Form State
  const [routeCode, setRouteCode] = useState("");
  const [routeName, setRouteName] = useState("");
  const [startStopId, setStartStopId] = useState("");
  const [endStopId, setEndStopId] = useState("");
  const [intermediateStopIds, setIntermediateStopIds] = useState<string[]>([]);
  const [routeStatus, setRouteStatus] = useState("ACTIVE");

  // Routing Calculation State
  const [calculating, setCalculating] = useState(false);
  const [calculationResult, setCalculationResult] = useState<RoutePreviewResponse | null>(null);
  const [isCalculationStale, setIsCalculationStale] = useState(false);
  const [calculationError, setCalculationError] = useState<string | null>(null);
  const [duplicateIgnored, setDuplicateIgnored] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const calculationRequestIdRef = useRef(0);

  const navigate = useNavigate();

  useEffect(() => {
    loadInitialData();

    const params = new URLSearchParams(window.location.search);
    const urlRouteId = params.get("routeId");
    if (urlRouteId) {
      navigate(`/routes/${urlRouteId}`, { replace: true });
    }
  }, [navigate]);

  const loadInitialData = async () => {
    try {
      setLoading(true);
      const [routesData, stopsData] = await Promise.all([
        apiFetch("/admin/routes"),
        apiFetch("/admin/stops"),
      ]);
      setRoutes(routesData);
      setAllStops(stopsData);
    } catch (err) {
      console.error("Failed to load data", err);
    } finally {
      setLoading(false);
    }
  };

  const loadRoutes = async () => {
    try {
      const data = await apiFetch("/admin/routes");
      setRoutes(data);
    } catch (err) {
      console.error("Failed to load routes", err);
    }
  };

  const resetCreateForm = () => {
    setRouteCode("");
    setRouteName("");
    setStartStopId("");
    setEndStopId("");
    setIntermediateStopIds([]);
    setRouteStatus("ACTIVE");
    setCalculationResult(null);
    setIsCalculationStale(false);
    setCalculationError(null);
    setDuplicateIgnored(false);
  };

  const handleOpenCreateModal = () => {
    resetCreateForm();
    setShowCreateModal(true);
  };

  // Add intermediate stop
  const handleAddIntermediateStop = () => {
    setIntermediateStopIds([...intermediateStopIds, ""]);
    setIsCalculationStale(true);
  };

  // Update intermediate stop at index
  const handleIntermediateStopChange = (index: number, stopId: string) => {
    const updated = [...intermediateStopIds];
    updated[index] = stopId;
    setIntermediateStopIds(updated);
    setIsCalculationStale(true);
  };

  // Remove intermediate stop at index
  const handleRemoveIntermediateStop = (index: number) => {
    const updated = [...intermediateStopIds];
    updated.splice(index, 1);
    setIntermediateStopIds(updated);
    setIsCalculationStale(true);
  };

  // Move intermediate stop up/down
  const handleMoveIntermediateStop = (index: number, direction: "up" | "down") => {
    if (direction === "up" && index === 0) return;
    if (direction === "down" && index === intermediateStopIds.length - 1) return;
    const targetIdx = direction === "up" ? index - 1 : index + 1;
    const updated = [...intermediateStopIds];
    [updated[index], updated[targetIdx]] = [updated[targetIdx], updated[index]];
    setIntermediateStopIds(updated);
    setIsCalculationStale(true);
  };

  // Check sequence validity for preview/create
  const validateStopSequence = () => {
    if (!startStopId) return "Please select a Start Stop.";
    if (!endStopId) return "Please select an End Stop.";
    if (startStopId === endStopId) return "Start Stop and End Stop cannot be the same.";

    if (intermediateStopIds.some((id) => !id)) {
      return "Please select a Stop for all intermediate positions or remove empty ones.";
    }

    if (intermediateStopIds.includes(startStopId)) {
      return "Start Stop cannot be repeated as an intermediate Stop.";
    }

    if (intermediateStopIds.includes(endStopId)) {
      return "End Stop cannot be repeated as an intermediate Stop.";
    }

    const uniqueIntermediates = new Set(intermediateStopIds);
    if (uniqueIntermediates.size !== intermediateStopIds.length) {
      return "Duplicate stops inside route sequence are not permitted.";
    }

    return null;
  };

  // Trigger Road Route Calculation
  const handleCalculateRoute = async () => {
    const errorMsg = validateStopSequence();
    if (errorMsg) {
      setCalculationError(errorMsg);
      return;
    }

    const reqId = ++calculationRequestIdRef.current;
    setCalculating(true);
    setCalculationError(null);
    setDuplicateIgnored(false);

    try {
      const result: RoutePreviewResponse = await previewRoute({
        start_stop_id: startStopId,
        end_stop_id: endStopId,
        intermediate_stop_ids: intermediateStopIds,
      });
      if (reqId !== calculationRequestIdRef.current) return;
      setCalculationResult(result);
      setIsCalculationStale(false);
    } catch (err: any) {
      if (reqId !== calculationRequestIdRef.current) return;
      setCalculationError(err.message || "Failed to calculate road route.");
    } finally {
      if (reqId === calculationRequestIdRef.current) {
        setCalculating(false);
      }
    }
  };

  // Submit Create Route
  const handleCreateRouteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const seqError = validateStopSequence();
    if (seqError) {
      alert(seqError);
      return;
    }

    if (!calculationResult) {
      alert("Please calculate the road route first.");
      return;
    }

    if (
      calculationResult.duplicate_match?.is_duplicate &&
      !duplicateIgnored
    ) {
      alert("Please review the duplicate route warning before proceeding.");
      return;
    }

    setSubmitting(true);
    try {
      await createRouteWithStops({
        route_code: routeCode.trim(),
        route_name: routeName.trim(),
        start_stop_id: startStopId,
        end_stop_id: endStopId,
        intermediate_stop_ids: intermediateStopIds,
        status: routeStatus,
      });
      setShowCreateModal(false);
      resetCreateForm();
      await loadRoutes();
    } catch (err: any) {
      alert(err.message || "Failed to create route.");
    } finally {
      setSubmitting(false);
    }
  };

  // Edit general route details
  const handleEditRoute = (route: Route) => {
    setEditingRoute(route);
    setEditFormData({
      route_code: route.route_code,
      route_name: route.route_name,
      status: route.status,
    });
    setShowEditModal(true);
  };

  const handleEditRouteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingRoute) return;
    try {
      await apiFetch(`/admin/routes/${editingRoute.id}`, {
        method: "PUT",
        body: JSON.stringify(editFormData),
      });
      setShowEditModal(false);
      setEditingRoute(null);
      await loadRoutes();
    } catch (err: any) {
      alert(err.message || "Failed to update route.");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this route?")) return;
    try {
      await apiFetch(`/admin/routes/${id}`, { method: "DELETE" });
      loadRoutes();
    } catch (err) {
      alert("Failed to delete route. It might be referenced by services or stops.");
    }
  };

  const filteredRoutes = routes.filter(
    (r) =>
      r.route_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.route_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Build Polyline and Map Bounds from calculationResult
  let previewPositions: [number, number][] = [];
  let mapBounds = new L.LatLngBounds([]);

  if (
    calculationResult &&
    calculationResult.geometry &&
    calculationResult.geometry.type === "LineString" &&
    calculationResult.geometry.coordinates
  ) {
    calculationResult.geometry.coordinates.forEach((coord: [number, number]) => {
      // GeoJSON [lon, lat] -> Leaflet [lat, lon]
      const latlng: [number, number] = [coord[1], coord[0]];
      previewPositions.push(latlng);
      mapBounds.extend(latlng);
    });
  }

  // Get Stop markers for map
  const getStopMarkerData = () => {
    if (!calculationResult?.stops) return [];
    return calculationResult.stops
      .map((ps) => {
        const fullStop = allStops.find((s) => s.id === ps.stop_id);
        if (fullStop && fullStop.latitude && fullStop.longitude) {
          const latlng: [number, number] = [fullStop.latitude, fullStop.longitude];
          mapBounds.extend(latlng);
          return {
            ...ps,
            latlng,
            isStart: ps.sequence_number === 1,
            isEnd: ps.sequence_number === calculationResult.stops.length,
          };
        }
        return null;
      })
      .filter(Boolean);
  };

  const stopMarkers = getStopMarkerData();
  if (!mapBounds.isValid()) {
    mapBounds = new L.LatLngBounds([[22.40, 88.35], [22.60, 88.45]]);
  }

  const isCreateReady =
    routeCode.trim() !== "" &&
    routeName.trim() !== "" &&
    startStopId !== "" &&
    endStopId !== "" &&
    !validateStopSequence() &&
    calculationResult !== null &&
    !isCalculationStale &&
    !calculating &&
    (!calculationResult?.duplicate_match?.is_duplicate || duplicateIgnored);

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Routes Management</h1>
          <p className="page-subtitle">Manage bus routes with automated road-network routing and stop sequences.</p>
        </div>
        <button
          className="btn-primary flex items-center gap-2"
          disabled={allStops.length < 2}
          title={allStops.length < 2 ? "At least 2 Stops are required to create a Route" : undefined}
          onClick={handleOpenCreateModal}
        >
          <Plus size={18} /> Add New Route
        </button>
      </div>

      {allStops.length < 2 && (
        <div className="p-4 mb-6 bg-amber-50 border border-amber-200 text-amber-900 rounded-xl flex items-center gap-3 text-sm">
          <AlertTriangle size={20} className="text-amber-600 shrink-0" />
          <span>
            <strong>Prerequisite Notice:</strong> Fewer than 2 active Stops exist in your catalog. Please create at least 2 Stops on the{" "}
            <a href="/stops" className="underline font-semibold hover:text-amber-950">
              Stops Management
            </a>{" "}
            page before creating a Route.
          </span>
        </div>
      )}

      <div className="data-table-card">
        <div className="table-toolbar">
          <div className="search-box">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              placeholder="Search routes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {loading ? (
          <div className="loading-state">Loading routes...</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Calculated Distance</th>
                <th>Status</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredRoutes.map((route) => (
                <tr
                  key={route.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/routes/${route.id}`)}
                >
                  <td>
                    <span className="code-badge">{route.route_code}</span>
                  </td>
                  <td className="font-medium">{route.route_name}</td>
                  <td>
                    <div className="location-cell">
                      <Map size={14} className="text-muted" />
                      <span>{route.distance_km ? `${route.distance_km.toFixed(2)} km` : "Not routed"}</span>
                    </div>
                  </td>
                  <td>
                    <span className={`status-badge ${route.status.toLowerCase()}`}>
                      {route.status}
                    </span>
                  </td>
                  <td className="text-right">
                    <button
                      className="action-btn"
                      title="View route operational details"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/routes/${route.id}`);
                      }}
                    >
                      <ExternalLink size={16} />
                    </button>
                    <button
                      className="action-btn"
                      title="Edit general details"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleEditRoute(route);
                      }}
                    >
                      <Edit2 size={16} />
                    </button>
                    <button
                      className="action-btn text-danger"
                      title="Delete"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(route.id);
                      }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
              {filteredRoutes.length === 0 && (
                <tr>
                  <td colSpan={5} className="empty-state">
                    No routes found in your organization.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* ========================================================================= */}
      {/* CREATE NEW ROUTE MODAL (ONE PRIMARY MODAL BODY SCROLL) */}
      {/* ========================================================================= */}
      {showCreateModal && (
        <div className="modal-overlay" style={{ padding: "16px" }}>
          <div
            className="modal-content"
            style={{
              maxWidth: "1050px",
              width: "100%",
              maxHeight: "calc(100vh - 32px)",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              borderRadius: "var(--radius)",
              background: "var(--bg-card)",
              border: "1px solid var(--border)",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
            }}
          >
            {/* FIXED HEADER */}
            <div
              className="modal-header"
              style={{
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "18px 24px",
                borderBottom: "1px solid var(--border)",
                background: "var(--bg-card)",
              }}
            >
              <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-main)", display: "flex", alignItems: "center", gap: "10px", margin: 0 }}>
                <Navigation size={22} color="var(--accent)" />
                CREATE NEW ROUTE
              </h2>
              <button
                type="button"
                className="close-btn"
                onClick={() => setShowCreateModal(false)}
                title="Close"
              >
                <X size={20} />
              </button>
            </div>

            {/* FORM WRAPPER: BODY (SCROLLABLE) + FOOTER (FIXED) */}
            <form
              onSubmit={handleCreateRouteSubmit}
              style={{
                flex: 1,
                minHeight: 0,
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                margin: 0,
              }}
            >
              {/* ONE PRIMARY VERTICAL SCROLL CONTAINER */}
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
                  background: "var(--bg-dark)",
                }}
              >
                {/* 1. GENERAL DEFINITION */}
                <div
                  style={{
                    background: "var(--bg-card)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius)",
                    padding: "20px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "16px",
                  }}
                >
                  <h3 style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", margin: 0 }}>
                    General Definition
                  </h3>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }}>
                    <div className="input-group">
                      <label>Route Code</label>
                      <input
                        required
                        value={routeCode}
                        onChange={(e) => setRouteCode(e.target.value)}
                        placeholder="e.g. SD5"
                      />
                    </div>
                    <div className="input-group" style={{ gridColumn: "span 2" }}>
                      <label>Route Name</label>
                      <input
                        required
                        value={routeName}
                        onChange={(e) => setRouteName(e.target.value)}
                        placeholder="e.g. Sonarpur Station - Kharibaria via Tollygunge & Behala"
                      />
                    </div>
                    <div className="input-group">
                      <label>Status</label>
                      <select
                        value={routeStatus}
                        onChange={(e) => setRouteStatus(e.target.value)}
                      >
                        <option value="ACTIVE">Active</option>
                        <option value="INACTIVE">Inactive</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* 2. ORDERED STOP SEQUENCE (CARD GROWING NATURALLY IN BODY FLOW) */}
                <div
                  style={{
                    background: "var(--bg-card)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius)",
                    padding: "20px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "16px",
                  }}
                >
                  <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: "8px", borderBottom: "1px solid var(--border)", paddingBottom: "12px" }}>
                    <div>
                      <h3 style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-main)", textTransform: "uppercase", letterSpacing: "0.05em", margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                        <span>Ordered Stop Sequence</span>
                        <span style={{ fontSize: "0.75rem", fontWeight: 600, padding: "2px 8px", background: "rgba(59, 130, 246, 0.15)", color: "var(--accent)", borderRadius: "6px" }}>
                          {2 + intermediateStopIds.length} Total Stops
                        </span>
                      </h3>
                      <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", margin: "4px 0 0 0" }}>
                        Existing stops only. Sequence defines authentic route direction from Start to End.
                      </p>
                    </div>
                  </div>

                  {/* START STOP (Sequence 1) */}
                  <div
                    style={{
                      padding: "14px 16px",
                      background: "rgba(16, 185, 129, 0.08)",
                      border: "1px solid rgba(16, 185, 129, 0.3)",
                      borderRadius: "10px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "6px",
                    }}
                  >
                    <label style={{ fontSize: "0.75rem", fontWeight: 700, color: "#10b981", textTransform: "uppercase", display: "flex", alignItems: "center", gap: "6px", letterSpacing: "0.05em" }}>
                      <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#10b981", display: "inline-block" }}></span>
                      START STOP (Sequence 1)
                    </label>
                    <SearchableStopSelect
                      id="start-stop-select"
                      stops={allStops}
                      value={startStopId}
                      onChange={(val) => {
                        setStartStopId(val);
                        setIsCalculationStale(true);
                      }}
                      placeholder="-- Select Existing Start Stop --"
                      disabledStopIds={[endStopId, ...intermediateStopIds].filter(Boolean)}
                      accentColor="#10b981"
                      required
                    />
                  </div>

                  {/* ORDERED INTERMEDIATE STOPS (NORMAL FLOW, NO INTERNAL SCROLL) */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0 4px" }}>
                      <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", display: "flex", alignItems: "center", gap: "6px", letterSpacing: "0.05em" }}>
                        <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--accent)", display: "inline-block" }}></span>
                        Intermediate Stops ({intermediateStopIds.length})
                      </span>
                      <button
                        type="button"
                        onClick={handleAddIntermediateStop}
                        className="btn-secondary"
                        style={{
                          padding: "6px 14px",
                          fontSize: "0.8rem",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        <Plus size={14} /> + Add Existing Stop
                      </button>
                    </div>

                    {/* Intermediate Stops List flowing naturally into body scroll */}
                    {intermediateStopIds.length === 0 ? (
                      <div
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--text-muted)",
                          fontStyle: "italic",
                          padding: "16px",
                          background: "rgba(0, 0, 0, 0.15)",
                          borderRadius: "8px",
                          border: "1px dashed var(--border)",
                          textAlign: "center",
                        }}
                      >
                        No intermediate stops added yet. Click "+ Add Existing Stop" to insert stops between Start and End.
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                        {intermediateStopIds.map((stopId, idx) => (
                          <div
                            key={idx}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "10px",
                              background: "var(--bg-dark)",
                              padding: "10px 14px",
                              borderRadius: "8px",
                              border: "1px solid var(--border)",
                            }}
                          >
                            <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--text-muted)", width: "32px", textAlign: "center", flexShrink: 0 }}>
                              {idx + 2}.
                            </span>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <SearchableStopSelect
                                stops={allStops}
                                value={stopId}
                                onChange={(val) => handleIntermediateStopChange(idx, val)}
                                placeholder={`-- Select Stop #${idx + 2} --`}
                                disabledStopIds={[
                                  startStopId,
                                  endStopId,
                                  ...intermediateStopIds.filter((_, i) => i !== idx),
                                ].filter(Boolean)}
                                required
                              />
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
                              <button
                                type="button"
                                className="action-btn"
                                style={{
                                  padding: "6px 8px",
                                  background: "var(--bg-card)",
                                  border: "1px solid var(--border)",
                                  borderRadius: "6px",
                                  color: "var(--text-main)",
                                  cursor: idx === 0 ? "not-allowed" : "pointer",
                                  opacity: idx === 0 ? 0.35 : 1,
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                }}
                                disabled={idx === 0}
                                onClick={() => handleMoveIntermediateStop(idx, "up")}
                                title="Move Up"
                              >
                                <ArrowUp size={15} />
                              </button>
                              <button
                                type="button"
                                className="action-btn"
                                style={{
                                  padding: "6px 8px",
                                  background: "var(--bg-card)",
                                  border: "1px solid var(--border)",
                                  borderRadius: "6px",
                                  color: "var(--text-main)",
                                  cursor: idx === intermediateStopIds.length - 1 ? "not-allowed" : "pointer",
                                  opacity: idx === intermediateStopIds.length - 1 ? 0.35 : 1,
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                }}
                                disabled={idx === intermediateStopIds.length - 1}
                                onClick={() => handleMoveIntermediateStop(idx, "down")}
                                title="Move Down"
                              >
                                <ArrowDown size={15} />
                              </button>
                              <button
                                type="button"
                                className="action-btn text-danger"
                                style={{
                                  padding: "6px 8px",
                                  background: "rgba(239, 68, 68, 0.1)",
                                  border: "1px solid rgba(239, 68, 68, 0.3)",
                                  borderRadius: "6px",
                                  color: "var(--danger)",
                                  cursor: "pointer",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                }}
                                onClick={() => handleRemoveIntermediateStop(idx)}
                                title="Remove Stop"
                              >
                                <Trash2 size={15} />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* END STOP (Sequence Final) */}
                  <div
                    style={{
                      padding: "14px 16px",
                      background: "rgba(239, 68, 68, 0.08)",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      borderRadius: "10px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "6px",
                    }}
                  >
                    <label style={{ fontSize: "0.75rem", fontWeight: 700, color: "#ef4444", textTransform: "uppercase", display: "flex", alignItems: "center", gap: "6px", letterSpacing: "0.05em" }}>
                      <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#ef4444", display: "inline-block" }}></span>
                      END STOP (Sequence Final: {2 + intermediateStopIds.length})
                    </label>
                    <SearchableStopSelect
                      id="end-stop-select"
                      stops={allStops}
                      value={endStopId}
                      onChange={(val) => {
                        setEndStopId(val);
                        setIsCalculationStale(true);
                      }}
                      placeholder="-- Select Existing End Stop --"
                      disabledStopIds={[startStopId, ...intermediateStopIds].filter(Boolean)}
                      accentColor="#ef4444"
                      required
                    />
                  </div>
                </div>

                {/* 3. ROUTE CALCULATION SECTION */}
                <div
                  style={{
                    background: "var(--bg-card)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius)",
                    padding: "20px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "16px",
                  }}
                >
                  <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
                    <div>
                      <h3 style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", margin: 0 }}>
                        Route Calculation
                      </h3>
                      <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", margin: "4px 0 0 0" }}>
                        Calculates authentic road distance and road-following geometry via routing engine
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={handleCalculateRoute}
                      disabled={calculating || !startStopId || !endStopId}
                      className="btn-primary"
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        opacity: (calculating || !startStopId || !endStopId) ? 0.5 : 1,
                        cursor: (calculating || !startStopId || !endStopId) ? "not-allowed" : "pointer",
                      }}
                    >
                      <RefreshCw size={16} className={calculating ? "animate-spin" : ""} />
                      {calculating
                        ? "Calculating route..."
                        : isCalculationStale
                        ? "Recalculate Route"
                        : calculationResult
                        ? "Refresh Route Calculation"
                        : "Calculate Route"}
                    </button>
                  </div>

                  {/* METRICS & STATUS */}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px" }}>
                    <div style={{ background: "var(--bg-dark)", padding: "16px", borderRadius: "10px", border: "1px solid var(--border)" }}>
                      <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", display: "block", marginBottom: "4px" }}>
                        Calculated Road Distance
                      </span>
                      <span style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--text-main)" }}>
                        {calculationResult ? formatKm(calculationResult.distance_km) : "—"}
                      </span>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginTop: "4px" }}>Read-only (Road routing)</span>
                    </div>

                    <div style={{ background: "var(--bg-dark)", padding: "16px", borderRadius: "10px", border: "1px solid var(--border)" }}>
                      <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", display: "block", marginBottom: "4px" }}>
                        Estimated Road Duration
                      </span>
                      <span style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--text-main)" }}>
                        {calculationResult ? formatDuration(calculationResult.duration_seconds) : "—"}
                      </span>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginTop: "4px" }}>Road routing estimate</span>
                    </div>

                    <div style={{ background: "var(--bg-dark)", padding: "16px", borderRadius: "10px", border: "1px solid var(--border)", display: "flex", flexDirection: "column", justifyContent: "center" }}>
                      <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", display: "block", marginBottom: "4px" }}>
                        Routing Status
                      </span>
                      {calculating ? (
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--accent)", fontWeight: 600, fontSize: "0.85rem" }}>
                          <RefreshCw size={16} className="animate-spin" />
                          <span>Calculating road route...</span>
                        </div>
                      ) : isCalculationStale ? (
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--warning, #f59e0b)", fontWeight: 600, fontSize: "0.85rem" }}>
                          <AlertTriangle size={16} style={{ flexShrink: 0 }} />
                          <span>Route calculation needs refresh</span>
                        </div>
                      ) : calculationResult ? (
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--success)", fontWeight: 700, fontSize: "0.9rem" }}>
                          <CheckCircle2 size={18} />
                          <span>✓ Road route calculated</span>
                        </div>
                      ) : calculationError ? (
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--danger)", fontWeight: 600, fontSize: "0.8rem" }}>
                          <AlertTriangle size={18} style={{ flexShrink: 0 }} />
                          <span>⚠ {calculationError}</span>
                        </div>
                      ) : (
                        <span style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}>Awaiting calculation</span>
                      )}
                    </div>
                  </div>

                  {/* DUPLICATE ROUTE DETECTION WARNING */}
                  {calculationResult?.duplicate_match?.is_duplicate && (
                    <div style={{ padding: "16px", background: "rgba(245, 158, 11, 0.1)", border: "1px solid rgba(245, 158, 11, 0.4)", borderRadius: "10px", color: "#fef3c7" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", fontWeight: 700, fontSize: "1rem", color: "var(--warning)", marginBottom: "8px" }}>
                        <AlertTriangle size={20} style={{ flexShrink: 0 }} />
                        <span>EXISTING ROUTE MATCH</span>
                      </div>
                      <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: "10px" }}>
                        An existing route in your organization already has this exact ordered stop sequence:
                      </p>
                      <div style={{ background: "var(--bg-dark)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border)", fontSize: "0.8rem", display: "flex", flexDirection: "column", gap: "4px", marginBottom: "12px" }}>
                        <div>
                          <span style={{ fontWeight: 600, color: "var(--text-muted)" }}>Route Code:</span>{" "}
                          <span className="code-badge">{calculationResult.duplicate_match.route_code}</span>
                        </div>
                        <div>
                          <span style={{ fontWeight: 600, color: "var(--text-muted)" }}>Route Name:</span>{" "}
                          <span style={{ color: "var(--text-main)" }}>{calculationResult.duplicate_match.route_name}</span>
                        </div>
                        <div>
                          <span style={{ fontWeight: 600, color: "var(--text-muted)" }}>Route ID:</span>{" "}
                          <span style={{ fontFamily: "monospace", color: "var(--text-muted)" }}>{calculationResult.duplicate_match.existing_route_id}</span>
                        </div>
                        <div>
                          <span style={{ fontWeight: 600, color: "var(--text-muted)" }}>Matching sequence:</span>{" "}
                          <span style={{ color: "var(--text-main)" }}>{calculationResult.duplicate_match.matching_stops?.join(" → ")}</span>
                        </div>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <button
                          type="button"
                          className="btn-primary"
                          style={{ padding: "6px 12px", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "6px" }}
                          onClick={() => {
                            const dupId = calculationResult.duplicate_match?.existing_route_id;
                            setShowCreateModal(false);
                            if (dupId) navigate(`/routes/${dupId}`);
                          }}
                        >
                          <ExternalLink size={14} /> Use Existing Route
                        </button>
                        <button
                          type="button"
                          className="btn-secondary"
                          style={{
                            padding: "6px 12px",
                            fontSize: "0.8rem",
                            background: duplicateIgnored ? "rgba(16, 185, 129, 0.2)" : undefined,
                            color: duplicateIgnored ? "#10b981" : undefined,
                            borderColor: duplicateIgnored ? "#10b981" : undefined,
                          }}
                          onClick={() => setDuplicateIgnored(true)}
                        >
                          {duplicateIgnored ? "✓ Confirmed to Continue" : "Continue as New Route"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                {/* 4. MAP PREVIEW */}
                <div
                  style={{
                    background: "var(--bg-card)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius)",
                    overflow: "hidden",
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)", background: "var(--bg-card)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <h3 style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                      <Map size={16} color="var(--accent)" /> Map Preview
                    </h3>
                    {calculationResult && (
                      <span style={{ fontSize: "0.8rem", color: isCalculationStale ? "var(--warning, #f59e0b)" : "var(--text-muted)", fontWeight: 500 }}>
                        {isCalculationStale && "⚠️ Needs Refresh • "}
                        {calculationResult.stops.length} Stops • {formatKm(calculationResult.distance_km)}
                      </span>
                    )}
                  </div>
                  <ErrorBoundary fallbackTitle="Map Preview Unavailable" fallbackMessage="Map preview encountered an issue. Road route metrics and stop sequence remain valid.">
                    <div style={{ height: "300px", width: "100%", background: "var(--bg-dark)", position: "relative" }}>
                      <MapContainer
                        center={[22.5726, 88.3639]}
                        zoom={12}
                        style={{ height: "100%", width: "100%" }}
                        scrollWheelZoom={false}
                      >
                        <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />
                        {previewPositions.length > 0 && (
                          <Polyline positions={previewPositions} color={isCalculationStale ? "#94a3b8" : "#2563eb"} weight={5} opacity={0.85} />
                        )}
                        {stopMarkers.map((sm: any, i) => (
                          <Marker
                            key={sm.stop_id || i}
                            position={sm.latlng}
                            icon={sm.isStart ? startIcon : sm.isEnd ? endIcon : undefined}
                          >
                            <Popup>
                              <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>
                                {sm.isStart ? "● START: " : sm.isEnd ? "● END: " : ""}
                                {sm.stop_name}
                              </div>
                              <div style={{ fontSize: "0.75rem", color: "#666" }}>Stop Code: {sm.stop_code}</div>
                              <div style={{ fontSize: "0.75rem", color: "#666" }}>Seq: {sm.sequence_number}</div>
                              <div style={{ fontSize: "0.75rem", color: "#666" }}>
                                Cumulative: {formatKm(sm.distance_from_start)}
                              </div>
                              <div style={{ fontSize: "0.75rem", color: "#666" }}>
                                Est. Time: {formatDuration(sm.nominal_travel_time_seconds)}
                              </div>
                            </Popup>
                          </Marker>
                        ))}
                        <BoundsWrapper bounds={mapBounds} />
                      </MapContainer>
                    </div>
                  </ErrorBoundary>
                </div>
              </div>

              {/* FIXED MODAL ACTIONS FOOTER */}
              <div
                style={{
                  flexShrink: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "16px 24px",
                  borderTop: "1px solid var(--border)",
                  background: "var(--bg-card)",
                }}
              >
                <div style={{ fontSize: "0.85rem", color: isCalculationStale ? "var(--warning, #f59e0b)" : "var(--text-muted)" }}>
                  {isCalculationStale
                    ? "Stop sequence modified — recalculation required before creating route"
                    : calculationResult
                    ? `Road route calculated: ${formatKm(calculationResult.distance_km)} (${calculationResult.stops.length} stops)`
                    : "Route calculation required before creation"}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setShowCreateModal(false)}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={!isCreateReady || submitting}
                    className="btn-primary"
                    style={{
                      opacity: (!isCreateReady || submitting) ? 0.5 : 1,
                      cursor: (!isCreateReady || submitting) ? "not-allowed" : "pointer",
                    }}
                  >
                    {submitting ? "Creating Route..." : "Create Route"}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* EDIT GENERAL ROUTE MODAL */}
      {/* ========================================================================= */}
      {showEditModal && editingRoute && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: "500px" }}>
            <div className="modal-header">
              <h2>Edit Route Definition</h2>
              <button className="close-btn" onClick={() => setShowEditModal(false)}>
                ×
              </button>
            </div>
            <form onSubmit={handleEditRouteSubmit} className="modal-form">
              <div className="input-group">
                <label>Route Code</label>
                <input
                  required
                  value={editFormData.route_code}
                  onChange={(e) => setEditFormData({ ...editFormData, route_code: e.target.value })}
                />
              </div>
              <div className="input-group">
                <label>Route Name</label>
                <input
                  required
                  value={editFormData.route_name}
                  onChange={(e) => setEditFormData({ ...editFormData, route_name: e.target.value })}
                />
              </div>
              <div className="input-group">
                <label>Calculated Road Distance</label>
                <input
                  disabled
                  readOnly
                  value={`${editingRoute.distance_km ? editingRoute.distance_km.toFixed(2) : "0"} km`}
                  className="bg-gray-100 text-gray-500 cursor-not-allowed"
                />
                <span className="text-xs text-gray-400 mt-1">
                  Stops and distance are managed via the Route Detail Modal.
                </span>
              </div>
              <div className="input-group">
                <label>Status</label>
                <select
                  value={editFormData.status}
                  onChange={(e) => setEditFormData({ ...editFormData, status: e.target.value })}
                >
                  <option value="ACTIVE">Active</option>
                  <option value="INACTIVE">Inactive</option>
                </select>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn-secondary" onClick={() => setShowEditModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
