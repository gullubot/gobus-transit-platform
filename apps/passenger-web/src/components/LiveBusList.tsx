import { Clock, Navigation } from 'lucide-react';

interface LiveBus {
  vehicle_id: string;
  latitude: number | null;
  longitude: number | null;
  direction: string | null;
  eta_seconds: number | null;
  eta_status: string | null;
  crowd_level: string;
  state: string;
  last_updated_at: string | null;
}

interface LiveBusListProps {
  buses: LiveBus[];
  onSelectBus: (vehicleId: string) => void;
  isLoading?: boolean;
}

export default function LiveBusList({ buses, onSelectBus, isLoading = false }: LiveBusListProps) {
  if (isLoading && buses.length === 0) {
    return (
      <div className="live-bus-list">
        <div className="card skeleton-card">
          <div className="card__body">
            <div className="skeleton skeleton-text" style={{ width: '40%' }}></div>
            <div className="skeleton skeleton-text" style={{ width: '60%' }}></div>
          </div>
        </div>
        <div className="card skeleton-card">
          <div className="card__body">
            <div className="skeleton skeleton-text" style={{ width: '50%' }}></div>
            <div className="skeleton skeleton-text" style={{ width: '70%' }}></div>
          </div>
        </div>
      </div>
    );
  }

  if (buses.length === 0) {
    return (
      <div className="live-bus-list empty-state">
        <div className="card">
          <div className="card__body text-center text-subtle">
            No buses are currently running on this service.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="live-bus-list">
      {buses.map((bus) => {
        let etaText = 'ETA Unknown';
        let etaClass = '';
        if (bus.eta_seconds !== null) {
          const mins = Math.round(bus.eta_seconds / 60);
          if (mins <= 0) etaText = 'Due now';
          else etaText = `Arriving in ${mins} min`;
          
          if (bus.eta_status === 'DEGRADED') {
            etaText += ' (Est)';
            etaClass = 'text-warning';
          } else if (bus.eta_status === 'STALE') {
            etaText += ' (Stale)';
            etaClass = 'text-danger';
          }
        }

        let crowdText = 'Unknown crowding';
        if (bus.crowd_level === 'LOW') crowdText = 'Low crowding';
        if (bus.crowd_level === 'MEDIUM') crowdText = 'Medium crowding';
        if (bus.crowd_level === 'HIGH') crowdText = 'High crowding';
        if (bus.crowd_level === 'CRUSH') crowdText = 'Crush load';

        return (
          <div 
            key={bus.vehicle_id} 
            className="card live-bus-card" 
            onClick={() => onSelectBus(bus.vehicle_id)}
          >
            <div className="card__body">
              <div className="live-bus-card__header">
                <span className="bus-title">
                  <Navigation size={14} className="icon-blue" />
                  BUS {bus.vehicle_id.substring(0, 4)}...
                </span>
                <span className={`bus-status badge badge--${bus.state.toLowerCase()}`}>
                  {bus.state.replace('_', ' ')}
                </span>
              </div>
              
              <div className="live-bus-card__info">
                <div className={`bus-eta ${etaClass}`}>
                  <Clock size={16} />
                  <span>{etaText}</span>
                </div>
                <div className="bus-crowding">
                  <span className="dot">●</span>
                  <span>{crowdText}</span>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
