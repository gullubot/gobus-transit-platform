import React, { useEffect, useState, useCallback, useRef } from "react";
import { getLiveOperations } from "../../api/api";
import { LiveMap } from "../../components/live-operations/LiveMap";
import { VehicleDetailsPanel } from "../../components/live-operations/VehicleDetailsPanel";

interface VehicleLiveOperation {
  vehicle_id: string;
  vehicle_number: string;
  registration_number: string | null;
  vehicle_type: string;
  vehicle_status: string;
  service_id: string | null;
  service_name: string | null;
  route_id: string | null;
  route_name: string | null;
  direction: string | null;
  current_stop_id: string | null;
  current_stop_name: string | null;
  next_stop_id: string | null;
  next_stop_name: string | null;
  latitude: number | null;
  longitude: number | null;
  speed: number | null;
  heading: number | null;
  route_progress: number | null;
  dwell_state: string | null;
  eta_seconds: number | null;
  eta_status: string | null;
  state: string;
  state_reason: string | null;
  confidence: number;
  last_observed_at: string | null;
  scheduled_status: string | null;
  planned_departure: string | null;
}

export const LiveOperationsPage: React.FC = () => {
  const [vehicles, setVehicles] = useState<VehicleLiveOperation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null);
  const isComponentMounted = useRef(true);

  const fetchLiveOperations = useCallback(async () => {
    try {
      const data = await getLiveOperations();
      if (isComponentMounted.current) {
        setVehicles(data);
        setError(null);
      }
    } catch (err: any) {
      if (isComponentMounted.current) {
        console.error("Live operations poll failed:", err);
        setError(err.message || "Failed to load live operations data");
      }
    } finally {
      if (isComponentMounted.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isComponentMounted.current = true;
    
    // Initial fetch
    fetchLiveOperations();

    // Set up polling every 10 seconds per Step 8D rules (No WebSockets)
    const pollInterval = setInterval(() => {
      fetchLiveOperations();
    }, 10000);

    return () => {
      isComponentMounted.current = false;
      clearInterval(pollInterval);
    };
  }, [fetchLiveOperations]);

  const mapLocations = vehicles
    .filter(v => v.latitude !== null && v.longitude !== null)
    .map(v => ({
      id: v.vehicle_id,
      vehicle_name: v.vehicle_number,
      lat: v.latitude as number,
      lon: v.longitude as number,
      heading: v.heading || 0,
      stale: v.state === 'OFFLINE' || v.state === 'UNKNOWN', // basic mapping since stale isn't provided
      status: v.state
    }));

  const selectedVehicle = vehicles.find(v => v.vehicle_id === selectedVehicleId) || null;

  return (
    <div className="h-full flex flex-col relative overflow-hidden bg-gray-100">
      <div className="p-4 bg-white border-b border-gray-200 flex justify-between items-center shadow-sm z-10 relative">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Live Operations</h1>
          <p className="text-sm text-gray-500">Real-time fleet tracking and telemetry</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 text-sm">
            <span className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse"></span>
            <span className="text-gray-600">Active: {vehicles.filter(v => v.state !== 'OFFLINE' && v.state !== 'UNKNOWN').length}</span>
          </div>
          <div className="flex items-center space-x-2 text-sm">
            <span className="w-2.5 h-2.5 bg-red-500 rounded-full"></span>
            <span className="text-gray-600">Offline: {vehicles.filter(v => v.state === 'OFFLINE' || v.state === 'UNKNOWN').length}</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border-b border-red-100 text-red-700 z-10 relative">
          <p className="font-semibold">Connection Error</p>
          <p className="text-sm">{error}</p>
        </div>
      )}

      <div className="flex-1 relative z-0">
        {loading && vehicles.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50/80 z-20">
            <div className="text-gray-500 font-medium">Loading live map...</div>
          </div>
        ) : (
          <LiveMap 
            locations={mapLocations}
            selectedVehicleId={selectedVehicleId}
            onSelectVehicle={setSelectedVehicleId}
          />
        )}

        <VehicleDetailsPanel 
          vehicle={selectedVehicle} 
          onClose={() => setSelectedVehicleId(null)}
        />
      </div>
    </div>
  );
};
