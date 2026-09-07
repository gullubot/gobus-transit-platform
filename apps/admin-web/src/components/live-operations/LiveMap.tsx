import React from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix leaflet default icons
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

interface VehicleLocation {
  id: string;
  vehicle_name: string;
  lat: number;
  lon: number;
  heading: number;
  stale: boolean;
  status: string;
}

interface LiveMapProps {
  locations: VehicleLocation[];
  selectedVehicleId: string | null;
  onSelectVehicle: (id: string) => void;
}



export const LiveMap: React.FC<LiveMapProps> = ({ locations, selectedVehicleId, onSelectVehicle }) => {
  const defaultCenter: [number, number] = [40.7128, -74.0060]; // Default to NYC, update based on org location if needed
  
  const mapCenter = locations.length > 0
    ? [locations[0].lat, locations[0].lon] as [number, number]
    : defaultCenter;

  return (
    <MapContainer center={mapCenter} zoom={13} style={{ height: "100%", width: "100%" }}>
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {locations.map((loc) => (
        <Marker
          key={loc.id}
          position={[loc.lat, loc.lon]}
          eventHandlers={{
            click: () => onSelectVehicle(loc.id)
          }}
          // Basic customization based on stale/active
          opacity={loc.stale ? 0.5 : 1}
        >
          <Popup>
            <div className="font-semibold">{loc.vehicle_name}</div>
            <div className="text-xs text-gray-500">{loc.status}</div>
            {loc.stale && <div className="text-xs text-red-500 mt-1">Stale Data</div>}
            {selectedVehicleId === loc.id && <div className="text-xs text-blue-500 mt-1">Selected</div>}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
};
