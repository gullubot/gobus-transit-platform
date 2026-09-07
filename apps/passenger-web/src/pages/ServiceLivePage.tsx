import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, WifiOff } from 'lucide-react';
import { Polyline, CircleMarker } from 'react-leaflet';
import { api } from '../api/client';
import Map from '../components/Map';
import LiveBusList from '../components/LiveBusList';
import BusMarker from '../components/BusMarker';
import SelectedBusSheet from '../components/SelectedBusSheet';

export default function ServiceLivePage() {
  const { serviceId } = useParams<{ serviceId: string }>();
  const navigate = useNavigate();

  const [serviceData, setServiceData] = useState<any>(null);
  const [liveBuses, setLiveBuses] = useState<any[]>([]);
  
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPollingError, setIsPollingError] = useState(false);
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
  
  const [mapBounds, setMapBounds] = useState<[[number, number], [number, number]] | null>(null);
  const hasInitializedBounds = useRef(false);

  // Load static service details once
  useEffect(() => {
    async function fetchService() {
      if (!serviceId) return;
      try {
        const data = await api.getServiceDetail(serviceId);
        setServiceData(data);
        
        // Compute bounds based on stops
        if (data.stops && data.stops.length > 0 && !hasInitializedBounds.current) {
          const lats = data.stops.filter((s: any) => s.latitude !== null).map((s: any) => s.latitude);
          const lngs = data.stops.filter((s: any) => s.longitude !== null).map((s: any) => s.longitude);
          
          if (lats.length > 0 && lngs.length > 0) {
            const minLat = Math.min(...lats);
            const maxLat = Math.max(...lats);
            const minLng = Math.min(...lngs);
            const maxLng = Math.max(...lngs);
            setMapBounds([[minLat, minLng], [maxLat, maxLng]]);
            hasInitializedBounds.current = true;
          }
        }
      } catch (err) {
        console.error("Failed to load service details", err);
      }
    }
    fetchService();
  }, [serviceId]);

  // Polling for live buses
  useEffect(() => {
    if (!serviceId) return;

    async function fetchLive() {
      if (!navigator.onLine) {
        setIsOffline(true);
        return;
      }
      setIsOffline(false);
      
      try {
        const buses = await api.getServiceLive(serviceId!);
        setLiveBuses(buses);
        setIsPollingError(false);
        setIsLoading(false);
      } catch (err) {
        console.error("Failed to fetch live buses", err);
        setIsPollingError(true);
        setIsLoading(false);
      }
    }

    // Initial fetch
    fetchLive();

    const intervalId = setInterval(fetchLive, 10000);
    return () => clearInterval(intervalId);
  }, [serviceId]);

  // Handle selected bus disappearance
  useEffect(() => {
    if (selectedVehicleId && !isLoading && liveBuses.length > 0) {
      const stillExists = liveBuses.some(b => b.vehicle_id === selectedVehicleId);
      if (!stillExists) {
        // Bus vanished from live feed
        setSelectedVehicleId(null);
        // We could show a toast here in a real app, but for now just clear selection
      }
    }
  }, [liveBuses, selectedVehicleId, isLoading]);

  // Listen to global online/offline
  useEffect(() => {
    function handleOnline() { setIsOffline(false); }
    function handleOffline() { setIsOffline(true); }
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const selectedBus = selectedVehicleId ? liveBuses.find(b => b.vehicle_id === selectedVehicleId) : null;

  // Prepare map features
  const polylinePositions = serviceData?.route_geometry?.coordinates
    ? serviceData.route_geometry.coordinates.map((coord: number[]) => [coord[1], coord[0]]) // GeoJSON is [lng, lat], Leaflet is [lat, lng]
    : [];

  return (
    <div className="app-shell service-live-shell">
      {/* Header */}
      <header className="top-app-bar top-app-bar--floating">
        <button className="icon-button" onClick={() => navigate(-1)}>
          <ArrowLeft size={20} />
        </button>
        <div className="top-app-bar__title">
          {serviceData ? (
            <div className="service-live-header">
              <span className="service-name">{serviceData.service_name}</span>
              <span className="service-direction">Towards {serviceData.schedules?.[0]?.direction?.replace('_', ' ') || 'Destination'}</span>
            </div>
          ) : (
            'Loading...'
          )}
        </div>
      </header>

      {/* Offline Banner */}
      {isOffline && (
        <div className="offline-banner">
          <WifiOff size={16} />
          <span>You are offline. Live updates paused.</span>
        </div>
      )}

      {/* Polling Error Banner (subtle) */}
      {isPollingError && !isOffline && liveBuses.length > 0 && (
        <div className="offline-banner offline-banner--warning">
          <span>Live update delayed. Retrying...</span>
        </div>
      )}

      {/* Map Background */}
      <div className="home-map-container">
        <Map center={[22.5726, 88.3639]} zoom={13} bounds={mapBounds}>
          {/* Route Polyline */}
          {polylinePositions.length > 0 && (
            <Polyline positions={polylinePositions} pathOptions={{ color: '#0A2540', weight: 4, opacity: 0.6 }} />
          )}

          {/* Stop Markers */}
          {serviceData?.stops?.map((stop: any) => {
            if (stop.latitude && stop.longitude) {
              return (
                <CircleMarker
                  key={stop.stop_id}
                  center={[stop.latitude, stop.longitude]}
                  radius={4}
                  pathOptions={{ color: '#0A2540', fillColor: '#ffffff', fillOpacity: 1, weight: 2 }}
                />
              );
            }
            return null;
          })}

          {/* Active Bus Markers */}
          {liveBuses.map((bus) => {
            if (bus.latitude && bus.longitude) {
              return (
                <BusMarker
                  key={bus.vehicle_id}
                  position={[bus.latitude, bus.longitude]}
                  isSelected={bus.vehicle_id === selectedVehicleId}
                  onClick={() => setSelectedVehicleId(bus.vehicle_id)}
                />
              );
            }
            return null;
          })}
        </Map>
      </div>

      {/* Floating Bottom UI */}
      <div className={`home-floating-ui home-floating-ui--expanded`}>
        {selectedBus && serviceData ? (
          <SelectedBusSheet
            bus={selectedBus}
            serviceName={serviceData.service_name}
            direction={serviceData.schedules?.[0]?.direction?.replace('_', ' ') || 'Destination'}
            onClose={() => setSelectedVehicleId(null)}
          />
        ) : (
          <div className="service-live-list-container">
            <h3 className="section-title">Active Buses</h3>
            <LiveBusList
              buses={liveBuses}
              isLoading={isLoading}
              onSelectBus={(vid) => setSelectedVehicleId(vid)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
