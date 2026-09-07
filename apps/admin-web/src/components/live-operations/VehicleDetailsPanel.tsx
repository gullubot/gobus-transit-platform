import React from "react";

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

interface VehicleDetailsPanelProps {
  vehicle: VehicleLiveOperation | null;
  onClose: () => void;
}

export const VehicleDetailsPanel: React.FC<VehicleDetailsPanelProps> = ({ vehicle, onClose }) => {
  if (!vehicle) return null;

  return (
    <div className="absolute top-4 right-4 w-80 bg-white shadow-xl rounded-lg overflow-hidden border border-gray-200 z-[1000]">
      <div className="p-4 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
        <h3 className="text-lg font-bold text-gray-800">{vehicle.vehicle_number}</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="p-4 space-y-4">
        {/* Status indicator */}
        <div className="flex items-center space-x-2">
          <span className={`w-3 h-3 rounded-full ${vehicle.state === 'OFFLINE' || vehicle.state === 'UNKNOWN' ? 'bg-red-500' : 'bg-green-500'}`}></span>
          <span className={`font-semibold ${vehicle.state === 'OFFLINE' || vehicle.state === 'UNKNOWN' ? 'text-red-700' : 'text-green-700'}`}>
            {vehicle.state === 'OFFLINE' || vehicle.state === 'UNKNOWN' ? 'STALE / DEGRADED' : 'ACTIVE'}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-gray-500">State</div>
            <div className="font-medium text-gray-900">{vehicle.state}</div>
          </div>
          
          <div>
            <div className="text-gray-500">Route</div>
            <div className="font-medium text-gray-900">{vehicle.route_name || 'None'}</div>
          </div>

          <div>
            <div className="text-gray-500">Service</div>
            <div className="font-medium text-gray-900">{vehicle.service_name || 'None'}</div>
          </div>

          <div>
            <div className="text-gray-500">Direction</div>
            <div className="font-medium text-gray-900">{vehicle.direction || 'None'}</div>
          </div>

          <div>
            <div className="text-gray-500">Current Stop</div>
            <div className="font-medium text-gray-900">{vehicle.current_stop_name || 'None'}</div>
          </div>

          <div>
            <div className="text-gray-500">Next Stop</div>
            <div className="font-medium text-gray-900">{vehicle.next_stop_name || 'None'}</div>
          </div>

          <div>
            <div className="text-gray-500">Speed</div>
            <div className="font-medium text-gray-900">{vehicle.speed !== null ? `${Math.round(vehicle.speed * 3.6)} km/h` : 'N/A'}</div>
          </div>

          <div>
            <div className="text-gray-500">ETA</div>
            <div className="font-medium text-gray-900">
              {vehicle.eta_seconds !== null ? `${Math.round(vehicle.eta_seconds / 60)} min` : 'N/A'}
            </div>
          </div>
        </div>

        <div className="pt-4 border-t border-gray-100 text-xs text-gray-400 text-center">
          Last updated: {vehicle.last_observed_at ? new Date(vehicle.last_observed_at).toLocaleTimeString() : 'Never'}
        </div>
      </div>
    </div>
  );
};
