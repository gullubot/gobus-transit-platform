import React, { useEffect, useState } from "react";
import { apiFetch, checkRouteDuplicateStops } from "../api/api";
import { X, Map as MapIcon, Navigation, Edit2, Trash2, ArrowUp, ArrowDown, Plus, Save, Network, Clock, AlertTriangle } from "lucide-react";
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

// Fix leaflet icon path issues
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

interface Stop {
  id: string;
  stop_code: string;
  name: string;
  latitude: number;
  longitude: number;
}

interface RouteStop {
  id?: string;
  route_id: string;
  stop_id: string;
  stop_code?: string;
  stop_name?: string;
  sequence_number: number;
  distance_from_start: number | null;
  nominal_travel_time_seconds: number | null;
}

interface RouteDetail {
  id: string;
  route_code: string;
  route_name: string;
  distance_km: number;
  status: string;
  geometry: any | null;
}

interface RouteDetailModalProps {
  routeId: string;
  onClose: () => void;
  onServiceClick?: (serviceId: string) => void;
}

import { ErrorBoundary } from "./ErrorBoundary";

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

const formatTime = (sec: number | null) => {
  if (sec === null || sec === undefined) return "—";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  const parts = [];
  if (h > 0) parts.push(`${h} hr`);
  if (m > 0) parts.push(`${m} min`);
  if (s > 0) parts.push(`${s} sec`);
  return parts.length > 0 ? parts.join(" ") : "0 min";
};

export const RouteDetailModal: React.FC<RouteDetailModalProps> = ({ routeId, onClose, onServiceClick }) => {
  const [route, setRoute] = useState<RouteDetail | null>(null);
  const [stops, setStops] = useState<RouteStop[]>([]);
  const [allStops, setAllStops] = useState<Stop[]>([]);
  const [services, setServices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [isEditingStops, setIsEditingStops] = useState(false);
  const [editingStops, setEditingStops] = useState<RouteStop[]>([]);
  const [stopToAdd, setStopToAdd] = useState("");
  const [duplicateWarning, setDuplicateWarning] = useState<any | null>(null);

  const fetchDetails = async () => {
    try {
      setLoading(true);
      const [routeData, stopsData, allServicesData, allStopsData] = await Promise.all([
        apiFetch(`/admin/routes/${routeId}`),
        apiFetch(`/admin/routes/${routeId}/stops`),
        apiFetch(`/admin/services`),
        apiFetch(`/admin/stops`),
      ]);
      setRoute(routeData);
      setStops(stopsData);
      setServices(allServicesData.filter((s: any) => s.route_id === routeId));
      setAllStops(allStopsData);
    } catch (err: any) {
      setError(err.message || "Failed to load route details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetails();
  }, [routeId]);

  const handleEditStopsStart = () => {
    setEditingStops([...stops]);
    setIsEditingStops(true);
    setDuplicateWarning(null);
  };

  const handleCancelEditStops = () => {
    setIsEditingStops(false);
    setEditingStops([]);
    setStopToAdd("");
    setDuplicateWarning(null);
  };

  const handleSaveStops = async (forceProceed = false) => {
    try {
      const stopIds = editingStops.map(s => s.stop_id);
      
      // Duplicate detection check
      if (!forceProceed && stopIds.length > 0) {
        try {
          const checkRes = await checkRouteDuplicateStops(routeId, stopIds);
          if (checkRes.is_duplicate) {
            setDuplicateWarning(checkRes);
            return;
          }
        } catch (checkErr) {
          console.warn("Could not check duplicate route stops:", checkErr);
        }
      }

      // Re-assign sequence numbers sequentially starting from 1
      const payloadStops = editingStops.map((s, index) => ({
        stop_id: s.stop_id,
        sequence_number: index + 1,
        distance_from_start: s.distance_from_start !== null ? Number(s.distance_from_start) : null,
        nominal_travel_time_seconds: s.nominal_travel_time_seconds !== null ? Number(s.nominal_travel_time_seconds) : null
      }));
      await apiFetch(`/admin/routes/${routeId}/stops`, {
        method: "POST",
        body: JSON.stringify({ stops: payloadStops })
      });
      setIsEditingStops(false);
      setDuplicateWarning(null);
      await fetchDetails();
    } catch (err: any) {
      alert("Failed to update route stops: " + err.message);
    }
  };

  const handleAddStop = () => {
    if (!stopToAdd) return;
    const stopDef = allStops.find(s => s.id === stopToAdd);
    if (!stopDef) return;
    
    setEditingStops([
      ...editingStops,
      {
        route_id: routeId,
        stop_id: stopDef.id,
        stop_code: stopDef.stop_code,
        stop_name: stopDef.name,
        sequence_number: editingStops.length + 1,
        distance_from_start: null,
        nominal_travel_time_seconds: null
      }
    ]);
    setStopToAdd("");
  };

  const handleRemoveEditingStop = (index: number) => {
    if(!confirm("Are you sure you want to remove this stop from the route?")) return;
    const newStops = [...editingStops];
    newStops.splice(index, 1);
    setEditingStops(newStops);
  };

  const handleMoveStop = (index: number, direction: 'up' | 'down') => {
    if (direction === 'up' && index === 0) return;
    if (direction === 'down' && index === editingStops.length - 1) return;
    const newStops = [...editingStops];
    const swapIndex = direction === 'up' ? index - 1 : index + 1;
    [newStops[index], newStops[swapIndex]] = [newStops[swapIndex], newStops[index]];
    setEditingStops(newStops);
  };

  const handleEditingStopChange = (index: number, field: keyof RouteStop, value: string) => {
    const newStops = [...editingStops];
    const val = value === "" ? null : Number(value);
    newStops[index] = { ...newStops[index], [field]: val };
    setEditingStops(newStops);
  };

  if (loading) {
    return (
      <div className="modal-overlay">
        <div className="modal-content" style={{ maxWidth: "1000px", minHeight: "300px", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div className="loading-state">Loading route details...</div>
        </div>
      </div>
    );
  }

  if (error || !route) {
    return (
      <div className="modal-overlay">
        <div className="modal-content" style={{ maxWidth: "1000px" }}>
          <div className="modal-header shrink-0">
            <h2>Error</h2>
            <button className="close-btn" onClick={onClose}><X size={20} /></button>
          </div>
          <div className="p-6 text-red-600">{error || "Route not found"}</div>
        </div>
      </div>
    );
  }

  // Calculate Map Bounds and Polyline
  let positions: [number, number][] = [];
  let mapBounds = new L.LatLngBounds([]);

  if (route.geometry && route.geometry.type === "LineString" && route.geometry.coordinates) {
    route.geometry.coordinates.forEach((coord: [number, number]) => {
      // GeoJSON is [lng, lat], Leaflet is [lat, lng]
      const latlng: [number, number] = [coord[1], coord[0]];
      positions.push(latlng);
      mapBounds.extend(latlng);
    });
  }
  
  // Also extend bounds with stop coordinates
  const stopMarkers = stops.map(s => {
    const fullStop = allStops.find(st => st.id === s.stop_id);
    if (fullStop) {
      const latlng: [number, number] = [fullStop.latitude, fullStop.longitude];
      mapBounds.extend(latlng);
      return { ...s, latlng };
    }
    return null;
  }).filter(Boolean);

  if (!mapBounds.isValid()) {
    // Default to a generic view if no valid coordinates
    mapBounds = new L.LatLngBounds([[22.5, 88.3], [22.6, 88.4]]);
  }

  const totalTravelTime = stops.reduce((acc, curr) => acc + (curr.nominal_travel_time_seconds || 0), 0);

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: "1100px", width: "95%", maxHeight: "90vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
        
        {/* HEADER */}
        <div className="modal-header shrink-0 flex items-center justify-between border-b border-gray-200 bg-white z-10 p-5">
          <div className="flex items-center gap-4">
            <h2 className="text-2xl font-bold flex items-center gap-3 text-gray-900">
              <span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-md text-sm font-bold">{route.route_code}</span>
              {route.route_name}
            </h2>
            <span className={`status-badge ${route.status.toLowerCase()}`}>
              {route.status}
            </span>
          </div>
          <button className="close-btn p-2 hover:bg-gray-100 rounded-full transition-colors" onClick={onClose}>
            <X size={24} className="text-gray-500" />
          </button>
        </div>
        
        {/* SCROLLABLE CONTENT */}
        <div className="overflow-y-auto p-6 flex-1 min-h-0 bg-gray-50/50 space-y-6">
          
          {/* SUMMARY CARDS */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center gap-4">
              <div className="p-3 bg-blue-50 text-blue-600 rounded-lg">
                <MapIcon size={24} />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">Total Distance</p>
                <p className="text-xl font-bold text-gray-900">{route.distance_km ? route.distance_km.toFixed(2) : "0"} km</p>
              </div>
            </div>
            
            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center gap-4">
              <div className="p-3 bg-emerald-50 text-emerald-600 rounded-lg">
                <Navigation size={24} />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">Total Stops</p>
                <p className="text-xl font-bold text-gray-900">{stops.length} Stops</p>
              </div>
            </div>

            <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-sm flex items-center gap-4">
              <div className="p-3 bg-purple-50 text-purple-600 rounded-lg">
                <Clock size={24} />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">Total Travel Time</p>
                <p className="text-xl font-bold text-gray-900">{totalTravelTime > 0 ? formatTime(totalTravelTime) : "—"}</p>
              </div>
            </div>
          </div>

          {/* MAP CARD */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col">
            <div className="px-5 py-4 border-b border-gray-100 bg-gray-50">
              <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                <MapIcon size={18} className="text-blue-600"/> Route Geometry
              </h3>
            </div>
            <ErrorBoundary fallbackTitle="Map Geometry Preview Unavailable" fallbackMessage="Map geometry encountered an issue. Stop sequence and operational service links remain valid.">
              <div className="h-[360px] w-full bg-gray-100 relative">
                <MapContainer center={[22.5726, 88.3639]} zoom={12} style={{ height: "100%", width: "100%", zIndex: 0 }} scrollWheelZoom={false}>
                  <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />
                  {positions.length > 0 && <Polyline positions={positions} color="#3b82f6" weight={5} />}
                  {stopMarkers.map((sm: any, i) => (
                    <Marker key={i} position={sm.latlng}>
                      <Popup>
                        <div className="font-bold">{sm.stop_name}</div>
                        <div className="text-sm text-gray-600">Stop Code: {sm.stop_code}</div>
                        <div className="text-sm text-gray-600">Sequence: {sm.sequence_number}</div>
                      </Popup>
                    </Marker>
                  ))}
                  <BoundsWrapper bounds={mapBounds} />
                </MapContainer>
              </div>
            </ErrorBoundary>
          </div>

          {/* SERVICES CARD */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 bg-gray-50">
              <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                <Network size={18} className="text-indigo-600"/> Services Operating on this Route
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead className="bg-white border-b border-gray-100 text-xs uppercase text-gray-500">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Service Code</th>
                    <th className="px-5 py-3 font-semibold">Service Name</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
                    <th className="px-5 py-3 font-semibold text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {services.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-5 py-8 text-center text-gray-500">No services currently operate on this route.</td>
                    </tr>
                  ) : (
                    services.map((service) => (
                      <tr key={service.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-5 py-4"><span className="bg-indigo-50 text-indigo-700 px-2 py-1 rounded text-xs font-bold">{service.service_code}</span></td>
                        <td className="px-5 py-4 font-medium text-gray-900">{service.service_name}</td>
                        <td className="px-5 py-4">
                          <span className={`status-badge ${service.status.toLowerCase()}`}>
                            {service.status}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-right">
                          <button 
                            className="btn-secondary btn-sm"
                            onClick={() => onServiceClick && onServiceClick(service.id)}
                          >
                            View Details
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* STOP MANAGEMENT CARD */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col">
            <div className="px-5 py-4 border-b border-gray-100 bg-gray-50 flex justify-between items-center transition-colors">
              <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                <Navigation size={18} className="text-rose-600"/> Ordered Route Stops
              </h3>
              {!isEditingStops ? (
                <button className="btn-secondary btn-sm flex items-center gap-2" onClick={handleEditStopsStart}>
                  <Edit2 size={14} /> Manage Stops
                </button>
              ) : (
                <div className="flex items-center gap-2">
                  <button className="px-4 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800 transition-colors" onClick={handleCancelEditStops}>
                    Cancel
                  </button>
                  <button className="btn-primary btn-sm flex items-center gap-2 bg-rose-600 hover:bg-rose-700 border-none" onClick={() => handleSaveStops(false)}>
                    <Save size={14} /> Save Changes
                  </button>
                </div>
              )}
            </div>

            {duplicateWarning && (
              <div className="p-5 bg-amber-50 border-b-2 border-amber-300 text-amber-900">
                <div className="flex items-center gap-2 font-bold text-base mb-2">
                  <AlertTriangle size={20} className="text-amber-600" />
                  <span>⚠ EXISTING ROUTE MATCH</span>
                </div>
                <p className="text-sm mb-2">An identical route already exists in your organization with this exact ordered stop sequence:</p>
                <div className="bg-white/90 p-3 rounded-lg border border-amber-200 text-xs space-y-1 mb-3">
                  <div><span className="font-semibold">Route Code:</span> {duplicateWarning.route_code}</div>
                  <div><span className="font-semibold">Route Name:</span> {duplicateWarning.route_name}</div>
                  <div><span className="font-semibold">Route ID:</span> <span className="font-mono">{duplicateWarning.existing_route_id}</span></div>
                  <div>
                    <span className="font-semibold">Matching stop sequence:</span>{" "}
                    {duplicateWarning.matching_stops?.join(" → ")}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <button 
                    type="button" 
                    className="btn-primary btn-sm bg-amber-600 hover:bg-amber-700 border-none"
                    onClick={() => {
                      onClose();
                      window.location.href = `/routes?routeId=${duplicateWarning.existing_route_id}`;
                    }}
                  >
                    Use Existing Route
                  </button>
                  <button 
                    type="button" 
                    className="btn-secondary btn-sm"
                    onClick={() => handleSaveStops(true)}
                  >
                    Continue as New Route
                  </button>
                  <button 
                    type="button" 
                    className="px-3 py-1.5 text-xs text-amber-800 hover:text-amber-950 transition-colors"
                    onClick={() => setDuplicateWarning(null)}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {isEditingStops && allStops.length === 0 ? (
              <div className="px-5 py-4 bg-amber-50 border-b border-amber-200 text-amber-900 text-sm flex items-center gap-2">
                <AlertTriangle size={16} className="text-amber-600 shrink-0" />
                <span>No stops available. Please create Stops on the Stops Management page first.</span>
              </div>
            ) : isEditingStops ? (
              <div className="px-5 py-4 bg-rose-50 border-b border-rose-100 flex flex-wrap items-end gap-4">
                <div className="flex-1 min-w-[250px]">
                  <label className="text-sm font-medium text-gray-700 block mb-1">Add Existing Stop to Route</label>
                  <select 
                    className="w-full p-2 border border-rose-200 bg-white rounded-lg focus:ring-2 focus:ring-rose-500 focus:border-rose-500 transition-all outline-none"
                    value={stopToAdd} 
                    onChange={e => setStopToAdd(e.target.value)}
                  >
                    <option value="">-- Select a Stop --</option>
                    {allStops.map(s => (
                      <option key={s.id} value={s.id}>{s.name} ({s.stop_code})</option>
                    ))}
                  </select>
                </div>
                <button className="btn-primary flex items-center gap-2 bg-rose-600 hover:bg-rose-700 border-none px-6" onClick={handleAddStop}>
                  <Plus size={16} /> Add Stop
                </button>
              </div>
            ) : null}

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead className="bg-white border-b border-gray-100 text-xs uppercase text-gray-500">
                  <tr>
                    <th className="px-5 py-3 font-semibold text-center w-16">Seq</th>
                    <th className="px-5 py-3 font-semibold">Stop Code</th>
                    <th className="px-5 py-3 font-semibold">Stop Name</th>
                    <th className="px-5 py-3 font-semibold text-right">Distance</th>
                    <th className="px-5 py-3 font-semibold text-right">Est. Travel Time</th>
                    {isEditingStops && <th className="px-5 py-3 font-semibold text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {(!isEditingStops ? stops : editingStops).length === 0 ? (
                    <tr>
                      <td colSpan={isEditingStops ? 6 : 5} className="px-5 py-8 text-center text-gray-500">
                        No stops defined for this route.
                      </td>
                    </tr>
                  ) : (
                    (!isEditingStops ? stops : editingStops).map((stop, index) => (
                      <tr key={isEditingStops ? `${stop.stop_id}-${index}` : stop.id} className={`${isEditingStops ? "bg-white hover:bg-rose-50/30" : "hover:bg-gray-50"} transition-colors`}>
                        <td className="px-5 py-4 text-center font-medium text-gray-400">
                          {isEditingStops ? index + 1 : stop.sequence_number}
                        </td>
                        <td className="px-5 py-4">
                          <span className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded font-mono font-medium">
                            {stop.stop_code}
                          </span>
                        </td>
                        <td className="px-5 py-4 font-medium text-gray-900">{stop.stop_name || "Unknown Stop"}</td>
                        <td className="px-5 py-4 text-right text-gray-600">
                          {isEditingStops ? (
                            <div className="flex items-center justify-end gap-2">
                              <input 
                                type="number" 
                                step="any"
                                className="w-24 p-1.5 border border-gray-300 rounded-md text-right text-sm focus:ring-2 focus:ring-rose-500 focus:border-rose-500 outline-none" 
                                value={stop.distance_from_start === null ? "" : stop.distance_from_start}
                                onChange={(e) => handleEditingStopChange(index, "distance_from_start", e.target.value)}
                                placeholder="0.0"
                              />
                              <span className="text-xs text-gray-500 font-medium w-6 text-left">km</span>
                            </div>
                          ) : (
                            <span className="font-medium text-sm">
                              {stop.distance_from_start !== null && stop.distance_from_start !== undefined 
                                ? `${stop.distance_from_start.toFixed(2)} km` 
                                : "—"}
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-4 text-right text-gray-600">
                          {isEditingStops ? (
                            <div className="flex items-center justify-end gap-2">
                              <input 
                                type="number" 
                                className="w-24 p-1.5 border border-gray-300 rounded-md text-right text-sm focus:ring-2 focus:ring-rose-500 focus:border-rose-500 outline-none" 
                                value={stop.nominal_travel_time_seconds === null ? "" : stop.nominal_travel_time_seconds}
                                onChange={(e) => handleEditingStopChange(index, "nominal_travel_time_seconds", e.target.value)}
                                placeholder="0"
                              />
                              <span className="text-xs text-gray-500 font-medium w-6 text-left">sec</span>
                            </div>
                          ) : (
                            <span className="font-medium text-sm">
                              {formatTime(stop.nominal_travel_time_seconds)}
                            </span>
                          )}
                        </td>
                        {isEditingStops && (
                          <td className="px-5 py-4 text-right">
                            <div className="flex justify-end gap-1.5">
                              <button 
                                className="p-1.5 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded disabled:opacity-30 transition-colors"
                                disabled={index === 0}
                                onClick={() => handleMoveStop(index, 'up')}
                                title="Move Up"
                              >
                                <ArrowUp size={16} />
                              </button>
                              <button 
                                className="p-1.5 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded disabled:opacity-30 transition-colors"
                                disabled={index === editingStops.length - 1}
                                onClick={() => handleMoveStop(index, 'down')}
                                title="Move Down"
                              >
                                <ArrowDown size={16} />
                              </button>
                              <button 
                                className="p-1.5 bg-red-50 hover:bg-red-100 text-red-600 rounded ml-2 transition-colors"
                                onClick={() => handleRemoveEditingStop(index)}
                                title="Remove from Route"
                              >
                                <Trash2 size={16} />
                              </button>
                            </div>
                          </td>
                        )}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
};
